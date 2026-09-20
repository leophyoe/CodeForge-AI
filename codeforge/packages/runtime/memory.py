"""Memory detection and management for CodeForge AI."""

from __future__ import annotations

import logging

from .models import DeviceType, MemoryInfo

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages system and GPU memory detection."""

    def get_system_memory(self) -> MemoryInfo:
        """Get system RAM information."""
        try:
            import psutil

            mem = psutil.virtual_memory()
            return MemoryInfo(
                total_gb=round(mem.total / (1024**3), 2),
                available_gb=round(mem.available / (1024**3), 2),
                used_gb=round(mem.used / (1024**3), 2),
                usage_percent=round(mem.percent, 1),
            )
        except Exception as e:
            logger.debug("Failed to get system memory: %s", e)
            return MemoryInfo()

    def get_gpu_memory(self, device_index: int = 0) -> MemoryInfo:
        """Get GPU memory information for a specific CUDA device."""
        try:
            import torch  # noqa: F401
        except ImportError:
            return MemoryInfo()

        import torch

        try:
            if not torch.cuda.is_available():
                return MemoryInfo()

            free_mem, total_mem = torch.cuda.mem_get_info(device_index)
            allocated = torch.cuda.memory_allocated(device_index)
            reserved = torch.cuda.memory_reserved(device_index)

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
                    round((total_gb - free_gb) / total_gb * 100, 1)
                    if total_gb > 0
                    else 0.0
                ),
            )
        except Exception as e:
            logger.debug("Failed to get GPU memory: %s", e)
            return MemoryInfo()

    def get_memory_for_device(
        self, device_type: DeviceType, device_index: int = 0
    ) -> MemoryInfo:
        """Get memory info for the specified device type."""
        if device_type == DeviceType.CUDA:
            return self.get_gpu_memory(device_index)
        if device_type == DeviceType.MPS:
            # MPS uses unified memory, no per-device API
            return MemoryInfo()
        return self.get_system_memory()
