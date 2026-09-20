"""Structured error types for model management."""

from __future__ import annotations


class ModelError(Exception):
    """Base error for model operations."""

    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict:
        return {"error": self.code, "message": self.message, "details": self.details}


class ModelNotFoundError(ModelError):
    def __init__(self, model_id: str) -> None:
        super().__init__("MODEL_NOT_FOUND", f"Model '{model_id}' not found")


class ModelConfigInvalidError(ModelError):
    def __init__(self, model_id: str, reason: str) -> None:
        super().__init__("MODEL_CONFIG_INVALID", f"Config for '{model_id}' invalid: {reason}")


class ModelFormatUnsupportedError(ModelError):
    def __init__(self, path: str, reason: str = "") -> None:
        msg = f"Unsupported model format at '{path}'"
        if reason:
            msg += f": {reason}"
        super().__init__("MODEL_FORMAT_UNSUPPORTED", msg)


class TokenizerNotFoundError(ModelError):
    def __init__(self, model_id: str) -> None:
        super().__init__("TOKENIZER_NOT_FOUND", f"Tokenizer not found for '{model_id}'")


class ModelLoadError(ModelError):
    def __init__(self, model_id: str, reason: str = "") -> None:
        msg = f"Failed to load model '{model_id}'"
        if reason:
            msg += f": {reason}"
        super().__init__("MODEL_LOAD_FAILED", msg)


class ModelUnloadError(ModelError):
    def __init__(self, model_id: str, reason: str = "") -> None:
        msg = f"Failed to unload model '{model_id}'"
        if reason:
            msg += f": {reason}"
        super().__init__("MODEL_UNLOAD_FAILED", msg)


class InsufficientMemoryError(ModelError):
    def __init__(self, model_id: str, required_gb: float, available_gb: float) -> None:
        super().__init__(
            "INSUFFICIENT_MEMORY",
            f"Model '{model_id}' requires {required_gb:.1f}GB"
            f" but only {available_gb:.1f}GB available",
            {"required_gb": required_gb, "available_gb": available_gb},
        )


class UnsupportedDtypeError(ModelError):
    def __init__(self, dtype: str, device: str) -> None:
        super().__init__(
            "UNSUPPORTED_DTYPE",
            f"Dtype '{dtype}' not supported on device '{device}'",
        )


class UnsupportedDeviceError(ModelError):
    def __init__(self, device: str) -> None:
        super().__init__("UNSUPPORTED_DEVICE", f"Device '{device}' is not supported")


class ModelAlreadyLoadedError(ModelError):
    def __init__(self, model_id: str) -> None:
        super().__init__("MODEL_ALREADY_LOADED", f"Model '{model_id}' is already loaded")
