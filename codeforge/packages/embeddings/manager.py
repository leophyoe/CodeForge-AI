from __future__ import annotations

import time

from .cache import EmbeddingCache
from .models import EmbeddingConfig, EmbeddingResult
from .provider import EmbeddingProvider, FallbackEmbeddingProvider


class EmbeddingManager:
    def __init__(
        self,
        config: EmbeddingConfig | None = None,
        cache: EmbeddingCache | None = None,
    ) -> None:
        self.config = config or EmbeddingConfig()
        self.cache = cache or EmbeddingCache()
        self._provider: EmbeddingProvider | None = None

    def get_provider(self) -> EmbeddingProvider:
        if self._provider is None:
            self._provider = FallbackEmbeddingProvider(dimension=self.config.dimension)
        return self._provider

    def set_provider(self, provider: EmbeddingProvider) -> None:
        self._provider = provider
        self.config.dimension = provider.get_dimension()

    def embed(self, text: str, use_cache: bool = True) -> EmbeddingResult:
        model_id = self.config.model
        if use_cache:
            cached = self.cache.get(text, model_id)
            if cached is not None:
                return EmbeddingResult(
                    text=text,
                    embedding=cached,
                    model=model_id,
                    cached=True,
                )

        start = time.time()
        provider = self.get_provider()
        embedding = provider.embed_text(text)
        duration = (time.time() - start) * 1000

        if use_cache:
            self.cache.put(text, model_id, embedding)

        return EmbeddingResult(
            text=text,
            embedding=embedding,
            model=model_id,
            duration_ms=duration,
            cached=False,
        )

    def embed_batch(self, texts: list[str], use_cache: bool = True) -> list[EmbeddingResult]:
        model_id = self.config.model
        results: list[EmbeddingResult | None] = [None] * len(texts)
        uncached_texts: list[tuple[int, str]] = []

        for i, text in enumerate(texts):
            if use_cache:
                cached = self.cache.get(text, model_id)
                if cached is not None:
                    results[i] = EmbeddingResult(
                        text=text,
                        embedding=cached,
                        model=model_id,
                        cached=True,
                    )
                    continue
            uncached_texts.append((i, text))

        if uncached_texts:
            start = time.time()
            provider = self.get_provider()
            batch_embeddings = provider.embed_batch([t for _, t in uncached_texts])
            if len(batch_embeddings) != len(uncached_texts):
                raise ValueError(
                    f"Embedding provider returned {len(batch_embeddings)} vectors "
                    f"for {len(uncached_texts)} texts"
                )
            duration = (time.time() - start) * 1000

            for idx, (orig_idx, text) in enumerate(uncached_texts):
                embedding = batch_embeddings[idx]
                if use_cache:
                    self.cache.put(text, model_id, embedding)
                results[orig_idx] = EmbeddingResult(
                    text=text,
                    embedding=embedding,
                    model=model_id,
                    duration_ms=duration / len(uncached_texts),
                    cached=False,
                )

        if any(r is None for r in results):
            raise ValueError("Embedding batch left unresolved entries")
        return [r for r in results if r is not None]

    def get_dimension(self) -> int:
        return self.get_provider().get_dimension()

    def health_check(self) -> bool:
        return self.get_provider().health_check()

    def get_model_info(self) -> dict:
        return self.get_provider().get_model_info()

    def clear_cache(self) -> int:
        return self.cache.clear()

    def close(self) -> None:
        self.cache.close()
