"""OS and system information detection."""

from __future__ import annotations

import platform
import socket
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class SystemInfo:
    """Basic system information."""

    os_name: str
    os_version: str
    os_release: str
    architecture: str
    hostname: str
    python_version: str
    kernel: str


def detect_system() -> SystemInfo:
    """Detect operating system and system information.

    Returns:
        SystemInfo with OS, architecture, and Python details.
    """
    system = platform.system()
    machine = platform.machine()

    os_name = system
    os_version = platform.version()
    os_release = platform.release()

    # Normalize architecture
    arch = machine
    if system == "Linux":
        arch = _detect_linux_arch()
    elif system == "Darwin":
        arch = _detect_macos_arch()
    elif system == "Windows":
        arch = platform.machine()

    python_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    try:
        hostname = socket.gethostname()
    except Exception:
        hostname = "unknown"

    kernel = platform.release()

    return SystemInfo(
        os_name=os_name,
        os_version=os_version,
        os_release=os_release,
        architecture=arch,
        hostname=hostname,
        python_version=python_ver,
        kernel=kernel,
    )


def _detect_linux_arch() -> str:
    """Detect Linux architecture with proper naming."""
    machine = platform.machine()
    arch_map = {
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "aarch64": "aarch64",
        "arm64": "aarch64",
        "armv7l": "armv7l",
        "armv6l": "armv6l",
        "i686": "i686",
        "i386": "i686",
    }
    return arch_map.get(machine, machine)


def _detect_macos_arch() -> str:
    """Detect macOS architecture (Intel vs Apple Silicon)."""
    machine = platform.machine()
    if machine == "arm64":
        return "arm64 (Apple Silicon)"
    if machine == "x86_64":
        return "x86_64 (Intel)"
    return machine
