from __future__ import annotations

import abc

from .models import SearchResult, VectorRecord


class VectorStore(abc.ABC):
    @abc.abstractmethod
    def add(self, record: VectorRecord) -> str:
        pass

    @abc.abstractmethod
    def upsert(self, record: VectorRecord) -> str:
        pass

    @abc.abstractmethod
    def delete(self, record_id: str) -> bool:
        pass

    @abc.abstractmethod
    def delete_by_workspace(self, workspace_id: str) -> int:
        pass

    @abc.abstractmethod
    def delete_by_chunk_id(self, chunk_id: str) -> bool:
        pass

    @abc.abstractmethod
    def search(
        self,
        query_embedding: list[float],
        workspace_id: str,
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        pass

    @abc.abstractmethod
    def count(self, workspace_id: str | None = None) -> int:
        pass

    @abc.abstractmethod
    def clear(self) -> int:
        pass

    @abc.abstractmethod
    def health_check(self) -> bool:
        pass
