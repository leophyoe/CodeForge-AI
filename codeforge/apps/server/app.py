"""FastAPI application for CodeForge AI server (Phase 7+ scaffolding).

Currently provides:
- GET /v1/hardware - Hardware detection endpoint
- GET /v1/health - Health check endpoint
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import hardware_router

app = FastAPI(
    title="CodeForge AI",
    description="Local-first AI coding assistant",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(hardware_router, prefix="/v1")


@app.get("/v1/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}
