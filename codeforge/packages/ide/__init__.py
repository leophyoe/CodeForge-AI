"""IDE-facing helpers for editor clients (Pulsar, VS Code, and friends).

The package is deliberately free of FastAPI types so it can be unit tested
without booting the server.
"""

from .completions import (
    CURSOR_MARKER,
    build_completion_prompt,
    clean_completion,
    run_completion,
)
from .config import IDEConfig
from .context import (
    EditorContext,
    build_editor_context,
    render_context,
    render_workspace_context,
    truncate_prefix,
    truncate_suffix,
)
from .explain import (
    ASSIST_ACTIONS,
    AssistAction,
    assist_generation_config,
    build_assist_prompt,
    code_under_discussion,
    is_valid_action,
    run_assist,
)
from .workspace_bridge import WorkspaceBridge

__all__ = [
    "ASSIST_ACTIONS",
    "AssistAction",
    "CURSOR_MARKER",
    "EditorContext",
    "IDEConfig",
    "WorkspaceBridge",
    "assist_generation_config",
    "build_assist_prompt",
    "build_completion_prompt",
    "build_editor_context",
    "clean_completion",
    "code_under_discussion",
    "is_valid_action",
    "render_context",
    "render_workspace_context",
    "run_assist",
    "run_completion",
    "truncate_prefix",
    "truncate_suffix",
]
