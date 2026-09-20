"""FastAPI dependency injection functions."""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from fastapi import Request  # noqa: TC002

from codeforge.api.errors import (
    AuthenticationRequiredError,
    PathTraversalError,
)

logger = logging.getLogger(__name__)

_singletons: dict[str, Any] = {}

_PATH_TRAVERSAL_RE = re.compile(r"(^|[\\/])\.\.($|[\\/])")
_ABSOLUTE_PATH_RE = re.compile(r"^([a-zA-Z]:[/\\]|/)")


def get_request_id(request: Request) -> str:
    """Extract X-Request-ID header or generate a uuid4."""
    request_id = request.headers.get("X-Request-ID")
    if not request_id:
        request_id = str(uuid.uuid4())
    return request_id


def get_generation_service() -> Any:
    """Get or create the lazy singleton GenerationService.

    Import is deferred so torch is not required at module level.
    """
    if "generation_service" not in _singletons:
        from codeforge.packages.generation.service import GenerationService

        _singletons["generation_service"] = GenerationService()
    return _singletons["generation_service"]


def get_model_manager() -> Any:
    """Get or create the lazy singleton ModelManager."""
    if "model_manager" not in _singletons:
        from codeforge.packages.models.manager import ModelManager

        _singletons["model_manager"] = ModelManager()
    return _singletons["model_manager"]


def get_hardware_manager() -> Any:
    """Get or create the lazy singleton HardwareManager."""
    if "hardware_manager" not in _singletons:
        from codeforge.packages.hardware.manager import HardwareManager

        _singletons["hardware_manager"] = HardwareManager()
    return _singletons["hardware_manager"]


def get_runtime_manager() -> Any:
    """Get or create the lazy singleton RuntimeManager."""
    if "runtime_manager" not in _singletons:
        from codeforge.packages.runtime.manager import RuntimeManager

        _singletons["runtime_manager"] = RuntimeManager()
    return _singletons["runtime_manager"]


def validate_model_id(model_id: str) -> str:
    """Validate and sanitize a model ID.

    Rejects path traversal (../), absolute paths, and empty strings.
    Returns the stripped model ID.
    """
    model_id = model_id.strip()
    if not model_id:
        raise ValueError("model_id cannot be empty")

    if _PATH_TRAVERSAL_RE.search(model_id):
        raise PathTraversalError(model_id)

    if _ABSOLUTE_PATH_RE.match(model_id):
        raise PathTraversalError(model_id)

    return model_id


def get_auth_provider() -> Any | None:
    """Return the auth provider if configured, otherwise None.

    Checks the CODEFORGE_API_KEY environment variable. If set,
    returns a simple dict-based auth provider.
    """
    import os

    api_key = os.environ.get("CODEFORGE_API_KEY", "").strip()
    if not api_key:
        return None

    return {"type": "api_key", "api_key": api_key}


def verify_api_key(request: Request) -> None:
    """Dependency that verifies the API key if auth is configured.

    Raises AuthenticationRequiredError if the key is missing or invalid.
    """
    from codeforge.api.config import AppConfig

    config = AppConfig()
    if not config.api.auth_required:
        return

    provider = get_auth_provider()
    if provider is None:
        return

    provided_key = request.headers.get("X-API-Key", "")
    if not provided_key or provided_key != provider["api_key"]:
        raise AuthenticationRequiredError


def reset_singletons() -> None:
    """Reset all singletons (useful for testing or shutdown)."""
    _singletons.clear()
