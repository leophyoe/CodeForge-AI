"""Hardware detection API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from codeforge.api.dependencies import get_hardware_manager, get_request_id

router = APIRouter(tags=["hardware"])


@router.get("/hardware")
async def get_hardware(request_id: str = Depends(get_request_id)) -> dict:  # noqa: ARG001
    manager = get_hardware_manager()
    info = manager.detect()
    return info.to_dict()


@router.get("/hardware/summary")
async def get_hardware_summary(request_id: str = Depends(get_request_id)) -> dict:  # noqa: ARG001
    manager = get_hardware_manager()
    return manager.get_summary()


@router.get("/hardware/compatibility")
async def get_hardware_compatibility(request_id: str = Depends(get_request_id)) -> dict:  # noqa: ARG001
    manager = get_hardware_manager()
    return manager.check_compatibility()
