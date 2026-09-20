"""HardwareManager - Main hardware detection and management interface.

This is the primary entry point for hardware detection in CodeForge AI.
It aggregates information from all hardware detection modules and provides
a unified interface for querying system capabilities.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from .cpu import detect_cpu
from .disk import detect_disk
from .gpu import detect_gpu
from .models import HardwareInfo
from .pytorch_detect import detect_pytorch
from .ram import detect_ram
from .system import detect_system

logger = logging.getLogger(__name__)


class HardwareManager:
    """Manages hardware detection and capability reporting.

    The HardwareManager provides a unified interface for detecting and
    querying system hardware capabilities. It is designed to work across
    Linux, Windows, and macOS without hard-coding platform assumptions.

    Usage:
        manager = HardwareManager()
        info = manager.detect()
        print(info.to_dict())
    """

    def __init__(self, cache_ttl_seconds: int = 30) -> None:
        """Initialize HardwareManager.

        Args:
            cache_ttl_seconds: How long to cache detection results (default 30s).
                Set to 0 to disable caching.
        """
        self._cache_ttl = cache_ttl_seconds
        self._cached_info: Optional[HardwareInfo] = None
        self._cache_timestamp: float = 0.0

    def detect(self, force: bool = False) -> HardwareInfo:
        """Detect all hardware information.

        Results are cached for cache_ttl_seconds to avoid repeated detection.
        Use force=True to bypass the cache.

        Args:
            force: If True, bypass cache and re-detect everything.

        Returns:
            HardwareInfo with complete system hardware details.
        """
        if not force and self._is_cache_valid():
            logger.debug("Returning cached hardware info")
            return self._cached_info  # type: ignore[return-value]

        start_time = time.monotonic()
        logger.info("Starting hardware detection")

        try:
            system_info = detect_system()
            cpu_info = detect_cpu()
            ram_info = detect_ram()
            gpu_info = detect_gpu()
            disk_info = detect_disk()
            pytorch_info = detect_pytorch()

            info = HardwareInfo(
                os_name=system_info.os_name,
                os_version=system_info.os_version,
                os_release=system_info.os_release,
                architecture=system_info.architecture,
                hostname=system_info.hostname,
                python_version=system_info.python_version,
                cpu=cpu_info,
                ram=ram_info,
                gpu=gpu_info,
                disk=disk_info,
                pytorch=pytorch_info,
            )

            elapsed = time.monotonic() - start_time
            logger.info(
                "Hardware detection completed in %.3fs: %s, %s, GPU=%s",
                elapsed,
                info.os_name,
                info.cpu_model,
                info.gpu_name or "none",
            )

            self._cached_info = info
            self._cache_timestamp = time.monotonic()

            return info

        except Exception as e:
            logger.error("Hardware detection failed: %s", e)
            raise

    def get_summary(self) -> dict:
        """Get a human-readable hardware summary.

        Returns:
            Dictionary with key hardware information for display.
        """
        info = self.detect()
        return {
            "system": f"{info.os_name} {info.os_version}",
            "architecture": info.architecture,
            "cpu": info.cpu_model,
            "cores": f"{info.cpu_cores_physical}C/{info.cpu_cores_logical}T",
            "ram": f"{info.ram_total_gb:.1f} GB",
            "gpu": info.gpu_name or "Not detected",
            "vram": f"{info.vram_gb:.1f} GB" if info.vram_gb else "N/A",
            "acceleration": info.acceleration_backend,
            "pytorch": info.pytorch_version or "Not installed",
            "disk_free": f"{info.disk_free_gb:.1f} GB",
        }

    def check_compatibility(self) -> dict:
        """Check system compatibility with CodeForge AI.

        Returns:
            Dictionary with compatibility status and recommendations.
        """
        info = self.detect()
        issues: list[str] = []
        warnings: list[str] = []

        # Check Python version
        parts = info.python_version.split(".")
        py_major, py_minor = int(parts[0]), int(parts[1])
        if py_major < 3 or (py_major == 3 and py_minor < 10):
            issues.append(f"Python {info.python_version} is too old. Need >= 3.10.")

        # Check RAM
        if info.ram_total_gb < 4:
            warnings.append(f"Only {info.ram_total_gb:.1f} GB RAM. 8+ GB recommended.")
        elif info.ram_total_gb < 8:
            warnings.append(f"{info.ram_total_gb:.1f} GB RAM. 16+ GB recommended for large models.")

        # Check disk space
        if info.disk_free_gb < 10:
            warnings.append(f"Only {info.disk_free_gb:.1f} GB free disk space. 50+ GB recommended.")

        # Check GPU
        if not info.cuda_available and not info.rocm_available and not info.mps_available:
            warnings.append("No GPU acceleration detected. Will use CPU-only mode.")

        # Check PyTorch
        if not info.pytorch.installed:
            warnings.append("PyTorch not installed. Install with: pip install torch")

        return {
            "compatible": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "acceleration": info.acceleration_backend,
        }

    def _is_cache_valid(self) -> bool:
        """Check if cached info is still valid."""
        if self._cached_info is None:
            return False
        if self._cache_ttl <= 0:
            return False
        return (time.monotonic() - self._cache_timestamp) < self._cache_ttl

    def invalidate_cache(self) -> None:
        """Manually invalidate the cached hardware info."""
        self._cached_info = None
        self._cache_timestamp = 0.0
