"""GPU detection module.

Supports:
- NVIDIA GPU via nvidia-ml-py (pynvml)
- NVIDIA GPU via PyTorch CUDA
- AMD GPU via ROCm (rocminfo)
- Apple Silicon MPS via PyTorch
- Fallback detection methods
"""

from __future__ import annotations

import platform
import re
import subprocess
from dataclasses import dataclass
from typing import Optional

from .models import GPUInfo


def detect_gpu() -> GPUInfo:
    """Detect GPU information using multiple methods.

    Tries detection in order:
    1. nvidia-ml-py (pynvml) for NVIDIA GPUs
    2. PyTorch CUDA for NVIDIA GPUs
    3. rocminfo for AMD GPUs
    4. PyTorch MPS for Apple Silicon
    5. Returns empty GPUInfo if nothing detected

    Returns:
        GPUInfo with detected GPU details.
    """
    system = platform.system()

    # Try NVIDIA detection first (Linux, Windows)
    if system in ("Linux", "Windows"):
        nvidia_info = _detect_nvidia_pynvml()
        if nvidia_info is not None:
            return nvidia_info

        nvidia_info = _detect_nvidia_torch()
        if nvidia_info is not None:
            return nvidia_info

        # Try AMD ROCm on Linux
        if system == "Linux":
            amd_info = _detect_amd_rocm()
            if amd_info is not None:
                return amd_info

    # Try Apple Silicon MPS
    if system == "Darwin":
        mps_info = _detect_apple_mps()
        if mps_info is not None:
            return mps_info

    return GPUInfo()


def _detect_nvidia_pynvml() -> Optional[GPUInfo]:
    """Detect NVIDIA GPU using nvidia-ml-py (pynvml)."""
    try:
        import pynvml

        pynvml.nvmlInit()
        driver_version = pynvml.nvmlSystemGetDriverVersion()
        if isinstance(driver_version, bytes):
            driver_version = driver_version.decode("utf-8")

        device_count = pynvml.nvmlDeviceGetCount()

        if device_count == 0:
            pynvml.nvmlShutdown()
            return None

        # Use first GPU (primary)
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        name = pynvml.nvmlDeviceGetName(handle)
        if isinstance(name, bytes):
            name = name.decode("utf-8")

        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        vram_total = mem_info.total / (1024**3)
        vram_free = mem_info.free / (1024**3)

        # Try to get CUDA version
        cuda_version = None
        try:
            cuda_ver = pynvml.nvmlSystemGetCudaDriverVersion_v2()
            major = cuda_ver // 1000
            minor = (cuda_ver % 1000) // 10
            cuda_version = f"{major}.{minor}"
        except Exception:
            pass

        # Try to get temperature
        temperature = None
        try:
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            temperature = float(temp)
        except Exception:
            pass

        # Try to get utilization
        utilization = None
        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            utilization = float(util.gpu)
        except Exception:
            pass

        pynvml.nvmlShutdown()

        # Check if PyTorch CUDA is also available
        cuda_available = _check_torch_cuda()
        torch_cuda_version = _get_torch_cuda_version()

        return GPUInfo(
            name=name,
            vendor="NVIDIA",
            vram_gb=round(vram_total, 2),
            vram_free_gb=round(vram_free, 2),
            driver_version=driver_version,
            cuda_version=cuda_version or torch_cuda_version,
            cuda_available=cuda_available,
            rocm_available=False,
            mps_available=False,
            temperature=temperature,
            utilization=utilization,
        )
    except Exception:
        return None


def _detect_nvidia_torch() -> Optional[GPUInfo]:
    """Detect NVIDIA GPU via PyTorch CUDA."""
    try:
        import torch

        if not torch.cuda.is_available():
            return None

        name = torch.cuda.get_device_name(0)
        props = torch.cuda.get_device_properties(0)
        vram_total = props.total_mem / (1024**3)

        # Get free memory
        free_mem, total_mem = torch.cuda.mem_get_info(0)
        vram_free = free_mem / (1024**3)

        cuda_version = torch.version.cuda
        driver_version = torch.version.cuda  # Approximate

        return GPUInfo(
            name=name,
            vendor="NVIDIA",
            vram_gb=round(vram_total, 2),
            vram_free_gb=round(vram_free, 2),
            driver_version=None,
            cuda_version=cuda_version,
            cuda_available=True,
            rocm_available=False,
            mps_available=False,
        )
    except Exception:
        return None


def _detect_amd_rocm() -> Optional[GPUInfo]:
    """Detect AMD GPU using rocminfo."""
    try:
        result = subprocess.run(
            ["rocminfo"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None

        output = result.stdout

        # Parse GPU name from rocminfo
        name_match = re.search(r"Marketing Name:\s+(.+)", output)
        name = name_match.group(1).strip() if name_match else "AMD GPU"

        # Check for VRAM info
        vram_match = re.search(
            r"Memory Size:\s+([\d.]+)\s*(GB|MB|TB)", output, re.IGNORECASE
        )
        vram_gb: Optional[float] = None
        if vram_match:
            size = float(vram_match.group(1))
            unit = vram_match.group(2).upper()
            if unit == "MB":
                vram_gb = size / 1024
            elif unit == "GB":
                vram_gb = size
            elif unit == "TB":
                vram_gb = size * 1024

        # Check if ROCm is actually functional
        rocm_available = _check_rocm_functional()

        return GPUInfo(
            name=name,
            vendor="AMD",
            vram_gb=round(vram_gb, 2) if vram_gb else None,
            vram_free_gb=None,
            driver_version=None,
            cuda_version=None,
            cuda_available=False,
            rocm_available=rocm_available,
            mps_available=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _detect_apple_mps() -> Optional[GPUInfo]:
    """Detect Apple Silicon GPU via PyTorch MPS."""
    try:
        import torch

        if not hasattr(torch.backends, "mps"):
            return None

        if not torch.backends.mps.is_available():
            return None

        # Apple Silicon GPU - no VRAM info available via MPS API
        return GPUInfo(
            name="Apple Silicon GPU",
            vendor="Apple",
            vram_gb=None,  # Unified memory, not reported per-device
            vram_free_gb=None,
            driver_version=None,
            cuda_version=None,
            cuda_available=False,
            rocm_available=False,
            mps_available=True,
        )
    except Exception:
        return None


def _check_torch_cuda() -> bool:
    """Check if PyTorch CUDA is available."""
    try:
        import torch

        return torch.cuda.is_available()  # type: ignore[no-any-return]
    except Exception:
        return False


def _get_torch_cuda_version() -> Optional[str]:
    """Get CUDA version from PyTorch."""
    try:
        import torch

        if torch.cuda.is_available():
            return torch.version.cuda  # type: ignore[no-any-return]
    except Exception:
        pass
    return None


def _check_rocm_functional() -> bool:
    """Check if ROCm is actually functional (not just installed)."""
    try:
        import torch

        if hasattr(torch, "hip"):
            return torch.cuda.is_available()  # type: ignore[no-any-return]
    except Exception:
        pass

    # Check if rocm-smi is available and working
    try:
        result = subprocess.run(
            ["rocm-smi", "--showuse"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
