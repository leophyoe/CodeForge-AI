"""Core file operations: atomic writes and exact-match string replacement."""

from __future__ import annotations

import contextlib
import difflib
import os
import tempfile
from pathlib import Path

from .errors import (
    FileAlreadyExistsError,
    FileNotFoundEditError,
    FileTooLargeError,
    InvalidEditError,
    StrReplaceMismatchError,
)


def _line_count(text: str) -> int:
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def make_diff(old: str, new: str, path: str) -> str:
    """Unified diff between old and new content (empty when identical)."""
    if old == new:
        return ""
    diff = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    )
    return "".join(diff)


def atomic_write(path: Path, content: str, max_bytes: int) -> int:
    """Write ``content`` atomically (temp file + rename). Returns bytes written."""
    data = content.encode("utf-8")
    if len(data) > max_bytes:
        raise FileTooLargeError(str(path), len(data), max_bytes)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".cf-edit-")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        tmp.replace(path)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise
    return len(data)


def read_text(path: Path, max_bytes: int) -> str:
    if not path.exists():
        raise FileNotFoundEditError(str(path))
    if not path.is_file():
        raise InvalidEditError(f"Not a regular file: {path}")
    size = path.stat().st_size
    if size > max_bytes:
        raise FileTooLargeError(str(path), size, max_bytes)
    return path.read_text(encoding="utf-8", errors="replace")


def write_file(
    path: Path, content: str, *, create_only: bool, max_bytes: int
) -> tuple[int, int, str]:
    """Write content to ``path``.

    Returns ``(bytes_written, lines_after, diff)``. Raises
    :class:`FileAlreadyExistsError` when ``create_only`` and the file exists.
    """
    if not isinstance(content, str):
        raise InvalidEditError("content must be a string")
    existed = path.exists()
    if create_only and existed:
        raise FileAlreadyExistsError(str(path))
    old = read_text(path, max_bytes) if existed else ""
    written = atomic_write(path, content, max_bytes)
    diff = make_diff(old, content, path.name) if existed else ""
    return written, _line_count(content), diff


def str_replace(
    path: Path,
    old: str,
    new: str,
    *,
    replace_all: bool,
    max_bytes: int,
) -> tuple[int, int, int, str, str]:
    """Replace exact occurrences of ``old`` with ``new`` in ``path``.

    Returns ``(replacements, lines_before, lines_after, diff, new_content)``.
    Zero matches or multiple matches without ``replace_all`` raise
    :class:`StrReplaceMismatchError`.
    """
    if not old:
        raise InvalidEditError("old text must be non-empty")
    if old == new:
        raise InvalidEditError("old and new text are identical")

    content = read_text(path, max_bytes)
    count = content.count(old)
    if count == 0:
        raise StrReplaceMismatchError(str(path), 1, 0)
    if count > 1 and not replace_all:
        raise StrReplaceMismatchError(str(path), 1, count)

    updated = content.replace(old, new) if replace_all else content.replace(old, new, 1)
    replacements = count if replace_all else 1
    atomic_write(path, updated, max_bytes)
    diff = make_diff(content, updated, path.name)
    return replacements, _line_count(content), _line_count(updated), diff, updated
