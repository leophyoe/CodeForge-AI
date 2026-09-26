"""Process executor — safe command execution with workspace restriction."""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import time
from dataclasses import dataclass, field
from pathlib import Path

from codeforge.packages.terminal.errors import (
    CommandNotFoundError,
    CommandPermissionError,
    DangerousCommandError,
    PathTraversalError,
    TerminalError,
    WorkspaceAccessError,
)
from codeforge.packages.terminal.models import (
    CommandClassification,
    CommandExecutionContext,
    CommandRequest,
    CommandResult,
    CommandStatus,
)
from codeforge.packages.terminal.policy import CommandPolicy, RiskLevel

_TRUNCATION_MARKER = "\n... (output truncated)"
_POLL_INTERVAL = 0.05
_TERMINATE_GRACE = 5.0


@dataclass
class _ActiveProcess:
    process: asyncio.subprocess.Process
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)


class ProcessExecutor:
    def __init__(self, policy: CommandPolicy | None = None) -> None:
        self.policy = policy or CommandPolicy()
        self._active: dict[str, _ActiveProcess] = {}

    @property
    def active_count(self) -> int:
        return len(self._active)

    def _workspace_root(self, workspace_id: str) -> Path:
        if not workspace_id or not workspace_id.strip() or "\x00" in workspace_id:
            raise WorkspaceAccessError(workspace_id, "")
        raw = Path(workspace_id)
        if raw.is_absolute():
            root = raw
        else:
            base = Path("workspaces").resolve()
            root = (base / workspace_id).resolve()
            if not root.is_relative_to(base):
                raise PathTraversalError(workspace_id)
        if not root.exists() or not root.is_dir():
            raise WorkspaceAccessError(workspace_id, workspace_id)
        return root.resolve()

    def _resolve_cwd(self, working_directory: str, workspace_id: str) -> str:
        root = self._workspace_root(workspace_id)
        if "\x00" in working_directory:
            raise PathTraversalError(working_directory)
        relative = working_directory.strip() or "."
        candidate = Path(relative)
        resolved = (candidate if candidate.is_absolute() else (root / candidate)).resolve()
        if not resolved.is_relative_to(root):
            raise PathTraversalError(working_directory)
        if not resolved.exists() or not resolved.is_dir():
            raise WorkspaceAccessError(workspace_id, working_directory)
        return str(resolved)

    def _validate_path(self, path: str, workspace_id: str) -> str:
        return self._resolve_cwd(path, workspace_id)

    @staticmethod
    def _context_from_request(request: CommandRequest) -> CommandExecutionContext:
        return CommandExecutionContext(
            request_id=request.request_id,
            workspace_id=request.workspace_id,
            working_directory=request.working_directory,
            timeout_seconds=request.timeout_seconds,
            max_output_bytes=request.max_output_bytes,
            max_total_output_bytes=request.max_total_output_bytes,
        )

    @staticmethod
    def _apply_output_limits(
        stdout: bytes,
        stderr: bytes,
        max_stream: int,
        max_total: int,
    ) -> tuple[str, str, bool]:
        truncated = False
        stdout_truncated = False
        stderr_truncated = False
        if len(stdout) > max_stream:
            stdout = stdout[:max_stream]
            stdout_truncated = truncated = True
        if len(stderr) > max_stream:
            stderr = stderr[:max_stream]
            stderr_truncated = truncated = True
        if max_total and len(stdout) + len(stderr) > max_total:
            truncated = True
            if len(stdout) >= max_total:
                stdout = stdout[:max_total]
                stderr = b""
                stdout_truncated = True
            else:
                stderr = stderr[: max_total - len(stdout)]
                stderr_truncated = True
        if stdout_truncated:
            stdout += _TRUNCATION_MARKER.encode()
        elif stderr_truncated:
            stderr += _TRUNCATION_MARKER.encode()
        return (
            stdout.decode(errors="replace"),
            stderr.decode(errors="replace"),
            truncated,
        )

    async def execute(
        self,
        request: CommandRequest,
        context: CommandExecutionContext | None = None,
    ) -> CommandResult:
        start = time.monotonic()
        context = context or self._context_from_request(request)
        request_id = context.request_id

        def _elapsed_ms() -> float:
            return (time.monotonic() - start) * 1000

        cwd = self._resolve_cwd(request.working_directory or ".", request.workspace_id)

        level = self.policy.classify(request.command, request.arguments)
        classification = CommandClassification(level.value)
        approval_state = "granted" if request.approved else "not_required"

        if level == RiskLevel.BLOCKED:
            raise DangerousCommandError(request.command, request_id=request_id)

        if level == RiskLevel.DANGEROUS:
            if not request.require_approval:
                raise CommandPermissionError(
                    "Approval cannot be disabled for dangerous commands",
                    command=request.command,
                    request_id=request_id,
                )
            if not request.approved:
                return CommandResult(
                    command=request.command,
                    arguments=request.arguments,
                    status=CommandStatus.WAITING_APPROVAL,
                    executed=False,
                    approval_required=True,
                    approved=False,
                    security_classification=classification,
                    duration_ms=_elapsed_ms(),
                    request_id=request_id,
                    stderr="Approval required before execution",
                    metadata={"approval_state": "pending"},
                )

        if context.is_cancelled:
            return CommandResult(
                command=request.command,
                arguments=request.arguments,
                cwd=cwd,
                status=CommandStatus.CANCELLED,
                cancelled=True,
                executed=False,
                security_classification=classification,
                duration_ms=_elapsed_ms(),
                request_id=request_id,
                stderr="Command was cancelled before execution",
                metadata={"approval_state": approval_state},
            )

        env = self.policy.sanitize_environment()

        try:
            process = await asyncio.create_subprocess_exec(
                request.command,
                *request.arguments,
                cwd=cwd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
                start_new_session=(os.name != "nt"),
            )
        except FileNotFoundError:
            raise CommandNotFoundError(request.command, request_id=request_id) from None
        except PermissionError as exc:
            raise CommandPermissionError(
                f"Command is not executable: {request.command}",
                command=request.command,
                request_id=request_id,
            ) from exc
        except OSError as exc:
            raise TerminalError(
                f"Failed to start command: {exc.strerror or exc}",
                code="COMMAND_SPAWN_FAILED",
                command=request.command,
                request_id=request_id,
            ) from exc

        active = _ActiveProcess(process=process)
        self._active[request_id] = active
        communicate_task = asyncio.ensure_future(process.communicate())
        deadline = start + context.timeout_seconds

        try:
            result = await self._poll(
                request=request,
                context=context,
                classification=classification,
                level=level,
                active=active,
                communicate_task=communicate_task,
                cwd=cwd,
                deadline=deadline,
                start=start,
                approval_state=approval_state,
            )
            if result is not None:
                return result
            stdout_bytes, stderr_bytes = communicate_task.result()
        finally:
            self._active.pop(request_id, None)

        out, err, truncated = self._apply_output_limits(
            stdout_bytes or b"",
            stderr_bytes or b"",
            context.max_output_bytes,
            context.max_total_output_bytes,
        )
        exit_code = process.returncode
        return CommandResult(
            command=request.command,
            arguments=request.arguments,
            cwd=cwd,
            exit_code=exit_code,
            stdout=out,
            stderr=err,
            duration_ms=_elapsed_ms(),
            truncated=truncated,
            security_classification=classification,
            status=(CommandStatus.COMPLETED if exit_code == 0 else CommandStatus.FAILED),
            request_id=request_id,
            approval_required=level == RiskLevel.DANGEROUS,
            approved=request.approved,
            metadata={"approval_state": approval_state},
        )

    async def _poll(
        self,
        request: CommandRequest,
        context: CommandExecutionContext,
        classification: CommandClassification,
        level: RiskLevel,
        active: _ActiveProcess,
        communicate_task: asyncio.Task,
        cwd: str,
        deadline: float,
        start: float,
        approval_state: str,
    ) -> CommandResult | None:
        def _elapsed_ms() -> float:
            return (time.monotonic() - start) * 1000

        while True:
            done, _ = await asyncio.wait({communicate_task}, timeout=_POLL_INTERVAL)
            cancelled = active.cancel_event.is_set() or context.is_cancelled
            if cancelled:
                await self._terminate_process(active.process)
                stdout_bytes, stderr_bytes = await self._drain(communicate_task)
                out, err, truncated = self._apply_output_limits(
                    stdout_bytes,
                    stderr_bytes,
                    context.max_output_bytes,
                    context.max_total_output_bytes,
                )
                return CommandResult(
                    command=request.command,
                    arguments=request.arguments,
                    cwd=cwd,
                    exit_code=active.process.returncode,
                    stdout=out,
                    stderr=err or "Command was cancelled",
                    duration_ms=_elapsed_ms(),
                    cancelled=True,
                    truncated=truncated,
                    security_classification=classification,
                    status=CommandStatus.CANCELLED,
                    request_id=context.request_id,
                    approval_required=level == RiskLevel.DANGEROUS,
                    approved=request.approved,
                    metadata={"approval_state": approval_state},
                )
            if communicate_task in done:
                return None
            if time.monotonic() >= deadline:
                await self._terminate_process(active.process)
                stdout_bytes, stderr_bytes = await self._drain(communicate_task)
                out, err, truncated = self._apply_output_limits(
                    stdout_bytes,
                    stderr_bytes,
                    context.max_output_bytes,
                    context.max_total_output_bytes,
                )
                return CommandResult(
                    command=request.command,
                    arguments=request.arguments,
                    cwd=cwd,
                    exit_code=active.process.returncode,
                    stdout=out,
                    stderr=err,
                    duration_ms=_elapsed_ms(),
                    timed_out=True,
                    truncated=truncated,
                    security_classification=classification,
                    status=CommandStatus.TIMED_OUT,
                    request_id=context.request_id,
                    approval_required=level == RiskLevel.DANGEROUS,
                    approved=request.approved,
                    metadata={
                        "approval_state": approval_state,
                        "timeout_seconds": context.timeout_seconds,
                    },
                )

    async def _drain(self, communicate_task: asyncio.Task) -> tuple[bytes, bytes]:
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                asyncio.shield(communicate_task), timeout=_TERMINATE_GRACE
            )
        except asyncio.TimeoutError:
            stdout_bytes, stderr_bytes = b"", b""
        finally:
            if not communicate_task.done():
                communicate_task.cancel()
        return stdout_bytes or b"", stderr_bytes or b""

    def cancel(self, request_id: str) -> bool:
        active = self._active.get(request_id)
        if active is None:
            return False
        active.cancel_event.set()
        process = active.process
        if process.returncode is None:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                if os.name == "nt":
                    process.terminate()
                else:
                    process.send_signal(signal.SIGTERM)
        return True

    async def _terminate_process(self, process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        with contextlib.suppress(ProcessLookupError, PermissionError):
            if os.name == "nt":
                process.terminate()
            else:
                process.send_signal(signal.SIGTERM)
        try:
            await asyncio.wait_for(process.wait(), timeout=_TERMINATE_GRACE)
        except asyncio.TimeoutError:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                if os.name == "nt":
                    process.kill()
                else:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(process.wait(), timeout=2.0)

    def cleanup(self, request_id: str) -> None:
        self._active.pop(request_id, None)

    def cleanup_all(self) -> int:
        count = len(self._active)
        self._active.clear()
        return count
