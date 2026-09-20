"""FastAPI application for CodeForge AI server.

Provides:
- GET /v1/hardware - Hardware detection endpoint
- GET /v1/runtime - Runtime environment endpoint
- GET /v1/device - Device detection endpoint
- GET /v1/environment - Python environment endpoint
- GET /v1/health - Health check endpoint
- GET /v1/models - List models
- GET /v1/models/{model_id} - Get model info
- POST /v1/models/{model_id}/load - Load model
- POST /v1/models/{model_id}/unload - Unload model
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import hardware_router, models_router, runtime_router

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
app.include_router(runtime_router, prefix="/v1")
app.include_router(models_router, prefix="/v1")


@app.get("/v1/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}
