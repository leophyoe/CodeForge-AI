"""IDE integration configuration.

Every value here is a default that the IDE client (or ``CODEFORGE_IDE_*``
environment variables) may override.  Nothing in this module touches the
network or the filesystem so it stays cheap to import.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields

DEFAULT_STOP_SEQUENCES = [
    "\n\n",
    "\ndef ",
    "\nclass ",
    "\nif ",
    "\nfor ",
    "\nwhile ",
    "\nreturn ",
    "\n#",
]

_ENV_PREFIX = "CODEFORGE_IDE_"


@dataclass
class IDEConfig:
    """Runtime configuration for the IDE-facing endpoints."""

    server_url: str = "http://127.0.0.1:8000"
    model: str = ""
    request_timeout: float = 60.0

    completion_enabled: bool = True
    completion_max_tokens: int = 64
    completion_max_prefix_chars: int = 2000
    completion_max_suffix_chars: int = 500
    completion_stop: list[str] = field(default_factory=lambda: list(DEFAULT_STOP_SEQUENCES))

    chat_max_context_chars: int = 8000
    context_max_chunks: int = 8
    context_max_symbols: int = 40

    assist_max_tokens: int = 512
    assist_temperature: float = 0.3

    auto_index: bool = True

    @classmethod
    def from_dict(cls, data: dict | None) -> IDEConfig:
        """Build a config from a plain dict, ignoring unknown keys."""
        if not data:
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    @classmethod
    def from_env(cls, data: dict | None = None) -> IDEConfig:
        """Build a config from ``data`` overlaid on ``CODEFORGE_IDE_*`` vars."""
        base = cls.from_dict(data)
        overrides: dict = {}
        for f in fields(cls):
            raw = os.environ.get(f"{_ENV_PREFIX}{f.name.upper()}")
            if raw is None:
                continue
            overrides[f.name] = _coerce(raw, f.type)
        return base.merge(overrides)

    def merge(self, overrides: dict | None) -> IDEConfig:
        """Return a copy with ``overrides`` applied (unknown keys ignored)."""
        if not overrides:
            return IDEConfig(**self.to_dict())
        known = {f.name for f in fields(self)}
        merged = self.to_dict()
        merged.update({k: v for k, v in overrides.items() if k in known})
        return IDEConfig(**merged)

    def to_dict(self) -> dict:
        return {
            "server_url": self.server_url,
            "model": self.model,
            "request_timeout": self.request_timeout,
            "completion_enabled": self.completion_enabled,
            "completion_max_tokens": self.completion_max_tokens,
            "completion_max_prefix_chars": self.completion_max_prefix_chars,
            "completion_max_suffix_chars": self.completion_max_suffix_chars,
            "completion_stop": list(self.completion_stop),
            "chat_max_context_chars": self.chat_max_context_chars,
            "context_max_chunks": self.context_max_chunks,
            "context_max_symbols": self.context_max_symbols,
            "assist_max_tokens": self.assist_max_tokens,
            "assist_temperature": self.assist_temperature,
            "auto_index": self.auto_index,
        }


def _coerce(raw: str, type_hint: object) -> object:
    """Convert an environment string to the annotated field type."""
    text = str(type_hint)
    if "bool" in text:
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if "int" in text and "float" not in text:
        try:
            return int(raw)
        except ValueError:
            return raw
    if "float" in text:
        try:
            return float(raw)
        except ValueError:
            return raw
    if "list" in text:
        return [part for part in raw.split(",") if part]
    return raw
