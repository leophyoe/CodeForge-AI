"""Remote model providers (OpenAI, Gemini) — GitHub-Copilot-style switching."""

from __future__ import annotations

from .catalog import (
    get_remote_provider,
    is_remote_model,
    list_remote_models,
    remote_metadata,
    reset_remote_providers,
    set_remote_provider,
    split_model_id,
)
from .gemini_provider import GeminiProvider
from .openai_provider import OpenAIProvider
from .settings import RemoteSettings, clear_remote_settings_cache, get_remote_settings

__all__ = [
    "GeminiProvider",
    "OpenAIProvider",
    "RemoteSettings",
    "clear_remote_settings_cache",
    "get_remote_provider",
    "get_remote_settings",
    "is_remote_model",
    "list_remote_models",
    "remote_metadata",
    "reset_remote_providers",
    "set_remote_provider",
    "split_model_id",
]
