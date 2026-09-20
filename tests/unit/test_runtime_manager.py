"""Tests for RuntimeManager and API endpoints."""

from __future__ import annotations

from codeforge.packages.runtime.manager import RuntimeManager
from codeforge.packages.runtime.models import BackendStatus, RuntimeInfo


class TestRuntimeManager:
    def test_detect(self) -> None:
        rm = RuntimeManager()
        info = rm.detect()
        assert isinstance(info, RuntimeInfo)
        rm.shutdown()

    def test_detect_has_python(self) -> None:
        rm = RuntimeManager()
        info = rm.detect()
        assert info.python.version != "Unknown"
        rm.shutdown()

    def test_detect_has_environment(self) -> None:
        rm = RuntimeManager()
        info = rm.detect()
        valid_types = ("conda", "venv", "virtualenv", "system", "unknown")
        assert info.environment.env_type.value in valid_types
        rm.shutdown()

    def test_detect_has_device(self) -> None:
        rm = RuntimeManager()
        info = rm.detect()
        assert info.selected_device.is_available is True
        rm.shutdown()

    def test_backend_status(self) -> None:
        rm = RuntimeManager()
        info = rm.detect()
        assert isinstance(info.backend_status, BackendStatus)
        rm.shutdown()

    def test_smoke_test(self) -> None:
        rm = RuntimeManager()
        rm.detect()
        result = rm.run_smoke_test()
        assert isinstance(result, dict)
        assert "success" in result
        rm.shutdown()

    def test_shutdown(self) -> None:
        rm = RuntimeManager()
        rm.detect()
        rm.shutdown()
        assert rm.get_backend() is None

    def test_get_runtime_info_caches(self) -> None:
        rm = RuntimeManager()
        i1 = rm.get_runtime_info()
        i2 = rm.get_runtime_info()
        assert i1 is i2
        rm.shutdown()

    def test_preferred_device(self) -> None:
        rm = RuntimeManager(preferred_device="cpu")
        info = rm.detect()
        assert info.selected_device.device_type.value == "cpu"
        rm.shutdown()

    def test_to_dict(self) -> None:
        rm = RuntimeManager()
        info = rm.detect()
        d = info.to_dict()
        assert "python" in d
        assert "pytorch" in d
        assert "backend_status" in d
        rm.shutdown()
