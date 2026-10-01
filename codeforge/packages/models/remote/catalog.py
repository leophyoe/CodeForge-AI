"""Catalog + dispatch for remote model ids (``openai:...`` / ``gemini:...``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from codeforge.packages.models.errors import ModelNotFoundError
from codeforge.packages.models.models import ModelFormat, ModelMetadata, ModelTask

from .settings import get_remote_settings

if TYPE_CHECKING:
    from codeforge.packages.models.provider import ModelProvider

_PREFIXES = ("openai", "gemini")

_CONTEXT_LENGTHS = {"openai": 128000, "gemini": 1048576}

_providers: dict[str, ModelProvider] = {}


def split_model_id(model_id: str) -> tuple[str, str] | None:
    """Split ``openai:gpt-4o-mini`` into (prefix, name); None if not remote."""
    if ":" not in model_id:
        return None
    prefix, sep, name = model_id.partition(":")
    if sep and prefix in _PREFIXES and name:
        return prefix, name
    return None


def is_remote_model(model_id: str) -> bool:
    """True when model_id targets a remote provider."""
    return split_model_id(model_id) is not None


def get_remote_provider(prefix: str) -> ModelProvider:
    """Return (cached) provider instance for a remote prefix."""
    if prefix not in _PREFIXES:
        raise ModelNotFoundError(prefix)
    provider = _providers.get(prefix)
    if provider is None:
        if prefix == "openai":
            from .openai_provider import OpenAIProvider

            provider = OpenAIProvider()
        else:
            from .gemini_provider import GeminiProvider

            provider = GeminiProvider()
        _providers[prefix] = provider
    return provider


def set_remote_provider(prefix: str, provider: ModelProvider) -> None:
    """Inject a provider instance (used by tests to avoid real network)."""
    _providers[prefix] = provider


def reset_remote_providers() -> None:
    """Drop cached provider instances."""
    for provider in list(_providers.values()):
        close = getattr(provider, "close", None)
        if callable(close):
            close()
    _providers.clear()


def _has_key(prefix: str) -> bool:
    settings = get_remote_settings()
    if prefix == "openai":
        return bool(settings.openai_key())
    return bool(settings.gemini_key())


def _entry(prefix: str, name: str) -> dict:
    model_id = f"{prefix}:{name}"
    return {
        "model_id": model_id,
        "id": model_id,
        "name": f"{name} ({prefix})",
        "path": "",
        "provider": prefix,
        "task": "causal-lm",
        "format": "api",
        "dtype": "api",
        "parameter_count": None,
        "context_length": _CONTEXT_LENGTHS[prefix],
        "quantization": "none",
        "source": "remote",
        "license": "",
        "has_tokenizer": True,
        "status": "remote",
        "object": "model",
        "owned_by": prefix,
    }


def list_remote_models() -> list[dict]:
    """Catalog entries for every configured remote model (key present)."""
    settings = get_remote_settings()
    entries: list[dict] = []
    if settings.openai_key():
        entries.extend(_entry("openai", name) for name in settings.openai_models)
    if settings.gemini_key():
        entries.extend(_entry("gemini", name) for name in settings.gemini_models)
    return entries


def remote_metadata(prefix: str, name: str) -> ModelMetadata:
    """Build ModelMetadata for a remote model id."""
    return ModelMetadata(
        model_id=f"{prefix}:{name}",
        name=name,
        path="",
        provider=prefix,
        task=ModelTask.CAUSAL_LM,
        dtype="api",
        context_length=_CONTEXT_LENGTHS[prefix],
        has_tokenizer=True,
        format=ModelFormat.API,
        config_exists=True,
        weight_files=[],
    )
