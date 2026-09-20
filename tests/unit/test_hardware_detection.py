"""Tests for hardware detection modules."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from codeforge.packages.hardware.cpu import detect_cpu
from codeforge.packages.hardware.disk import detect_disk
from codeforge.packages.hardware.gpu import detect_gpu
from codeforge.packages.hardware.models import CPUInfo, DiskInfo, GPUInfo, RAMInfo
from codeforge.packages.hardware.ram import detect_ram
from codeforge.packages.hardware.system import detect_system


class TestSystemDetection:
    def test_detect_system_returns_valid(self) -> None:
        info = detect_system()
        assert info.os_name in ("Linux", "Windows", "Darwin")
        assert info.architecture != ""
        assert info.hostname != ""
        assert info.python_version != ""

    def test_detect_system_has_version(self) -> None:
        info = detect_system()
        assert info.os_version != ""
        assert info.os_release != ""


class TestCPUDetection:
    def test_detect_cpu_returns_valid(self) -> None:
        info = detect_cpu()
        assert isinstance(info, CPUInfo)
        assert info.model != ""
        assert info.cores_logical > 0
        assert info.threads > 0

    def test_detect_cpu_has_architecture(self) -> None:
        info = detect_cpu()
        assert info.architecture != ""


class TestRAMDetection:
    def test_detect_ram_returns_valid(self) -> None:
        info = detect_ram()
        assert isinstance(info, RAMInfo)
        assert info.total_gb > 0
        assert info.available_gb > 0
        assert info.used_gb >= 0
        assert 0 <= info.usage_percent <= 100

    def test_detect_ram_consistency(self) -> None:
        info = detect_ram()
        # used + available should approximately equal total
        assert abs(info.used_gb + info.available_gb - info.total_gb) < 1.0


class TestDiskDetection:
    def test_detect_disk_returns_valid(self) -> None:
        info = detect_disk()
        assert isinstance(info, DiskInfo)
        assert info.total_gb > 0
        assert info.free_gb >= 0
        assert info.used_gb >= 0

    def test_detect_disk_custom_path(self) -> None:
        info = detect_disk(path="/tmp")
        assert isinstance(info, DiskInfo)
        assert info.total_gb > 0


class TestGPUDetection:
    def test_detect_gpu_returns_valid(self) -> None:
        info = detect_gpu()
        assert isinstance(info, GPUInfo)

    def test_detect_gpu_has_boolean_flags(self) -> None:
        info = detect_gpu()
        assert isinstance(info.cuda_available, bool)
        assert isinstance(info.rocm_available, bool)
        assert isinstance(info.mps_available, bool)

    def test_detect_gpu_no_false_positives(self) -> None:
        """GPU detection should not claim CUDA/ROCm/MPS if not available."""
        info = detect_gpu()
        # At most one should be True (unless NVIDIA + MPS which isn't possible)
        accelerations = [
            info.cuda_available,
            info.rocm_available,
            info.mps_available,
        ]
        # It's valid for none or one to be True
        assert sum(1 for a in accelerations if a) <= 1


class TestGPUMockNVIDIA:
    @patch("codeforge.packages.hardware.gpu._detect_nvidia_pynvml")
    @patch("codeforge.packages.hardware.gpu._detect_nvidia_torch")
    @patch("codeforge.packages.hardware.gpu._detect_amd_rocm")
    @patch("codeforge.packages.hardware.gpu._detect_apple_mps")
    def test_nvidia_detected_via_pynvml(
        self,
        mock_mps: MagicMock,
        mock_rocm: MagicMock,
        mock_torch: MagicMock,
        mock_pynvml: MagicMock,
    ) -> None:
        mock_pynvml.return_value = GPUInfo(
            name="RTX 4090",
            vendor="NVIDIA",
            vram_gb=24.0,
            cuda_available=True,
        )
        mock_torch.return_value = None
        mock_rocm.return_value = None
        mock_mps.return_value = None

        info = detect_gpu()
        assert info.name == "RTX 4090"
        assert info.vendor == "NVIDIA"
        assert info.cuda_available is True

    @patch("codeforge.packages.hardware.gpu._detect_nvidia_pynvml")
    @patch("codeforge.packages.hardware.gpu._detect_nvidia_torch")
    @patch("codeforge.packages.hardware.gpu._detect_amd_rocm")
    @patch("codeforge.packages.hardware.gpu._detect_apple_mps")
    def test_no_gpu_returns_empty(
        self,
        mock_mps: MagicMock,
        mock_rocm: MagicMock,
        mock_torch: MagicMock,
        mock_pynvml: MagicMock,
    ) -> None:
        mock_pynvml.return_value = None
        mock_torch.return_value = None
        mock_rocm.return_value = None
        mock_mps.return_value = None

        info = detect_gpu()
        assert info.name is None
        assert info.vendor is None
        assert info.cuda_available is False
