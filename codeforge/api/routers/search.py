"""Search endpoint - Phase 8 implementation."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["search"])


class SearchRequest(BaseModel):
    workspace_id: str
    query: str
    mode: str = "hybrid"
    limit: int = 10
    language: str | None = None
    file_path: str | None = None
    symbol: str | None = None


class SearchResultItem(BaseModel):
    chunk_id: str
    content: str
    score: float
    file_path: str = ""
    symbol_name: str = ""
    start_line: int = 0
    end_line: int = 0


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    total: int
    query: str
    mode: str


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    from codeforge.packages.search.hybrid import HybridSearch
    from codeforge.packages.search.models import SearchQuery, SearchMode

    hybrid_search = HybridSearch()

    search_query = SearchQuery(
        query=request.query,
        workspace_id=request.workspace_id,
        mode=SearchMode(request.mode),
        limit=request.limit,
        language=request.language,
        file_path=request.file_path,
        symbol=request.symbol,
    )

    results = await asyncio.to_thread(
        hybrid_search.search, search_query, chunks=[], symbols=[]
    )

    return SearchResponse(
        results=[
            SearchResultItem(
                chunk_id=r.chunk_id,
                content=r.content,
                score=r.score,
                file_path=r.file_path,
                symbol_name=r.symbol_name,
                start_line=r.start_line,
                end_line=r.end_line,
            )
            for r in results
        ],
        total=len(results),
        query=request.query,
        mode=request.mode,
    )


@router.get("/search/modes")
async def search_modes() -> dict:
    return {
        "modes": ["lexical", "symbol", "semantic", "hybrid"],
        "default": "hybrid",
    }
