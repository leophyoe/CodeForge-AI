"""Phase 10 — safe file editing (workspace-boundary, audited, atomic)."""

from __future__ import annotations

from .editor import atomic_write, make_diff, read_text, str_replace, write_file
from .errors import (
    FileAlreadyExistsError,
    FileEditError,
    FileNotFoundEditError,
    FileTooLargeError,
    InvalidEditError,
    PathTraversalError,
    SensitiveFileBlockedError,
    StrReplaceMismatchError,
    WorkspaceAccessError,
)
from .manager import FileEditManager, get_file_edit_manager, workspace_path
from .models import FileEditResult, ReadResult
from .policy import FileEditPolicy, FileEditPolicyConfig

__all__ = [
    "FileAlreadyExistsError",
    "FileEditError",
    "FileEditManager",
    "FileEditPolicy",
    "FileEditPolicyConfig",
    "FileEditResult",
    "FileNotFoundEditError",
    "FileTooLargeError",
    "InvalidEditError",
    "PathTraversalError",
    "ReadResult",
    "SensitiveFileBlockedError",
    "StrReplaceMismatchError",
    "WorkspaceAccessError",
    "atomic_write",
    "get_file_edit_manager",
    "make_diff",
    "read_text",
    "str_replace",
    "workspace_path",
    "write_file",
]
