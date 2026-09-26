"""Tool models — strongly typed interfaces for the tool system."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ToolCategory(Enum):
    READ = "read"
    SEARCH = "search"
    ANALYSIS = "analysis"
    GIT = "git"
    WRITE = "write"
    EXECUTION = "execution"
    EXTERNAL = "external"


class PermissionLevel(Enum):
    NONE = "none"
    READ_ONLY = "read_only"
    USER_APPROVAL = "user_approval"
    PRIVILEGED = "privileged"


@dataclass
class ToolResult:
    tool_name: str
    success: bool
    result: Any = None
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0
    request_id: str = ""
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
            "execution_time_ms": self.execution_time_ms,
            "request_id": self.request_id,
            "truncated": self.truncated,
        }


@dataclass
class ToolExecutionContext:
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workspace_id: str = ""
    permissions: list[str] = field(default_factory=list)
    timeout_seconds: float = 10.0
    max_output_bytes: int = 100_000
    metadata: dict[str, Any] = field(default_factory=dict)
    _cancelled: bool = field(default=False, repr=False)

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled


def make_request_id() -> str:
    return str(uuid.uuid4())


def current_time_ms() -> float:
    return time.time() * 1000
