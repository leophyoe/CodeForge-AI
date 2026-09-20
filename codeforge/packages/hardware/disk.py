"""Disk detection module."""

from __future__ import annotations

from pathlib import Path

from .models import DiskInfo


def detect_disk(path: str | Path | None = None) -> DiskInfo:
    """Detect disk space information.

    Args:
        path: Path to check disk space for. Defaults to current directory.

    Returns:
        DiskInfo with total, free, and used disk space.
    """
    import psutil

    target = Path(path) if path else Path.cwd()

    try:
        usage = psutil.disk_usage(str(target))
        total_gb = usage.total / (1024**3)
        free_gb = usage.free / (1024**3)
        used_gb = usage.used / (1024**3)
        percent = usage.percent

        return DiskInfo(
            total_gb=round(total_gb, 2),
            free_gb=round(free_gb, 2),
            used_gb=round(used_gb, 2),
            usage_percent=round(percent, 1),
        )
    except Exception:
        return DiskInfo()


def detect_disk_per_path(paths: list[str | Path] | None = None) -> dict[str, DiskInfo]:
    """Detect disk space for multiple paths.

    Useful for checking if different mount points have different disk space.

    Args:
        paths: List of paths to check. Defaults to common locations.

    Returns:
        Dictionary mapping path strings to DiskInfo.
    """
    if paths is None:
        paths = [Path.cwd(), Path("/"), Path.home()]

    results: dict[str, DiskInfo] = {}
    seen_devices: set[str] = set()

    for path in paths:
        target = Path(path)
        if not target.exists():
            continue

        try:
            import psutil

            usage = psutil.disk_usage(str(target))
            device_key = str(usage)

            # Skip if we've already seen this device
            if device_key in seen_devices:
                continue
            seen_devices.add(device_key)

            total_gb = usage.total / (1024**3)
            free_gb = usage.free / (1024**3)
            used_gb = usage.used / (1024**3)

            results[str(target)] = DiskInfo(
                total_gb=round(total_gb, 2),
                free_gb=round(free_gb, 2),
                used_gb=round(used_gb, 2),
                usage_percent=round(usage.percent, 1),
            )
        except Exception:
            continue

    return results
