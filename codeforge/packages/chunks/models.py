from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


@dataclass
class ChunkConfig:
    max_chunk_tokens: int = 512
    overlap_tokens: int = 50
    min_chunk_tokens: int = 50

    def to_dict(self) -> dict:
        return {
            "max_chunk_tokens": self.max_chunk_tokens,
            "overlap_tokens": self.overlap_tokens,
            "min_chunk_tokens": self.min_chunk_tokens,
        }


@dataclass
class CodeChunk:
    chunk_id: str = field(default_factory=_new_id)
    workspace_id: str = ""
    file_id: str = ""
    relative_path: str = ""
    language: str = ""
    symbol_id: str = ""
    symbol_name: str = ""
    qualified_name: str = ""
    parent_symbol: str = ""
    start_line: int = 0
    end_line: int = 0
    content: str = ""
    content_hash: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.content_hash and self.content:
            self.content_hash = hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    def token_estimate(self) -> int:
        return max(1, len(self.content) // 4)

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "workspace_id": self.workspace_id,
            "file_id": self.file_id,
            "relative_path": self.relative_path,
            "language": self.language,
            "symbol_id": self.symbol_id,
            "symbol_name": self.symbol_name,
            "qualified_name": self.qualified_name,
            "parent_symbol": self.parent_symbol,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content": self.content,
            "content_hash": self.content_hash,
            "metadata": self.metadata,
        }
