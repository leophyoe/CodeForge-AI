from __future__ import annotations

import uuid
from dataclasses import dataclass, field


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


@dataclass
class RAGConfig:
    enabled: bool = True
    top_k: int = 8
    max_context_tokens: int = 4000
    include_sources: bool = True
    include_related_context: bool = True
    system_prompt: str = (
        "You are CodeForge AI, a helpful coding assistant. "
        "Answer questions using the provided repository context. "
        "Always cite your sources using [file:line] format."
    )

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "top_k": self.top_k,
            "max_context_tokens": self.max_context_tokens,
            "include_sources": self.include_sources,
            "include_related_context": self.include_related_context,
        }


@dataclass
class RAGQuery:
    workspace_id: str = ""
    query: str = ""
    model: str = ""
    top_k: int = 8
    stream: bool = False
    language: str | None = None
    file_path: str | None = None

    def to_dict(self) -> dict:
        return {
            "workspace_id": self.workspace_id,
            "query": self.query,
            "model": self.model,
            "top_k": self.top_k,
            "stream": self.stream,
        }


@dataclass
class SourceReference:
    file_path: str = ""
    start_line: int = 0
    end_line: int = 0
    symbol: str = ""
    chunk_id: str = ""
    score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "symbol": self.symbol,
            "chunk_id": self.chunk_id,
            "score": self.score,
        }

    def format(self) -> str:
        line_info = f":{self.start_line}-{self.end_line}" if self.start_line else ""
        sym_info = f" ({self.symbol})" if self.symbol else ""
        return f"{self.file_path}{line_info}{sym_info}"


@dataclass
class RAGResponse:
    id: str = field(default_factory=_new_id)
    answer: str = ""
    sources: list[SourceReference] = field(default_factory=list)
    search_results: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "answer": self.answer,
            "sources": [s.to_dict() for s in self.sources],
            "usage": self.usage,
            "metrics": self.metrics,
        }
