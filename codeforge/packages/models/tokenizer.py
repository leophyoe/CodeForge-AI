"""Tokenizer detection, loading, and management."""

from __future__ import annotations

import logging
from pathlib import Path

from .errors import TokenizerNotFoundError

logger = logging.getLogger(__name__)

TOKENIZER_FILES = [
    "tokenizer.json",
    "tokenizer.model",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "vocab.json",
    "merges.txt",
]


class TokenizerManager:
    """Manages tokenizer loading and usage separate from model loading."""

    def __init__(self) -> None:
        self._loaded_tokenizers: dict[str, object] = {}

    def detect_tokenizer(self, model_path: str | Path) -> dict:
        """Detect if a tokenizer exists at the given path.

        Returns:
            Dict with tokenizer detection info.
        """
        path = Path(model_path)
        if not path.is_dir():
            return {"available": False, "path": str(path), "files": []}

        found_files = []
        for fname in TOKENIZER_FILES:
            fpath = path / fname
            if fpath.exists():
                found_files.append(fname)

        has_tokenizer = len(found_files) > 0
        has_tokenizer_json = (path / "tokenizer.json").exists()
        has_tokenizer_model = (path / "tokenizer.model").exists()

        tokenizer_type = "unknown"
        if has_tokenizer_json:
            tokenizer_type = "huggingface"
        elif has_tokenizer_model:
            tokenizer_type = "sentencepiece"

        return {
            "available": has_tokenizer,
            "type": tokenizer_type,
            "path": str(path),
            "files": found_files,
            "config_exists": (path / "tokenizer_config.json").exists(),
        }

    def load_tokenizer(self, model_path: str | Path) -> object:
        """Load a tokenizer from the given path.

        Returns:
            The loaded tokenizer object.

        Raises:
            TokenizerNotFoundError: If no tokenizer is found.
        """
        path = Path(model_path)
        cache_key = str(path.resolve())

        if cache_key in self._loaded_tokenizers:
            return self._loaded_tokenizers[cache_key]

        detection = self.detect_tokenizer(path)
        if not detection["available"]:
            raise TokenizerNotFoundError(str(path))

        tokenizer = _load_tokenizer_from_path(path)
        if tokenizer is not None:
            self._loaded_tokenizers[cache_key] = tokenizer

        return tokenizer

    def tokenize(self, model_path: str | Path, text: str) -> list[int]:
        """Tokenize text using the tokenizer at the given path."""
        tokenizer = self.load_tokenizer(model_path)
        return _tokenize_text(tokenizer, text)

    def decode(self, model_path: str | Path, token_ids: list[int]) -> str:
        """Decode token IDs back to text."""
        tokenizer = self.load_tokenizer(model_path)
        return _decode_tokens(tokenizer, token_ids)

    def get_vocab_info(self, model_path: str | Path) -> dict:
        """Get vocabulary information from the tokenizer."""
        tokenizer = self.load_tokenizer(model_path)
        return _get_vocab_info(tokenizer)

    def unload_tokenizer(self, model_path: str | Path) -> None:
        """Unload a cached tokenizer."""
        cache_key = str(Path(model_path).resolve())
        self._loaded_tokenizers.pop(cache_key, None)

    def is_loaded(self, model_path: str | Path) -> bool:
        """Check if a tokenizer is already loaded."""
        cache_key = str(Path(model_path).resolve())
        return cache_key in self._loaded_tokenizers


def _load_tokenizer_from_path(path: Path) -> object | None:
    """Load tokenizer using available libraries."""
    try:
        from transformers import AutoTokenizer

        tokenizer: object = AutoTokenizer.from_pretrained(
            str(path), trust_remote_code=True
        )
        logger.info("Loaded tokenizer from %s using transformers", path)
        return tokenizer
    except Exception as e:
        logger.debug("transformers tokenizer loading failed: %s", e)

    try:
        import sentencepiece as spm

        model_file = path / "tokenizer.model"
        if model_file.exists():
            sp: object = spm.SentencePieceProcessor()
            sp.Load(str(model_file))  # type: ignore[attr-defined]
            logger.info("Loaded SentencePiece tokenizer from %s", path)
            return sp
    except Exception as e:
        logger.debug("SentencePiece tokenizer loading failed: %s", e)

    return None


def _tokenize_text(tokenizer: object, text: str) -> list[int]:
    """Tokenize text using the loaded tokenizer."""
    try:
        if hasattr(tokenizer, "encode"):
            result: object = tokenizer.encode(text)
            if isinstance(result, list):
                return result
            if hasattr(result, "ids"):
                return list(result.ids)
        if callable(tokenizer):
            result = tokenizer(text)
            if isinstance(result, dict) and "input_ids" in result:
                ids = result["input_ids"]
                if hasattr(ids, "tolist"):
                    return list(ids.tolist())
                return list(ids)
    except Exception as e:
        logger.debug("Tokenization failed: %s", e)
    return []


def _decode_tokens(tokenizer: object, token_ids: list[int]) -> str:
    """Decode token IDs to text."""
    try:
        if hasattr(tokenizer, "decode"):
            return str(tokenizer.decode(token_ids))
    except Exception as e:
        logger.debug("Decoding failed: %s", e)
    return ""


def _get_vocab_info(tokenizer: object) -> dict:
    """Get vocabulary info from tokenizer."""
    info: dict = {"vocab_size": None, "model_max_length": None}

    import contextlib

    if hasattr(tokenizer, "vocab_size"):
        with contextlib.suppress(Exception):
            info["vocab_size"] = tokenizer.vocab_size()

    if hasattr(tokenizer, "model_max_length"):
        info["model_max_length"] = tokenizer.model_max_length

    if hasattr(tokenizer, "get_vocab"):
        with contextlib.suppress(Exception):
            vocab = tokenizer.get_vocab()
            info["vocab_size"] = len(vocab)

    return info
