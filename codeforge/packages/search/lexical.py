from __future__ import annotations

import re

from .models import SearchQuery, SearchResult


class LexicalSearch:
    def search(
        self,
        query: SearchQuery,
        chunks: list[dict],
    ) -> list[SearchResult]:
        results: list[SearchResult] = []
        pattern = self._build_pattern(query)

        for chunk in chunks:
            content = chunk.get("content", "")
            if not content:
                continue

            if query.language and chunk.get("language") != query.language:
                continue
            if query.file_path and query.file_path not in chunk.get("relative_path", ""):
                continue
            if query.directory and not chunk.get("relative_path", "").startswith(query.directory):
                continue

            score = self._score_content(content, pattern, query)
            if score > 0:
                results.append(SearchResult(
                    chunk_id=chunk.get("chunk_id", ""),
                    file_id=chunk.get("file_id", ""),
                    relative_path=chunk.get("relative_path", ""),
                    language=chunk.get("language", ""),
                    symbol_name=chunk.get("symbol_name", ""),
                    qualified_name=chunk.get("qualified_name", ""),
                    start_line=chunk.get("start_line", 0),
                    end_line=chunk.get("end_line", 0),
                    content=content,
                    score=score,
                    match_type="lexical",
                    metadata=chunk.get("metadata", {}),
                ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:query.limit]

    def _build_pattern(self, query: SearchQuery) -> re.Pattern | None:
        if not query.query:
            return None

        flags = 0 if query.case_sensitive else re.IGNORECASE

        if query.use_regex:
            try:
                return re.compile(re.escape(query.query), flags)
            except re.error:
                return None

        escaped = re.escape(query.query)
        return re.compile(escaped, flags)

    def _score_content(self, content: str, pattern: re.Pattern | None, query: SearchQuery) -> float:
        if not pattern:
            return 0.0

        matches = pattern.findall(content)
        if not matches:
            return 0.0

        exact_count = len(matches)
        content_lower = content.lower()
        query_lower = query.query.lower()

        position_bonus = 1.0
        first_pos = content_lower.find(query_lower)
        if first_pos >= 0:
            relative_pos = first_pos / max(1, len(content))
            position_bonus = 1.0 + (1.0 - relative_pos) * 0.3

        score = min(1.0, exact_count * 0.2) * position_bonus
        return min(1.0, score)
