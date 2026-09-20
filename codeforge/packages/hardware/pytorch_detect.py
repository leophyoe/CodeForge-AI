"""PyTorch environment detection."""

from __future__ import annotations

from typing import Optional

from .models import PyTorchInfo


def detect_pytorch() -> PyTorchInfo:
    """Detect PyTorch installation and capabilities.

    Returns:
        PyTorchInfo with version, CUDA, cuDNN, and MPS info.
    """
    try:
        import torch

        version = torch.__version__
        cuda_version: Optional[str] = None
        cudnn_version: Optional[str] = None

        if torch.cuda.is_available():
            cuda_version = torch.version.cuda

        if hasattr(torch.backends, "cudnn") and torch.backends.cudnn.is_available():
            cudnn_version = str(torch.backends.cudnn.version())

        hip_version: Optional[str] = None
        if hasattr(torch.version, "hip") and torch.version.hip is not None:
            hip_version = torch.version.hip

        mps_available = False
        if hasattr(torch.backends, "mps"):
            try:
                mps_available = torch.backends.mps.is_available()
            except Exception:
                mps_available = False

        return PyTorchInfo(
            installed=True,
            version=version,
            cuda_version=cuda_version,
            cudnn_version=cudnn_version,
            hip_version=hip_version,
            mps_available=mps_available,
        )
    except ImportError:
        return PyTorchInfo(installed=False)
    except Exception:
        return PyTorchInfo(installed=False)
