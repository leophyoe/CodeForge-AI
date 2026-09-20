"""API route definitions for CodeForge AI."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from codeforge.packages.hardware import HardwareManager
from codeforge.packages.runtime import DeviceManager, RuntimeManager

hardware_router = APIRouter(tags=["hardware"])
runtime_router = APIRouter(tags=["runtime"])
models_router = APIRouter(tags=["models"])

_hw_manager: HardwareManager | None = None
_rt_manager: RuntimeManager | None = None


def _get_hw_manager() -> HardwareManager:
    global _hw_manager
    if _hw_manager is None:
        _hw_manager = HardwareManager()
    return _hw_manager


def _get_rt_manager() -> RuntimeManager:
    global _rt_manager
    if _rt_manager is None:
        _rt_manager = RuntimeManager()
    return _rt_manager


# Hardware endpoints


@hardware_router.get("/hardware")
async def get_hardware() -> dict:
    manager = _get_hw_manager()
    info = manager.detect()
    return info.to_dict()


@hardware_router.get("/hardware/summary")
async def get_hardware_summary() -> dict:
    manager = _get_hw_manager()
    return manager.get_summary()


@hardware_router.get("/hardware/compatibility")
async def get_compatibility() -> dict:
    manager = _get_hw_manager()
    return manager.check_compatibility()


# Runtime endpoints


@runtime_router.get("/runtime")
async def get_runtime() -> dict:
    manager = _get_rt_manager()
    info = manager.detect()
    result = info.to_dict()
    manager.shutdown()
    return result


@runtime_router.get("/runtime/smoke-test")
async def runtime_smoke_test() -> dict:
    manager = _get_rt_manager()
    manager.detect()
    result = manager.run_smoke_test()
    manager.shutdown()
    return result


@runtime_router.get("/device")
async def get_devices() -> dict:
    dm = DeviceManager()
    devices = dm.detect_available_devices()
    default = dm.get_default_device()

    return {
        "devices": [
            {
                "type": d.device_type.value,
                "index": d.device_index,
                "name": d.name,
                "total_memory_gb": d.total_memory_gb,
                "compute_capability": d.compute_capability,
                "is_available": d.is_available,
            }
            for d in devices
        ],
        "default_device": {
            "type": default.device_type.value,
            "index": default.device_index,
            "name": default.name,
        },
    }


@runtime_router.get("/environment")
async def get_environment() -> dict:
    from codeforge.packages.runtime.environment import (
        detect_environment,
        detect_python,
        get_available_ml_packages,
    )

    python_info = detect_python()
    env_info = detect_environment()
    packages = get_available_ml_packages()

    return {
        "python": {
            "version": python_info.version,
            "executable": python_info.executable,
            "implementation": python_info.implementation,
            "architecture": python_info.architecture,
        },
        "environment": {
            "type": env_info.env_type.value,
            "name": env_info.env_name,
            "conda_env_name": env_info.conda_env_name,
        },
        "packages": packages,
    }


# Model endpoints


@models_router.get("/models")
async def list_models() -> dict:
    from codeforge.packages.models import ModelManager

    mm = ModelManager()
    models = mm.list_models()
    return {"models": models, "count": len(models)}


@models_router.get("/models/{model_id}")
async def get_model(model_id: str) -> dict:
    from codeforge.packages.models import ModelManager, ModelNotFoundError

    mm = ModelManager()
    try:
        return mm.inspect_model(model_id).to_dict()
    except ModelNotFoundError as err:
        raise HTTPException(
            status_code=404, detail=f"Model '{model_id}' not found"
        ) from err


@models_router.get("/models/{model_id}/status")
async def get_model_status(model_id: str) -> dict:
    from codeforge.packages.models import ModelManager

    mm = ModelManager()
    entry = mm.get_registry().get(model_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")

    status = mm.get_model_status(model_id)
    loaded = mm.get_loaded_models()
    return {
        "model_id": model_id,
        "status": status.value,
        "loaded": model_id in loaded,
    }


@models_router.post("/models/{model_id}/load")
async def load_model(model_id: str, device: str = "auto", dtype: str = "auto") -> dict:
    from codeforge.packages.models import (
        ModelAlreadyLoadedError,
        ModelManager,
        ModelNotFoundError,
    )

    mm = ModelManager()
    try:
        return mm.load_model(model_id, device=device, dtype=dtype)
    except ModelNotFoundError as err:
        raise HTTPException(
            status_code=404, detail=f"Model '{model_id}' not found"
        ) from err
    except ModelAlreadyLoadedError:
        return {"model_id": model_id, "status": "already_loaded"}
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err)) from err


@models_router.post("/models/{model_id}/unload")
async def unload_model(model_id: str) -> dict:
    from codeforge.packages.models import ModelManager, ModelNotFoundError

    mm = ModelManager()
    try:
        return mm.unload_model(model_id)
    except ModelNotFoundError as err:
        raise HTTPException(
            status_code=404, detail=f"Model '{model_id}' not found"
        ) from err
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err)) from err
