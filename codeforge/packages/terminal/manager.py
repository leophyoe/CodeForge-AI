"""Terminal manager — orchestrates command execution."""

from __future__ import annotations

import os
from typing import Any

from codeforge.packages.terminal.audit import TerminalAuditLogger
from codeforge.packages.terminal.errors import (
    CommandValidationError,
    TerminalError,
)
from codeforge.packages.terminal.executor import ProcessExecutor
from codeforge.packages.terminal.models import (
    CommandExecutionContext,
    CommandRequest,
    CommandResult,
)
from codeforge.packages.terminal.policy import CommandPolicy


class TerminalManager:
    def __init__(
        self,
        executor: ProcessExecutor | None = None,
        policy: CommandPolicy | None = None,
        audit: TerminalAuditLogger | None = None,
    ) -> None:
        if executor is None:
            policy = policy or CommandPolicy()
            executor = ProcessExecutor(policy)
        self.executor = executor
        self.policy = policy or executor.policy
        self.audit = audit or TerminalAuditLogger()

    async def execute(
        self,
        request: CommandRequest,
        context: CommandExecutionContext | None = None,
    ) -> CommandResult:
        errors = self.policy.validate(request)
        if errors:
            error = CommandValidationError(
                "; ".join(errors),
                command=request.command,
                request_id=request.request_id,
            )
            self._audit_rejection(request, error)
            raise error

        if context is None:
            context = CommandExecutionContext(
                request_id=request.request_id,
                workspace_id=request.workspace_id,
                working_directory=request.working_directory,
                timeout_seconds=request.timeout_seconds,
                max_output_bytes=request.max_output_bytes,
                max_total_output_bytes=request.max_total_output_bytes,
            )

        try:
            result = await self.executor.execute(request, context)
        except TerminalError as error:
            self._audit_rejection(request, error, context)
            raise

        self._audit_result(request, result, context)
        return result

    async def cancel(self, request_id: str) -> bool:
        return self.executor.cancel(request_id)

    def get_policy(self) -> dict[str, Any]:
        return self.policy.to_dict()

    def doctor(self) -> dict[str, Any]:
        config = self.policy.config
        return {
            "terminal_enabled": config.enabled,
            "executor": "asyncio-subprocess",
            "shell_execution": False,
            "default_timeout": config.default_timeout,
            "max_timeout": config.max_timeout,
            "max_output_bytes": config.max_output_bytes,
            "max_total_output_bytes": config.max_total_output_bytes,
            "approval_required": config.approval_required,
            "workspace_policy": (
                "commands run inside the workspace root; traversal and symlink escapes rejected"
            ),
            "environment_policy": ("allowlist only: " + ", ".join(self.policy.allowed_env_vars)),
            "platform": os.name,
            "active_processes": self.executor.active_count,
            "audit_entries": self.audit.count(),
        }

    def _audit_result(
        self,
        request: CommandRequest,
        result: CommandResult,
        context: CommandExecutionContext,
    ) -> None:
        approval_state = result.metadata.get("approval_state", "not_required")
        self.audit.log_command(
            request_id=result.request_id or context.request_id,
            workspace_id=request.workspace_id,
            command=request.command,
            classification=result.security_classification.value,
            approval_state=approval_state,
            duration_ms=result.duration_ms,
            success=result.success,
            status=result.status.value,
            exit_code=result.exit_code,
            timed_out=result.timed_out,
            cancelled=result.cancelled,
            working_directory=request.working_directory or ".",
            argument_count=len(request.arguments),
            metadata={
                "stdout_bytes": len(result.stdout),
                "stderr_bytes": len(result.stderr),
                "truncated": result.truncated,
                "executed": result.executed,
            },
        )

    def _audit_rejection(
        self,
        request: CommandRequest,
        error: TerminalError,
        context: CommandExecutionContext | None = None,
    ) -> None:
        approval_state = "denied" if "APPROVAL" in error.code else "rejected"
        self.audit.log_command(
            request_id=context.request_id if context else request.request_id,
            workspace_id=request.workspace_id,
            command=request.command,
            classification="blocked",
            approval_state=approval_state,
            duration_ms=0.0,
            success=False,
            status="rejected",
            error_code=error.code,
            working_directory=request.working_directory or ".",
            argument_count=len(request.arguments),
        )
