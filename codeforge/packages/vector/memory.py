from __future__ import annotations

import math

from .models import SearchResult, VectorRecord
from .store import VectorStore


class InMemoryVectorStore(VectorStore):
    def __init__(self) -> None:
        self._records: dict[str, VectorRecord] = {}

    def add(self, record: VectorRecord) -> str:
        self._records[record.id] = record
        return record.id

    def upsert(self, record: VectorRecord) -> str:
        for existing in self._records.values():
            if (
                existing.chunk_id == record.chunk_id
                and existing.workspace_id == record.workspace_id
            ):
                record.id = existing.id
                break
        self._records[record.id] = record
        return record.id

    def delete(self, record_id: str) -> bool:
        if record_id in self._records:
            del self._records[record_id]
            return True
        return False

    def delete_by_workspace(self, workspace_id: str) -> int:
        to_delete = [
            rid for rid, r in self._records.items()
            if r.workspace_id == workspace_id
        ]
        for rid in to_delete:
            del self._records[rid]
        return len(to_delete)

    def delete_by_chunk_id(self, chunk_id: str) -> bool:
        to_delete = [
            rid for rid, r in self._records.items()
            if r.chunk_id == chunk_id
        ]
        for rid in to_delete:
            del self._records[rid]
        return len(to_delete) > 0

    def search(
        self,
        query_embedding: list[float],
        workspace_id: str,
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        candidates = [
            r for r in self._records.values()
            if r.workspace_id == workspace_id
        ]

        if filters:
            for key, value in filters.items():
                candidates = [
                    r for r in candidates
                    if r.metadata.get(key) == value
                ]

        scored: list[tuple[VectorRecord, float]] = []
        for record in candidates:
            score = self._cosine_similarity(query_embedding, record.embedding)
            scored.append((record, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        results: list[SearchResult] = []
        for record, score in scored[:top_k]:
            results.append(SearchResult(
                record_id=record.id,
                chunk_id=record.chunk_id,
                score=score,
                content=record.metadata.get("content", ""),
                metadata=record.metadata,
                match_type="semantic",
            ))

        return results

    def count(self, workspace_id: str | None = None) -> int:
        if workspace_id:
            return sum(1 for r in self._records.values() if r.workspace_id == workspace_id)
        return len(self._records)

    def clear(self) -> int:
        count = len(self._records)
        self._records.clear()
        return count

    def health_check(self) -> bool:
        return True

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        if len(a) != len(b) or not a:
            return 0.0

        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot / (norm_a * norm_b)
