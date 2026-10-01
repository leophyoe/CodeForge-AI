"""run_command tool — bridges the Phase 10 terminal into the tool system."""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

from codeforge.packages.terminal import CommandRequest, TerminalManager
from codeforge.packages.terminal.errors import TerminalError
from codeforge.packages.tools.errors import (
    InvalidToolInputError,
    ToolExecutionError,
    ToolTimeoutError,
)
from codeforge.packages.tools.models import (
    PermissionLevel,
    ToolCategory,
    ToolExecutionContext,
    ToolResult,
)
from codeforge.packages.tools.tool import Tool

_MAX_COMMAND_LEN = 1024
_MAX_ARGS = 50
_MAX_ARG_LEN = 2048

_terminal: TerminalManager | None = None


def _get_terminal() -> TerminalManager:
    global _terminal
    if _terminal is None:
        _terminal = TerminalManager()
    return _terminal


def _run_coroutine(coro: Any) -> Any:
    """Run an async command from sync tool code (never blocks a live loop)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    box: list[Any] = []

    def _target() -> None:
        try:
            box.append(asyncio.run(coro))
        except BaseException as exc:  # noqa: BLE001 — re-raised below
            box.append(exc)

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join()
    value = box[0]
    if isinstance(value, BaseException):
        raise value
    return value


class RunCommandTool(Tool):
    @property
    def name(self) -> str:
        return "run_command"

    @property
    def description(self) -> str:
        return (
            "Run a shell command (argv list, never shell=True) with policy "
            "classification; dangerous commands require human approval"
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "command": {"type": "string", "description": "Executable name"},
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Arguments passed directly (no shell)",
                    "default": [],
                },
                "timeout_seconds": {
                    "type": "number",
                    "minimum": 0.1,
                    "maximum": 300,
                    "default": 30,
                },
            },
            "required": ["workspace_id", "command"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "exit_code": {"type": "integer"},
                "stdout": {"type": "string"},
                "stderr": {"type": "string"},
                "duration_ms": {"type": "number"},
                "status": {"type": "string"},
            },
        }

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.EXECUTION

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.USER_APPROVAL

    def validate_input(self, arguments: dict[str, Any]) -> None:
        command = arguments.get("command")
        if not command or not isinstance(command, str):
            raise InvalidToolInputError("command is required")
        if len(command) > _MAX_COMMAND_LEN:
            raise InvalidToolInputError(f"command exceeds {_MAX_COMMAND_LEN} chars")
        if not arguments.get("workspace_id"):
            raise InvalidToolInputError("workspace_id is required")
        args = arguments.get("args", [])
        if not isinstance(args, list):
            raise InvalidToolInputError("args must be an array of strings")
        if len(args) > _MAX_ARGS:
            raise InvalidToolInputError(f"args exceeds {_MAX_ARGS} items")
        for item in args:
            if not isinstance(item, str) or len(item) > _MAX_ARG_LEN:
                raise InvalidToolInputError("args must be short strings")

    def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        start_ms = time.time() * 1000
        request = CommandRequest(
            command=arguments["command"],
            arguments=list(arguments.get("args", [])),
            workspace_id=arguments["workspace_id"],
            timeout_seconds=float(arguments.get("timeout_seconds", 30.0)),
            max_output_bytes=min(context.max_output_bytes, 100_000),
            require_approval=True,
            approved=False,  # agents can never self-approve
        )
        try:
            result = _run_coroutine(_get_terminal().execute(request))
        except TerminalError as exc:
            return self._error(ToolExecutionError(str(exc)), context, start_ms)
        except TimeoutError:
            return self._error(
                ToolTimeoutError(self.name, request.timeout_seconds), context, start_ms
            )

        if result.approval_required:
            return self._error(
                ToolExecutionError(
                    f"approval_required: '{request.command}' is DANGEROUS; "
                    "run it yourself via POST /v1/terminal/execute with approved=true"
                ),
                context,
                start_ms,
            )
        if result.timed_out:
            return self._error(
                ToolTimeoutError(self.name, request.timeout_seconds), context, start_ms
            )
        if not result.success:
            detail = result.stderr.strip() or result.status.value
            return self._error(
                ToolExecutionError(
                    f"exit {result.exit_code}: {detail}" if result.exit_code is not None else detail
                ),
                context,
                start_ms,
            )
        return self._success(
            {
                "command": request.command,
                "exit_code": result.exit_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration_ms": result.duration_ms,
                "status": result.status.value,
            },
            context,
            start_ms,
        )


__all__ = ["RunCommandTool"]
