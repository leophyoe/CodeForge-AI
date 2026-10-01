"""Environment-driven settings for remote model providers (OpenAI, Gemini)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

ENV_FILE = Path(".env")


def mask_secret(value: str) -> str:
    """Mask a secret for display (never reveal the full value)."""
    value = value.strip()
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:3]}...{value[-4:]}"


def persist_env_value(name: str, value: str) -> None:
    """Upsert ``NAME=value`` in ``.env`` and apply it to this process.

    The file is created with mode 0600. Other lines (comments, unrelated
    variables) are preserved. The settings cache is cleared so the new
    value takes effect immediately.
    """
    if not name.isidentifier():
        raise ValueError(f"invalid env var name: {name!r}")
    if "\n" in value or "\r" in value:
        raise ValueError("env var value must be a single line")
    lines: list[str] = []
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    prefix = f"{name}="
    for index, line in enumerate(lines):
        if line.startswith(prefix) or line.split("=", 1)[0].strip() == name:
            lines[index] = f"{name}={value}"
            break
    else:
        lines.append(f"{name}={value}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ENV_FILE.chmod(0o600)
    os.environ[name] = value
    clear_remote_settings_cache()


def unset_env_value(name: str) -> None:
    """Remove ``NAME`` from ``.env`` and from this process environment."""
    if ENV_FILE.exists():
        lines = [
            line
            for line in ENV_FILE.read_text(encoding="utf-8").splitlines()
            if line.split("=", 1)[0].strip() != name
        ]
        text = "\n".join(lines)
        ENV_FILE.write_text(text + ("\n" if text else ""), encoding="utf-8")
    os.environ.pop(name, None)
    clear_remote_settings_cache()


class RemoteSettings(BaseSettings):
    """API keys and endpoints, read from env / .env (standard names)."""

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_models: list[str] = ["gpt-4o-mini", "gpt-4o"]

    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_models: list[str] = ["gemini-2.5-flash", "gemini-1.5-flash"]

    def openai_key(self) -> str:
        """Return the OpenAI key (CODEFORGE_ override supported)."""
        key = self.openai_api_key.strip()
        return key or os.environ.get("CODEFORGE_OPENAI_API_KEY", "").strip()

    def gemini_key(self) -> str:
        """Return the Gemini key (CODEFORGE_ override supported)."""
        key = self.gemini_api_key.strip()
        return key or os.environ.get("CODEFORGE_GEMINI_API_KEY", "").strip()


@lru_cache(maxsize=1)
def get_remote_settings() -> RemoteSettings:
    """Cached settings instance (clear after changing env in tests)."""
    return RemoteSettings()


def clear_remote_settings_cache() -> None:
    """Drop the cached settings so env changes take effect."""
    get_remote_settings.cache_clear()
