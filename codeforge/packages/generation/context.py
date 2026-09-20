"""Context window management and tokenization helpers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .errors import ContextLengthExceededError, TokenizationError

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONTEXT = 2048


class ContextManager:
    """Handles tokenization and context length validation."""

    def __init__(self, tokenizer_manager: object | None = None) -> None:
        self._tokenizer_manager = tokenizer_manager

    def tokenize(self, text: str, model_path: str | Path | None = None) -> list[int]:
        """Tokenize text using the tokenizer manager."""
        if self._tokenizer_manager is None:
            raise TokenizationError("", "No tokenizer manager configured")
        try:
            if model_path is not None:
                return self._tokenizer_manager.tokenize(model_path, text)
            if hasattr(self._tokenizer_manager, "tokenize") and callable(
                self._tokenizer_manager.tokenize
            ):
                return self._tokenizer_manager.tokenize(text)
            return []
        except Exception as e:
            raise TokenizationError(str(model_path or ""), str(e)) from e

    def count_tokens(self, text: str, model_path: str | Path | None = None) -> int:
        """Count tokens in text."""
        tokens = self.tokenize(text, model_path)
        return len(tokens)

    def validate_context_length(
        self,
        prompt: str,
        max_context: int,
        model_id: str = "",
        model_path: str | Path | None = None,
    ) -> int:
        """Validate that prompt fits within context length.

        Returns the token count. Raises ContextLengthExceededError if too long.
        """
        token_count = self.count_tokens(prompt, model_path)
        if max_context > 0 and token_count > max_context:
            raise ContextLengthExceededError(model_id, token_count, max_context)
        return token_count

    def truncate_to_context(
        self,
        text: str,
        max_context: int,
        model_path: str | Path | None = None,
        keep_end: bool = True,
    ) -> str:
        """Truncate text to fit within context length."""
        tokens = self.tokenize(text, model_path)
        if len(tokens) <= max_context or max_context <= 0:
            return text
        truncated = tokens[-max_context:] if keep_end else tokens[:max_context]
        if self._tokenizer_manager and hasattr(self._tokenizer_manager, "decode"):
            try:
                return self._tokenizer_manager.decode(truncated)
            except Exception:
                pass
        return text[:max_context]

    def format_chat_prompt(self, messages: list[dict]) -> str:
        """Format chat messages into a prompt string."""
        parts: list[str] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            parts.append(f"{role}: {content}")
        parts.append("assistant:")
        return "\n".join(parts)

    def estimate_token_count(self, text: str) -> int:
        """Rough estimate of token count (4 chars per token heuristic)."""
        return max(1, len(text) // 4)
