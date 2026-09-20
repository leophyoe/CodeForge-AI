from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


@dataclass
class EmbeddingConfig:
    provider: str = "local"
    model: str = "default"
    device: str = "cpu"
    batch_size: int = 32
    normalize: bool = True
    dimension: int = 384

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "device": self.device,
            "batch_size": self.batch_size,
            "normalize": self.normalize,
            "dimension": self.dimension,
        }


@dataclass
class Embedding:
    vector: list[float]
    dimension: int = 0

    def __post_init__(self) -> None:
        if self.dimension == 0:
            self.dimension = len(self.vector)

    def normalize_vector(self) -> None:
        import math

        norm = math.sqrt(sum(x * x for x in self.vector))
        if norm > 0:
            self.vector = [x / norm for x in self.vector]

    def to_dict(self) -> dict:
        return {"vector": self.vector, "dimension": self.dimension}


@dataclass
class EmbeddingResult:
    id: str = field(default_factory=_new_id)
    text: str = ""
    embedding: Embedding | None = None
    model: str = ""
    duration_ms: float = 0.0
    cached: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text[:100],
            "model": self.model,
            "duration_ms": self.duration_ms,
            "cached": self.cached,
            "dimension": self.embedding.dimension if self.embedding else 0,
        }


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
