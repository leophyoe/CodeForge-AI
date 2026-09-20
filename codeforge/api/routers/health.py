"""Health and readiness endpoints."""

from __future__ import annotations

import platform
import sys
from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from codeforge import __version__
from codeforge.api.dependencies import get_request_id

router = APIRouter()

_SYSTEM = {
    "version": __version__,
    "api_version": "v1",
    "platform": platform.system().lower(),
    "architecture": platform.machine(),
}


@router.get("/health")
async def health(request_id: str = Depends(get_request_id)) -> dict:  # noqa: ARG001
    return {
        "status": "ok",
        "version": __version__,
        "runtime": "python",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/ready")
async def ready(request_id: str = Depends(get_request_id)) -> dict:  # noqa: ARG001
    from codeforge.api.dependencies import get_model_manager

    try:
        mm = get_model_manager()
        loaded_models = mm.get_loaded_models()
    except Exception:
        loaded_models = []

    status = "ready" if loaded_models else "not_ready"
    return {
        "status": status,
        "loaded_models": len(loaded_models),
        "models": loaded_models,
    }


@router.get("/system")
async def system(request_id: str = Depends(get_request_id)) -> dict:  # noqa: ARG001
    return {
        **_SYSTEM,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}"
        f".{sys.version_info.micro}",
    }
