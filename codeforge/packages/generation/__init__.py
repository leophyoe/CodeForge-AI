"""CodeForge AI - Generation package for text generation and streaming."""

from .context import ContextManager
from .errors import (
    ChatFormatError,
    ContextLengthExceededError,
    GenerationConfigError,
    GenerationError,
    ModelNotLoadedError,
    StreamTimeoutError,
    TokenizationError,
)
from .metrics import GenerationMetrics
from .schemas import (
    ChatMessage,
    ChatRequest,
    FinishReason,
    GenerationConfig,
    GenerationRequest,
    GenerationResponse,
    StreamEvent,
    StreamEventType,
    UsageInfo,
)
from .service import GenerationService
from .streamer import BlockingStreamer, TokenStreamer

__all__ = [
    "GenerationService",
    "ContextManager",
    "GenerationMetrics",
    "TokenStreamer",
    "BlockingStreamer",
    "GenerationConfig",
    "GenerationRequest",
    "GenerationResponse",
    "ChatMessage",
    "ChatRequest",
    "StreamEvent",
    "StreamEventType",
    "FinishReason",
    "UsageInfo",
    "GenerationError",
    "ContextLengthExceededError",
    "ModelNotLoadedError",
    "TokenizationError",
    "GenerationConfigError",
    "StreamTimeoutError",
    "ChatFormatError",
]
