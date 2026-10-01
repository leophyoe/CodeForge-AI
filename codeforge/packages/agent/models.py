"""Data models for the agent engine (Phase 11)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any


class AgentStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    MAX_STEPS = "max_steps"
    CANCELLED = "cancelled"


@dataclass
class AgentConfig:
    """Runtime configuration for one agent task."""

    model_id: str
    workspace_id: str = "default"
    max_steps: int = 10
    max_tokens: int = 512
    temperature: float = 0.2
    allowed_tools: list[str] | None = None
    tool_result_char_limit: int = 4000

    def validate(self) -> None:
        from .errors import AgentConfigError

        if not self.model_id.strip():
            raise AgentConfigError("model_id is required")
        if not 1 <= self.max_steps <= 50:
            raise AgentConfigError("max_steps must be between 1 and 50")
        if not 16 <= self.max_tokens <= 8192:
            raise AgentConfigError("max_tokens must be between 16 and 8192")
        if not 0.0 <= self.temperature <= 2.0:
            raise AgentConfigError("temperature must be between 0 and 2")


@dataclass
class ToolCall:
    """A parsed tool invocation requested by the model."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    raw: str = ""


@dataclass
class AgentStep:
    """One action in the agent trajectory (LLM turn or tool execution)."""

    index: int
    kind: str  # "llm" | "tool"
    text: str = ""
    tool_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: str = ""
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "index": self.index,
            "kind": self.kind,
            "text": self.text,
            "success": self.success,
            "duration_ms": round(self.duration_ms, 2),
        }
        if self.kind == "tool":
            data["tool_name"] = self.tool_name
            data["arguments"] = self.arguments
        if self.error:
            data["error"] = self.error
        return data


@dataclass
class AgentResult:
    """Full outcome of an agent run."""

    task_id: str
    task: str
    model_id: str
    status: AgentStatus = AgentStatus.RUNNING
    final_text: str = ""
    steps: list[AgentStep] = field(default_factory=list)
    error: str = ""
    workspace_id: str = "default"
    created_at: float = field(default_factory=time)
    finished_at: float = 0.0
    llm_calls: int = 0
    tool_calls: int = 0
    cancelled: bool = False

    @property
    def duration_s(self) -> float:
        end = self.finished_at or time()
        return max(0.0, end - self.created_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task": self.task,
            "model_id": self.model_id,
            "workspace_id": self.workspace_id,
            "status": self.status.value,
            "final_text": self.final_text,
            "error": self.error,
            "steps": [step.to_dict() for step in self.steps],
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
            "duration_s": round(self.duration_s, 3),
            "created_at": self.created_at,
            "finished_at": self.finished_at,
        }
