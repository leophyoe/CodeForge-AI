"""Generation-specific error types."""

from __future__ import annotations


class GenerationError(Exception):
    """Base error for generation operations."""

    def __init__(self, message: str, model_id: str = "") -> None:
        self.model_id = model_id
        super().__init__(message)


class ContextLengthExceededError(GenerationError):
    """Prompt exceeds model context length."""

    def __init__(self, model_id: str, prompt_tokens: int, max_context: int) -> None:
        self.prompt_tokens = prompt_tokens
        self.max_context = max_context
        super().__init__(
            f"Prompt has {prompt_tokens} tokens, model context is {max_context}",
            model_id,
        )


class ModelNotLoadedError(GenerationError):
    """Model is not loaded for generation."""

    def __init__(self, model_id: str) -> None:
        super().__init__(f"Model '{model_id}' is not loaded", model_id)


class TokenizationError(GenerationError):
    """Tokenization failed."""

    def __init__(self, model_id: str, detail: str = "") -> None:
        if detail:
            msg = f"Tokenization failed for model '{model_id}': {detail}"
        else:
            msg = f"Tokenization failed for model '{model_id}'"
        super().__init__(msg, model_id)


class GenerationConfigError(GenerationError):
    """Invalid generation configuration."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"Invalid generation config: {detail}")


class StreamTimeoutError(GenerationError):
    """Streaming generation timed out."""

    def __init__(self, model_id: str, timeout_s: float) -> None:
        super().__init__(
            f"Streaming timed out after {timeout_s}s for model '{model_id}'",
            model_id,
        )


class ChatFormatError(GenerationError):
    """Invalid chat message format."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"Invalid chat format: {detail}")
