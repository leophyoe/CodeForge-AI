"""Tests for HardwareManager."""

from __future__ import annotations

from unittest.mock import patch

from codeforge.packages.hardware.manager import HardwareManager
from codeforge.packages.hardware.models import (
    CPUInfo,
    HardwareInfo,
)


class TestHardwareManager:
    def test_detect_returns_hardware_info(self) -> None:
        manager = HardwareManager()
        info = manager.detect()
        assert isinstance(info, HardwareInfo)

    def test_detect_has_os(self) -> None:
        manager = HardwareManager()
        info = manager.detect()
        assert info.os_name in ("Linux", "Windows", "Darwin")

    def test_detect_has_cpu(self) -> None:
        manager = HardwareManager()
        info = manager.detect()
        assert info.cpu.model != ""
        assert info.cpu.cores_logical > 0

    def test_detect_has_ram(self) -> None:
        manager = HardwareManager()
        info = manager.detect()
        assert info.ram.total_gb > 0

    def test_detect_has_disk(self) -> None:
        manager = HardwareManager()
        info = manager.detect()
        assert info.disk.total_gb > 0

    def test_caching(self) -> None:
        manager = HardwareManager(cache_ttl_seconds=60)
        info1 = manager.detect()
        info2 = manager.detect()
        # Same object due to caching
        assert info1 is info2

    def test_cache_invalidation(self) -> None:
        manager = HardwareManager(cache_ttl_seconds=60)
        info1 = manager.detect()
        manager.invalidate_cache()
        info2 = manager.detect()
        # Different objects after invalidation
        assert info1 is not info2
        # Core static values should be the same (RAM may fluctuate slightly)
        assert info1.os_name == info2.os_name
        assert info1.cpu_model == info2.cpu_model
        assert info1.architecture == info2.architecture

    def test_force_detection(self) -> None:
        manager = HardwareManager(cache_ttl_seconds=60)
        info1 = manager.detect()
        info2 = manager.detect(force=True)
        # Different objects when forced
        assert info1 is not info2

    def test_cache_expiry(self) -> None:
        manager = HardwareManager(cache_ttl_seconds=0)
        info1 = manager.detect()
        info2 = manager.detect()
        # Different objects when cache is disabled
        assert info1 is not info2

    def test_get_summary(self) -> None:
        manager = HardwareManager()
        summary = manager.get_summary()
        assert "system" in summary
        assert "cpu" in summary
        assert "ram" in summary
        assert "gpu" in summary
        assert "acceleration" in summary
        assert "pytorch" in summary

    def test_check_compatibility(self) -> None:
        manager = HardwareManager()
        compat = manager.check_compatibility()
        assert "compatible" in compat
        assert "issues" in compat
        assert "warnings" in compat
        assert "acceleration" in compat
        assert isinstance(compat["issues"], list)
        assert isinstance(compat["warnings"], list)

    def test_to_dict(self) -> None:
        manager = HardwareManager()
        info = manager.detect()
        d = info.to_dict()
        assert isinstance(d, dict)
        assert "os" in d
        assert "cpu" in d
        assert "ram" in d
        assert "gpu" in d
        assert "disk" in d
        assert "pytorch" in d

    @patch("codeforge.packages.hardware.manager.detect_cpu")
    def test_detect_with_mocked_cpu(self, mock_cpu: object) -> None:
        mock_cpu.return_value = CPUInfo(  # type: ignore[union-attr]
            model="Mocked CPU",
            cores_physical=4,
            cores_logical=8,
            threads=8,
        )
        manager = HardwareManager()
        manager.invalidate_cache()
        info = manager.detect(force=True)
        assert info.cpu_model == "Mocked CPU"
        assert info.cpu_cores_physical == 4
