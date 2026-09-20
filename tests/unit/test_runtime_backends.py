"""Tests for backends and memory management."""

from __future__ import annotations

from codeforge.packages.runtime.backends import CPUBackend, CUDABackend, MPSBackend
from codeforge.packages.runtime.memory import MemoryManager
from codeforge.packages.runtime.models import BackendStatus, DeviceType, MemoryInfo


class TestCPUBackend:
    def test_initialize(self) -> None:
        backend = CPUBackend()
        status = backend.initialize()
        assert status == BackendStatus.READY

    def test_is_available(self) -> None:
        backend = CPUBackend()
        assert backend.is_available() is True

    def test_get_device(self) -> None:
        backend = CPUBackend()
        dev = backend.get_device()
        assert dev.device_type == DeviceType.CPU
        assert dev.is_available is True

    def test_run_tensor_test(self) -> None:
        backend = CPUBackend()
        result = backend.run_tensor_test()
        assert isinstance(result, dict)
        assert "success" in result
        # May fail if PyTorch is not installed
        if result["success"] is False:
            assert "error" in result

    def test_get_memory_info(self) -> None:
        backend = CPUBackend()
        mem = backend.get_memory_info()
        assert isinstance(mem, MemoryInfo)
        assert mem.total_gb > 0

    def test_shutdown(self) -> None:
        backend = CPUBackend()
        backend.initialize()
        backend.shutdown()


class TestCUDABackend:
    def test_is_available(self) -> None:
        backend = CUDABackend()
        result = backend.is_available()
        assert isinstance(result, bool)

    def test_initialize_without_torch(self) -> None:
        backend = CUDABackend()
        status = backend.initialize()
        valid_statuses = (
            BackendStatus.READY,
            BackendStatus.NOT_INSTALLED,
            BackendStatus.NOT_AVAILABLE,
            BackendStatus.ERROR,
        )
        assert status in valid_statuses

    def test_get_device(self) -> None:
        backend = CUDABackend()
        dev = backend.get_device()
        assert dev.device_type == DeviceType.CUDA


class TestMPSBackend:
    def test_is_available(self) -> None:
        backend = MPSBackend()
        result = backend.is_available()
        assert isinstance(result, bool)

    def test_initialize(self) -> None:
        backend = MPSBackend()
        status = backend.initialize()
        valid_statuses = (
            BackendStatus.READY,
            BackendStatus.NOT_INSTALLED,
            BackendStatus.NOT_AVAILABLE,
            BackendStatus.ERROR,
        )
        assert status in valid_statuses

    def test_get_device(self) -> None:
        backend = MPSBackend()
        dev = backend.get_device()
        assert dev.device_type == DeviceType.MPS


class TestMemoryManager:
    def test_get_system_memory(self) -> None:
        mm = MemoryManager()
        mem = mm.get_system_memory()
        assert isinstance(mem, MemoryInfo)
        assert mem.total_gb > 0
        assert mem.available_gb > 0

    def test_get_gpu_memory_without_torch(self) -> None:
        mm = MemoryManager()
        mem = mm.get_gpu_memory(0)
        assert isinstance(mem, MemoryInfo)

    def test_get_memory_for_device_cpu(self) -> None:
        mm = MemoryManager()
        mem = mm.get_memory_for_device(DeviceType.CPU)
        assert isinstance(mem, MemoryInfo)
        assert mem.total_gb > 0

    def test_get_memory_for_device_cuda(self) -> None:
        mm = MemoryManager()
        mem = mm.get_memory_for_device(DeviceType.CUDA)
        assert isinstance(mem, MemoryInfo)

    def test_get_memory_for_device_mps(self) -> None:
        mm = MemoryManager()
        mem = mm.get_memory_for_device(DeviceType.MPS)
        assert isinstance(mem, MemoryInfo)
