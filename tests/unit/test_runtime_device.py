"""Tests for device management."""

from __future__ import annotations

from codeforge.packages.runtime.device import DeviceManager, _parse_device_string
from codeforge.packages.runtime.models import DeviceInfo, DeviceType


class TestParseDeviceString:
    def test_cpu(self) -> None:
        result = _parse_device_string("cpu")
        assert result == (DeviceType.CPU, 0)

    def test_cuda(self) -> None:
        result = _parse_device_string("cuda")
        assert result == (DeviceType.CUDA, 0)

    def test_cuda_index(self) -> None:
        result = _parse_device_string("cuda:1")
        assert result == (DeviceType.CUDA, 1)

    def test_mps(self) -> None:
        result = _parse_device_string("mps")
        assert result == (DeviceType.MPS, 0)

    def test_invalid(self) -> None:
        result = _parse_device_string("invalid")
        assert result is None

    def test_cuda_invalid_index(self) -> None:
        result = _parse_device_string("cuda:abc")
        assert result is None

    def test_whitespace(self) -> None:
        result = _parse_device_string("  cpu  ")
        assert result == (DeviceType.CPU, 0)


class TestDeviceManager:
    def test_detect_available_returns_list(self) -> None:
        dm = DeviceManager()
        devices = dm.detect_available_devices()
        assert isinstance(devices, list)
        assert len(devices) >= 1

    def test_cpu_always_available(self) -> None:
        dm = DeviceManager()
        devices = dm.detect_available_devices()
        cpu_devices = [d for d in devices if d.device_type == DeviceType.CPU]
        assert len(cpu_devices) >= 1
        assert cpu_devices[0].is_available is True

    def test_get_default_device(self) -> None:
        dm = DeviceManager()
        dev = dm.get_default_device()
        assert isinstance(dev, DeviceInfo)
        assert dev.is_available is True

    def test_validate_valid_device(self) -> None:
        dm = DeviceManager()
        result = dm.validate_device("cpu")
        assert result is not None
        assert result.device_type == DeviceType.CPU

    def test_validate_invalid_device(self) -> None:
        dm = DeviceManager()
        result = dm.validate_device("invalid_device_xyz")
        assert result is None

    def test_select_device_cpu(self) -> None:
        dm = DeviceManager()
        dev = dm.select_device("cpu")
        assert dev.device_type == DeviceType.CPU

    def test_select_device_invalid_raises(self) -> None:
        dm = DeviceManager()
        try:
            dm.select_device("invalid_device_xyz")
            raise AssertionError("Should have raised ValueError")
        except ValueError:
            pass

    def test_get_device_info(self) -> None:
        dm = DeviceManager()
        info = dm.get_device_info("cpu")
        assert "available" in info
        assert info["available"] is True

    def test_get_device_info_invalid(self) -> None:
        dm = DeviceManager()
        info = dm.get_device_info("invalid")
        assert info["available"] is False

    def test_preferred_device_cpu(self) -> None:
        dm = DeviceManager(preferred_device="cpu")
        dev = dm.get_default_device()
        assert dev.device_type == DeviceType.CPU

    def test_caching(self) -> None:
        dm = DeviceManager()
        d1 = dm.detect_available_devices()
        d2 = dm.detect_available_devices()
        assert d1 is d2
