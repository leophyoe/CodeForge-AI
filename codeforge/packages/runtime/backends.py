"""Runtime backend abstraction for CodeForge AI."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from .models import BackendStatus, DeviceInfo, DeviceType, MemoryInfo

logger = logging.getLogger(__name__)


class RuntimeBackend(ABC):
    """Abstract base class for runtime backends."""

    @abstractmethod
    def initialize(self) -> BackendStatus:
        """Initialize the backend. Returns status."""

    @abstractmethod
    def shutdown(self) -> None:
        """Shutdown the backend and release resources."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is available."""

    @abstractmethod
    def get_device(self) -> DeviceInfo:
        """Get the device info for this backend."""

    @abstractmethod
    def get_device_info(self) -> dict:
        """Get detailed device information."""

    @abstractmethod
    def run_tensor_test(self) -> dict:
        """Run a tensor smoke test on this backend."""

    @abstractmethod
    def get_memory_info(self) -> MemoryInfo:
        """Get memory information for this backend."""


class CPUBackend(RuntimeBackend):
    """CPU-only runtime backend."""

    def __init__(self) -> None:
        self._initialized = False

    def initialize(self) -> BackendStatus:
        self._initialized = True
        logger.info("CPU backend initialized")
        return BackendStatus.READY

    def shutdown(self) -> None:
        self._initialized = False
        logger.info("CPU backend shutdown")

    def is_available(self) -> bool:
        return True

    def get_device(self) -> DeviceInfo:
        return DeviceInfo(
            device_type=DeviceType.CPU,
            device_index=0,
            name="CPU",
            is_available=True,
        )

    def get_device_info(self) -> dict:
        return {"type": "cpu", "name": "CPU", "available": True}

    def run_tensor_test(self) -> dict:
        try:
            import torch

            t1 = torch.randn(2, 3)
            t2 = torch.randn(2, 3)
            result = (t1 + t2).mean().item()
            del t1, t2
            return {"success": True, "device": "cpu", "result": result}
        except ImportError:
            return {"success": False, "error": "PyTorch not installed", "device": "cpu"}
        except Exception as e:
            return {"success": False, "error": str(e), "device": "cpu"}

    def get_memory_info(self) -> MemoryInfo:
        try:
            import psutil

            mem = psutil.virtual_memory()
            return MemoryInfo(
                total_gb=round(mem.total / (1024**3), 2),
                available_gb=round(mem.available / (1024**3), 2),
                used_gb=round(mem.used / (1024**3), 2),
                usage_percent=round(mem.percent, 1),
            )
        except Exception:
            return MemoryInfo()


