"""Tests for runtime data models."""

from __future__ import annotations

from codeforge.packages.runtime.models import (
    BackendStatus,
    DeviceInfo,
    DeviceType,
    EnvironmentType,
    MemoryInfo,
    ModelMemoryEstimate,
    PrecisionInfo,
    PythonInfo,
    PyTorchEnvInfo,
    RuntimeInfo,
)


class TestDeviceType:
    def test_cpu(self) -> None:
        assert DeviceType.CPU.value == "cpu"

    def test_cuda(self) -> None:
        assert DeviceType.CUDA.value == "cuda"

    def test_mps(self) -> None:
        assert DeviceType.MPS.value == "mps"


class TestEnvironmentType:
    def test_conda(self) -> None:
        assert EnvironmentType.CONDA.value == "conda"

    def test_venv(self) -> None:
        assert EnvironmentType.VENV.value == "venv"

    def test_system(self) -> None:
        assert EnvironmentType.SYSTEM.value == "system"


class TestBackendStatus:
    def test_ready(self) -> None:
        assert BackendStatus.READY.value == "READY"

    def test_not_available(self) -> None:
        assert BackendStatus.NOT_AVAILABLE.value == "NOT_AVAILABLE"

    def test_not_installed(self) -> None:
        assert BackendStatus.NOT_INSTALLED.value == "NOT_INSTALLED"

    def test_error(self) -> None:
        assert BackendStatus.ERROR.value == "ERROR"


class TestPythonInfo:
    def test_defaults(self) -> None:
        info = PythonInfo()
        assert info.version == "Unknown"
        assert info.executable == "Unknown"

    def test_custom(self) -> None:
        info = PythonInfo(version="3.12.0", version_major=3, version_minor=12)
        assert info.version == "3.12.0"
        assert info.version_major == 3


class TestDeviceInfo:
    def test_defaults(self) -> None:
        info = DeviceInfo()
        assert info.device_type == DeviceType.CPU
        assert info.is_available is False

    def test_custom(self) -> None:
        info = DeviceInfo(
            device_type=DeviceType.CUDA,
            device_index=0,
            name="RTX 4090",
            total_memory_gb=24.0,
            is_available=True,
        )
        assert info.device_type == DeviceType.CUDA
        assert info.name == "RTX 4090"
        assert info.total_memory_gb == 24.0


class TestMemoryInfo:
    def test_defaults(self) -> None:
        info = MemoryInfo()
        assert info.total_gb == 0.0
        assert info.allocated_gb is None

    def test_custom(self) -> None:
        info = MemoryInfo(total_gb=24.0, available_gb=20.0, allocated_gb=4.0)
        assert info.total_gb == 24.0
        assert info.allocated_gb == 4.0


class TestRuntimeInfo:
    def test_defaults(self) -> None:
        info = RuntimeInfo()
        assert info.backend_status == BackendStatus.NOT_AVAILABLE
        assert info.backend_name == "None"

    def test_to_dict(self) -> None:
        info = RuntimeInfo()
        d = info.to_dict()
        assert "python" in d
        assert "environment" in d
        assert "pytorch" in d
        assert "selected_device" in d
        assert "memory" in d
        assert "precision" in d
        assert "backend_status" in d

    def test_to_dict_with_device(self) -> None:
        device = DeviceInfo(
            device_type=DeviceType.CUDA,
            device_index=0,
            name="Test GPU",
            total_memory_gb=8.0,
            is_available=True,
        )
        info = RuntimeInfo(selected_device=device)
        d = info.to_dict()
        assert d["selected_device"]["type"] == "cuda"
        assert d["selected_device"]["name"] == "Test GPU"


class TestPrecisionInfo:
    def test_defaults(self) -> None:
        info = PrecisionInfo()
        assert info.float32_supported is True
        assert info.float16_supported is False
        assert info.default_dtype == "float32"


class TestModelMemoryEstimate:
    def test_defaults(self) -> None:
        est = ModelMemoryEstimate()
        assert est.is_estimate is True
        assert est.parameter_count == 0.0

    def test_custom(self) -> None:
        est = ModelMemoryEstimate(
            parameter_count=7_000_000_000,
            dtype="float16",
            recommended_ram_gb=16.0,
        )
        assert est.parameter_count == 7_000_000_000
        assert est.dtype == "float16"


class TestPyTorchEnvInfo:
    def test_not_installed(self) -> None:
        info = PyTorchEnvInfo()
        assert info.installed is False
        assert info.devices == []

    def test_installed(self) -> None:
        info = PyTorchEnvInfo(
            installed=True,
            version="2.1.0",
            cuda_available=True,
            device_count=1,
        )
        assert info.installed is True
        assert info.cuda_available is True
