"""Hardware information data models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CPUInfo:
    """CPU information."""

    model: str = "Unknown"
    cores_physical: int = 0
    cores_logical: int = 0
    threads: int = 0
    architecture: str = "Unknown"
    max_frequency_mhz: float | None = None
    min_frequency_mhz: float | None = None
    current_frequency_mhz: float | None = None
    l2_cache_kb: int | None = None
    l3_cache_kb: int | None = None
    flags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RAMInfo:
    """RAM information."""

    total_gb: float = 0.0
    available_gb: float = 0.0
    used_gb: float = 0.0
    usage_percent: float = 0.0


@dataclass(frozen=True)
class GPUInfo:
    """GPU information."""

    name: str | None = None
    vendor: str | None = None
    vram_gb: float | None = None
    vram_free_gb: float | None = None
    driver_version: str | None = None
    cuda_version: str | None = None
    cuda_available: bool = False
    rocm_available: bool = False
    mps_available: bool = False
    temperature: float | None = None
    utilization: float | None = None


@dataclass(frozen=True)
class DiskInfo:
    """Disk information."""

    total_gb: float = 0.0
    free_gb: float = 0.0
    used_gb: float = 0.0
    usage_percent: float = 0.0


@dataclass(frozen=True)
class PyTorchInfo:
    """PyTorch environment information."""

    installed: bool = False
    version: str | None = None
    cuda_version: str | None = None
    cudnn_version: str | None = None
    hip_version: str | None = None
    mps_available: bool = False


@dataclass(frozen=True)
class HardwareInfo:
    """Complete hardware information snapshot."""

    os_name: str = "Unknown"
    os_version: str = "Unknown"
    os_release: str = "Unknown"
    architecture: str = "Unknown"
    hostname: str = "Unknown"
    python_version: str = "Unknown"

    cpu: CPUInfo = field(default_factory=CPUInfo)
    ram: RAMInfo = field(default_factory=RAMInfo)
    gpu: GPUInfo = field(default_factory=GPUInfo)
    disk: DiskInfo = field(default_factory=DiskInfo)
    pytorch: PyTorchInfo = field(default_factory=PyTorchInfo)

    # Convenience accessors for backward compatibility
    @property
    def cpu_model(self) -> str:
        return self.cpu.model

    @property
    def cpu_cores_physical(self) -> int:
        return self.cpu.cores_physical

    @property
    def cpu_cores_logical(self) -> int:
        return self.cpu.cores_logical

    @property
    def cpu_threads(self) -> int:
        return self.cpu.threads

    @property
    def ram_total_gb(self) -> float:
        return self.ram.total_gb

    @property
    def ram_available_gb(self) -> float:
        return self.ram.available_gb

    @property
    def gpu_name(self) -> str | None:
        return self.gpu.name

    @property
    def gpu_vendor(self) -> str | None:
        return self.gpu.vendor

    @property
    def vram_gb(self) -> float | None:
        return self.gpu.vram_gb

    @property
    def cuda_available(self) -> bool:
        return self.gpu.cuda_available

    @property
    def rocm_available(self) -> bool:
        return self.gpu.rocm_available

    @property
    def mps_available(self) -> bool:
        return self.gpu.mps_available

    @property
    def pytorch_version(self) -> str | None:
        return self.pytorch.version

    @property
    def pytorch_cuda_version(self) -> str | None:
        return self.pytorch.cuda_version

    @property
    def disk_total_gb(self) -> float:
        return self.disk.total_gb

    @property
    def disk_free_gb(self) -> float:
        return self.disk.free_gb

    @property
    def acceleration_backend(self) -> str:
        """Determine the best available acceleration backend."""
        if self.gpu.cuda_available:
            return "CUDA"
        if self.gpu.rocm_available:
            return "ROCm"
        if self.gpu.mps_available:
            return "MPS"
        return "CPU"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "os": self.os_name,
            "os_version": self.os_version,
            "os_release": self.os_release,
            "architecture": self.architecture,
            "hostname": self.hostname,
            "python_version": self.python_version,
            "cpu": {
                "model": self.cpu.model,
                "cores_physical": self.cpu.cores_physical,
                "cores_logical": self.cpu.cores_logical,
                "threads": self.cpu.threads,
                "architecture": self.cpu.architecture,
                "max_frequency_mhz": self.cpu.max_frequency_mhz,
                "min_frequency_mhz": self.cpu.min_frequency_mhz,
                "current_frequency_mhz": self.cpu.current_frequency_mhz,
                "l2_cache_kb": self.cpu.l2_cache_kb,
                "l3_cache_kb": self.cpu.l3_cache_kb,
                "flags": self.cpu.flags,
            },
            "ram": {
                "total_gb": self.ram.total_gb,
                "available_gb": self.ram.available_gb,
                "used_gb": self.ram.used_gb,
                "usage_percent": self.ram.usage_percent,
            },
            "gpu": {
                "name": self.gpu.name,
                "vendor": self.gpu.vendor,
                "vram_gb": self.gpu.vram_gb,
                "vram_free_gb": self.gpu.vram_free_gb,
                "driver_version": self.gpu.driver_version,
                "cuda_version": self.gpu.cuda_version,
                "cuda_available": self.gpu.cuda_available,
                "rocm_available": self.gpu.rocm_available,
                "mps_available": self.gpu.mps_available,
                "temperature": self.gpu.temperature,
                "utilization": self.gpu.utilization,
            },
            "disk": {
                "total_gb": self.disk.total_gb,
                "free_gb": self.disk.free_gb,
                "used_gb": self.disk.used_gb,
                "usage_percent": self.disk.usage_percent,
            },
            "pytorch": {
                "installed": self.pytorch.installed,
                "version": self.pytorch.version,
                "cuda_version": self.pytorch.cuda_version,
                "cudnn_version": self.pytorch.cudnn_version,
                "hip_version": self.pytorch.hip_version,
                "mps_available": self.pytorch.mps_available,
            },
            "acceleration_backend": self.acceleration_backend,
        }
