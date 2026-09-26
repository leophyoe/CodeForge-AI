"""Terminal audit logger — reuses the Phase 9 tool audit infrastructure."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from codeforge.packages.tools.audit import ToolAuditLogger

if TYPE_CHECKING:
    from codeforge.packages.tools.audit import AuditEntry

_SECRET_PATTERN_HINTS = ("secret", "token", "password", "key")


class TerminalAuditLogger:
    """Records terminal executions without capturing sensitive content.

    Never records stdout/stderr bodies, argument values, or environment
    values — only classification, approval state, timing and exit status.
    """

    def __init__(self, max_entries: int = 10_000) -> None:
        self._audit = ToolAuditLogger(max_entries=max_entries)

    def log_command(
        self,
        *,
        request_id: str,
        workspace_id: str,
        command: str,
        classification: str,
        approval_state: str,
        duration_ms: float,
        success: bool,
        status: str,
        exit_code: int | None = None,
        timed_out: bool = False,
        cancelled: bool = False,
        error_code: str = "",
        working_directory: str = "",
        argument_count: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        entry_metadata: dict[str, Any] = {
            "status": status,
            "approval_state": approval_state,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "cancelled": cancelled,
            "argument_count": argument_count,
            "working_directory": working_directory,
        }
        for key, value in (metadata or {}).items():
            if any(hint in key.lower() for hint in _SECRET_PATTERN_HINTS):
                continue
            entry_metadata[key] = value
        self._audit.log(
            request_id=request_id,
            workspace_id=workspace_id,
            tool_name=f"terminal:{command}",
            permission_level=classification,
            success=success,
            duration_ms=duration_ms,
            error_code=error_code,
            metadata=entry_metadata,
        )

    def count(self) -> int:
        return self._audit.count()

    def get_entries(
        self,
        command: str | None = None,
        workspace_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        tool_name = f"terminal:{command}" if command else None
        return self._audit.get_entries(tool_name=tool_name, workspace_id=workspace_id, limit=limit)

    def stats(self) -> dict[str, Any]:
        return self._audit.get_stats()
