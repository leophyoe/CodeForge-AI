"""Inline completion prompting.

The generation API only accepts a single ``prompt`` (no prefix/suffix pair),
so the fill-in-the-middle contract lives here as a prompt template plus the
cleanup needed to turn raw model output into insertable text.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from codeforge.packages.generation.schemas import (
    GenerationConfig,
    GenerationRequest,
    GenerationResponse,
)

from .context import truncate_prefix, truncate_suffix

if TYPE_CHECKING:
    from codeforge.packages.ide.config import IDEConfig
    from codeforge.packages.ide.context import EditorContext

CURSOR_MARKER = "<CURSOR>"

PROMPT_TEMPLATE = """\
You are a code completion engine. Complete the code at the end of the prefix below.
Return only the text to insert — no explanations, no markdown fences, no repeating the prefix.

File: {file_path}
Language: {language}

What comes after the cursor:
{suffix}

Code up to the cursor:
{prefix}"""


class CompletionService(Protocol):
    """The slice of GenerationService used by completions."""

    def generate(self, request: GenerationRequest) -> GenerationResponse: ...


def build_completion_prompt(ctx: EditorContext, config: IDEConfig) -> str:
    """Build the fill-in-the-middle prompt for a single editor position.

    The suffix is emitted *before* the prefix so the causal model keeps
    generating from the cursor position instead of from the end of the file.
    """
    prefix = truncate_prefix(ctx.prefix, config.completion_max_prefix_chars)
    suffix = truncate_suffix(ctx.suffix, config.completion_max_suffix_chars)
    return PROMPT_TEMPLATE.format(
        file_path=ctx.file_path or "(unsaved)",
        language=ctx.language or "text",
        suffix=suffix or "(end of file)",
        prefix=prefix,
    )


def _strip_fences(text: str) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) >= 2 and lines[0].strip().startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1])
    return text


def _cut_at_stop(text: str, stop_sequences: list[str]) -> str:
    cut = len(text)
    for stop in stop_sequences:
        if not stop:
            continue
        idx = text.find(stop)
        if idx >= 0:
            cut = min(cut, idx)
    return text[:cut]


def _strip_suffix_overlap(text: str, suffix: str) -> str:
    """Drop a leading copy of the suffix's first line when the model echoed it."""
    if not suffix:
        return text
    first_line = next((ln.strip() for ln in suffix.split("\n") if ln.strip()), "")
    if len(first_line) < 4:
        return text
    trimmed = text.rstrip()
    if trimmed.endswith(first_line):
        return trimmed[: -len(first_line)].rstrip()
    return text


def clean_completion(text: str, config: IDEConfig, suffix: str = "") -> str:
    """Turn raw model output into text that is safe to insert at the cursor."""
    if not text:
        return ""
    cleaned = _strip_fences(text)
    cleaned = _cut_at_stop(cleaned, config.completion_stop)
    cleaned = _strip_suffix_overlap(cleaned, suffix)
    return cleaned.strip("\r\n").strip()


def run_completion(
    service: CompletionService,
    model: str,
    config: IDEConfig,
    ctx: EditorContext,
) -> dict:
    """Generate and clean a single inline completion."""
    prompt = build_completion_prompt(ctx, config)
    request = GenerationRequest(
        prompt=prompt,
        model_id=model,
        config=GenerationConfig(
            max_tokens=config.completion_max_tokens,
            temperature=0.2,
            stop_sequences=list(config.completion_stop),
        ),
    )
    response = service.generate(request)
    reason = response.finish_reason
    return {
        "text": clean_completion(response.text, config, ctx.suffix),
        "finish_reason": reason.value if hasattr(reason, "value") else reason,
        "usage": response.usage.to_dict(),
        "model_id": response.model_id,
        "cursor_marker": CURSOR_MARKER,
    }
