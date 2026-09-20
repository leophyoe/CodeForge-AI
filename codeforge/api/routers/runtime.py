"""Runtime detection API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from codeforge.api.dependencies import get_request_id, get_runtime_manager

router = APIRouter(tags=["runtime"])


@router.get("/runtime")
async def get_runtime(request_id: str = Depends(get_request_id)) -> dict:  # noqa: ARG001
    manager = get_runtime_manager()
    info = manager.detect()
    return info.to_dict()


@router.get("/runtime/smoke-test")
async def get_runtime_smoke_test(request_id: str = Depends(get_request_id)) -> dict:  # noqa: ARG001
    manager = get_runtime_manager()
    return manager.run_smoke_test()
