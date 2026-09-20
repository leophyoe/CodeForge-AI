"""PyTorch environment detection and validation."""

from __future__ import annotations

import logging

from .models import DeviceInfo, DeviceType, PyTorchEnvInfo

logger = logging.getLogger(__name__)


def detect_pytorch_environment() -> PyTorchEnvInfo:
    """Detect detailed PyTorch environment information.

    Returns:
        PyTorchEnvInfo with version, device, and capability details.
    """
    try:
        import torch  # noqa: F401
    except ImportError:
        logger.info("PyTorch is not installed")
        return PyTorchEnvInfo(
            installed=False,
            device_count=1,
            devices=[
                DeviceInfo(
                    device_type=DeviceType.CPU,
                    device_index=0,
                    name="CPU",
                    is_available=True,
                )
            ],
        )
    except Exception as e:
        logger.error("Failed to import PyTorch: %s", e)
        return PyTorchEnvInfo(
            installed=False,
            device_count=1,
            devices=[
                DeviceInfo(
                    device_type=DeviceType.CPU,
                    device_index=0,
                    name="CPU",
                    is_available=True,
                )
            ],
        )

    import torch

    version = torch.__version__
    cuda_available = False
    cuda_version: str | None = None
    cudnn_version: str | None = None
    rocm_available = False
    hip_version: str | None = None
    mps_available = False

    # CUDA detection
    try:
        cuda_available = torch.cuda.is_available()
        if cuda_available:
            cuda_version = torch.version.cuda
            if hasattr(torch.backends, "cudnn") and torch.backends.cudnn.is_available():
                cudnn_version = str(torch.backends.cudnn.version())
    except Exception as e:
        logger.debug("CUDA detection failed: %s", e)

    # ROCm/HIP detection
    try:
        if hasattr(torch.version, "hip") and torch.version.hip is not None:
            hip_version = torch.version.hip
            rocm_available = True
    except Exception as e:
        logger.debug("ROCm detection failed: %s", e)

    # MPS detection
    try:
        if hasattr(torch.backends, "mps"):
            mps_available = torch.backends.mps.is_available()
    except Exception as e:
        logger.debug("MPS detection failed: %s", e)

    # Device enumeration
    devices = _enumerate_devices(cuda_available, mps_available)

    device_count = len(devices)
    if device_count == 0:
        devices.append(
            DeviceInfo(
                device_type=DeviceType.CPU,
                device_index=0,
                name="CPU",
                is_available=True,
            )
        )
        device_count = 1

    return PyTorchEnvInfo(
        installed=True,
        version=version,
        cuda_available=cuda_available,
        cuda_version=cuda_version,
        cudnn_version=cudnn_version,
        rocm_available=rocm_available,
        hip_version=hip_version,
        mps_available=mps_available,
        device_count=device_count,
        devices=devices,
    )


def _enumerate_devices(
    cuda_available: bool,
    mps_available: bool,
) -> list[DeviceInfo]:
    """Enumerate available PyTorch devices."""
    devices: list[DeviceInfo] = []

    # CPU is always available
    devices.append(
        DeviceInfo(
            device_type=DeviceType.CPU,
            device_index=0,
            name="CPU",
            is_available=True,
        )
    )

    # CUDA devices
    if cuda_available:
        try:
            import torch

            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                total_mem = props.total_mem / (1024**3)
                name = props.name
                if isinstance(name, bytes):
                    name = name.decode("utf-8")
                compute_cap = f"{props.major}.{props.minor}"

                devices.append(
                    DeviceInfo(
                        device_type=DeviceType.CUDA,
                        device_index=i,
                        name=name,
                        total_memory_gb=round(total_mem, 2),
                        compute_capability=compute_cap,
                        is_available=True,
                    )
                )
        except Exception as e:
            logger.debug("Failed to enumerate CUDA devices: %s", e)

    # MPS device
    if mps_available:
        devices.append(
            DeviceInfo(
                device_type=DeviceType.MPS,
                device_index=0,
                name="Apple Silicon GPU (MPS)",
                is_available=True,
            )
        )

    return devices


def run_tensor_smoke_test(device: str = "cpu") -> dict:
    """Run a minimal PyTorch smoke test.

    Creates a tiny tensor, performs basic math, and verifies the device works.

    Args:
        device: Device string (e.g., "cpu", "cuda:0", "mps").

    Returns:
        Dictionary with test results.
    """
    try:
        import torch  # noqa: F401
    except ImportError:
        return {"success": False, "error": "PyTorch not installed", "device": device}

    import torch

    try:
        # Create tiny tensor
        t1 = torch.randn(2, 3)
        t2 = torch.randn(2, 3)

        # Basic math
        t3 = t1 + t2
        t4 = t1 * t2
        t5 = t1.mean()

        # Verify basic operations
        _ = t3.sum().item()
        _ = t4.sum().item()
        result = t5.item()

        # Move to target device if not CPU
        if device != "cpu":
            try:
                target = torch.device(device)
                t1_dev = t1.to(target)
                t2_dev = t2.to(target)
                t3_dev = t1_dev + t2_dev
                _ = t3_dev.sum().item()
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Device transfer failed: {e}",
                    "device": device,
                }

        # Cleanup
        del t1, t2, t3, t4, t5

        return {
            "success": True,
            "device": device,
            "result": result,
            "message": "Tensor operations completed successfully",
        }

    except Exception as e:
        return {"success": False, "error": str(e), "device": device}
