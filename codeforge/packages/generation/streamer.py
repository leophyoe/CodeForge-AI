"""Token streaming for generation."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

from codeforge.packages.models.models import StreamToken

from .metrics import GenerationMetrics
from .schemas import FinishReason, StreamEvent, StreamEventType, UsageInfo

if TYPE_CHECKING:
    from collections.abc import Generator

logger = logging.getLogger(__name__)


class TokenStreamer:
    """Wraps provider stream_generate and yields StreamEvents."""

    def __init__(self, provider: Any, model_instance: object) -> None:
        self._provider = provider
        self._model_instance = model_instance

    def stream(
        self,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stop_sequences: list[str] | None = None,
    ) -> Generator[StreamEvent, None, None]:
        """Stream tokens from the provider."""
        metrics = GenerationMetrics()
        metrics.start()

        yield StreamEvent(event_type=StreamEventType.START)

        collected_text = ""
        token_count = 0

        try:
            for stream_token in self._provider.stream_generate(
                self._model_instance,
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
            ):
                if isinstance(stream_token, StreamToken):
                    text = stream_token.text
                    is_end = stream_token.is_end
                else:
                    text = str(stream_token)
                    is_end = False

                if is_end:
                    break

                collected_text += text
                token_count += 1
                metrics.record_token()

                if token_count == 1:
                    metrics.record_first_token()

                should_stop = False
                if stop_sequences:
                    for seq in stop_sequences:
                        if seq in collected_text:
                            should_stop = True
                            break

                yield StreamEvent(
                    event_type=StreamEventType.TOKEN,
                    text=text,
                    token_id=stream_token.token_id if isinstance(stream_token, StreamToken) else 0,
                )

                if should_stop:
                    break

        except Exception as e:
            yield StreamEvent(event_type=StreamEventType.ERROR, error=str(e))
            return

        metrics.completion_tokens = token_count
        metrics.finish()

        usage = UsageInfo(
            prompt_tokens=metrics.prompt_tokens,
            completion_tokens=metrics.completion_tokens,
            total_tokens=metrics.prompt_tokens + metrics.completion_tokens,
        )

        yield StreamEvent(
            event_type=StreamEventType.END,
            is_end=True,
            usage=usage,
        )


class BlockingStreamer:
    """Thread-safe streaming wrapper for synchronous contexts."""

    def __init__(self, token_streamer: TokenStreamer) -> None:
        self._token_streamer = token_streamer
        self._events: list[StreamEvent] = []
        self._lock = threading.Lock()
        self._done = threading.Event()

    def collect(
        self,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> list[StreamEvent]:
        """Collect all streaming events into a list."""
        return list(
            self._token_streamer.stream(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
            )
        )

    def get_text(self, events: list[StreamEvent]) -> str:
        """Extract assembled text from collected events."""
        parts: list[str] = []
        for event in events:
            if event.event_type == StreamEventType.TOKEN and event.text:
                parts.append(event.text)
        return "".join(parts)

    def get_usage(self, events: list[StreamEvent]) -> UsageInfo:
        """Extract usage info from collected events."""
        for event in reversed(events):
            if event.usage is not None:
                return event.usage
        return UsageInfo()

    def get_finish_reason(self, events: list[StreamEvent]) -> FinishReason:
        """Determine finish reason from events."""
        for event in reversed(events):
            if event.event_type == StreamEventType.ERROR:
                return FinishReason.ERROR
        return FinishReason.STOP
