"""CodeForge AI - Runtime environment detection and management."""

from .backends import CPUBackend, CUDABackend, MPSBackend, RuntimeBackend
from .device import DeviceManager
from .environment import detect_environment, detect_python, get_available_ml_packages
from .manager import RuntimeManager
from .memory import MemoryManager
from .model_estimator import estimate_model_memory
from .models import (
    BackendStatus,
    DeviceInfo,
    DeviceType,
    EnvironmentInfo,
    EnvironmentType,
    MemoryInfo,
    ModelMemoryEstimate,
    PrecisionInfo,
    PythonInfo,
    PyTorchEnvInfo,
    RuntimeInfo,
)
from .precision import PrecisionManager
from .pytorch_check import detect_pytorch_environment, run_tensor_smoke_test

__all__ = [
    "RuntimeManager",
    "DeviceManager",
    "MemoryManager",
    "PrecisionManager",
    "RuntimeBackend",
    "CPUBackend",
    "CUDABackend",
    "MPSBackend",
    "RuntimeInfo",
    "PythonInfo",
    "EnvironmentInfo",
    "PyTorchEnvInfo",
    "DeviceInfo",
    "MemoryInfo",
    "PrecisionInfo",
    "ModelMemoryEstimate",
    "DeviceType",
    "EnvironmentType",
    "BackendStatus",
    "detect_python",
    "detect_environment",
    "detect_pytorch_environment",
    "run_tensor_smoke_test",
    "estimate_model_memory",
    "get_available_ml_packages",
]
