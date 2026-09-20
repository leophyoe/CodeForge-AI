"""Tests for ModelProvider and LocalPyTorchProvider."""

from pathlib import Path

import pytest

from codeforge.packages.models.errors import ModelLoadError
from codeforge.packages.models.models import ModelMetadata
from codeforge.packages.models.provider import LocalPyTorchProvider, _format_parameter_count

torch = pytest.importorskip("torch", reason="PyTorch not installed")


class TestFormatParameterCount:
    def test_billions(self) -> None:
        assert _format_parameter_count(7_000_000_000) == "7.00B"

    def test_millions(self) -> None:
        assert _format_parameter_count(125_000_000) == "125.00M"

    def test_thousands(self) -> None:
        assert _format_parameter_count(5_000) == "5.00K"

    def test_small(self) -> None:
        assert _format_parameter_count(42) == "42"


class TestLocalPyTorchProvider:
    def test_init(self) -> None:
        p = LocalPyTorchProvider()
        assert p._torch_available is True  # noqa: SLF001

    def test_estimate_memory(self) -> None:
        p = LocalPyTorchProvider()
        meta = ModelMetadata(
            model_id="test",
            parameter_count=1e9,
            dtype="float32",
            context_length=2048,
        )
        mem = p.estimate_memory(meta)
        assert "model_memory_gb" in mem
        assert mem["model_memory_gb"] > 0
        assert mem["dtype"] == "float32"

    def test_estimate_memory_float16(self) -> None:
        p = LocalPyTorchProvider()
        meta = ModelMetadata(model_id="test", parameter_count=1e9, dtype="float16")
        mem = p.estimate_memory(meta)
        assert mem["dtype"] == "float16"
        assert mem["model_memory_gb"] < 4.0

    def test_is_loaded_none(self) -> None:
        p = LocalPyTorchProvider()
        assert p.is_loaded(None) is False

    def test_load_model_nonexistent_path(self) -> None:
        p = LocalPyTorchProvider()
        meta = ModelMetadata(model_id="test", path="/nonexistent/path")
        try:
            p.load_model(meta)
            raise AssertionError("Should have raised ModelLoadError")
        except ModelLoadError:
            pass

    def test_load_test_model(self, tmp_path: Path) -> None:
        from codeforge.packages.models.test_model import create_test_model

        model_path = create_test_model(tmp_path / "test_model")
        assert (model_path / "config.json").exists()

        p = LocalPyTorchProvider()
        meta = ModelMetadata(
            model_id="test-model",
            path=str(model_path),
            parameter_count=100000,
        )
        instance = p.load_model(meta, device="cpu", dtype="float32")
        assert instance is not None
        assert p.is_loaded(instance) is True

    def test_get_model_info(self, tmp_path: Path) -> None:
        from codeforge.packages.models.test_model import create_test_model

        model_path = create_test_model(tmp_path / "test_model")
        p = LocalPyTorchProvider()
        meta = ModelMetadata(model_id="test", path=str(model_path), parameter_count=1000)
        instance = p.load_model(meta, device="cpu")
        info = p.get_model_info(instance)
        assert info["loaded"] is True
        assert "parameter_count" in info

    def test_health_check(self, tmp_path: Path) -> None:
        from codeforge.packages.models.test_model import create_test_model

        model_path = create_test_model(tmp_path / "test_model")
        p = LocalPyTorchProvider()
        meta = ModelMetadata(model_id="test", path=str(model_path), parameter_count=1000)
        instance = p.load_model(meta, device="cpu")
        hc = p.health_check(instance)
        assert hc["healthy"] is True
        assert hc["loaded"] is True

    def test_generate(self, tmp_path: Path) -> None:
        from codeforge.packages.models.test_model import create_test_model

        model_path = create_test_model(tmp_path / "test_model")
        p = LocalPyTorchProvider()
        meta = ModelMetadata(model_id="test", path=str(model_path), parameter_count=1000)
        instance = p.load_model(meta, device="cpu")
        result = p.generate(instance, "hello", max_tokens=5)
        assert result is not None
        assert result.finish_reason == "stop"

    def test_stream_generate(self, tmp_path: Path) -> None:
        from codeforge.packages.models.test_model import create_test_model

        model_path = create_test_model(tmp_path / "test_model")
        p = LocalPyTorchProvider()
        meta = ModelMetadata(model_id="test", path=str(model_path), parameter_count=1000)
        instance = p.load_model(meta, device="cpu")
        tokens = list(p.stream_generate(instance, "hello", max_tokens=5))
        assert len(tokens) > 0
        assert tokens[-1].is_end is True

    def test_chat(self, tmp_path: Path) -> None:
        from codeforge.packages.models.test_model import create_test_model

        model_path = create_test_model(tmp_path / "test_model")
        p = LocalPyTorchProvider()
        meta = ModelMetadata(model_id="test", path=str(model_path), parameter_count=1000)
        instance = p.load_model(meta, device="cpu")
        result = p.chat(
            instance,
            [{"role": "user", "content": "hello"}],
            max_tokens=5,
        )
        assert result is not None

    def test_get_context_length(self, tmp_path: Path) -> None:
        from codeforge.packages.models.test_model import create_test_model

        model_path = create_test_model(tmp_path / "test_model")
        p = LocalPyTorchProvider()
        meta = ModelMetadata(model_id="test", path=str(model_path), parameter_count=1000)
        instance = p.load_model(meta, device="cpu")
        ctx = p.get_context_length(instance)
        assert ctx == 128

    def test_unload_model(self, tmp_path: Path) -> None:
        from codeforge.packages.models.test_model import create_test_model

        model_path = create_test_model(tmp_path / "test_model")
        p = LocalPyTorchProvider()
        meta = ModelMetadata(model_id="test", path=str(model_path), parameter_count=1000)
        instance = p.load_model(meta, device="cpu")
        p.unload_model(instance)
