"""Structured terminal errors."""

from __future__ import annotations


class TerminalError(Exception):
    def __init__(
        self,
        message: str,
        code: str = "terminal_error",
        command: str = "",
        request_id: str = "",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.command = command
        self.request_id = request_id

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": str(self),
            "command": self.command,
            "request_id": self.request_id,
        }


class CommandValidationError(TerminalError):
    def __init__(self, message: str, command: str = "", **kwargs: str) -> None:
        super().__init__(message, code="COMMAND_VALIDATION_ERROR", command=command, **kwargs)


class CommandNotFoundError(TerminalError):
    def __init__(self, command: str, **kwargs: str) -> None:
        super().__init__(
            f"Command not found: {command}",
            code="COMMAND_NOT_FOUND",
            command=command,
            **kwargs,
        )


class CommandPermissionError(TerminalError):
    def __init__(self, message: str, command: str = "", **kwargs: str) -> None:
        super().__init__(message, code="COMMAND_PERMISSION_DENIED", command=command, **kwargs)


class CommandTimeoutError(TerminalError):
    def __init__(self, command: str, timeout: float, **kwargs: str) -> None:
        super().__init__(
            f"Command '{command}' timed out after {timeout}s",
            code="COMMAND_TIMEOUT",
            command=command,
            **kwargs,
        )


class CommandCancelledError(TerminalError):
    def __init__(self, command: str, **kwargs: str) -> None:
        super().__init__(
            f"Command '{command}' was cancelled",
            code="COMMAND_CANCELLED",
            command=command,
            **kwargs,
        )


class CommandOutputLimitError(TerminalError):
    def __init__(self, command: str, limit: int, **kwargs: str) -> None:
        super().__init__(
            f"Command output exceeded {limit} bytes",
            code="OUTPUT_LIMIT_EXCEEDED",
            command=command,
            **kwargs,
        )


class WorkspaceAccessError(TerminalError):
    def __init__(self, workspace_id: str, path: str, **kwargs: str) -> None:
        super().__init__(
            f"Access denied: workspace={workspace_id}, path={path}",
            code="WORKSPACE_ACCESS_ERROR",
            **kwargs,
        )


class PathTraversalError(TerminalError):
    def __init__(self, path: str, **kwargs: str) -> None:
        super().__init__(
            f"Path traversal detected: {path}",
            code="PATH_TRAVERSAL_ERROR",
            **kwargs,
        )


class DangerousCommandError(TerminalError):
    def __init__(self, command: str, **kwargs: str) -> None:
        super().__init__(
            f"Dangerous command blocked: {command}",
            code="DANGEROUS_COMMAND_BLOCKED",
            command=command,
            **kwargs,
        )


class ApprovalRequiredError(TerminalError):
    def __init__(self, command: str, **kwargs: str) -> None:
        super().__init__(
            f"Approval required for: {command}",
            code="APPROVAL_REQUIRED",
            command=command,
            **kwargs,
        )
