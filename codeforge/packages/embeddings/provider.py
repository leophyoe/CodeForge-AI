from __future__ import annotations

import abc

from .models import Embedding


class EmbeddingProvider(abc.ABC):
    @abc.abstractmethod
    def embed_text(self, text: str) -> Embedding:
        pass

    @abc.abstractmethod
    def embed_batch(self, texts: list[str]) -> list[Embedding]:
        pass

    @abc.abstractmethod
    def get_dimension(self) -> int:
        pass

    @abc.abstractmethod
    def get_model_info(self) -> dict:
        pass

    @abc.abstractmethod
    def health_check(self) -> bool:
        pass


class FallbackEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension
        self._model_info = {
            "name": "fallback-hash",
            "dimension": dimension,
            "device": "cpu",
            "type": "deterministic-hash",
        }

    def embed_text(self, text: str) -> Embedding:
        import hashlib
        import struct

        h = hashlib.sha512(text.encode("utf-8")).digest()
        floats = []
        for i in range(0, min(len(h), self.dimension * 4), 4):
            chunk = h[i : i + 4]
            if len(chunk) == 4:
                val = struct.unpack("f", chunk)[0]
                floats.append(val)
        while len(floats) < self.dimension:
            floats.append(0.0)
        floats = floats[: self.dimension]
        embedding = Embedding(vector=floats, dimension=self.dimension)
        embedding.normalize_vector()
        return embedding

    def embed_batch(self, texts: list[str]) -> list[Embedding]:
        return [self.embed_text(t) for t in texts]

    def get_dimension(self) -> int:
        return self.dimension

    def get_model_info(self) -> dict:
        return self._model_info

    def health_check(self) -> bool:
        return True
