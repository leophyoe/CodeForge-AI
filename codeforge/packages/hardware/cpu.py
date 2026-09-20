"""CPU detection module."""

from __future__ import annotations

import platform

from .models import CPUInfo


def detect_cpu() -> CPUInfo:
    """Detect CPU information.

    Uses multiple methods for cross-platform compatibility:
    - py-cpuinfo (preferred)
    - psutil (fallback)
    - platform module (last resort)

    Returns:
        CPUInfo with detected CPU details.
    """
    info = _detect_with_cpuinfo()
    if info is not None:
        return info

    info = _detect_with_psutil()
    if info is not None:
        return info

    return _detect_with_platform()


def _detect_with_cpuinfo() -> CPUInfo | None:
    """Detect CPU info using py-cpuinfo library."""
    try:
        import cpuinfo

        data = cpuinfo.get_cpu_info()

        flags = data.get("flags", [])
        if isinstance(flags, str):
            flags = flags.split()

        l2 = data.get("l2_cache_size")
        l3 = data.get("l3_cache_size")

        # Convert bytes to KB if present
        l2_kb = int(l2 // 1024) if l2 and l2 > 0 else None
        l3_kb = int(l3 // 1024) if l3 and l3 > 0 else None

        freq_max = data.get("hz_advertised_fmax")
        freq_min = data.get("hz_advertised_fmin")
        freq_current = data.get("hz_actual_fmax")

        # Convert Hz to MHz
        freq_max_mhz = float(freq_max / 1_000_000) if freq_max else None
        freq_min_mhz = float(freq_min / 1_000_000) if freq_min else None
        freq_current_mhz = float(freq_current / 1_000_000) if freq_current else None

        return CPUInfo(
            model=data.get("brand_raw", "Unknown"),
            cores_physical=data.get("physical_cores") or 0,
            cores_logical=data.get("count") or 0,
            threads=data.get("count") or 0,
            architecture=data.get("arch_string_raw", platform.machine()),
            max_frequency_mhz=freq_max_mhz,
            min_frequency_mhz=freq_min_mhz,
            current_frequency_mhz=freq_current_mhz,
            l2_cache_kb=l2_kb,
            l3_cache_kb=l3_kb,
            flags=flags[:50],  # Limit flags to prevent huge strings
        )
    except Exception:
        return None


def _detect_with_psutil() -> CPUInfo | None:
    """Detect CPU info using psutil."""
    try:
        import psutil

        cores_physical = psutil.cpu_count(logical=False) or 0
        cores_logical = psutil.cpu_count(logical=True) or 0
        freq = psutil.cpu_freq()

        # Try to get CPU model from /proc/cpuinfo on Linux
        model = _get_cpu_model_linux()

        return CPUInfo(
            model=model,
            cores_physical=cores_physical,
            cores_logical=cores_logical,
            threads=cores_logical,
            architecture=platform.machine(),
            max_frequency_mhz=freq.max if freq else None,
            min_frequency_mhz=freq.min if freq else None,
            current_frequency_mhz=freq.current if freq else None,
        )
    except Exception:
        return None


def _detect_with_platform() -> CPUInfo:
    """Detect CPU info using only the platform module (minimal)."""
    model = _get_cpu_model_linux() or platform.processor() or "Unknown"
    cores = _get_cpu_count_platform()

    return CPUInfo(
        model=model,
        cores_physical=cores,
        cores_logical=cores,
        threads=cores,
        architecture=platform.machine(),
    )


def _get_cpu_model_linux() -> str:
    """Read CPU model from /proc/cpuinfo on Linux."""
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except (FileNotFoundError, PermissionError, IndexError):
        pass
    return "Unknown"


def _get_cpu_count_platform() -> int:
    """Get CPU count using os module as last resort."""
    try:
        import os

        return os.cpu_count() or 1
    except Exception:
        return 1
