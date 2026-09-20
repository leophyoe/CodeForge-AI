"""Runtime data models for CodeForge AI Phase 2."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DeviceType(str, Enum):
    """Supported device types."""

    CPU = "cpu"
    CUDA = "cuda"
    MPS = "mps"


class EnvironmentType(str, Enum):
    """Detected environment types."""

    CONDA = "conda"
    VENV = "venv"
    VIRTUALENV = "virtualenv"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class BackendStatus(str, Enum):
    """Runtime backend status."""

    READY = "READY"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    NOT_INSTALLED = "NOT_INSTALLED"
    ERROR = "ERROR"


@dataclass(frozen=True)
class PythonInfo:
    """Python interpreter information."""

    version: str = "Unknown"
    version_major: int = 0
    version_minor: int = 0
    version_micro: int = 0
    executable: str = "Unknown"
    implementation: str = "Unknown"
    compiler: str = "Unknown"
    architecture: str = "Unknown"


@dataclass(frozen=True)
class EnvironmentInfo:
    """Current Python environment information."""

    env_type: EnvironmentType = EnvironmentType.UNKNOWN
    env_name: str = ""
    env_path: str = ""
    conda_env_name: str = ""
    conda_prefix: str = ""
    virtual_env: str = ""
    site_packages: str = ""


@dataclass(frozen=True)
class PyTorchEnvInfo:
    """Detailed PyTorch environment information."""

    installed: bool = False
    version: str = ""
    cuda_available: bool = False
    cuda_version: str | None = None
    cudnn_version: str | None = None
    rocm_available: bool = False
    hip_version: str | None = None
    mps_available: bool = False
    device_count: int = 0
    devices: list[DeviceInfo] = field(default_factory=list)


@dataclass(frozen=True)
class DeviceInfo:
    """Information about a single compute device."""

    device_type: DeviceType = DeviceType.CPU
    device_index: int = 0
    name: str = "Unknown"
    total_memory_gb: float | None = None
    free_memory_gb: float | None = None
    compute_capability: str | None = None
    is_available: bool = False


@dataclass(frozen=True)
class MemoryInfo:
    """Memory information for a device."""

    total_gb: float = 0.0
    available_gb: float = 0.0
    used_gb: float = 0.0
    allocated_gb: float | None = None
    reserved_gb: float | None = None
    usage_percent: float = 0.0


@dataclass(frozen=True)
class PrecisionInfo:
    """Supported precision information."""

    float32_supported: bool = True
    float16_supported: bool = False
    bfloat16_supported: bool = False
    default_dtype: str = "float32"


@dataclass(frozen=True)
class ModelMemoryEstimate:
    """Estimated memory requirements for a model."""

    parameter_count: float = 0.0
    dtype: str = "float32"
    quantization: str = "none"
    context_length: int = 0
    estimated_model_memory_gb: float = 0.0
    estimated_kv_cache_gb: float = 0.0
    estimated_runtime_memory_gb: float = 0.0
    recommended_ram_gb: float = 0.0
    recommended_vram_gb: float = 0.0
    is_estimate: bool = True


@dataclass(frozen=True)
class RuntimeInfo:
    """Complete runtime information snapshot."""

    python: PythonInfo = field(default_factory=PythonInfo)
    environment: EnvironmentInfo = field(default_factory=EnvironmentInfo)
    pytorch: PyTorchEnvInfo = field(default_factory=PyTorchEnvInfo)
    selected_device: DeviceInfo = field(default_factory=DeviceInfo)
    memory: MemoryInfo = field(default_factory=MemoryInfo)
    precision: PrecisionInfo = field(default_factory=PrecisionInfo)
    backend_status: BackendStatus = BackendStatus.NOT_AVAILABLE
    backend_name: str = "None"
    error_message: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "python": {
                "version": self.python.version,
                "executable": self.python.executable,
                "implementation": self.python.implementation,
                "architecture": self.python.architecture,
            },
            "environment": {
                "type": self.environment.env_type.value,
                "name": self.environment.env_name,
                "conda_env_name": self.environment.conda_env_name,
            },
            "pytorch": {
                "installed": self.pytorch.installed,
                "version": self.pytorch.version,
                "cuda_available": self.pytorch.cuda_available,
                "cuda_version": self.pytorch.cuda_version,
                "rocm_available": self.pytorch.rocm_available,
                "mps_available": self.pytorch.mps_available,
                "device_count": self.pytorch.device_count,
                "devices": [
                    {
                        "type": d.device_type.value,
                        "name": d.name,
                        "total_memory_gb": d.total_memory_gb,
                        "is_available": d.is_available,
                    }
                    for d in self.pytorch.devices
                ],
            },
            "selected_device": {
                "type": self.selected_device.device_type.value,
                "name": self.selected_device.name,
                "total_memory_gb": self.selected_device.total_memory_gb,
                "is_available": self.selected_device.is_available,
            },
            "memory": {
                "total_gb": self.memory.total_gb,
                "available_gb": self.memory.available_gb,
                "used_gb": self.memory.used_gb,
                "allocated_gb": self.memory.allocated_gb,
                "reserved_gb": self.memory.reserved_gb,
            },
            "precision": {
                "float32_supported": self.precision.float32_supported,
                "float16_supported": self.precision.float16_supported,
                "bfloat16_supported": self.precision.bfloat16_supported,
                "default_dtype": self.precision.default_dtype,
            },
            "backend_status": self.backend_status.value,
            "backend_name": self.backend_name,
            "error_message": self.error_message,
        }
