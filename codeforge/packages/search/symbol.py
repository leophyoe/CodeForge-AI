from __future__ import annotations

from .models import SearchQuery, SearchResult


class SymbolSearch:
    def search(
        self,
        query: SearchQuery,
        symbols: list[dict],
        chunks: list[dict] | None = None,
    ) -> list[SearchResult]:
        results: list[SearchResult] = []
        query_lower = query.query.lower()

        chunk_map: dict[str, dict] = {}
        if chunks:
            for c in chunks:
                chunk_map[c.get("chunk_id", "")] = c

        for sym in symbols:
            name = sym.get("name", "")
            qualified = sym.get("qualified_name", "")
            kind = sym.get("kind", "")

            score = self._score_symbol(query_lower, name, qualified, kind)
            if score <= 0:
                continue

            chunk_id = sym.get("file_id", "")
            chunk = chunk_map.get(chunk_id, {})

            results.append(
                SearchResult(
                    chunk_id=sym.get("symbol_id", chunk_id),
                    file_id=sym.get("file_id", ""),
                    relative_path=chunk.get("relative_path", sym.get("relative_path", "")),
                    language=sym.get("language", ""),
                    symbol_name=name,
                    qualified_name=qualified,
                    start_line=sym.get("start_line", 0),
                    end_line=sym.get("end_line", 0),
                    content=chunk.get("content", ""),
                    score=score,
                    match_type="symbol",
                    metadata={"symbol_kind": kind},
                )
            )

        results.sort(key=lambda r: r.score, reverse=True)
        return results[: query.limit]

    def _score_symbol(self, query_lower: str, name: str, qualified: str, _kind: str) -> float:
        name_lower = name.lower()
        qualified_lower = qualified.lower()

        if name_lower == query_lower:
            return 1.0
        if qualified_lower == query_lower:
            return 0.95
        if query_lower in name_lower:
            return 0.8
        if query_lower in qualified_lower:
            return 0.7

        query_parts = query_lower.split(".")
        if len(query_parts) > 1 and query_parts[-1] in name_lower:
            return 0.6

        name_parts = name_lower.split("_")
        query_words = query_lower.split()
        matches = sum(1 for w in query_words if any(w in np for np in name_parts))
        if matches > 0:
            return 0.3 * (matches / len(query_words))

        return 0.0
