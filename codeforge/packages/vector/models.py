from __future__ import annotations

import uuid
from dataclasses import dataclass, field


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


@dataclass
class VectorRecord:
    id: str = field(default_factory=_new_id)
    chunk_id: str = ""
    workspace_id: str = ""
    embedding: list[float] = field(default_factory=list)
    content_hash: str = ""
    embedding_model: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "chunk_id": self.chunk_id,
            "workspace_id": self.workspace_id,
            "content_hash": self.content_hash,
            "embedding_model": self.embedding_model,
            "metadata": self.metadata,
            "dimension": len(self.embedding),
        }


@dataclass
class SearchResult:
    record_id: str = ""
    chunk_id: str = ""
    score: float = 0.0
    content: str = ""
    metadata: dict = field(default_factory=dict)
    match_type: str = "semantic"

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "chunk_id": self.chunk_id,
            "score": self.score,
            "content": self.content[:200],
            "metadata": self.metadata,
            "match_type": self.match_type,
        }
