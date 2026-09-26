from __future__ import annotations

from typing import TYPE_CHECKING

from .lexical import LexicalSearch
from .symbol import SymbolSearch

if TYPE_CHECKING:
    from .models import SearchQuery, SearchResult
    from .semantic import SemanticSearch


class HybridSearch:
    def __init__(
        self,
        lexical: LexicalSearch | None = None,
        symbol_search: SymbolSearch | None = None,
        semantic: SemanticSearch | None = None,
        lexical_weight: float = 0.3,
        semantic_weight: float = 0.4,
        symbol_weight: float = 0.3,
    ) -> None:
        self.lexical = lexical or LexicalSearch()
        self.symbol_search = symbol_search or SymbolSearch()
        self.semantic = semantic
        self.lexical_weight = lexical_weight
        self.semantic_weight = semantic_weight
        self.symbol_weight = symbol_weight

    def search(
        self,
        query: SearchQuery,
        chunks: list[dict] | None = None,
        symbols: list[dict] | None = None,
    ) -> list[SearchResult]:
        all_results: list[SearchResult] = []

        if chunks:
            lexical_results = self.lexical.search(query, chunks)
            all_results.extend(lexical_results)

        if symbols:
            symbol_results = self.symbol_search.search(query, symbols, chunks)
            all_results.extend(symbol_results)

        if (
            self.semantic
            and self.semantic.is_available()
            and query.mode.value in ("semantic", "hybrid")
        ):
            try:
                semantic_results = self.semantic.search(query)
                all_results.extend(semantic_results)
            except Exception:
                pass

        if not all_results:
            return []

        normalized = self._normalize_scores(all_results)
        merged = self._merge_results(normalized)
        ranked = self._rank_results(merged)

        return ranked[: query.limit]

    def _normalize_scores(self, results: list[SearchResult]) -> list[SearchResult]:
        if not results:
            return results

        by_type: dict[str, list[SearchResult]] = {}
        for r in results:
            by_type.setdefault(r.match_type, []).append(r)

        for _match_type, type_results in by_type.items():
            scores = [r.score for r in type_results]
            if not scores:
                continue
            min_s = min(scores)
            max_s = max(scores)
            range_s = max_s - min_s
            for r in type_results:
                if range_s > 0:
                    r.score = (r.score - min_s) / range_s
                else:
                    r.score = 1.0

        return results

    def _merge_results(self, results: list[SearchResult]) -> dict[str, SearchResult]:
        merged: dict[str, SearchResult] = {}

        for r in results:
            key = r.chunk_id or f"{r.relative_path}:{r.start_line}"

            if key not in merged:
                merged[key] = r
            else:
                existing = merged[key]
                weight = self._get_weight(r.match_type)
                existing.score += r.score * weight

        return merged

    def _rank_results(self, merged: dict[str, SearchResult]) -> list[SearchResult]:
        results = list(merged.values())

        for r in results:
            weight = self._get_weight(r.match_type)
            r.score = r.score * weight

        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def _get_weight(self, match_type: str) -> float:
        weights = {
            "lexical": self.lexical_weight,
            "semantic": self.semantic_weight,
            "symbol": self.symbol_weight,
            "structural": 0.2,
            "hybrid": 1.0,
        }
        return weights.get(match_type, 0.1)
