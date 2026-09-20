"""Tests for generation context manager."""

import pytest

from codeforge.packages.generation.context import ContextManager
from codeforge.packages.generation.errors import (
    ContextLengthExceededError,
    TokenizationError,
)


class TestContextManager:
    def test_init_without_tokenizer(self) -> None:
        cm = ContextManager()
        assert cm._tokenizer_manager is None  # noqa: SLF001

    def test_tokenize_no_manager(self) -> None:
        cm = ContextManager()
        with pytest.raises(TokenizationError, match="No tokenizer manager"):
            cm.tokenize("hello")

    def test_tokenize_with_mock_tokenizer(self) -> None:
        class MockTokenizer:
            def tokenize(self, model_path, text):  # noqa: ARG002
                return list(range(len(text)))

        cm = ContextManager(MockTokenizer())
        tokens = cm.tokenize("hello", "/fake/path")
        assert tokens == [0, 1, 2, 3, 4]

    def test_count_tokens(self) -> None:
        class MockTokenizer:
            def tokenize(self, model_path, text):  # noqa: ARG002
                return list(range(len(text)))

        cm = ContextManager(MockTokenizer())
        count = cm.count_tokens("hello", "/fake/path")
        assert count == 5

    def test_validate_context_length_ok(self) -> None:
        class MockTokenizer:
            def tokenize(self, model_path, text):  # noqa: ARG002
                return [1, 2, 3]

        cm = ContextManager(MockTokenizer())
        result = cm.validate_context_length("test", 10, "model", "/path")
        assert result == 3

    def test_validate_context_length_exceeded(self) -> None:
        class MockTokenizer:
            def tokenize(self, model_path, text):  # noqa: ARG002
                return list(range(20))

        cm = ContextManager(MockTokenizer())
        with pytest.raises(ContextLengthExceededError):
            cm.validate_context_length("test", 10, "model", "/path")

    def test_truncate_to_context_no_truncation(self) -> None:
        class MockTokenizer:
            def tokenize(self, model_path, text):  # noqa: ARG002
                return [1, 2, 3]

            def decode(self, tokens):  # noqa: ARG002
                return "".join(str(t) for t in tokens)

        cm = ContextManager(MockTokenizer())
        result = cm.truncate_to_context("hello", 10, "/path")
        assert result == "hello"

    def test_format_chat_prompt(self) -> None:
        cm = ContextManager()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        result = cm.format_chat_prompt(messages)
        assert "user: Hello" in result
        assert "assistant: Hi there!" in result
        assert result.endswith("assistant:")

    def test_format_chat_prompt_single_message(self) -> None:
        cm = ContextManager()
        messages = [{"role": "user", "content": "Test"}]
        result = cm.format_chat_prompt(messages)
        assert result == "user: Test\nassistant:"

    def test_estimate_token_count(self) -> None:
        cm = ContextManager()
        assert cm.estimate_token_count("") >= 1
        assert cm.estimate_token_count("hello") >= 1
        count = cm.estimate_token_count("a" * 100)
        assert count == 25

    def test_tokenize_with_none_model_path(self) -> None:
        class MockTokenizer:
            def tokenize(self, text):  # noqa: ARG002
                return [1, 2]

        cm = ContextManager(MockTokenizer())
        tokens = cm.tokenize("hello")
        assert tokens == [1, 2]
