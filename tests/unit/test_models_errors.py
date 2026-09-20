"""Tests for model error types."""

from codeforge.packages.models.errors import (
    InsufficientMemoryError,
    ModelAlreadyLoadedError,
    ModelConfigInvalidError,
    ModelError,
    ModelFormatUnsupportedError,
    ModelLoadError,
    ModelNotFoundError,
    ModelUnloadError,
    TokenizerNotFoundError,
    UnsupportedDeviceError,
    UnsupportedDtypeError,
)


class TestModelErrors:
    def test_base_error(self) -> None:
        e = ModelError("TEST_CODE", "test message")
        assert e.code == "TEST_CODE"
        assert str(e) == "test message"
        d = e.to_dict()
        assert d["error"] == "TEST_CODE"

    def test_not_found(self) -> None:
        e = ModelNotFoundError("my-model")
        assert "my-model" in e.message
        assert e.code == "MODEL_NOT_FOUND"

    def test_config_invalid(self) -> None:
        e = ModelConfigInvalidError("m1", "missing field")
        assert "missing field" in e.message

    def test_format_unsupported(self) -> None:
        e = ModelFormatUnsupportedError("/path/to/file")
        assert "/path/to/file" in e.message

    def test_tokenizer_not_found(self) -> None:
        e = TokenizerNotFoundError("m1")
        assert e.code == "TOKENIZER_NOT_FOUND"

    def test_load_error(self) -> None:
        e = ModelLoadError("m1", "corrupt file")
        assert "corrupt file" in e.message

    def test_unload_error(self) -> None:
        e = ModelUnloadError("m1")
        assert e.code == "MODEL_UNLOAD_FAILED"

    def test_insufficient_memory(self) -> None:
        e = InsufficientMemoryError("m1", 8.0, 4.0)
        assert e.details["required_gb"] == 8.0
        assert e.details["available_gb"] == 4.0

    def test_unsupported_dtype(self) -> None:
        e = UnsupportedDtypeError("float64", "cpu")
        assert e.code == "UNSUPPORTED_DTYPE"

    def test_unsupported_device(self) -> None:
        e = UnsupportedDeviceError("tpu")
        assert e.code == "UNSUPPORTED_DEVICE"

    def test_already_loaded(self) -> None:
        e = ModelAlreadyLoadedError("m1")
        assert e.code == "MODEL_ALREADY_LOADED"
