"""Provider settings endpoints (API keys) for the web UI."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from codeforge.packages.models.remote.settings import (
    get_remote_settings,
    mask_secret,
    persist_env_value,
    unset_env_value,
)

router = APIRouter()

_PROVIDERS: dict[str, dict[str, str]] = {
    "openai": {
        "key_env": "OPENAI_API_KEY",
        "base_env": "OPENAI_BASE_URL",
        "default_base": "https://api.openai.com/v1",
    },
    "gemini": {
        "key_env": "GEMINI_API_KEY",
        "base_env": "GEMINI_BASE_URL",
        "default_base": "https://generativelanguage.googleapis.com/v1beta",
    },
}


class ProviderSettingsUpdate(BaseModel):
    """Update request for one provider (key and/or base URL)."""

    provider: str = Field(min_length=1, max_length=32)
    api_key: str | None = Field(default=None, max_length=512)
    base_url: str | None = Field(default=None, max_length=2048)
    clear: bool = False


def _persist(name: str, value: str) -> None:
    """Persist an env var, mapping bad values to HTTP 422."""
    try:
        persist_env_value(name, value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _provider_state(name: str) -> dict:
    meta = _PROVIDERS[name]
    settings = get_remote_settings()
    if name == "openai":
        key = settings.openai_key()
        base = settings.openai_base_url
    else:
        key = settings.gemini_key()
        base = settings.gemini_base_url
    return {
        "provider": name,
        "configured": bool(key),
        "key_masked": mask_secret(key),
        "key_env": meta["key_env"],
        "base_url": base or meta["default_base"],
    }


@router.get("/settings/providers")
async def list_provider_settings() -> dict:
    """Status of each provider (keys are masked, never returned in full)."""
    return {"providers": [_provider_state(name) for name in _PROVIDERS]}


@router.put("/settings/providers")
async def update_provider_settings(body: ProviderSettingsUpdate) -> dict:
    """Save or clear a provider API key / base URL (persisted to .env)."""
    meta = _PROVIDERS.get(body.provider)
    if meta is None:
        raise HTTPException(
            status_code=422,
            detail=f"unknown provider {body.provider!r}; expected one of {sorted(_PROVIDERS)}",
        )

    if body.clear and (body.api_key is not None or body.base_url is not None):
        raise HTTPException(
            status_code=422,
            detail="clear cannot be combined with api_key or base_url",
        )

    if body.clear:
        unset_env_value(meta["key_env"])
        return {"providers": [_provider_state(name) for name in _PROVIDERS]}

    if body.api_key is not None:
        key = body.api_key.strip()
        if len(key) < 8:
            raise HTTPException(status_code=422, detail="api_key must be at least 8 characters")
        _persist(meta["key_env"], key)

    if body.base_url is not None:
        base = body.base_url.strip()
        if not base.startswith(("http://", "https://")):
            raise HTTPException(
                status_code=422, detail="base_url must start with http:// or https://"
            )
        _persist(meta["base_env"], base)

    if body.api_key is None and body.base_url is None:
        raise HTTPException(
            status_code=422, detail="nothing to update: set api_key, base_url or clear"
        )

    return {"providers": [_provider_state(name) for name in _PROVIDERS]}


@router.get("/settings/env")
async def list_env_hints() -> dict:
    """Non-secret environment hints (variable names only)."""
    return {
        "env_vars": [meta["key_env"] for meta in _PROVIDERS.values()],
        "cwd_env_file": str(Path(".env").resolve()),
    }
