from __future__ import annotations

import re

from .models import ChunkConfig, CodeChunk


class CodeChunker:
    def __init__(self, config: ChunkConfig | None = None) -> None:
        self.config = config or ChunkConfig()

    def chunk_file(
        self,
        source: str,
        language: str,
        relative_path: str = "",
        file_id: str = "",
        workspace_id: str = "",
        symbols: list[dict] | None = None,
    ) -> list[CodeChunk]:
        if not source.strip():
            return []

        if symbols:
            return self._chunk_by_symbols(
                source, language, relative_path, file_id, workspace_id, symbols
            )
        return self._chunk_by_structure(
            source, language, relative_path, file_id, workspace_id
        )

    def _chunk_by_symbols(
        self,
        source: str,
        language: str,
        relative_path: str,
        file_id: str,
        workspace_id: str,
        symbols: list[dict],
    ) -> list[CodeChunk]:
        lines = source.split("\n")
        chunks: list[CodeChunk] = []

        sorted_symbols = sorted(symbols, key=lambda s: s.get("start_line", 0))

        for sym in sorted_symbols:
            start = sym.get("start_line", 0)
            end = sym.get("end_line", start + 10)
            name = sym.get("name", "")
            kind = sym.get("kind", "")
            qualified = sym.get("qualified_name", name)
            parent = sym.get("parent_symbol_id", "")

            start = max(0, start)
            end = min(len(lines), end + 1)
            content = "\n".join(lines[start:end])

            if not content.strip():
                continue

            token_est = max(1, len(content) // 4)
            if token_est > self.config.max_chunk_tokens:
                sub_chunks = self._split_large_chunk(
                    content, lines, start, language, relative_path,
                    file_id, workspace_id, name, qualified, parent
                )
                chunks.extend(sub_chunks)
            else:
                chunks.append(CodeChunk(
                    workspace_id=workspace_id,
                    file_id=file_id,
                    relative_path=relative_path,
                    language=language,
                    symbol_name=name,
                    qualified_name=qualified,
                    parent_symbol=parent,
                    start_line=start,
                    end_line=end - 1,
                    content=content,
                    metadata={"symbol_kind": kind},
                ))

        if not chunks:
            chunks = self._chunk_by_structure(
                source, language, relative_path, file_id, workspace_id
            )

        return chunks

    def _chunk_by_structure(
        self,
        source: str,
        language: str,
        relative_path: str,
        file_id: str,
        workspace_id: str,
    ) -> list[CodeChunk]:
        lines = source.split("\n")
        boundaries = self._find_structure_boundaries(lines, language)

        if not boundaries:
            return self._chunk_by_lines(
                source, language, relative_path, file_id, workspace_id
            )

        chunks: list[CodeChunk] = []
        for start, end, name in boundaries:
            content = "\n".join(lines[start:end])
            if not content.strip():
                continue
            chunks.append(CodeChunk(
                workspace_id=workspace_id,
                file_id=file_id,
                relative_path=relative_path,
                language=language,
                symbol_name=name,
                start_line=start,
                end_line=end - 1,
                content=content,
            ))

        if not chunks:
            return self._chunk_by_lines(
                source, language, relative_path, file_id, workspace_id
            )

        return chunks

    def _chunk_by_lines(
        self,
        source: str,
        language: str,
        relative_path: str,
        file_id: str,
        workspace_id: str,
    ) -> list[CodeChunk]:
        lines = source.split("\n")
        chunks: list[CodeChunk] = []
        chunk_size = 50
        overlap = 5

        i = 0
        while i < len(lines):
            end = min(i + chunk_size, len(lines))
            content = "\n".join(lines[i:end])
            if content.strip():
                chunks.append(CodeChunk(
                    workspace_id=workspace_id,
                    file_id=file_id,
                    relative_path=relative_path,
                    language=language,
                    start_line=i,
                    end_line=end - 1,
                    content=content,
                ))
            i += chunk_size - overlap

        return chunks

    def _find_structure_boundaries(
        self, lines: list[str], language: str
    ) -> list[tuple[int, int, str]]:
        boundaries: list[tuple[int, int, str]] = []
        patterns = self._get_structure_patterns(language)

        for i, line in enumerate(lines):
            stripped = line.strip()
            for pattern, kind in patterns:
                match = re.match(pattern, stripped)
                if match:
                    name = match.group(1) if match.lastindex else ""
                    end = self._find_block_end(lines, i)
                    boundaries.append((i, end, name))
                    break

        return boundaries

    def _get_structure_patterns(self, language: str) -> list[tuple[str, str]]:
        patterns: dict[str, list[tuple[str, str]]] = {
            "python": [
                (r"^class\s+(\w+)", "class"),
                (r"^(?:async\s+)?def\s+(\w+)", "function"),
            ],
            "javascript": [
                (r"^(?:export\s+)?class\s+(\w+)", "class"),
                (r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)", "function"),
            ],
            "typescript": [
                (r"^(?:export\s+)?class\s+(\w+)", "class"),
                (r"^(?:export\s+)?interface\s+(\w+)", "interface"),
                (r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)", "function"),
            ],
            "java": [
                (r"^(?:public|private|protected)?\s*(?:abstract\s+)?class\s+(\w+)", "class"),
                (r"^(?:public|private|protected)\s+(?:static\s+)?(?:\w+\s+)+(\w+)\s*\(", "method"),
            ],
            "go": [
                (r"^func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)", "function"),
                (r"^type\s+(\w+)\s+struct", "struct"),
            ],
            "rust": [
                (r"^(?:pub\s+)?fn\s+(\w+)", "function"),
                (r"^(?:pub\s+)?struct\s+(\w+)", "struct"),
                (r"^(?:pub\s+)?impl\s+(?:\w+\s+for\s+)?(\w+)", "impl"),
            ],
            "c": [
                (r"^(?:static\s+)?(?:\w+\s+)+(\w+)\s*\(", "function"),
            ],
            "cpp": [
                (r"^(?:class|struct)\s+(\w+)", "class"),
                (r"^(?:static\s+)?(?:\w+\s+)+(\w+)\s*\(", "function"),
            ],
            "csharp": [
                (r"^(?:public|private|protected)?\s*class\s+(\w+)", "class"),
                (r"^(?:public|private|protected)\s+(?:static\s+)?(?:\w+\s+)+(\w+)\s*\(", "method"),
            ],
        }
        return patterns.get(language, [])

    def _find_block_end(self, lines: list[str], start: int) -> int:
        if start >= len(lines):
            return len(lines)

        start_indent = len(lines[start]) - len(lines[start].lstrip())

        for i in range(start + 1, len(lines)):
            line = lines[i]
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip())
            if indent <= start_indent and line.strip():
                return i

        return len(lines)

    def _split_large_chunk(
        self,
        content: str,
        lines: list[str],
        start_line: int,
        language: str,
        relative_path: str,
        file_id: str,
        workspace_id: str,
        symbol_name: str,
        qualified_name: str,
        parent_symbol: str,
    ) -> list[CodeChunk]:
        content_lines = content.split("\n")
        chunks: list[CodeChunk] = []
        chunk_size = 30
        overlap = 3

        i = 0
        part = 0
        while i < len(content_lines):
            end = min(i + chunk_size, len(content_lines))
            chunk_content = "\n".join(content_lines[i:end])
            if chunk_content.strip():
                chunks.append(CodeChunk(
                    workspace_id=workspace_id,
                    file_id=file_id,
                    relative_path=relative_path,
                    language=language,
                    symbol_name=f"{symbol_name} (part {part + 1})" if part > 0 else symbol_name,
                    qualified_name=qualified_name,
                    parent_symbol=parent_symbol,
                    start_line=start_line + i,
                    end_line=start_line + end - 1,
                    content=chunk_content,
                    metadata={"symbol_kind": "split", "part": part + 1},
                ))
            part += 1
            i += chunk_size - overlap

        return chunks
