"""Embeddings endpoint - interface boundary for Phase 8."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["embeddings"])


@router.post("/embeddings")
async def create_embeddings() -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={
            "error": {
                "code": "embeddings_not_implemented",
                "message": "Embedding generation is not implemented yet.",
            }
        },
    )
