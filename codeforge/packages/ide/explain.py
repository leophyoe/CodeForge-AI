"""Prompt builders for the Explain / Fix / Refactor / Tests commands.

Each action is a self-contained prompt: instruction, editor context, optional
workspace context, then the code under discussion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol

from codeforge.packages.generation.schemas import (
    GenerationConfig,
    GenerationRequest,
    GenerationResponse,
)

if TYPE_CHECKING:
    from codeforge.packages.ide.config import IDEConfig
    from codeforge.packages.ide.context import EditorContext

AssistAction = Literal["explain", "fix", "refactor", "tests"]

ASSIST_ACTIONS: tuple[str, ...] = ("explain", "fix", "refactor", "tests")

_INSTRUCTIONS: dict[str, str] = {
    "explain": (
        "Explain what the following {language} code does. Cover its purpose, "
        "control flow, and any edge cases. Use short paragraphs and no preamble."
    ),
    "fix": (
        "Find and fix the bugs in the following {language} code. "
        "Return the corrected code first, then briefly list what you changed."
    ),
    "refactor": (
        "Refactor the following {language} code for clarity and correctness. "
        "Return only the refactored code, then briefly note the changes."
    ),
    "tests": (
        "Write unit tests for the following {language} code. "
        "Return runnable test code only, with no commentary."
    ),
}


class AssistService(Protocol):
    """The slice of GenerationService used by the assist commands."""

    def generate(self, request: GenerationRequest) -> GenerationResponse: ...


def is_valid_action(action: str) -> bool:
    return action in _INSTRUCTIONS


def code_under_discussion(ctx: EditorContext) -> str:
    """Prefer the selection; fall back to the code before the cursor."""
    if ctx.has_selection:
        return ctx.selection
    return ctx.prefix


def build_assist_prompt(
    action: str,
    ctx: EditorContext,
    workspace_context: str = "",
) -> str:
    """Build the prompt for one assist action.

    Raises ``ValueError`` for an unknown action so callers can map it to 422.
    """
    instruction = _INSTRUCTIONS.get(action)
    if instruction is None:
        raise ValueError(f"Unknown action: {action}")

    language = ctx.language or "text"
    sections = [
        instruction.format(language=language),
        (
            f"File: {ctx.file_path or '(unsaved)'}"
            f" | language: {language} | cursor: {ctx.line}:{ctx.column}"
        ),
    ]
    if workspace_context.strip():
        sections.append("## Workspace context\n" + workspace_context.strip())
    sections.append(
        f"## Code\n```{language}\n{code_under_discussion(ctx).strip()}\n```"
    )
    return "\n\n".join(sections)


def assist_generation_config(config: IDEConfig) -> GenerationConfig:
    """Shared generation settings for both blocking and streaming assist."""
    return GenerationConfig(
        max_tokens=config.assist_max_tokens,
        temperature=config.assist_temperature,
    )


def run_assist(
    service: AssistService,
    model: str,
    config: IDEConfig,
    action: str,
    ctx: EditorContext,
    workspace_context: str = "",
) -> dict:
    """Generate the answer for one assist action."""
    prompt = build_assist_prompt(action, ctx, workspace_context)
    request = GenerationRequest(
        prompt=prompt,
        model_id=model,
        config=assist_generation_config(config),
    )
    response = service.generate(request)
    reason = response.finish_reason
    return {
        "action": action,
        "text": response.text.strip(),
        "finish_reason": reason.value if hasattr(reason, "value") else reason,
        "usage": response.usage.to_dict(),
        "model_id": response.model_id,
        "prompt_chars": len(prompt),
    }
