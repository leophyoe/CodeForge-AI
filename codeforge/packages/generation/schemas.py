"""Generation data schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FinishReason(str, Enum):
    """Why generation stopped."""

    STOP = "stop"
    LENGTH = "length"
    ERROR = "error"
    CANCELLED = "cancelled"


class StreamEventType(str, Enum):
    """Types of streaming events."""

    TOKEN = "token"  # noqa: S105
    START = "start"
    END = "end"
    ERROR = "error"


@dataclass
class GenerationConfig:
    """Configuration for text generation."""

    max_tokens: int = 256
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 0
    repetition_penalty: float = 1.0
    do_sample: bool = True
    stop_sequences: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be >= 1")
        if self.max_tokens > 32768:
            raise ValueError("max_tokens must be <= 32768")
        if self.temperature < 0.0:
            raise ValueError("temperature must be >= 0.0")
        if self.temperature > 2.0:
            raise ValueError("temperature must be <= 2.0")
        if self.top_p < 0.0 or self.top_p > 1.0:
            raise ValueError("top_p must be in [0.0, 1.0]")
        if self.repetition_penalty < 0.0:
            raise ValueError("repetition_penalty must be >= 0.0")


@dataclass
class ChatMessage:
    """A single chat message."""

    role: str = "user"
    content: str = ""

    def validate(self) -> None:
        if self.role not in ("system", "user", "assistant"):
            raise ValueError(f"Invalid role: {self.role}")
        if not self.content.strip():
            raise ValueError("Content cannot be empty")


@dataclass
class GenerationRequest:
    """Request for text generation."""

    prompt: str = ""
    model_id: str = ""
    config: GenerationConfig = field(default_factory=GenerationConfig)

    def validate(self) -> None:
        if not self.prompt.strip():
            raise ValueError("Prompt cannot be empty")
        if not self.model_id.strip():
            raise ValueError("model_id cannot be empty")
        self.config.validate()


@dataclass
class ChatRequest:
    """Request for chat generation."""

    messages: list[ChatMessage] = field(default_factory=list)
    model_id: str = ""
    config: GenerationConfig = field(default_factory=GenerationConfig)

    def validate(self) -> None:
        if not self.messages:
            raise ValueError("Messages cannot be empty")
        if not self.model_id.strip():
            raise ValueError("model_id cannot be empty")
        for msg in self.messages:
            msg.validate()
        self.config.validate()


@dataclass
class UsageInfo:
    """Token usage information."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def to_dict(self) -> dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class GenerationResponse:
    """Response from text generation."""

    text: str = ""
    finish_reason: FinishReason = FinishReason.STOP
    usage: UsageInfo = field(default_factory=UsageInfo)
    model_id: str = ""
    tokens: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "finish_reason": self.finish_reason.value,
            "usage": self.usage.to_dict(),
            "model_id": self.model_id,
        }


@dataclass
class StreamEvent:
    """A single streaming event."""

    event_type: StreamEventType = StreamEventType.TOKEN
    text: str = ""
    token_id: int = 0
    is_end: bool = False
    usage: UsageInfo | None = None
    error: str = ""

    def to_dict(self) -> dict:
        d: dict = {"event_type": self.event_type.value}
        if self.text:
            d["text"] = self.text
        if self.token_id:
            d["token_id"] = self.token_id
        if self.is_end:
            d["is_end"] = True
        if self.usage:
            d["usage"] = self.usage.to_dict()
        if self.error:
            d["error"] = self.error
        return d
