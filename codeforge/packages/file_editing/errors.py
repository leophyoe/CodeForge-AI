"""Structured file-editing errors with stable codes."""

from __future__ import annotations


class FileEditError(Exception):
    """Base error for file editing operations."""

    def __init__(self, message: str, code: str = "file_edit_error") -> None:
        super().__init__(message)
        self.code = code

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": str(self)}


class FileNotFoundEditError(FileEditError):
    def __init__(self, path: str) -> None:
        super().__init__(f"File not found: {path}", code="file_not_found")


class FileAlreadyExistsError(FileEditError):
    def __init__(self, path: str) -> None:
        super().__init__(f"File already exists: {path}", code="file_already_exists")


class InvalidEditError(FileEditError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="invalid_edit")


class StrReplaceMismatchError(FileEditError):
    def __init__(self, path: str, expected: int, found: int) -> None:
        super().__init__(
            f"Replace failed for {path}: expected {expected} occurrence(s), found {found}",
            code="replace_mismatch",
        )
        self.expected = expected
        self.found = found


class FileTooLargeError(FileEditError):
    def __init__(self, path: str, size: int, limit: int) -> None:
        super().__init__(
            f"File too large: {path} is {size} bytes (limit {limit})",
            code="file_too_large",
        )


class WorkspaceAccessError(FileEditError):
    def __init__(self, workspace_id: str, path: str) -> None:
        super().__init__(
            f"Access denied: workspace={workspace_id}, path={path}",
            code="workspace_access_error",
        )


class PathTraversalError(FileEditError):
    def __init__(self, path: str) -> None:
        super().__init__(f"Path traversal detected: {path}", code="path_traversal_error")


class SensitiveFileBlockedError(FileEditError):
    def __init__(self, path: str) -> None:
        super().__init__(f"Sensitive file blocked: {path}", code="sensitive_file_blocked")
