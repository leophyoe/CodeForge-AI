"""GenerationService - orchestrates model loading and text generation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from codeforge.packages.models.errors import ModelNotFoundError
from codeforge.packages.models.manager import ModelManager
from codeforge.packages.models.models import GenerationResult, ModelStatus

from .context import ContextManager
from .errors import (
    GenerationConfigError,
    ModelNotLoadedError,
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
            metadata = self._get_metadata(model_id)
            path_value = metadata.get("path") if isinstance(metadata, dict) else None
            model_path = Path(str(path_value)) if path_value else None
            self._context_mgr.validate_context_length(
                request.prompt,
                context_len,
                model_id,
                model_path,
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
            ),
            model_id=model_id,
            tokens=result.tokens,
        )

    def chat(self, request: ChatRequest) -> GenerationResponse:
        """Generate a chat response."""
        request.validate()
        model_id = request.model_id
        provider, instance = self._get_loaded_model(model_id)

        messages_dicts = [{"role": m.role, "content": m.content} for m in request.messages]

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
        prompt = self._context_mgr.format_chat_prompt(
            [{"role": m.role, "content": m.content} for m in messages]
        )

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
        """Get the provider and loaded model instance."""
        status = self._model_manager.get_model_status(model_id)
        if status != ModelStatus.LOADED:
            raise ModelNotLoadedError(model_id)

        provider = self._model_manager.get_provider()
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
