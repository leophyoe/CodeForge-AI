"""Tool Audit Logger — records tool execution for security auditing."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AuditEntry:
    timestamp: float
    request_id: str
    workspace_id: str
    tool_name: str
    permission_level: str
    success: bool
    duration_ms: float
    error_code: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolAuditLogger:
    def __init__(self, max_entries: int = 10_000) -> None:
        self._entries: list[AuditEntry] = []
        self._max_entries = max_entries

    def log(
        self,
        request_id: str,
        workspace_id: str,
        tool_name: str,
        permission_level: str,
        success: bool,
        duration_ms: float,
        error_code: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        entry = AuditEntry(
            timestamp=time.time(),
            request_id=request_id,
            workspace_id=workspace_id,
            tool_name=tool_name,
            permission_level=permission_level,
            success=success,
            duration_ms=duration_ms,
            error_code=error_code,
            metadata=metadata or {},
        )
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries :]

    def get_entries(
        self,
        tool_name: str | None = None,
        workspace_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        entries = self._entries
        if tool_name:
            entries = [e for e in entries if e.tool_name == tool_name]
        if workspace_id:
            entries = [e for e in entries if e.workspace_id == workspace_id]
        return entries[-limit:]

    def count(self) -> int:
        return len(self._entries)

    def clear(self) -> int:
        count = len(self._entries)
        self._entries.clear()
        return count

    def get_stats(self) -> dict[str, Any]:
        if not self._entries:
            return {"total": 0, "success": 0, "failure": 0}
        success = sum(1 for e in self._entries if e.success)
        return {
            "total": len(self._entries),
            "success": success,
            "failure": len(self._entries) - success,
        }
