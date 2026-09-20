"""API error types and exception handlers for FastAPI."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import Request  # noqa: TC002
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base API error with structured error info."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 500,
        request_id: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.request_id = request_id or str(uuid.uuid4())
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "request_id": self.request_id,
            }
        }


class ModelNotLoadedAPIError(APIError):
    """Model is not loaded (409 Conflict)."""

    def __init__(self, model_id: str, request_id: str | None = None) -> None:
        super().__init__(
            code="model_not_loaded",
            message=(
                f"Model '{model_id}' is not loaded. "
                f"Load it first via POST /v1/models/{model_id}/load."
            ),
            status_code=409,
            request_id=request_id,
        )


class ContextLengthExceededAPIError(APIError):
    """Prompt exceeds model context length (400 Bad Request)."""

    def __init__(
        self,
        model_id: str,
        prompt_tokens: int,
        max_context: int,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            code="context_length_exceeded",
            message=(
                f"Prompt has {prompt_tokens} tokens, "
                f"but model '{model_id}' supports max {max_context} tokens."
            ),
            status_code=400,
            request_id=request_id,
        )


class InvalidGenerationConfigAPIError(APIError):
    """Invalid generation configuration (422 Unprocessable Entity)."""

    def __init__(self, detail: str, request_id: str | None = None) -> None:
        super().__init__(
            code="invalid_generation_config",
            message=f"Invalid generation config: {detail}",
            status_code=422,
            request_id=request_id,
        )


class ModelNotFoundAPIError(APIError):
    """Model not found (404 Not Found)."""

    def __init__(self, model_id: str, request_id: str | None = None) -> None:
        super().__init__(
            code="model_not_found",
            message=f"Model '{model_id}' not found.",
            status_code=404,
            request_id=request_id,
        )


class EmbeddingsNotImplementedError(APIError):
    """Embeddings endpoint not implemented (501 Not Implemented)."""

    def __init__(self, request_id: str | None = None) -> None:
        super().__init__(
            code="embeddings_not_implemented",
            message="Embeddings endpoint is not yet implemented.",
            status_code=501,
            request_id=request_id,
        )


class RequestTooLargeError(APIError):
    """Request body exceeds size limit (413 Payload Too Large)."""

    def __init__(
        self,
        max_bytes: int,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            code="request_too_large",
            message=f"Request body exceeds maximum size of {max_bytes} bytes.",
            status_code=413,
            request_id=request_id,
        )


class RequestTimeoutError(APIError):
    """Request processing timed out (504 Gateway Timeout)."""

    def __init__(
        self,
        timeout_seconds: float,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            code="request_timeout",
            message=f"Request timed out after {timeout_seconds}s.",
            status_code=504,
            request_id=request_id,
        )


class RateLimitExceededError(APIError):
    """Rate limit exceeded (429 Too Many Requests)."""

    def __init__(
        self,
        retry_after: float,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            code="rate_limit_exceeded",
            message=f"Rate limit exceeded. Try again in {retry_after:.1f}s.",
            status_code=429,
            request_id=request_id,
        )
        self.retry_after = retry_after


class AuthenticationRequiredError(APIError):
    """Authentication required (401 Unauthorized)."""

    def __init__(self, request_id: str | None = None) -> None:
        super().__init__(
            code="authentication_required",
            message="Valid API key is required. Set the X-API-Key header.",
            status_code=401,
            request_id=request_id,
        )


class PathTraversalError(APIError):
    """Path traversal attempt detected (400 Bad Request)."""

    def __init__(self, path: str, request_id: str | None = None) -> None:
        super().__init__(
            code="path_traversal",
            message=f"Invalid path component: '{path}' contains path traversal sequences.",
            status_code=400,
            request_id=request_id,
        )


def _get_request_id_from_scope(request: Request) -> str:
    """Extract request ID from request state or generate one."""
    request_id = getattr(request.state, "request_id", None)
    if request_id is None:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    return str(request_id)


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle APIError exceptions and return structured JSON response."""
    if exc.request_id == str(uuid.uuid4()):
        exc.request_id = _get_request_id_from_scope(request)

    logger.warning(
        "API error [%s] %s: %s (request_id=%s)",
        exc.status_code,
        exc.code,
        exc.message,
        exc.request_id,
    )

    headers: dict[str, str] = {}
    if exc.status_code == 429 and hasattr(exc, "retry_after"):
        headers["Retry-After"] = str(int(exc.retry_after))  # type: ignore[attr-defined]

    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
        headers=headers,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions without leaking stack traces."""
    request_id = _get_request_id_from_scope(request)

    logger.exception(
        "Unhandled exception (request_id=%s): %s",
        request_id,
        exc,
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "An internal server error occurred.",
                "request_id": request_id,
            }
        },
    )
