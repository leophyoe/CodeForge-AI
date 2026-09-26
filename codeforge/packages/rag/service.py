from __future__ import annotations

import time
from typing import TYPE_CHECKING

from .context import ContextBuilder
from .models import RAGConfig, RAGQuery, RAGResponse
from .retriever import RAGRetriever

if TYPE_CHECKING:
    from codeforge.packages.search.hybrid import HybridSearch


class RAGService:
    def __init__(
        self,
        hybrid_search: HybridSearch,
        config: RAGConfig | None = None,
        chunks: list[dict] | None = None,
        symbols: list[dict] | None = None,
    ) -> None:
        self.config = config or RAGConfig()
        self.retriever = RAGRetriever(hybrid_search)
        self.context_builder = ContextBuilder(self.config)
        self.chunks = chunks or []
        self.symbols = symbols or []

    def update_context(self, chunks: list[dict], symbols: list[dict]) -> None:
        self.chunks = chunks
        self.symbols = symbols

    def query(self, rag_query: RAGQuery) -> RAGResponse:
        start_time = time.time()

        retrieval_start = time.time()
        search_results = self.retriever.retrieve(
            rag_query,
            chunks=self.chunks,
            symbols=self.symbols,
        )
        retrieval_time = (time.time() - retrieval_start) * 1000

        context_start = time.time()
        context_text, sources = self.context_builder.build_context(search_results)
        context_time = (time.time() - context_start) * 1000

        messages = self.context_builder.build_prompt(rag_query.query, context_text)

        answer = self._generate_answer(messages, rag_query)

        total_time = (time.time() - start_time) * 1000

        return RAGResponse(
            answer=answer,
            sources=sources,
            search_results=search_results,
            usage={
                "context_tokens": self.context_builder.estimate_tokens(context_text),
                "query": rag_query.query,
            },
            metrics={
                "retrieval_time_ms": retrieval_time,
                "context_time_ms": context_time,
                "total_time_ms": total_time,
                "candidates": len(search_results),
                "selected": len(sources),
            },
        )

    def _generate_answer(self, messages: list[dict], rag_query: RAGQuery) -> str:
        context_parts = []
        for msg in messages:
            if msg["role"] == "system" and "RETRIEVED" in msg.get("content", ""):
                context_parts.append(msg["content"])

        if not context_parts:
            return (
                f"I don't have specific repository context to answer '{rag_query.query}'. "
                "Please ensure the workspace is indexed and embeddings are built."
            )

        context = "\n\n".join(context_parts)
        return (
            f"Based on the repository context:\n\n"
            f"{context}\n\n"
            f"Question: {rag_query.query}\n\n"
            f"(Note: Full LLM generation requires a loaded model via GenerationService)"
        )
