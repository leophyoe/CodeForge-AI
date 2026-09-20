"""Tests for TokenizerManager."""

from pathlib import Path

from codeforge.packages.models.errors import TokenizerNotFoundError
from codeforge.packages.models.tokenizer import TokenizerManager


class TestTokenizerManager:
    def test_detect_no_tokenizer(self, tmp_path: Path) -> None:
        tm = TokenizerManager()
        result = tm.detect_tokenizer(tmp_path)
        assert result["available"] is False

    def test_detect_tokenizer_json(self, tmp_path: Path) -> None:
        (tmp_path / "tokenizer.json").touch()
        tm = TokenizerManager()
        result = tm.detect_tokenizer(tmp_path)
        assert result["available"] is True
        assert result["type"] == "huggingface"

    def test_detect_tokenizer_model(self, tmp_path: Path) -> None:
        (tmp_path / "tokenizer.model").touch()
        tm = TokenizerManager()
        result = tm.detect_tokenizer(tmp_path)
        assert result["available"] is True
        assert result["type"] == "sentencepiece"

    def test_detect_nonexistent_dir(self) -> None:
        tm = TokenizerManager()
        result = tm.detect_tokenizer("/nonexistent/path")
        assert result["available"] is False

    def test_load_tokenizer_missing(self, tmp_path: Path) -> None:
        tm = TokenizerManager()
        try:
            tm.load_tokenizer(tmp_path)
            raise AssertionError("Should have raised")
        except TokenizerNotFoundError:
            pass

    def test_is_loaded(self, tmp_path: Path) -> None:
        tm = TokenizerManager()
        assert tm.is_loaded(tmp_path) is False

    def test_unload_tokenizer(self, tmp_path: Path) -> None:
        tm = TokenizerManager()
        tm.unload_tokenizer(tmp_path)
        assert tm.is_loaded(tmp_path) is False
