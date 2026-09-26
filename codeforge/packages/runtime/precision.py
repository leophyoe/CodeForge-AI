"""Precision and dtype management for CodeForge AI."""

from __future__ import annotations

import logging

from .models import DeviceType, PrecisionInfo

logger = logging.getLogger(__name__)


class PrecisionManager:
    """Manages supported precision types and dtype selection."""

    def get_supported_dtypes(self, device_type: DeviceType = DeviceType.CPU) -> PrecisionInfo:
        """Detect supported precision types for a given device."""
        float32 = True
        float16 = False
        bfloat16 = False

        try:
            import torch  # noqa: F401
        except ImportError:
            return PrecisionInfo(
                float32_supported=float32,
                float16_supported=float16,
                bfloat16_supported=bfloat16,
                default_dtype="float32",
            )

        if device_type == DeviceType.CPU:
            float16 = True
            bfloat16 = _check_bfloat16_cpu()
        elif device_type == DeviceType.CUDA:
            float16 = True
            bfloat16 = _check_bfloat16_cuda()
        elif device_type == DeviceType.MPS:
            float16 = True
            bfloat16 = False  # MPS does not support bfloat16

        default = "float32"
        if bfloat16:
            default = "bfloat16"
        elif float16:
            default = "float16"

        return PrecisionInfo(
            float32_supported=float32,
            float16_supported=float16,
            bfloat16_supported=bfloat16,
            default_dtype=default,
        )

    def select_dtype(
        self,
        device_type: DeviceType = DeviceType.CPU,
        preferred: str = "auto",
    ) -> str:
        """Select the best dtype for the given device.

        Args:
            device_type: Target device.
            preferred: Preferred dtype ("auto", "float32", "float16", "bfloat16").

        Returns:
            Selected dtype string.
        """
        if preferred != "auto":
            if self.validate_dtype(preferred, device_type):
                return preferred
            logger.warning(
                "Preferred dtype '%s' not supported on %s, auto-selecting",
                preferred,
                device_type.value,
            )

        info = self.get_supported_dtypes(device_type)
        return info.default_dtype

    def validate_dtype(self, dtype_str: str, device_type: DeviceType = DeviceType.CPU) -> bool:
        """Validate that a dtype is supported on the given device."""
        info = self.get_supported_dtypes(device_type)
        dtype_map = {
            "float32": info.float32_supported,
            "float16": info.float16_supported,
            "bfloat16": info.bfloat16_supported,
        }
        return dtype_map.get(dtype_str, False)


def _check_bfloat16_cpu() -> bool:
    """Check if bfloat16 is supported on CPU."""
    try:
        import torch

        x = torch.tensor([1.0], dtype=torch.bfloat16)
        _ = x.sum().item()
        del x
        return True
    except Exception:
        return False


def _check_bfloat16_cuda() -> bool:
    """Check if bfloat16 is supported on CUDA."""
    try:
        import torch

        if not torch.cuda.is_available():
            return False
        x = torch.tensor([1.0], dtype=torch.bfloat16, device="cuda")
        _ = x.sum().item()
        del x
        return True
    except Exception:
        return False
