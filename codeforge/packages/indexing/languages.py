from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".cs": "csharp",
    ".go": "go",
    ".rs": "rust",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "css",
    ".less": "css",
    ".sql": "sql",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".fish": "bash",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".r": "r",
    ".R": "r",
    ".lua": "lua",
    ".pl": "perl",
    ".pm": "perl",
    ".ex": "elixir",
    ".exs": "elixir",
    ".erl": "erlang",
    ".hs": "haskell",
    ".ml": "ocaml",
    ".mli": "ocaml",
    ".fs": "fsharp",
    ".fsx": "fsharp",
    ".dart": "dart",
    ".vue": "javascript",
    ".svelte": "javascript",
    ".astro": "javascript",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    ".md": "markdown",
    ".rst": "markdown",
    ".txt": "text",
    ".ini": "ini",
    ".cfg": "ini",
    ".conf": "ini",
    ".dockerfile": "dockerfile",
    ".tf": "terraform",
    ".hcl": "terraform",
}

SHEBANG_MAP: dict[str, str] = {
    "python": "python",
    "python3": "python",
    "python2": "python",
    "node": "javascript",
    "nodejs": "javascript",
    "bash": "bash",
    "sh": "bash",
    "zsh": "bash",
    "fish": "bash",
    "ruby": "ruby",
    "perl": "perl",
    "lua": "lua",
    "Rscript": "r",
    "go": "go",
    "rust": "rust",
    "java": "java",
    "php": "php",
}

SUPPORTED_LANGUAGES = {
    "python",
    "javascript",
    "typescript",
    "java",
    "c",
    "cpp",
    "csharp",
    "go",
    "rust",
    "html",
    "css",
    "sql",
    "bash",
    "ruby",
    "php",
    "json",
    "yaml",
    "toml",
    "markdown",
    "text",
}

SOURCED_LANGUAGE_EXTENSIONS = {
    "python",
    "javascript",
    "typescript",
    "java",
    "c",
    "cpp",
    "csharp",
    "go",
    "rust",
    "bash",
    "ruby",
    "php",
}


def detect_language(file_path: Path, content: bytes | None = None) -> str:
    name = file_path.name.lower()
    if name == "dockerfile":
        return "dockerfile"
    if name == "makefile":
        return "makefile"
    suffix = file_path.suffix.lower()
    if suffix in EXTENSION_MAP:
        return EXTENSION_MAP[suffix]
    if content is None:
        try:
            content = file_path.read_bytes()
        except OSError:
            return "unknown"
    if not content:
        return "unknown"
    if content.startswith(b"#!"):
        first_line = content.split(b"\n", 1)[0]
        if first_line:
            line_str = first_line.decode("utf-8", errors="replace")
            parts = line_str.split()
            if len(parts) >= 2:
                interpreter = parts[1].split("/")[-1].strip()
                if interpreter in SHEBANG_MAP:
                    return SHEBANG_MAP[interpreter]
    return "unknown"


def is_source_language(language: str) -> bool:
    return language in SOURCED_LANGUAGE_EXTENSIONS


def is_supported_language(language: str) -> bool:
    return language in SUPPORTED_LANGUAGES
