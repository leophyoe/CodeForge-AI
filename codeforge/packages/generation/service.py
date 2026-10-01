"""GenerationService - orchestrates model loading and text generation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from codeforge.packages.models.errors import ModelNotFoundError
from codeforge.packages.models.manager import ModelManager
from codeforge.packages.models.models import GenerationResult, ModelStatus
from codeforge.packages.models.remote import is_remote_model

from .context import ContextManager
from .errors import (
    ContextLengthExceededError,
    GenerationConfigError,
    ModelNotLoadedError,
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
    UsageInfo,
)
from .streamer import TokenStreamer

if TYPE_CHECKING:
    from collections.abc import Generator

logger = logging.getLogger(__name__)


class GenerationService:
    """High-level service for text generation."""

    def __init__(self, model_manager: ModelManager | None = None) -> None:
        self._model_manager = model_manager or ModelManager()
        self._context_mgr = ContextManager(self._model_manager.get_tokenizer_manager())

    @property
    def model_manager(self) -> ModelManager:
        return self._model_manager

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate text from a prompt."""
        request.validate()
        model_id = request.model_id
        provider, instance = self._get_loaded_model(model_id)

        metrics = GenerationMetrics()
        metrics.start()

        context_len = provider.get_context_length(instance)
        if context_len > 0:
            self._context_mgr.validate_context_length(
                request.prompt,
                context_len,
                model_id,
                self._model_path(model_id),
            )

        result: GenerationResult = provider.generate(
            instance,
            request.prompt,
            max_tokens=request.config.max_tokens,
            temperature=request.config.temperature,
            top_p=request.config.top_p,
        )

        metrics.finish()
        metrics.prompt_tokens = result.usage.get("prompt_tokens", 0)
        metrics.completion_tokens = result.usage.get("completion_tokens", 0)

        finish_reason = _map_finish_reason(result.finish_reason)

        return GenerationResponse(
            text=result.text,
            finish_reason=finish_reason,
            usage=UsageInfo(
                prompt_tokens=metrics.prompt_tokens,
                completion_tokens=metrics.completion_tokens,
                total_tokens=metrics.prompt_tokens + metrics.completion_tokens,
                error=str(result.usage.get("error", "")),
            ),
            model_id=model_id,
            tokens=result.tokens,
        )

    def _model_path(self, model_id: str) -> Path | None:
        """Resolve the on-disk model path for tokenizer-aware operations.

        Remote models have no local registry entry — returns None for them.
        """
        try:
            metadata = self._get_metadata(model_id)
        except ModelNotFoundError:
            return None
        path_value = metadata.get("path") if isinstance(metadata, dict) else None
        return Path(str(path_value)) if path_value else None

    def _fit_chat_messages(
        self,
        messages: list[dict],
        max_context: int,
        max_new_tokens: int,
        model_id: str,
        model_path: Path | None,
    ) -> list[dict]:
        """Trim chat messages so the rendered prompt fits the model context.

        Oldest non-system messages are dropped first; if the system prompt
        alone is too big it is truncated keeping its tail (instructions live
        at the end). Raises ContextLengthExceededError when the conversation
        still cannot fit.
        """
        if max_context <= 0 or not messages:
            return messages
        budget = max_context - max_new_tokens if max_context > max_new_tokens else max_context
        try:
            counts = [
                self._context_mgr.count_tokens(m.get("content", ""), model_path) + 10
                for m in messages
            ]
        except TokenizationError:
            return messages
        total = sum(counts)
        if total <= budget:
            return messages

        system_idx = 0 if messages[0].get("role") == "system" else -1
        last_idx = len(messages) - 1
        kept = list(range(len(messages)))
        for i in list(kept):
            if total <= budget:
                break
            if i in (system_idx, last_idx):
                continue
            kept.remove(i)
            total -= counts[i]

        result = [messages[i] for i in kept]
        if total > budget and system_idx in kept:
            content = str(messages[system_idx].get("content", ""))
            reserved = counts[last_idx] if last_idx != system_idx else 0
            content = self._context_mgr.truncate_to_context(
                content, max(1, budget - reserved - 10), model_path
            )
            result[kept.index(system_idx)] = {**messages[system_idx], "content": content}
            try:
                new_count = self._context_mgr.count_tokens(content, model_path) + 10
            except TokenizationError:
                new_count = counts[system_idx]
            total = new_count + reserved

        if total > budget:
            raise ContextLengthExceededError(model_id, total, budget)
        return result

    def chat(self, request: ChatRequest) -> GenerationResponse:
        """Generate a chat response."""
        request.validate()
        model_id = request.model_id
        provider, instance = self._get_loaded_model(model_id)

        messages_dicts = [{"role": m.role, "content": m.content} for m in request.messages]

        context_len = provider.get_context_length(instance)
        if context_len > 0:
            messages_dicts = self._fit_chat_messages(
                messages_dicts,
                context_len,
                request.config.max_tokens,
                model_id,
                self._model_path(model_id),
            )

        metrics = GenerationMetrics()
        metrics.start()

        result: GenerationResult = provider.chat(
            instance,
            messages_dicts,
            max_tokens=request.config.max_tokens,
            temperature=request.config.temperature,
        )

        metrics.finish()
        metrics.prompt_tokens = result.usage.get("prompt_tokens", 0)
        metrics.completion_tokens = result.usage.get("completion_tokens", 0)

        return GenerationResponse(
            text=result.text,
            finish_reason=_map_finish_reason(result.finish_reason),
            usage=UsageInfo(
                prompt_tokens=metrics.prompt_tokens,
                completion_tokens=metrics.completion_tokens,
                total_tokens=metrics.prompt_tokens + metrics.completion_tokens,
                error=str(result.usage.get("error", "")),
            ),
            model_id=model_id,
            tokens=result.tokens,
        )

    def stream_generate(
        self,
        prompt: str,
        model_id: str,
        config: GenerationConfig | None = None,
    ) -> Generator[StreamEvent, None, None]:
        """Stream tokens from generation."""
        if not prompt.strip():
            raise GenerationConfigError("Prompt cannot be empty")
        if not model_id.strip():
            raise GenerationConfigError("model_id cannot be empty")

        cfg = config or GenerationConfig()
        provider, instance = self._get_loaded_model(model_id)

        streamer = TokenStreamer(provider, instance)
        yield from streamer.stream(
            prompt,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
            top_p=cfg.top_p,
            stop_sequences=cfg.stop_sequences,
        )

    def stream_chat(
        self,
        messages: list[ChatMessage],
        model_id: str,
        config: GenerationConfig | None = None,
    ) -> Generator[StreamEvent, None, None]:
        """Stream tokens from a chat request."""
        if not messages:
            raise GenerationConfigError("Messages cannot be empty")
        if not model_id.strip():
            raise GenerationConfigError("model_id cannot be empty")

        cfg = config or GenerationConfig()
        provider, instance = self._get_loaded_model(model_id)
        dicts = [{"role": m.role, "content": m.content} for m in messages]
        context_len = provider.get_context_length(instance)
        if context_len > 0:
            dicts = self._fit_chat_messages(
                dicts, context_len, cfg.max_tokens, model_id, self._model_path(model_id)
            )
        prompt = self._context_mgr.format_chat_prompt(dicts)

        streamer = TokenStreamer(provider, instance)
        yield from streamer.stream(
            prompt,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
            top_p=cfg.top_p,
            stop_sequences=cfg.stop_sequences,
        )

    def get_model_status(self, model_id: str) -> dict:
        """Get generation readiness status for a model."""
        try:
            _ = self._get_metadata(model_id)
        except ModelNotFoundError:
            return {"model_id": model_id, "ready": False, "reason": "Model not found"}

        status = self._model_manager.get_model_status(model_id)
        if status != ModelStatus.LOADED:
            return {"model_id": model_id, "ready": False, "reason": f"Model status: {status.value}"}

        try:
            provider, instance = self._get_loaded_model(model_id)
            health = provider.health_check(instance)
            return {
                "model_id": model_id,
                "ready": health.get("healthy", False),
                "status": status.value,
                "device": health.get("device", "unknown"),
                "dtype": health.get("dtype", "unknown"),
            }
        except Exception as e:
            return {"model_id": model_id, "ready": False, "reason": str(e)}

    def _get_loaded_model(self, model_id: str) -> tuple:
        """Get the provider and loaded model instance.

        Remote models (openai:/gemini:) auto-load on first use since loading
        only validates credentials; local models must be loaded explicitly.
        """
        status = self._model_manager.get_model_status(model_id)
        if status != ModelStatus.LOADED and is_remote_model(model_id):
            self._model_manager.load_model(model_id)
            status = self._model_manager.get_model_status(model_id)
        if status != ModelStatus.LOADED:
            raise ModelNotLoadedError(model_id)

        provider = self._model_manager.get_provider_for_model(model_id)
        cache = self._model_manager.get_cache()
        instance = cache.get(model_id)
        if instance is None:
            raise ModelNotLoadedError(model_id)
        return provider, instance

    def _get_metadata(self, model_id: str) -> object:
        """Get model metadata from registry."""
        registry = self._model_manager.get_registry()
        entry = registry.get(model_id)
        if entry is None:
            raise ModelNotFoundError(model_id)
        return entry


def _map_finish_reason(reason: str) -> FinishReason:
    """Map provider finish reason to our enum."""
    mapping = {
        "stop": FinishReason.STOP,
        "length": FinishReason.LENGTH,
        "error": FinishReason.ERROR,
    }
    return mapping.get(reason, FinishReason.STOP)
