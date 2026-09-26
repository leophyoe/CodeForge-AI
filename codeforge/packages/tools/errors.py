"""Structured tool errors with stable error codes."""

from __future__ import annotations


class ToolError(Exception):
    def __init__(
        self,
        message: str,
        code: str = "tool_error",
        tool_name: str = "",
        request_id: str = "",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.tool_name = tool_name
        self.request_id = request_id

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": str(self),
            "tool_name": self.tool_name,
            "request_id": self.request_id,
        }


class InvalidToolInputError(ToolError):
    def __init__(self, message: str, **kwargs: str) -> None:
        super().__init__(message, code="invalid_tool_input", **kwargs)


class ToolNotFoundError(ToolError):
    def __init__(self, tool_name: str, **kwargs: str) -> None:
        super().__init__(
            f"Tool not found: {tool_name}", code="tool_not_found", tool_name=tool_name, **kwargs
        )


class ToolPermissionError(ToolError):
    def __init__(self, message: str, **kwargs: str) -> None:
        super().__init__(message, code="tool_permission_error", **kwargs)


class ToolTimeoutError(ToolError):
    def __init__(self, tool_name: str, timeout_seconds: float, **kwargs: str) -> None:
        super().__init__(
            f"Tool '{tool_name}' timed out after {timeout_seconds}s",
            code="tool_timeout",
            tool_name=tool_name,
            **kwargs,
        )


class ToolExecutionError(ToolError):
    def __init__(self, message: str, **kwargs: str) -> None:
        super().__init__(message, code="tool_execution_error", **kwargs)


class WorkspaceAccessError(ToolError):
    def __init__(self, workspace_id: str, path: str, **kwargs: str) -> None:
        super().__init__(
            f"Access denied: workspace={workspace_id}, path={path}",
            code="workspace_access_error",
            **kwargs,
        )


class PathTraversalError(ToolError):
    def __init__(self, path: str, **kwargs: str) -> None:
        super().__init__(
            f"Path traversal detected: {path}",
            code="path_traversal_error",
            **kwargs,
        )


class SensitiveFileBlockedError(ToolError):
    def __init__(self, path: str, **kwargs: str) -> None:
        super().__init__(
            f"Sensitive file blocked: {path}",
            code="sensitive_file_blocked",
            **kwargs,
        )


class ToolNotAvailableError(ToolError):
    def __init__(self, tool_name: str, **kwargs: str) -> None:
        super().__init__(
            f"Tool not available: {tool_name}",
            code="tool_not_available",
            tool_name=tool_name,
            **kwargs,
        )
