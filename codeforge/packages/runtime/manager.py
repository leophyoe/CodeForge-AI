"""RuntimeManager - Main orchestration layer for CodeForge AI runtime."""

from __future__ import annotations

import logging

from .backends import CPUBackend, CUDABackend, MPSBackend, RuntimeBackend
from .device import DeviceManager
from .environment import detect_environment, detect_python
from .memory import MemoryManager
from .model_estimator import estimate_model_memory
from .models import (
    BackendStatus,
    DeviceInfo,
    DeviceType,
    ModelMemoryEstimate,
    RuntimeInfo,
)
from .precision import PrecisionManager
from .pytorch_check import detect_pytorch_environment, run_tensor_smoke_test

logger = logging.getLogger(__name__)


class RuntimeManager:
    """Manages the complete Python/PyTorch runtime environment.

    Orchestrates environment detection, device selection, backend
    initialization, and runtime validation.
    """

    def __init__(self, preferred_device: str = "auto") -> None:
        self._preferred_device = preferred_device
        self._device_manager = DeviceManager(preferred_device)
        self._memory_manager = MemoryManager()
        self._precision_manager = PrecisionManager()
        self._backend: RuntimeBackend | None = None
        self._runtime_info: RuntimeInfo | None = None

    def detect(self) -> RuntimeInfo:
        """Detect complete runtime information.

        Returns:
            RuntimeInfo with all detected runtime details.
        """
        python_info = detect_python()
        env_info = detect_environment()
        pytorch_info = detect_pytorch_environment()
        selected_device = self._device_manager.get_default_device()
        memory_info = self._memory_manager.get_memory_for_device(
            selected_device.device_type, selected_device.device_index
        )
        precision_info = self._precision_manager.get_supported_dtypes(selected_device.device_type)

        # Determine backend
        backend_name = _get_backend_name(selected_device.device_type)
        backend_status = BackendStatus.NOT_AVAILABLE
        error_msg = ""

        if pytorch_info.installed:
            backend = self._create_backend(selected_device.device_type)
            if backend is not None:
                status = backend.initialize()
                backend_status = status
                if status == BackendStatus.READY:
                    self._backend = backend
                elif status != BackendStatus.READY:
                    error_msg = f"Backend initialization returned: {status.value}"
            else:
                error_msg = "No backend found for device"
        else:
            error_msg = "PyTorch not installed"

        info = RuntimeInfo(
            python=python_info,
            environment=env_info,
            pytorch=pytorch_info,
            selected_device=selected_device,
            memory=memory_info,
            precision=precision_info,
            backend_status=backend_status,
            backend_name=backend_name,
            error_message=error_msg,
        )

        self._runtime_info = info
        return info

    def run_smoke_test(self) -> dict:
        """Run a PyTorch tensor smoke test on the selected device."""
        if self._runtime_info is None:
            self.detect()

        if self._runtime_info is None:
            return {"success": False, "error": "Runtime detection failed"}
        device_str = _device_to_string(self._runtime_info.selected_device)
        return run_tensor_smoke_test(device_str)

    def get_runtime_info(self) -> RuntimeInfo:
        """Get cached runtime info, or detect if not yet done."""
        if self._runtime_info is None:
            return self.detect()
        return self._runtime_info

    def get_backend(self) -> RuntimeBackend | None:
        """Get the current backend."""
        return self._backend

    def shutdown(self) -> None:
        """Shutdown the runtime and release resources."""
        if self._backend is not None:
            self._backend.shutdown()
            self._backend = None
        self._runtime_info = None

    def _create_backend(self, device_type: DeviceType) -> RuntimeBackend | None:
        """Create the appropriate backend for the device type."""
        if device_type == DeviceType.CUDA:
            return CUDABackend()
        if device_type == DeviceType.MPS:
            return MPSBackend()
        if device_type == DeviceType.CPU:
            return CPUBackend()
        return None

    def estimate_model_memory(
        self,
        parameter_count: float,
        dtype: str = "float32",
        quantization: str = "none",
        context_length: int = 0,
    ) -> ModelMemoryEstimate:
        """Estimate model memory requirements."""
        return estimate_model_memory(
            parameter_count=parameter_count,
            dtype=dtype,
            quantization=quantization,
            context_length=context_length,
        )


def _get_backend_name(device_type: DeviceType) -> str:
    """Get the backend name for a device type."""
    mapping = {
        DeviceType.CPU: "CPU",
        DeviceType.CUDA: "CUDA",
        DeviceType.MPS: "MPS",
    }
    return mapping.get(device_type, "Unknown")


def _device_to_string(device: DeviceInfo) -> str:
    """Convert DeviceInfo to a device string."""
    if device.device_index > 0:
        return f"{device.device_type.value}:{device.device_index}"
    return device.device_type.value
