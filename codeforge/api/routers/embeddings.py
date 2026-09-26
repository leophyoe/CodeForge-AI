"""Embeddings endpoint - Phase 8 implementation."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["embeddings"])


class EmbedRequest(BaseModel):
    text: str
    model: str = "default"
    normalize: bool = True


class EmbedBatchRequest(BaseModel):
    texts: list[str]
    model: str = "default"
    normalize: bool = True


class EmbedResponse(BaseModel):
    embedding: list[float]
    model: str
    dimension: int
    cached: bool = False


class EmbedBatchResponse(BaseModel):
    embeddings: list[list[float]]
    model: str
    dimension: int
    count: int


@router.post("/embeddings", response_model=EmbedResponse)
async def create_embedding(request: EmbedRequest) -> EmbedResponse:
    from codeforge.packages.embeddings import EmbeddingConfig, EmbeddingManager
    from codeforge.packages.embeddings.cache import EmbeddingCache

    config = EmbeddingConfig(model=request.model, normalize=request.normalize)
    manager = EmbeddingManager(config=config, cache=EmbeddingCache())

    result = await asyncio.to_thread(manager.embed, request.text)

    if result.embedding is None:
        raise HTTPException(status_code=500, detail="Embedding provider returned no vector")

    return EmbedResponse(
        embedding=result.embedding.vector,
        model=request.model,
        dimension=result.embedding.dimension,
        cached=result.cached,
    )


@router.post("/embeddings/batch", response_model=EmbedBatchResponse)
async def create_embeddings_batch(request: EmbedBatchRequest) -> EmbedBatchResponse:
    from codeforge.packages.embeddings import EmbeddingConfig, EmbeddingManager
    from codeforge.packages.embeddings.cache import EmbeddingCache

    config = EmbeddingConfig(model=request.model, normalize=request.normalize)
    manager = EmbeddingManager(config=config, cache=EmbeddingCache())

    results = await asyncio.to_thread(manager.embed_batch, request.texts)

    vectors: list[list[float]] = []
    dimension = 0
    for r in results:
        if r.embedding is None:
            raise HTTPException(status_code=500, detail="Embedding provider returned no vector")
        vectors.append(r.embedding.vector)
        dimension = r.embedding.dimension

    return EmbedBatchResponse(
        embeddings=vectors,
        model=request.model,
        dimension=dimension,
        count=len(vectors),
    )


@router.get("/embeddings/health")
async def embedding_health() -> dict:
    from codeforge.packages.embeddings import EmbeddingManager
    from codeforge.packages.embeddings.cache import EmbeddingCache

    manager = EmbeddingManager(cache=EmbeddingCache())
    healthy = await asyncio.to_thread(manager.health_check)

    return {"status": "healthy" if healthy else "unhealthy"}


@router.get("/embeddings/config")
async def embedding_config() -> dict:
    from codeforge.packages.embeddings import EmbeddingConfig

    config = EmbeddingConfig()
    return {
        "provider": config.provider,
        "model": config.model,
        "device": config.device,
        "batch_size": config.batch_size,
        "normalize": config.normalize,
        "dimension": config.dimension,
    }
