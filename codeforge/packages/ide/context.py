"""Editor context extraction and prompt rendering.

The IDE client sends whatever the editor knows (path, language, selection,
prefix/suffix around the cursor).  This module normalises that into an
:class:`EditorContext` and renders workspace chunks/symbols into a prompt
block that is small enough to fit a chat request.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from codeforge.packages.ide.config import IDEConfig

_MAX_SELECTION_CHARS = 4000


@dataclass
class EditorContext:
    """A snapshot of the editor at the moment the user asked for help."""

    file_path: str = ""
    language: str = ""
    workspace_id: str = ""
    root_path: str = ""
    selection: str = ""
    prefix: str = ""
    suffix: str = ""
    line: int = 0
    column: int = 0

    @property
    def has_selection(self) -> bool:
        return bool(self.selection.strip())

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "language": self.language,
            "workspace_id": self.workspace_id,
            "root_path": self.root_path,
            "has_selection": self.has_selection,
            "line": self.line,
            "column": self.column,
        }


def truncate_prefix(text: str, max_chars: int) -> str:
    """Keep the tail of ``text`` — the part nearest the cursor."""
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[-max_chars:]


def truncate_suffix(text: str, max_chars: int) -> str:
    """Keep the head of ``text`` — the part nearest the cursor."""
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars]


def build_editor_context(
    config: IDEConfig,
    *,
    file_path: str = "",
    language: str = "",
    workspace_id: str = "",
    root_path: str = "",
    selection: str = "",
    prefix: str = "",
    suffix: str = "",
    line: int = 0,
    column: int = 0,
) -> EditorContext:
    """Normalise raw editor state, applying the configured size limits."""
    return EditorContext(
        file_path=file_path,
        language=language,
        workspace_id=workspace_id,
        root_path=root_path,
        selection=truncate_prefix(selection, _MAX_SELECTION_CHARS),
        prefix=truncate_prefix(prefix, config.completion_max_prefix_chars),
        suffix=truncate_suffix(suffix, config.completion_max_suffix_chars),
        line=max(0, line),
        column=max(0, column),
    )


def _fence(language: str, body: str) -> str:
    lang = language.strip() or "text"
    return f"```{lang}\n{body.rstrip()}\n```"


def render_workspace_context(
    chunks: list[dict] | None = None,
    symbols: list[dict] | None = None,
    max_chars: int = 4000,
) -> str:
    """Render only the index-derived part (symbols + chunks)."""
    parts: list[str] = []

    if symbols:
        lines = [
            f"- {s.get('kind', '')} {s.get('name', '')} "
            f"({s.get('relative_path', '')}:{s.get('start_line', 0)})"
            for s in symbols
        ]
        parts.append("## Symbols\n" + "\n".join(lines))

    if chunks:
        blocks = []
        for c in chunks:
            body = c.get("content", "")
            if not body:
                continue
            header = f"{c.get('relative_path', '')}:{c.get('start_line', 0)}"
            blocks.append(f"### {header}\n{_fence(c.get('language', ''), body)}")
        if blocks:
            parts.append("## Related code\n" + "\n\n".join(blocks))

    text = "\n\n".join(parts)
    if max_chars > 0 and len(text) > max_chars:
        text = text[:max_chars].rstrip()
    return text


def render_context(
    ctx: EditorContext,
    chunks: list[dict] | None = None,
    symbols: list[dict] | None = None,
    max_chars: int = 8000,
) -> str:
    """Render editor + workspace state into a single prompt block."""
    parts: list[str] = []

    header = [
        f"file: {ctx.file_path}" if ctx.file_path else "file: (unsaved)",
        f"language: {ctx.language}" if ctx.language else "",
        f"cursor: {ctx.line}:{ctx.column}",
    ]
    parts.append("## File\n" + "\n".join(h for h in header if h))

    if ctx.has_selection:
        parts.append("## Selection\n" + _fence(ctx.language, ctx.selection))

    workspace = render_workspace_context(chunks, symbols)
    if workspace:
        parts.append(workspace)

    text = "\n\n".join(parts)
    if max_chars > 0 and len(text) > max_chars:
        text = text[:max_chars].rstrip()
    return text
