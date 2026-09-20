from __future__ import annotations

from ..search.hybrid import HybridSearch
from ..search.models import SearchQuery
from .models import RAGQuery


class RAGRetriever:
    def __init__(self, hybrid_search: HybridSearch) -> None:
        self.hybrid_search = hybrid_search

    def retrieve(
        self,
        query: RAGQuery,
        chunks: list[dict] | None = None,
        symbols: list[dict] | None = None,
    ) -> list[dict]:
        search_query = SearchQuery(
            workspace_id=query.workspace_id,
            query=query.query,
            limit=query.top_k,
            language=query.language,
            file_path=query.file_path,
        )

        results = self.hybrid_search.search(
            search_query,
            chunks=chunks,
            symbols=symbols,
        )

        return [r.to_dict() for r in results]
