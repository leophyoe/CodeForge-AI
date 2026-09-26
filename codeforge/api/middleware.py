"""FastAPI middleware classes."""

from __future__ import annotations

import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import Request  # noqa: TC002
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response  # noqa: TC002

if TYPE_CHECKING:
    from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Adds X-Request-ID to all responses."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds standard security headers to all responses."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """Logs request duration and adds X-Process-Time header."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
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
    Returns a structured 429 JSON response directly: exceptions raised in
    middleware never reach FastAPI's ExceptionMiddleware (it sits inside the
    user middleware stack), so raising here would surface as a 500.
    """

    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 60,
        skip_paths: tuple[str, ...] = ("/v1/health",),
    ) -> None:
        super().__init__(app)
        self._rpm = requests_per_minute
        self._window_size = 60.0
        self._skip_paths = skip_paths
        self._clients: dict[str, deque[_WindowEntry]] = {}

    _MAX_CLIENTS = 10_000

    def _prune_clients(self, now: float) -> None:
        """Bound memory use: X-Forwarded-For is client-controlled, so an
        attacker could otherwise grow _clients without limit."""
        if len(self._clients) <= self._MAX_CLIENTS:
            return
        for client_id in list(self._clients):
            window = self._clients[client_id]
            self._prune_window(window, now)
            if not window:
                del self._clients[client_id]
        if len(self._clients) > self._MAX_CLIENTS:
            # Still full of active windows: drop oldest entries (insertion
            # order). Rate limiting is best-effort; bounded memory wins.
            excess = len(self._clients) - self._MAX_CLIENTS // 2
            for client_id in list(self._clients)[:excess]:
                del self._clients[client_id]

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

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if any(request.url.path.startswith(p) for p in self._skip_paths):
            return await call_next(request)

        client_id = self._get_client_id(request)
        now = time.monotonic()

        if client_id not in self._clients:
            self._prune_clients(now)
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
            request_id = str(getattr(request.state, "request_id", None) or uuid.uuid4())
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limit_exceeded",
                        "message": (f"Rate limit exceeded. Try again in {retry_after:.1f}s."),
                        "request_id": request_id,
                    }
                },
                headers={"Retry-After": str(int(retry_after))},
            )

        window.append(_WindowEntry(timestamp=now))
        return await call_next(request)
