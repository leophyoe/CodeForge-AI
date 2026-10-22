"""IDE endpoints — chat dock context, inline completion, and code actions.

All paths are registered with the ``/v1`` prefix by ``app.py`` (this router
declares none of its own) and share the API-wide auth dependency.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from codeforge.packages.generation.errors import (
    ContextLengthExceededError,
    GenerationConfigError,
    ModelNotLoadedError,
)
from codeforge.packages.ide import (
    ASSIST_ACTIONS,
    IDEConfig,
    WorkspaceBridge,
    assist_generation_config,
    build_assist_prompt,
    build_editor_context,
    is_valid_action,
    render_context,
    render_workspace_context,
    run_assist,
    run_completion,
)
from codeforge.packages.indexing.errors import IndexingError, UnauthorizedWorkspaceError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from codeforge.packages.ide.context import EditorContext

router = APIRouter(tags=["ide"])

_GEN_ERRORS = (
    ModelNotLoadedError,
    ContextLengthExceededError,
    GenerationConfigError,
    ValueError,
)

_service: Any | None = None
_bridge: WorkspaceBridge | None = None


def get_service() -> Any:
    """Generation service used by completions/assist (injectable for tests)."""
    global _service
    if _service is None:
        from codeforge.api.dependencies import get_generation_service

        _service = get_generation_service()
    return _service


def set_service(service: Any | None) -> None:
    global _service
    _service = service


def get_bridge() -> WorkspaceBridge:
    """Workspace index bridge (injectable for tests)."""
    global _bridge
    if _bridge is None:
        _bridge = WorkspaceBridge()
    return _bridge


def set_bridge(bridge: WorkspaceBridge | None) -> None:
    global _bridge
    _bridge = bridge


# ── request models ────────────────────────────────────────────────────────


class EditorState(BaseModel):
    """Everything the editor knows about the cursor position."""

    file_path: str = ""
    language: str = ""
    workspace_id: str = ""
    root_path: str = ""
    selection: str = ""
    prefix: str = ""
    suffix: str = ""
    line: int = Field(default=0, ge=0)
    column: int = Field(default=0, ge=0)


class IDEPayload(BaseModel):
    editor: EditorState = Field(default_factory=EditorState)
    model: str = ""
    settings: dict[str, Any] = Field(default_factory=dict)


class CompletionPayload(IDEPayload):
    pass


class AssistPayload(IDEPayload):
    action: str
    include_workspace: bool = True
    stream: bool = False


class ContextPayload(IDEPayload):
    query: str = ""
    max_chars: int = Field(default=0, ge=0)


class IndexPayload(BaseModel):
    root: str = ""
    workspace_id: str = ""
    force: bool = False
    background: bool = True


# ── helpers ───────────────────────────────────────────────────────────────


def _create_sse_event(data: dict[str, Any] | str) -> str:
    payload = json.dumps(data) if isinstance(data, dict) else data
    return f"data: {payload}\n\n"


def _sse_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }


def _config(settings: dict[str, Any] | None) -> IDEConfig:
    return IDEConfig.from_env().merge(settings)


def _editor_ctx(config: IDEConfig, editor: EditorState) -> EditorContext:
    return build_editor_context(
        config,
        file_path=editor.file_path,
        language=editor.language,
        workspace_id=editor.workspace_id,
        root_path=editor.root_path,
        selection=editor.selection,
        prefix=editor.prefix,
        suffix=editor.suffix,
        line=editor.line,
        column=editor.column,
    )


def _first_model() -> str:
    from codeforge.api.dependencies import get_model_manager

    for entry in get_model_manager().list_models():
        model_id = entry.get("model_id") or entry.get("id") or ""
        if model_id:
            return str(model_id)
    return ""


def _resolve_model(explicit: str, config: IDEConfig) -> str:
    model = (explicit or config.model or _first_model()).strip()
    if not model:
        raise HTTPException(status_code=409, detail="No model available")
    return model


def _workspace_id(ctx: EditorContext) -> str:
    if ctx.workspace_id:
        return ctx.workspace_id
    target = ctx.root_path or ctx.file_path
    if not target:
        return ""
    ws = get_bridge().find_by_root(target)
    return ws.workspace_id if ws else ""


def _relative_path(ctx: EditorContext, workspace_id: str) -> str:
    if not workspace_id or not ctx.file_path:
        return ""
    ws = get_bridge().manager.get_workspace(workspace_id)
    if ws is None:
        return ""
    path = ctx.file_path.replace("\\", "/")
    root = ws.root_path.replace("\\", "/").rstrip("/")
    if root and path.startswith(root + "/"):
        return path[len(root) + 1 :]
    if not path.startswith("/"):
        return path
    return ""


def _gather(
    workspace_id: str,
    ctx: EditorContext,
    config: IDEConfig,
    query: str = "",
) -> tuple[list[dict], list[dict], list[dict]]:
    """Collect file chunks, file symbols and (optionally) search hits."""
    if not workspace_id:
        return [], [], []

    bridge = get_bridge()
    relative = _relative_path(ctx, workspace_id)
    chunks: list[dict] = []
    symbols: list[dict] = []
    if relative:
        chunks = bridge.chunks_for_file(workspace_id, relative, config.context_max_chunks)
        symbols = bridge.symbols_for_file(workspace_id, relative)[: config.context_max_symbols]

    results: list[dict] = []
    if query.strip():
        results = bridge.search(
            workspace_id, query, limit=config.context_max_chunks, language=ctx.language or None
        )
        seen = {c.get("chunk_id") for c in chunks}
        extra = [r for r in results if r.get("chunk_id") not in seen]
        chunks = (chunks + extra)[: config.context_max_chunks]

    return chunks, symbols, results


def _map_generation_errors(exc: Exception) -> HTTPException:
    if isinstance(exc, ModelNotLoadedError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, ContextLengthExceededError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, (GenerationConfigError, ValueError)):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


# ── endpoints ─────────────────────────────────────────────────────────────


@router.post("/ide/completions")
async def ide_completions(payload: CompletionPayload) -> dict:
    """Inline completion for the cursor position."""
    config = _config(payload.settings)
    if not config.completion_enabled:
        raise HTTPException(status_code=400, detail="Inline completion is disabled")

    model = _resolve_model(payload.model, config)
    ctx = _editor_ctx(config, payload.editor)

    try:
        return await asyncio.to_thread(run_completion, get_service(), model, config, ctx)
    except _GEN_ERRORS as exc:
        raise _map_generation_errors(exc) from exc


@router.post("/ide/assist", response_model=None)
async def ide_assist(payload: AssistPayload) -> dict[str, Any] | StreamingResponse:
    """Run one of the Explain / Fix / Refactor / Tests actions."""
    if not is_valid_action(payload.action):
        raise HTTPException(status_code=422, detail=f"Unknown action: {payload.action}")

    config = _config(payload.settings)
    model = _resolve_model(payload.model, config)
    ctx = _editor_ctx(config, payload.editor)

    workspace_context = ""
    if payload.include_workspace:
        workspace_id = _workspace_id(ctx)
        if workspace_id:
            chunks, symbols, _ = _gather(workspace_id, ctx, config)
            workspace_context = render_workspace_context(
                chunks, symbols, config.chat_max_context_chars
            )

    if not payload.stream:
        try:
            return await asyncio.to_thread(
                run_assist, get_service(), model, config, payload.action, ctx, workspace_context
            )
        except _GEN_ERRORS as exc:
            raise _map_generation_errors(exc) from exc

    prompt = build_assist_prompt(payload.action, ctx, workspace_context)
    generation_config = assist_generation_config(config)

    async def _event_stream() -> AsyncIterator[str]:
        try:
            usage: dict[str, Any] = {}
            service = get_service()
            for event in service.stream_generate(prompt, model, generation_config):
                if event.event_type.value == "token":
                    yield _create_sse_event({"type": "token", "text": event.text})
                elif event.event_type.value == "error":
                    yield _create_sse_event({"type": "error", "error": event.error})
                    return
                if event.usage is not None:
                    usage = event.usage.to_dict()
            yield _create_sse_event(
                {"type": "end", "finish_reason": "stop", "usage": usage, "action": payload.action}
            )
            yield _create_sse_event("[DONE]")
        except Exception as exc:
            yield _create_sse_event({"type": "error", "error": str(exc)})

    return StreamingResponse(
        _event_stream(), media_type="text/event-stream", headers=_sse_headers()
    )


@router.post("/ide/context")
async def ide_context(payload: ContextPayload) -> dict[str, Any]:
    """Gather editor + workspace context for a chat message."""
    config = _config(payload.settings)
    ctx = _editor_ctx(config, payload.editor)
    workspace_id = _workspace_id(ctx)
    chunks, symbols, results = _gather(workspace_id, ctx, config, payload.query)

    max_chars = payload.max_chars or config.chat_max_context_chars
    return {
        "workspace_id": workspace_id,
        "context": render_context(ctx, chunks, symbols, max_chars),
        "chunks": chunks,
        "symbols": symbols,
        "results": results,
        "editor": ctx.to_dict(),
    }


@router.post("/ide/index")
async def ide_index(payload: IndexPayload) -> dict[str, Any]:
    """Create or refresh the index for a workspace (auto-index on connect)."""
    bridge = get_bridge()
    workspace_id = payload.workspace_id or None
    root_path = payload.root or None
    if not workspace_id and not root_path:
        raise HTTPException(status_code=422, detail="root or workspace_id is required")

    try:
        ws, job = bridge.ensure_indexed(
            workspace_id=workspace_id,
            root_path=root_path,
            force=payload.force,
            background=payload.background,
        )
    except UnauthorizedWorkspaceError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except IndexingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "workspace_id": ws.workspace_id,
        "root_path": ws.root_path,
        "index_status": ws.index_status.value,
        "job": job.to_dict() if job else None,
        "stats": bridge.stats(ws.workspace_id),
    }


@router.get("/ide/status")
async def ide_status() -> dict[str, Any]:
    """Connection/status payload for the IDE status bar."""
    config = IDEConfig.from_env()
    bridge = get_bridge()
    workspaces = [
        {
            "workspace_id": ws.workspace_id,
            "root_path": ws.root_path,
            "index_status": ws.index_status.value,
        }
        for ws in bridge.manager.list_workspaces()
    ]
    return {
        "server": "codeforge",
        "config": config.to_dict(),
        "model": config.model or _first_model(),
        "workspaces": workspaces,
        "actions": list(ASSIST_ACTIONS),
    }
