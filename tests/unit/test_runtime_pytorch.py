"""Tests for PyTorch environment detection."""

from __future__ import annotations

from codeforge.packages.runtime.models import DeviceType, PyTorchEnvInfo
from codeforge.packages.runtime.pytorch_check import (
    detect_pytorch_environment,
    run_tensor_smoke_test,
)


class TestPyTorchDetection:
    def test_detect_returns_valid(self) -> None:
        info = detect_pytorch_environment()
        assert isinstance(info, PyTorchEnvInfo)

    def test_installed_field(self) -> None:
        info = detect_pytorch_environment()
        assert isinstance(info.installed, bool)

    def test_devices_list(self) -> None:
        info = detect_pytorch_environment()
        assert isinstance(info.devices, list)
        assert len(info.devices) >= 1

    def test_cpu_device_present(self) -> None:
        info = detect_pytorch_environment()
        cpu_devices = [d for d in info.devices if d.device_type == DeviceType.CPU]
        assert len(cpu_devices) >= 1
        assert cpu_devices[0].is_available is True

    def test_device_count_matches(self) -> None:
        info = detect_pytorch_environment()
        assert info.device_count == len(info.devices)

    def test_cuda_fields(self) -> None:
        info = detect_pytorch_environment()
        assert isinstance(info.cuda_available, bool)
        if info.cuda_available:
            assert info.cuda_version is not None

    def test_mps_field(self) -> None:
        info = detect_pytorch_environment()
        assert isinstance(info.mps_available, bool)

    def test_rocm_field(self) -> None:
        info = detect_pytorch_environment()
        assert isinstance(info.rocm_available, bool)


class TestTensorSmokeTest:
    def test_cpu_smoke_test(self) -> None:
        result = run_tensor_smoke_test("cpu")
        assert isinstance(result, dict)
        assert "success" in result
        assert "device" in result

    def test_cpu_test_succeeds(self) -> None:
        result = run_tensor_smoke_test("cpu")
        if result.get("error") == "PyTorch not installed":
            return
        assert result["success"] is True

    def test_invalid_device(self) -> None:
        result = run_tensor_smoke_test("invalid_device")
        assert isinstance(result, dict)
        assert "success" in result

    def test_cpu_result_has_value(self) -> None:
        result = run_tensor_smoke_test("cpu")
        if result["success"]:
            assert "result" in result
