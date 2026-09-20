"""Embeddings package for local-first vector representations."""

from .cache import EmbeddingCache
from .manager import EmbeddingManager
from .models import Embedding, EmbeddingConfig, EmbeddingResult
from .provider import EmbeddingProvider

__all__ = [
    "Embedding",
    "EmbeddingResult",
    "EmbeddingConfig",
    "EmbeddingProvider",
    "EmbeddingCache",
    "EmbeddingManager",
]
