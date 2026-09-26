from __future__ import annotations

from typing import TYPE_CHECKING

from .models import SearchQuery, SearchResult

if TYPE_CHECKING:
    from codeforge.packages.embeddings.manager import EmbeddingManager
    from codeforge.packages.vector.store import VectorStore


class SemanticSearch:
    def __init__(
        self,
        vector_store: VectorStore,
        embedding_manager: EmbeddingManager,
    ) -> None:
        self.vector_store = vector_store
        self.embedding_manager = embedding_manager

    def search(self, query: SearchQuery) -> list[SearchResult]:
        if not query.query.strip():
            return []

        try:
            result = self.embedding_manager.embed(query.query)
            if not result.embedding:
                return []
            query_embedding = result.embedding.vector
        except Exception:
            return []

        vector_results = self.vector_store.search(
            query_embedding=query_embedding,
            workspace_id=query.workspace_id,
            top_k=query.limit,
        )

        results: list[SearchResult] = []
        for vr in vector_results:
            results.append(
                SearchResult(
                    chunk_id=vr.chunk_id,
                    relative_path=vr.metadata.get("relative_path", ""),
                    language=vr.metadata.get("language", ""),
                    symbol_name=vr.metadata.get("symbol_name", ""),
                    qualified_name=vr.metadata.get("qualified_name", ""),
                    start_line=vr.metadata.get("start_line", 0),
                    end_line=vr.metadata.get("end_line", 0),
                    content=vr.content,
                    score=vr.score,
                    match_type="semantic",
                    metadata=vr.metadata,
                )
            )

        return results

    def is_available(self) -> bool:
        return self.embedding_manager.health_check()
