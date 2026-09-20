from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SearchMode(str, Enum):
    LEXICAL = "lexical"
    SYMBOL = "symbol"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


@dataclass
class SearchQuery:
    workspace_id: str = ""
    query: str = ""
    mode: SearchMode = SearchMode.HYBRID
    limit: int = 10
    language: str | None = None
    file_path: str | None = None
    symbol: str | None = None
    directory: str | None = None
    case_sensitive: bool = False
    use_regex: bool = False

    def to_dict(self) -> dict:
        return {
            "workspace_id": self.workspace_id,
            "query": self.query,
            "mode": self.mode.value,
            "limit": self.limit,
            "language": self.language,
            "file_path": self.file_path,
            "symbol": self.symbol,
            "directory": self.directory,
        }


@dataclass
class SearchResult:
    chunk_id: str = ""
    file_id: str = ""
    relative_path: str = ""
    language: str = ""
    symbol_name: str = ""
    qualified_name: str = ""
    start_line: int = 0
    end_line: int = 0
    content: str = ""
    score: float = 0.0
    match_type: str = "hybrid"
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "relative_path": self.relative_path,
            "language": self.language,
            "symbol_name": self.symbol_name,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content": self.content[:500],
            "score": self.score,
            "match_type": self.match_type,
        }
