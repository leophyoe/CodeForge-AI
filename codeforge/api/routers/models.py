"""Model management endpoints."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from codeforge.api.dependencies import get_model_manager

router = APIRouter(tags=["models"])


def _validate_model_id(model_id: str) -> str:
    if ".." in model_id or model_id.startswith("/") or "\\" in model_id:
        raise HTTPException(status_code=400, detail="Invalid model ID")
    return model_id


class LoadModelRequest(BaseModel):
    device: str = "auto"
    dtype: str = "auto"
    force: bool = False


@router.get("/models")
async def list_models() -> dict[str, Any]:
    """List models in OpenAI-compatible shape with native metadata merged.

    Single source of truth for GET /v1/models (the OpenAI-compat router used
    to register a shadowed duplicate of this path).
    """
    mm = get_model_manager()
    created = int(time.time())
    data: list[dict[str, Any]] = []
    for m in mm.list_models():
        item: dict[str, Any] = dict(m)
        item.setdefault("id", m.get("model_id", ""))
        item["object"] = "model"
        item.setdefault("created", created)
        item.setdefault("owned_by", "codeforge")
        data.append(item)
    return {"object": "list", "data": data}


@router.get("/models/{model_id}")
async def get_model(model_id: str) -> dict:
    model_id = _validate_model_id(model_id)
    mm = get_model_manager()
    try:
        inspection = mm.inspect_model(model_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return inspection.to_dict()


@router.post("/models/{model_id}/load")
async def load_model(model_id: str, body: LoadModelRequest) -> dict:
    from codeforge.packages.models.errors import ModelAlreadyLoadedError

    model_id = _validate_model_id(model_id)
    mm = get_model_manager()
    try:
        return mm.load_model(model_id, body.device, body.dtype, body.force)
    except ModelAlreadyLoadedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/models/{model_id}/unload")
async def unload_model(model_id: str) -> dict:
    model_id = _validate_model_id(model_id)
    mm = get_model_manager()
    try:
        return mm.unload_model(model_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/models/{model_id}/status")
async def get_model_status(model_id: str) -> dict:
    model_id = _validate_model_id(model_id)
    mm = get_model_manager()
    status = mm.get_model_status(model_id)
    return {"model_id": model_id, "status": status.value}
