"""FastAPI middleware classes."""

from __future__ import annotations

import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass

from fastapi import Request  # noqa: TC002
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response  # noqa: TC002

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Adds X-Request-ID to all responses."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds standard security headers to all responses."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """Logs request duration and adds X-Process-Time header."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start

        response.headers["X-Process-Time"] = f"{elapsed:.4f}"

        logger.info(
            "%s %s %s %.4fs",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        return response


@dataclass
class _WindowEntry:
    """Single entry in the sliding window."""

    timestamp: float


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory sliding window rate limiter.

    Skips health check endpoints (paths starting with /v1/health).
    """

    def __init__(
        self,
        requests_per_minute: int = 60,
        skip_paths: tuple[str, ...] = ("/v1/health",),
    ) -> None:
        super().__init__(None)  # type: ignore[arg-type]
        self._rpm = requests_per_minute
        self._window_size = 60.0
        self._skip_paths = skip_paths
        self._clients: dict[str, deque[_WindowEntry]] = {}

    def _get_client_id(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    def _prune_window(self, window: deque[_WindowEntry], now: float) -> None:
        cutoff = now - self._window_size
        while window and window[0].timestamp < cutoff:
            window.popleft()

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if any(request.url.path.startswith(p) for p in self._skip_paths):
            return await call_next(request)

        client_id = self._get_client_id(request)
        now = time.monotonic()

        if client_id not in self._clients:
            self._clients[client_id] = deque()

        window = self._clients[client_id]
        self._prune_window(window, now)

        if len(window) >= self._rpm:
            oldest = window[0].timestamp
            retry_after = self._window_size - (now - oldest)
            logger.warning(
                "Rate limit exceeded for client %s (%d requests in window)",
                client_id,
                len(window),
            )
            from codeforge.api.errors import RateLimitExceededError

            raise RateLimitExceededError(retry_after=retry_after)

        window.append(_WindowEntry(timestamp=now))
        return await call_next(request)