class CUDABackend(RuntimeBackend):
    """NVIDIA CUDA runtime backend."""

    def __init__(self, device_index: int = 0) -> None:
        self._device_index = device_index
        self._initialized = False

    def initialize(self) -> BackendStatus:
        try:
            import torch  # noqa: F401
        except ImportError:
            return BackendStatus.NOT_INSTALLED

        import torch

        if not torch.cuda.is_available():
            return BackendStatus.NOT_AVAILABLE

        try:
            # Warm up the device
            _ = torch.cuda.current_device()
            self._initialized = True
            logger.info("CUDA backend initialized on device %d", self._device_index)
            return BackendStatus.READY
        except Exception as e:
            logger.error("CUDA backend initialization failed: %s", e)
            return BackendStatus.ERROR

    def shutdown(self) -> None:
        self._initialized = False
        logger.info("CUDA backend shutdown")

    def is_available(self) -> bool:
        try:
            import torch

            result: bool = torch.cuda.is_available()
            return result
        except ImportError:
            return False

    def get_device(self) -> DeviceInfo:
        try:
            import torch

            if torch.cuda.is_available():
                props = torch.cuda.get_device_properties(self._device_index)
                total_mem = props.total_mem / (1024**3)
                name = props.name
                if isinstance(name, bytes):
                    name = name.decode("utf-8")
                return DeviceInfo(
                    device_type=DeviceType.CUDA,
                    device_index=self._device_index,
                    name=name,
                    total_memory_gb=round(total_mem, 2),
                    compute_capability=f"{props.major}.{props.minor}",
                    is_available=True,
                )
        except Exception:
            pass

        return DeviceInfo(
            device_type=DeviceType.CUDA,
            device_index=self._device_index,
            name="CUDA (unavailable)",
            is_available=False,
        )

    def get_device_info(self) -> dict:
        dev = self.get_device()
        return {
            "type": "cuda",
            "index": self._device_index,
            "name": dev.name,
            "total_memory_gb": dev.total_memory_gb,
            "compute_capability": dev.compute_capability,
            "available": dev.is_available,
        }

    def run_tensor_test(self) -> dict:
        try:
            import torch

            if not torch.cuda.is_available():
                return {"success": False, "error": "CUDA not available", "device": "cuda"}

            device = torch.device(f"cuda:{self._device_index}")
            t1 = torch.randn(2, 3, device=device)
            t2 = torch.randn(2, 3, device=device)
            result = (t1 + t2).mean().item()
            del t1, t2
            torch.cuda.empty_cache()
            return {"success": True, "device": f"cuda:{self._device_index}", "result": result}
        except ImportError:
            return {"success": False, "error": "PyTorch not installed", "device": "cuda"}
        except Exception as e:
            return {"success": False, "error": str(e), "device": "cuda"}

    def get_memory_info(self) -> MemoryInfo:
        try:
            import torch

            if not torch.cuda.is_available():
                return MemoryInfo()

            free_mem, total_mem = torch.cuda.mem_get_info(self._device_index)
            allocated = torch.cuda.memory_allocated(self._device_index)
            reserved = torch.cuda.memory_reserved(self._device_index)

            total_gb = total_mem / (1024**3)
            free_gb = free_mem / (1024**3)
            allocated_gb = allocated / (1024**3)
            reserved_gb = reserved / (1024**3)

            return MemoryInfo(
                total_gb=round(total_gb, 2),
                available_gb=round(free_gb, 2),
                used_gb=round(total_gb - free_gb, 2),
                allocated_gb=round(allocated_gb, 2),
                reserved_gb=round(reserved_gb, 2),
                usage_percent=(
                    round((total_gb - free_gb) / total_gb * 100, 1) if total_gb > 0 else 0.0
                ),
            )
        except Exception:
            return MemoryInfo()


class MPSBackend(RuntimeBackend):
    """Apple Silicon MPS runtime backend."""

    def __init__(self) -> None:
        self._initialized = False

    def initialize(self) -> BackendStatus:
        try:
            import torch  # noqa: F401
        except ImportError:
            return BackendStatus.NOT_INSTALLED

        import torch

        if not hasattr(torch.backends, "mps"):
            return BackendStatus.NOT_AVAILABLE

        if not torch.backends.mps.is_available():
            return BackendStatus.NOT_AVAILABLE

        try:
            device = torch.device("mps")
            _ = torch.zeros(1, device=device)
            self._initialized = True
            logger.info("MPS backend initialized")
            return BackendStatus.READY
        except Exception as e:
            logger.error("MPS backend initialization failed: %s", e)
            return BackendStatus.ERROR

    def shutdown(self) -> None:
        self._initialized = False
        logger.info("MPS backend shutdown")

    def is_available(self) -> bool:
        try:
            import torch

            if hasattr(torch.backends, "mps"):
                result: bool = torch.backends.mps.is_available()
                return result
        except ImportError:
            pass
        return False

    def get_device(self) -> DeviceInfo:
        if self.is_available():
            return DeviceInfo(
                device_type=DeviceType.MPS,
                device_index=0,
                name="Apple Silicon GPU (MPS)",
                is_available=True,
            )
        return DeviceInfo(
            device_type=DeviceType.MPS,
            device_index=0,
            name="MPS (unavailable)",
            is_available=False,
        )

    def get_device_info(self) -> dict:
        return {"type": "mps", "name": "Apple Silicon GPU (MPS)", "available": self.is_available()}

    def run_tensor_test(self) -> dict:
        try:
            import torch

            if not hasattr(torch.backends, "mps") or not torch.backends.mps.is_available():
                return {"success": False, "error": "MPS not available", "device": "mps"}

            device = torch.device("mps")
            t1 = torch.randn(2, 3, device=device)
            t2 = torch.randn(2, 3, device=device)
            result = (t1 + t2).mean().item()
            del t1, t2
            return {"success": True, "device": "mps", "result": result}
        except ImportError:
            return {"success": False, "error": "PyTorch not installed", "device": "mps"}
        except Exception as e:
            return {"success": False, "error": str(e), "device": "mps"}

    def get_memory_info(self) -> MemoryInfo:
        # MPS does not expose memory info through PyTorch API
        return MemoryInfo()
