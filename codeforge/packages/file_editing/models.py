"""Data models for file editing operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

EDIT_OPERATIONS = ("read", "write", "str_replace")


@dataclass
class FileEditResult:
    """Outcome of a file editing operation (JSON-serializable)."""

    success: bool
    operation: str
    path: str = ""
    content: str = ""
    bytes_written: int = 0
    replacements: int = 0
    lines_before: int = 0
    lines_after: int = 0
    diff: str = ""
    error: str = ""
    error_code: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "operation": self.operation,
            "path": self.path,
            "content": self.content,
            "bytes_written": self.bytes_written,
            "replacements": self.replacements,
            "lines_before": self.lines_before,
            "lines_after": self.lines_after,
            "diff": self.diff,
            "error": self.error,
            "error_code": self.error_code,
            "metadata": self.metadata,
        }


@dataclass
class ReadResult:
    """Outcome of a file read operation."""

    success: bool
    path: str = ""
    content: str = ""
    total_lines: int = 0
    size_bytes: int = 0
    error: str = ""
    error_code: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "path": self.path,
            "content": self.content,
            "total_lines": self.total_lines,
            "size_bytes": self.size_bytes,
            "error": self.error,
            "error_code": self.error_code,
        }
