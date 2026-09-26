"""Tests for hardware detection models."""

from __future__ import annotations

from codeforge.packages.hardware.models import (
    CPUInfo,
    DiskInfo,
    GPUInfo,
    HardwareInfo,
    PyTorchInfo,
    RAMInfo,
)


class TestCPUInfo:
    def test_default_values(self) -> None:
        info = CPUInfo()
        assert info.model == "Unknown"
        assert info.cores_physical == 0
        assert info.cores_logical == 0
        assert info.threads == 0
        assert info.architecture == "Unknown"
        assert info.flags == []

    def test_custom_values(self) -> None:
        info = CPUInfo(
            model="AMD Ryzen 9 5900X",
            cores_physical=12,
            cores_logical=24,
            threads=24,
            architecture="x86_64",
            max_frequency_mhz=4900.0,
            flags=["sse4_2", "avx2"],
        )
        assert info.model == "AMD Ryzen 9 5900X"
        assert info.cores_physical == 12
        assert info.cores_logical == 24
        assert info.threads == 24
        assert info.max_frequency_mhz == 4900.0
        assert "avx2" in info.flags

    def test_frozen(self) -> None:
        info = CPUInfo(model="Test")
        try:
            info.model = "Changed"  # type: ignore[misc]
            raise AssertionError("Should be frozen")
        except AttributeError:
            pass


class TestRAMInfo:
    def test_default_values(self) -> None:
        info = RAMInfo()
        assert info.total_gb == 0.0
        assert info.available_gb == 0.0
        assert info.used_gb == 0.0
        assert info.usage_percent == 0.0

    def test_custom_values(self) -> None:
        info = RAMInfo(total_gb=32.0, available_gb=16.0, used_gb=16.0, usage_percent=50.0)
        assert info.total_gb == 32.0
        assert info.available_gb == 16.0


class TestGPUInfo:
    def test_default_values(self) -> None:
        info = GPUInfo()
        assert info.name is None
        assert info.vendor is None
        assert info.vram_gb is None
        assert info.cuda_available is False
        assert info.rocm_available is False
        assert info.mps_available is False

    def test_nvidia_gpu(self) -> None:
        info = GPUInfo(
            name="RTX 4090",
            vendor="NVIDIA",
            vram_gb=24.0,
            cuda_available=True,
            cuda_version="12.1",
        )
        assert info.name == "RTX 4090"
        assert info.vendor == "NVIDIA"
        assert info.cuda_available is True


class TestHardwareInfo:
    def test_default_values(self) -> None:
        info = HardwareInfo()
        assert info.os_name == "Unknown"
        assert info.cpu_model == "Unknown"
        assert info.ram_total_gb == 0.0
        assert info.acceleration_backend == "CPU"

    def test_acceleration_backend_cuda(self) -> None:
        gpu = GPUInfo(cuda_available=True)
        info = HardwareInfo(gpu=gpu)
        assert info.acceleration_backend == "CUDA"

    def test_acceleration_backend_rocm(self) -> None:
        gpu = GPUInfo(rocm_available=True)
        info = HardwareInfo(gpu=gpu)
        assert info.acceleration_backend == "ROCm"

    def test_acceleration_backend_mps(self) -> None:
        gpu = GPUInfo(mps_available=True)
        info = HardwareInfo(gpu=gpu)
        assert info.acceleration_backend == "MPS"

    def test_acceleration_backend_cpu(self) -> None:
        info = HardwareInfo()
        assert info.acceleration_backend == "CPU"

    def test_to_dict(self) -> None:
        info = HardwareInfo(os_name="Linux")
        d = info.to_dict()
        assert d["os"] == "Linux"
        assert "cpu" in d
        assert "ram" in d
        assert "gpu" in d
        assert "disk" in d
        assert "pytorch" in d
        assert "acceleration_backend" in d

    def test_convenience_properties(self) -> None:
        cpu = CPUInfo(model="TestCPU", cores_physical=8, cores_logical=16, threads=16)
        ram = RAMInfo(total_gb=32.0, available_gb=16.0)
        gpu = GPUInfo(name="TestGPU", vendor="NVIDIA", vram_gb=8.0)
        disk = DiskInfo(total_gb=500.0, free_gb=250.0)
        pt = PyTorchInfo(installed=True, version="2.1.0")

        info = HardwareInfo(cpu=cpu, ram=ram, gpu=gpu, disk=disk, pytorch=pt)

        assert info.cpu_model == "TestCPU"
        assert info.cpu_cores_physical == 8
        assert info.cpu_cores_logical == 16
        assert info.cpu_threads == 16
        assert info.ram_total_gb == 32.0
        assert info.ram_available_gb == 16.0
        assert info.gpu_name == "TestGPU"
        assert info.gpu_vendor == "NVIDIA"
        assert info.vram_gb == 8.0
        assert info.pytorch_version == "2.1.0"
        assert info.disk_total_gb == 500.0
        assert info.disk_free_gb == 250.0


class TestPyTorchInfo:
    def test_default_not_installed(self) -> None:
        info = PyTorchInfo()
        assert info.installed is False
        assert info.version is None

    def test_installed(self) -> None:
        info = PyTorchInfo(installed=True, version="2.1.0", cuda_version="12.1")
        assert info.installed is True
        assert info.version == "2.1.0"
        assert info.cuda_version == "12.1"


class TestDiskInfo:
    def test_default_values(self) -> None:
        info = DiskInfo()
        assert info.total_gb == 0.0
        assert info.free_gb == 0.0
