"""Device management for PyTorch runtime."""

from __future__ import annotations

import logging
import os

from .models import DeviceInfo, DeviceType

logger = logging.getLogger(__name__)


class DeviceManager:
    """Manages PyTorch device detection, selection, and validation."""

    def __init__(self, preferred_device: str = "auto") -> None:
        self._preferred = preferred_device.lower().strip()
        self._available_devices: list[DeviceInfo] = []
        self._torch_available = False

    def detect_available_devices(self) -> list[DeviceInfo]:
        """Detect all available compute devices."""
        if self._available_devices:
            return self._available_devices

        self._available_devices.append(
            DeviceInfo(
                device_type=DeviceType.CPU,
                device_index=0,
                name="CPU",
                is_available=True,
            )
        )

        try:
            import torch  # noqa: F401
            self._torch_available = True
        except ImportError:
            logger.info("PyTorch not available, only CPU device detected")
            return self._available_devices

        import torch

        # CUDA devices
        try:
            if torch.cuda.is_available():
                for i in range(torch.cuda.device_count()):
                    props = torch.cuda.get_device_properties(i)
                    total_mem = props.total_mem / (1024**3)
                    name = props.name
                    if isinstance(name, bytes):
                        name = name.decode("utf-8")
                    self._available_devices.append(
                        DeviceInfo(
                            device_type=DeviceType.CUDA,
                            device_index=i,
                            name=name,
                            total_memory_gb=round(total_mem, 2),
                            compute_capability=f"{props.major}.{props.minor}",
                            is_available=True,
                        )
                    )
        except Exception as e:
            logger.debug("CUDA device detection failed: %s", e)

        # MPS device
        try:
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                self._available_devices.append(
                    DeviceInfo(
                        device_type=DeviceType.MPS,
                        device_index=0,
                        name="Apple Silicon GPU (MPS)",
                        is_available=True,
                    )
                )
        except Exception as e:
            logger.debug("MPS device detection failed: %s", e)

        return self._available_devices

    def get_default_device(self) -> DeviceInfo:
        """Get the default device based on availability and preferences."""
        devices = self.detect_available_devices()

        env_device = os.environ.get("CODEFORGE_DEVICE", "").lower().strip()
        preferred = env_device or self._preferred

        if preferred and preferred != "auto":
            result = self.validate_device(preferred)
            if result is not None:
                return result
            logger.warning(
                "Configured device '%s' not available, falling back", preferred
            )

        # Auto-select: prefer CUDA > MPS > CPU
        for dtype in [DeviceType.CUDA, DeviceType.MPS, DeviceType.CPU]:
            for dev in devices:
                if dev.device_type == dtype and dev.is_available:
                    return dev

        return DeviceInfo(
            device_type=DeviceType.CPU,
            device_index=0,
            name="CPU",
            is_available=True,
        )

    def validate_device(self, device_str: str) -> DeviceInfo | None:
        """Validate that a device string corresponds to an available device."""
        devices = self.detect_available_devices()
        parsed = _parse_device_string(device_str)

        if parsed is None:
            logger.warning("Invalid device string: %s", device_str)
            return None

        for dev in devices:
            if dev.device_type == parsed[0] and dev.device_index == parsed[1]:
                return dev

        return None

    def select_device(self, device_str: str) -> DeviceInfo:
        """Select a device, raising clear errors if unavailable.

        Args:
            device_str: Device string like "cpu", "cuda", "cuda:0", "mps".

        Returns:
            DeviceInfo for the selected device.

        Raises:
            ValueError: If the device string is invalid or device is unavailable.
        """
        result = self.validate_device(device_str)
        if result is not None:
            return result

        available = self.detect_available_devices()
        available_strs = [
            f"{d.device_type.value}:{d.device_index}" if d.device_index > 0
            else d.device_type.value
            for d in available
        ]

        raise ValueError(
            f"Device '{device_str}' is not available. "
            f"Available devices: {', '.join(available_strs)}"
        )

    def get_device_info(self, device_str: str) -> dict:
        """Get detailed information about a specific device."""
        dev = self.validate_device(device_str)
        if dev is None:
            return {"available": False, "device": device_str}

        return {
            "available": True,
            "type": dev.device_type.value,
            "index": dev.device_index,
            "name": dev.name,
            "total_memory_gb": dev.total_memory_gb,
            "compute_capability": dev.compute_capability,
        }


def _parse_device_string(device_str: str) -> tuple[DeviceType, int] | None:
    """Parse a device string into (DeviceType, index).

    Supported formats:
    - "cpu" -> (CPU, 0)
    - "cuda" -> (CUDA, 0)
    - "cuda:0" -> (CUDA, 0)
    - "cuda:1" -> (CUDA, 1)
    - "mps" -> (MPS, 0)
    """
    device_str = device_str.lower().strip()

    if device_str == "cpu":
        return (DeviceType.CPU, 0)

    if device_str == "mps":
        return (DeviceType.MPS, 0)

    if device_str.startswith("cuda"):
        parts = device_str.split(":")
        if len(parts) == 1:
            return (DeviceType.CUDA, 0)
        if len(parts) == 2:
            try:
                idx = int(parts[1])
                return (DeviceType.CUDA, idx)
            except ValueError:
                return None

    return None
