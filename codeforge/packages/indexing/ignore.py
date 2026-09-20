from __future__ import annotations

import re
from pathlib import Path

DEFAULT_IGNORE_DIRS = {
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".env",
    "dist",
    "build",
    "target",
    "coverage",
    ".cache",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".idea",
    ".vscode",
    "vendor",
    ".gradle",
    ".maven",
    "Pods",
    ".next",
    ".nuxt",
    "out",
    ".terraform",
    ".vagrant",
}

DEFAULT_IGNORE_FILES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.staging",
}

DEFAULT_IGNORE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".class",
    ".o",
    ".obj",
    ".dll",
    ".so",
    ".dylib",
    ".exe",
    ".bin",
    ".dat",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".ico",
    ".svg",
    ".webp",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".rar",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
}

SECRET_PATTERNS = [
    re.compile(r"\.pem$"),
    re.compile(r"\.key$"),
    re.compile(r"\.p12$"),
    re.compile(r"\.pfx$"),
    re.compile(r"\.keystore$"),
    re.compile(r"id_rsa"),
    re.compile(r"id_ed25519"),
    re.compile(r"credentials"),
    re.compile(r"secret"),
]

BINARY_CHECK_SIZE = 8192


class IgnoreRules:
    def __init__(
        self,
        ignore_dirs: set[str] | None = None,
        ignore_files: set[str] | None = None,
        ignore_extensions: set[str] | None = None,
        custom_patterns: list[str] | None = None,
    ) -> None:
        self.ignore_dirs = ignore_dirs or DEFAULT_IGNORE_DIRS.copy()
        self.ignore_files = ignore_files or DEFAULT_IGNORE_FILES.copy()
        self.ignore_extensions = ignore_extensions or DEFAULT_IGNORE_EXTENSIONS.copy()
        self.gitignore_patterns: list[tuple[str, re.Pattern[str]]] = []
        self.custom_patterns: list[re.Pattern[str]] = []
        if custom_patterns:
            for p in custom_patterns:
                try:
                    self.custom_patterns.append(re.compile(p))
                except re.error:
                    pass

    def load_gitignore(self, gitignore_path: Path) -> None:
        if not gitignore_path.exists():
            return
        try:
            content = gitignore_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("!"):
                continue
            if "/" in line:
                pattern = re.compile(re.escape(line).replace(r"\*\*", ".*").replace(r"\*", "[^/]*"))
            else:
                pattern = re.compile(re.escape(line).replace(r"\*\*", ".*").replace(r"\*", "[^/]*"))
            self.gitignore_patterns.append((line, pattern))

    def should_ignore_dir(self, dir_name: str, rel_path: str = "") -> bool:
        if dir_name in self.ignore_dirs:
            return True
        for _, pattern in self.gitignore_patterns:
            if pattern.search(dir_name) or pattern.search(rel_path):
                return True
        for pattern in self.custom_patterns:
            if pattern.search(dir_name):
                return True
        return False

    def should_ignore_file(self, file_path: Path, rel_path: str = "") -> bool:
        name = file_path.name
        if name in self.ignore_files:
            return True
        suffix = file_path.suffix.lower()
        if suffix in self.ignore_extensions:
            return True
        for pat in SECRET_PATTERNS:
            if pat.search(name) or pat.search(str(file_path)):
                return True
        for _, pattern in self.gitignore_patterns:
            if pattern.search(name) or pattern.search(rel_path):
                return True
        for pattern in self.custom_patterns:
            if pattern.search(name) or pattern.search(rel_path):
                return True
        return False

    def is_secret(self, file_path: Path) -> bool:
        name = file_path.name
        for pat in SECRET_PATTERNS:
            if pat.search(name) or pat.search(str(file_path)):
                return True
        return False


def is_binary_file(file_path: Path, check_size: int = BINARY_CHECK_SIZE) -> bool:
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(check_size)
    except OSError:
        return True
    if not chunk:
        return False
    if b"\x00" in chunk:
        return True
    null_count = chunk.count(b"\x00")
    if null_count > 0 and null_count / len(chunk) > 0.1:
        return True
    return False
