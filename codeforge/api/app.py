"""FastAPI application factory for CodeForge AI."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from codeforge.api.config import AppConfig
from codeforge.api.errors import (
    APIError,
    api_error_handler,
    unhandled_exception_handler,
)
from codeforge.api.middleware import (
    RateLimitMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
    TimingMiddleware,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)

_APP_VERSION = "0.1.0"


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("CodeForge AI server starting up")
    yield
    logger.info("CodeForge AI server shutting down")
    from codeforge.api.dependencies import reset_singletons
    reset_singletons()
    logger.info("Singletons cleared")


def create_app(config: AppConfig | None = None) -> FastAPI:
    if config is None:
        config = AppConfig()

    docs_url = "/docs" if config.api.docs_enabled else None
    redoc_url = "/redoc" if config.api.docs_enabled else None

    application = FastAPI(
        title="CodeForge AI",
        description="Local-first AI coding assistant",
        version=_APP_VERSION,
        docs_url=docs_url,
        redoc_url=redoc_url,
        lifespan=_lifespan,
    )

    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(RequestIDMiddleware)
    application.add_middleware(TimingMiddleware)

    if config.rate_limit.enabled:
        application.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=config.rate_limit.requests_per_minute,
        )

    if config.cors.enabled:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=config.cors.allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    application.add_exception_handler(APIError, api_error_handler)  # type: ignore[arg-type]
    application.add_exception_handler(Exception, unhandled_exception_handler)  # type: ignore[arg-type]

    _register_routers(application)
    return application


def _register_routers(app: FastAPI) -> None:
    from codeforge.api.routers import (
        embeddings,
        generation,
        hardware,
        health,
        models,
        openai_compat,
        runtime,
    )

    app.include_router(health.router, prefix="/v1")
    app.include_router(hardware.router, prefix="/v1")
    app.include_router(runtime.router, prefix="/v1")
    app.include_router(models.router, prefix="/v1")
    app.include_router(generation.router, prefix="/v1")
    app.include_router(embeddings.router, prefix="/v1")
    app.include_router(openai_compat.router, prefix="/v1")
