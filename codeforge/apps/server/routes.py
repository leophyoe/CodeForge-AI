"""API route definitions for CodeForge AI."""

from __future__ import annotations

from fastapi import APIRouter

from codeforge.packages.hardware import HardwareManager

hardware_router = APIRouter(tags=["hardware"])

_manager: HardwareManager | None = None


def _get_manager() -> HardwareManager:
    """Get or create the HardwareManager singleton."""
    global _manager
    if _manager is None:
        _manager = HardwareManager()
    return _manager


@hardware_router.get("/hardware")
async def get_hardware() -> dict:
    """Detect and return hardware information.

    Returns structured JSON with CPU, RAM, GPU, disk, and PyTorch info.
    """
    manager = _get_manager()
    info = manager.detect()
    return info.to_dict()


@hardware_router.get("/hardware/summary")
async def get_hardware_summary() -> dict:
    """Get a human-readable hardware summary."""
    manager = _get_manager()
    return manager.get_summary()


@hardware_router.get("/hardware/compatibility")
async def get_compatibility() -> dict:
    """Check system compatibility with CodeForge AI."""
    manager = _get_manager()
    return manager.check_compatibility()
