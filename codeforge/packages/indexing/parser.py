from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .errors import ParseError

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class ParseResult:
    source: bytes = b""
    language: str = ""
    has_errors: bool = False
    error_count: int = 0
    error_messages: list[str] = field(default_factory=list)
    tree_root: object = None


class CodeParser:
    def parse(self, source: bytes, language: str) -> ParseResult:
        return ParseResult(source=source, language=language, has_errors=False, error_count=0)

    def parse_file(self, file_path: Path, language: str | None = None) -> ParseResult:
        try:
            source = file_path.read_bytes()
        except OSError as e:
            raise ParseError(f"Cannot read file: {file_path}: {e}") from e
        if language is None:
            from .languages import detect_language

            language = detect_language(file_path)
        return self.parse(source, language)


class RegexParser(CodeParser):
    SYMBOL_PATTERNS: dict[str, list[tuple[str, str]]] = {
        "python": [
            (r"^\s*class\s+(\w+)", "class"),
            (r"^\s*def\s+(\w+)", "function"),
            (r"^\s*async\s+def\s+(\w+)", "function"),
            (r"^\s*import\s+(\w+)", "import"),
            (r"^\s*from\s+([\w.]+)\s+import", "from_import"),
        ],
        "javascript": [
            (r"^\s*function\s+(\w+)", "function"),
            (r"^\s*class\s+(\w+)", "class"),
            (r"^\s*const\s+(\w+)\s*=", "variable"),
            (r"^\s*let\s+(\w+)\s*=", "variable"),
            (r"^\s*var\s+(\w+)\s*=", "variable"),
            (r"^\s*export\s+(?:default\s+)?function\s+(\w+)", "function"),
            (r"^\s*export\s+(?:default\s+)?class\s+(\w+)", "class"),
            (r"^\s*import\s+.*from\s+['\"]([^'\"]+)['\"]", "import"),
            (r"^\s*const\s+.*=\s*require\s*\(\s*['\"]([^'\"]+)['\"]", "require"),
        ],
        "typescript": [
            (r"^\s*function\s+(\w+)", "function"),
            (r"^\s*class\s+(\w+)", "class"),
            (r"^\s*interface\s+(\w+)", "interface"),
            (r"^\s*type\s+(\w+)", "type"),
            (r"^\s*enum\s+(\w+)", "enum"),
            (r"^\s*const\s+(\w+)\s*=", "variable"),
            (r"^\s*let\s+(\w+)\s*=", "variable"),
            (r"^\s*export\s+(?:default\s+)?function\s+(\w+)", "function"),
            (r"^\s*export\s+(?:default\s+)?class\s+(\w+)", "class"),
            (r"^\s*export\s+interface\s+(\w+)", "interface"),
            (r"^\s*export\s+type\s+(\w+)", "type"),
            (r"^\s*export\s+enum\s+(\w+)", "enum"),
            (r"^\s*import\s+.*from\s+['\"]([^'\"]+)['\"]", "import"),
        ],
        "java": [
            (r"^\s*(?:public|private|protected)?\s*(?:static\s+)?class\s+(\w+)", "class"),
            (r"^\s*(?:public|private|protected)?\s*(?:static\s+)?interface\s+(\w+)", "interface"),
            (r"^\s*(?:public|private|protected)?\s*(?:static\s+)?enum\s+(\w+)", "enum"),
            (r"^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:\w+\s+)+(\w+)\s*\(", "method"),
            (r"^\s*import\s+([\w.]+);", "import"),
        ],
        "go": [
            (r"^\s*func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)", "function"),
            (r"^\s*type\s+(\w+)\s+struct", "struct"),
            (r"^\s*type\s+(\w+)\s+interface", "interface"),
            (r"^\s*type\s+(\w+)\s+", "type"),
            (r"^\s*var\s+(\w+)", "variable"),
            (r"^\s*const\s+(\w+)", "constant"),
            (r"^\s*import\s+\"([^\"]+)\"", "import"),
        ],
        "rust": [
            (r"^\s*fn\s+(\w+)", "function"),
            (r"^\s*(?:pub\s+)?struct\s+(\w+)", "struct"),
            (r"^\s*(?:pub\s+)?enum\s+(\w+)", "enum"),
            (r"^\s*(?:pub\s+)?trait\s+(\w+)", "interface"),
            (r"^\s*(?:pub\s+)?impl\s+(?:\w+\s+for\s+)?(\w+)", "impl"),
            (r"^\s*(?:pub\s+)?mod\s+(\w+)", "module"),
            (r"^\s*(?:pub\s+)?const\s+(\w+)", "constant"),
            (r"^\s*(?:pub\s+)?static\s+(\w+)", "variable"),
            (r"^\s*use\s+([\w:]+)", "import"),
        ],
        "c": [
            (r"^\s*(?:static\s+)?(?:inline\s+)?(?:\w+\s+)+(\w+)\s*\(", "function"),
            (r"^\s*(?:struct|union|enum)\s+(\w+)", "struct"),
            (r"^\s*#define\s+(\w+)", "macro"),
            (r"^\s*typedef\s+.*\s+(\w+)\s*;", "type"),
            (r"^\s*#include\s+[<\"]([^>\"]+)[>\"]", "import"),
        ],
        "cpp": [
            (r"^\s*(?:static\s+)?(?:inline\s+)?(?:\w+\s+)+(\w+)\s*\(", "function"),
            (r"^\s*(?:class|struct|enum)\s+(\w+)", "class"),
            (r"^\s*(?:namespace)\s+(\w+)", "namespace"),
            (r"^\s*#define\s+(\w+)", "macro"),
            (r"^\s*#include\s+[<\"]([^>\"]+)[>\"]", "import"),
        ],
        "csharp": [
            (r"^\s*(?:public|private|protected|internal)?\s*(?:static\s+)?class\s+(\w+)", "class"),
            (r"^\s*(?:public|private|protected|internal)?\s*interface\s+(\w+)", "interface"),
            (r"^\s*(?:public|private|protected|internal)?\s*struct\s+(\w+)", "struct"),
            (r"^\s*(?:public|private|protected|internal)?\s*enum\s+(\w+)", "enum"),
            (
                r"^\s*(?:public|private|protected|internal)?\s*(?:static\s+)?(?:\w+\s+)+(\w+)\s*\(",
                "method",
            ),
            (r"^\s*using\s+([\w.]+);", "import"),
        ],
        "bash": [
            (r"^\s*(\w+)\s*\(\s*\)", "function"),
            (r"^\s*function\s+(\w+)", "function"),
            (r"^\s*(\w+)=", "variable"),
        ],
        "ruby": [
            (r"^\s*class\s+(\w+)", "class"),
            (r"^\s*module\s+(\w+)", "module"),
            (r"^\s*def\s+(?:self\.)?(\w+)", "function"),
            (r"^\s*require\s+['\"]([^'\"]+)['\"]", "import"),
            (r"^\s*require_relative\s+['\"]([^'\"]+)['\"]", "import"),
        ],
        "php": [
            (r"^\s*(?:abstract\s+)?class\s+(\w+)", "class"),
            (r"^\s*interface\s+(\w+)", "interface"),
            (r"^\s*(?:public|private|protected)\s+function\s+(\w+)", "method"),
            (r"^\s*function\s+(\w+)", "function"),
            (r"^\s*use\s+([\w\\]+);", "import"),
            (r"^\s*require(?:_once)?\s+['\"]([^'\"]+)['\"]", "import"),
        ],
    }

    IMPORT_PATTERNS: dict[str, list[tuple[str, str]]] = {
        "python": [
            (r"^\s*import\s+([\w.,\s]+)", "import"),
            (r"^\s*from\s+([\w.]+)\s+import\s+(.*)", "from_import"),
        ],
        "javascript": [
            (r"^\s*import\s+.*from\s+['\"]([^'\"]+)['\"]", "import"),
            (r"^\s*const\s+\w+\s*=\s*require\s*\(\s*['\"]([^'\"]+)['\"]", "require"),
        ],
        "typescript": [
            (r"^\s*import\s+.*from\s+['\"]([^'\"]+)['\"]", "import"),
            (r"^\s*import\s*\(\s*['\"]([^'\"]+)['\"]", "dynamic_import"),
        ],
        "java": [
            (r"^\s*import\s+([\w.]+);", "import"),
        ],
        "go": [
            (r"^\s*import\s+\"([^\"]+)\"", "import"),
            (r"^\s*import\s+\(\s*([^)]+)\s*\)", "import"),
        ],
        "rust": [
            (r"^\s*use\s+([\w:]+)", "import"),
        ],
        "c": [
            (r"^\s*#include\s+[<\"]([^>\"]+)[>\"]", "import"),
        ],
        "cpp": [
            (r"^\s*#include\s+[<\"]([^>\"]+)[>\"]", "import"),
        ],
        "csharp": [
            (r"^\s*using\s+([\w.]+);", "import"),
        ],
        "ruby": [
            (r"^\s*require\s+['\"]([^'\"]+)['\"]", "import"),
            (r"^\s*require_relative\s+['\"]([^'\"]+)['\"]", "import"),
        ],
        "php": [
            (r"^\s*use\s+([\w\\]+);", "import"),
        ],
        "bash": [
            (r"^\s*source\s+(['\"]?([^'\"\\s]+))", "import"),
            (r"^\s*\.\s+(['\"]?([^'\"\\s]+))", "import"),
        ],
    }

    def parse(self, source: bytes, language: str) -> ParseResult:
        result = ParseResult(source=source, language=language)
        try:
            text = source.decode("utf-8", errors="replace")
            lines = text.split("\n")
            errors = []
            for i, line in enumerate(lines):
                stripped = line.strip()
                if not stripped or stripped.startswith(("#", "//")):
                    continue
                if language in self.SYMBOL_PATTERNS:
                    for _pattern, _kind in self.SYMBOL_PATTERNS[language]:
                        try:
                            re.match(_pattern, line)
                        except re.error as e:
                            errors.append(f"Line {i + 1}: {e}")
            if errors:
                result.has_errors = True
                result.error_count = len(errors)
                result.error_messages = errors[:10]
        except Exception as e:
            result.has_errors = True
            result.error_count = 1
            result.error_messages = [str(e)]
        return result
