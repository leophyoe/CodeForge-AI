"""FastAPI dependency injection functions."""

from __future__ import annotations

import logging
import re
import secrets
import uuid
from typing import TYPE_CHECKING, Any, cast

from fastapi import Request  # noqa: TC002

from codeforge.api.errors import (
    AuthenticationRequiredError,
    PathTraversalError,
)

if TYPE_CHECKING:
    from codeforge.packages.hardware.manager import HardwareManager
    from codeforge.packages.models.manager import ModelManager
    from codeforge.packages.runtime.manager import RuntimeManager

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


def get_model_manager() -> ModelManager:
    """Get or create the lazy singleton ModelManager."""
    if "model_manager" not in _singletons:
        from codeforge.packages.models.manager import ModelManager as _ModelManager

        _singletons["model_manager"] = _ModelManager()
    return cast("ModelManager", _singletons["model_manager"])


def get_hardware_manager() -> HardwareManager:
    """Get or create the lazy singleton HardwareManager."""
    if "hardware_manager" not in _singletons:
        from codeforge.packages.hardware.manager import HardwareManager as _HardwareManager

        _singletons["hardware_manager"] = _HardwareManager()
    return cast("HardwareManager", _singletons["hardware_manager"])


def get_runtime_manager() -> RuntimeManager:
    """Get or create the lazy singleton RuntimeManager."""
    if "runtime_manager" not in _singletons:
        from codeforge.packages.runtime.manager import RuntimeManager as _RuntimeManager

        _singletons["runtime_manager"] = _RuntimeManager()
    return cast("RuntimeManager", _singletons["runtime_manager"])


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
    """Dependency that verifies the API key when auth is enabled.

    Fail-closed: if auth is required but no key is configured, all requests
    are rejected. Comparison is timing-safe. GET /v1/health is exempt so
    liveness probes work without credentials.
    """
    from codeforge.api.config import AppConfig

    if request.url.path == "/v1/health":
        return

    config = getattr(request.app.state, "config", None)
    if config is None:
        config = AppConfig()
    if not config.api.auth_required:
        return

    expected = config.api.api_key.strip()
    if not expected:
        provider = get_auth_provider()
        if provider is not None:
            expected = str(provider.get("api_key", "")).strip()

    provided = request.headers.get("X-API-Key", "")
    if not expected:
        raise AuthenticationRequiredError
    if not provided or not secrets.compare_digest(
        provided.encode("utf-8"), expected.encode("utf-8")
    ):
        raise AuthenticationRequiredError


def reset_singletons() -> None:
    """Reset all singletons (useful for testing or shutdown)."""
    _singletons.clear()
