"""RAM detection module."""

from __future__ import annotations

from .models import RAMInfo


def detect_ram() -> RAMInfo:
    """Detect RAM information.

    Uses psutil for cross-platform RAM detection.

    Returns:
        RAMInfo with total, available, and used memory.
    """
    try:
        import psutil

        mem = psutil.virtual_memory()
        total_gb = mem.total / (1024**3)
        available_gb = mem.available / (1024**3)
        used_gb = mem.used / (1024**3)

        return RAMInfo(
            total_gb=round(total_gb, 2),
            available_gb=round(available_gb, 2),
            used_gb=round(used_gb, 2),
            usage_percent=round(mem.percent, 1),
        )
    except Exception:
        return _detect_ram_fallback()


def _detect_ram_fallback() -> RAMInfo:
    """Fallback RAM detection using platform-specific methods."""
    import platform
    import struct

    system = platform.system()

    if system == "Linux":
        return _detect_ram_linux()
    elif system == "Windows":
        return _detect_ram_windows()
    elif system == "Darwin":
        return _detect_ram_macos()

    return RAMInfo()


def _detect_ram_linux() -> RAMInfo:
    """Read RAM info from /proc/meminfo on Linux."""
    try:
        meminfo: dict[str, int] = {}
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val_parts = parts[1].strip().split()
                    if val_parts:
                        # Values are in kB
                        meminfo[key] = int(val_parts[0])

        total_kb = meminfo.get("MemTotal", 0)
        available_kb = meminfo.get("MemAvailable", 0)
        free_kb = meminfo.get("MemFree", 0)

        # If MemAvailable isn't present (older kernels), estimate it
        if available_kb == 0:
            buffers_kb = meminfo.get("Buffers", 0)
            cached_kb = meminfo.get("Cached", 0)
            sreclaimable_kb = meminfo.get("SReclaimable", 0)
            available_kb = free_kb + buffers_kb + cached_kb + sreclaimable_kb

        total_gb = total_kb / (1024 * 1024)
        available_gb = available_kb / (1024 * 1024)
        used_gb = total_gb - available_gb
        usage = (used_gb / total_gb * 100) if total_gb > 0 else 0.0

        return RAMInfo(
            total_gb=round(total_gb, 2),
            available_gb=round(available_gb, 2),
            used_gb=round(used_gb, 2),
            usage_percent=round(usage, 1),
        )
    except Exception:
        return RAMInfo()


def _detect_ram_windows() -> RAMInfo:
    """Detect RAM on Windows using ctypes."""
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        c_ulonglong = ctypes.c_ulonglong

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", c_ulonglong),
                ("ullAvailPhys", c_ulonglong),
                ("ullTotalPageFile", c_ulonglong),
                ("ullAvailPageFile", c_ulonglong),
                ("ullTotalVirtual", c_ulonglong),
                ("ullAvailVirtual", c_ulonglong),
                ("ullAvailExtendedVirtual", c_ulonglong),
            ]

        mem = MEMORYSTATUSEX()
        mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))

        total_gb = mem.ullTotalPhys / (1024**3)
        available_gb = mem.ullAvailPhys / (1024**3)
        used_gb = total_gb - available_gb
        usage = (mem.dwMemoryLoad,)

        return RAMInfo(
            total_gb=round(total_gb, 2),
            available_gb=round(available_gb, 2),
            used_gb=round(used_gb, 2),
            usage_percent=float(usage[0]),
        )
    except Exception:
        return RAMInfo()


def _detect_ram_macos() -> RAMInfo:
    """Detect RAM on macOS using sysctl."""
    try:
        import subprocess

        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        total_bytes = int(result.stdout.strip())
        total_gb = total_bytes / (1024**3)

        # Use psutil for the rest if available
        try:
            import psutil

            mem = psutil.virtual_memory()
            available_gb = mem.available / (1024**3)
            used_gb = mem.used / (1024**3)
            usage = mem.percent
        except ImportError:
            available_gb = total_gb * 0.5  # Rough estimate
            used_gb = total_gb - available_gb
            usage = 50.0

        return RAMInfo(
            total_gb=round(total_gb, 2),
            available_gb=round(available_gb, 2),
            used_gb=round(used_gb, 2),
            usage_percent=round(usage, 1),
        )
    except Exception:
        return RAMInfo()
