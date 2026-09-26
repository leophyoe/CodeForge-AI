"""Terminal models — command execution abstractions."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CommandClassification(Enum):
    SAFE = "safe"
    RESTRICTED = "restricted"
    DANGEROUS = "dangerous"
    BLOCKED = "blocked"


class CommandStatus(Enum):
    REGISTERED = "registered"
    VALIDATING = "validating"
    AUTHORIZED = "authorized"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    WAITING_APPROVAL = "waiting_approval"


@dataclass
class CommandRequest:
    command: str
    arguments: list[str] = field(default_factory=list)
    workspace_id: str = ""
    working_directory: str = ""
    timeout_seconds: float = 30.0
    max_output_bytes: int = 100_000
    max_total_output_bytes: int = 0
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    require_approval: bool = True
    approved: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CommandResult:
    command: str
    arguments: list[str]
    cwd: str = ""
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0
    timed_out: bool = False
    cancelled: bool = False
    truncated: bool = False
    executed: bool = True
    approval_required: bool = False
    approved: bool = False
    security_classification: CommandClassification = CommandClassification.SAFE
    status: CommandStatus = CommandStatus.COMPLETED
    request_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.executed and self.status == CommandStatus.COMPLETED and self.exit_code == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "arguments": self.arguments,
            "cwd": self.cwd,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "timed_out": self.timed_out,
            "cancelled": self.cancelled,
            "truncated": self.truncated,
            "executed": self.executed,
            "approval_required": self.approval_required,
            "approved": self.approved,
            "success": self.success,
            "security_classification": self.security_classification.value,
            "status": self.status.value,
            "request_id": self.request_id,
        }


@dataclass
class CommandExecutionContext:
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workspace_id: str = ""
    working_directory: str = ""
    timeout_seconds: float = 30.0
    max_output_bytes: int = 100_000
    max_total_output_bytes: int = 0
    permission_level: str = "USER_APPROVAL"
    cancelled: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def cancel(self) -> None:
        self.cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self.cancelled


@dataclass
class ApprovalRequest:
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    command: str = ""
    arguments: list[str] = field(default_factory=list)
    cwd: str = ""
    risk_category: CommandClassification = CommandClassification.RESTRICTED
    reason: str = ""
    timestamp: float = field(default_factory=time.time)


def current_time_ms() -> float:
    return time.time() * 1000
