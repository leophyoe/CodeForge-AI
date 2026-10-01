"""FileEditManager — policy-checked, audited file editing operations."""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from codeforge.packages.tools.audit import ToolAuditLogger

from . import editor
from .errors import FileEditError
from .models import FileEditResult, ReadResult
from .policy import FileEditPolicy


class FileEditManager:
    """Resolves paths safely, performs edits, and records an audit entry.

    All operations return a result object instead of raising; errors carry
    a stable ``error_code`` (``path_traversal_error``, ``replace_mismatch``...).
    """

    def __init__(
        self,
        policy: FileEditPolicy | None = None,
        audit: ToolAuditLogger | None = None,
    ) -> None:
        self.policy = policy or FileEditPolicy()
        self.audit = audit or ToolAuditLogger()

    # ------------------------------------------------------------------ read
    def read(self, workspace_id: str, rel_path: str, request_id: str = "") -> ReadResult:
        start = time.perf_counter()
        request_id = request_id or str(uuid.uuid4())
        try:
            path = self.policy.check_read(workspace_id, rel_path)
            content = editor.read_text(path, self.policy.config.max_file_size_bytes)
        except FileEditError as exc:
            self._audit(request_id, workspace_id, "file:read", False, start, exc.code)
            return ReadResult(success=False, path=rel_path, error=str(exc), error_code=exc.code)

        self._audit(request_id, workspace_id, "file:read", True, start, "")
        return ReadResult(
            success=True,
            path=rel_path,
            content=content,
            total_lines=len(content.splitlines()),
            size_bytes=len(content.encode("utf-8")),
        )

    # ----------------------------------------------------------------- write
    def write(
        self,
        workspace_id: str,
        rel_path: str,
        content: str,
        *,
        create_only: bool = False,
        request_id: str = "",
    ) -> FileEditResult:
        start = time.perf_counter()
        request_id = request_id or str(uuid.uuid4())
        operation = "write"
        try:
            path = self.policy.check_write(workspace_id, rel_path)
            written, lines_after, diff = editor.write_file(
                path,
                content,
                create_only=create_only,
                max_bytes=self.policy.config.max_write_bytes,
            )
        except FileEditError as exc:
            self._audit(request_id, workspace_id, f"file:{operation}", False, start, exc.code)
            return FileEditResult(
                success=False,
                operation=operation,
                path=rel_path,
                error=str(exc),
                error_code=exc.code,
            )

        self._audit(
            request_id,
            workspace_id,
            f"file:{operation}",
            True,
            start,
            "",
            metadata={"bytes": written},
        )
        return FileEditResult(
            success=True,
            operation=operation,
            path=rel_path,
            bytes_written=written,
            lines_after=lines_after,
            diff=diff,
        )

    # ----------------------------------------------------------- str_replace
    def str_replace(
        self,
        workspace_id: str,
        rel_path: str,
        old: str,
        new: str,
        *,
        replace_all: bool = False,
        request_id: str = "",
    ) -> FileEditResult:
        start = time.perf_counter()
        request_id = request_id or str(uuid.uuid4())
        operation = "str_replace"
        try:
            path = self.policy.check_write(workspace_id, rel_path)
            replacements, lines_before, lines_after, diff, updated = editor.str_replace(
                path,
                old,
                new,
                replace_all=replace_all,
                max_bytes=self.policy.config.max_write_bytes,
            )
        except FileEditError as exc:
            self._audit(request_id, workspace_id, f"file:{operation}", False, start, exc.code)
            return FileEditResult(
                success=False,
                operation=operation,
                path=rel_path,
                error=str(exc),
                error_code=exc.code,
            )

        self._audit(
            request_id,
            workspace_id,
            f"file:{operation}",
            True,
            start,
            "",
            metadata={"replacements": replacements},
        )
        return FileEditResult(
            success=True,
            operation=operation,
            path=rel_path,
            replacements=replacements,
            lines_before=lines_before,
            lines_after=lines_after,
            diff=diff,
            content=updated,
        )

    # ---------------------------------------------------------------- helpers
    def get_policy(self) -> dict[str, Any]:
        return self.policy.to_dict()

    def _audit(
        self,
        request_id: str,
        workspace_id: str,
        tool_name: str,
        success: bool,
        start: float,
        error_code: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        duration_ms = (time.perf_counter() - start) * 1000
        self.audit.log(
            request_id=request_id,
            workspace_id=workspace_id,
            tool_name=tool_name,
            permission_level="user_approval",
            success=success,
            duration_ms=duration_ms,
            error_code=error_code,
            metadata=metadata,
        )


_default_manager: FileEditManager | None = None


def get_file_edit_manager() -> FileEditManager:
    """Process-wide singleton (shared audit trail)."""
    global _default_manager
    if _default_manager is None:
        _default_manager = FileEditManager()
    return _default_manager


def workspace_path(workspace_id: str, rel_path: str) -> Path:
    """Absolute path helper used by tests and diagnostics."""
    return (Path("workspaces") / workspace_id / rel_path).resolve()
