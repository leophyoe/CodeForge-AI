"""Agent API endpoints — Phase 11."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from codeforge.packages.agent import (
    AgentConfig,
    AgentEngine,
    AgentSessionStore,
    GenerationLLM,
)
from codeforge.packages.generation import ModelNotLoadedError

router = APIRouter(tags=["agent"])

_store: AgentSessionStore | None = None
_engine: AgentEngine | None = None


def get_store() -> AgentSessionStore:
    global _store
    if _store is None:
        _store = AgentSessionStore()
    return _store


def reset_store() -> None:
    global _store
    _store = None


def get_engine() -> AgentEngine:
    """Default engine: API's GenerationService singleton + shared tools."""
    global _engine
    if _engine is None:
        from codeforge.api.dependencies import get_generation_service
        from codeforge.api.routers.tools import get_manager

        _engine = AgentEngine(
            llm=GenerationLLM(get_generation_service()),
            tool_manager=get_manager(),
        )
    return _engine


def set_engine(engine: AgentEngine | None) -> None:
    """Inject a test engine (None restores the default)."""
    global _engine
    _engine = engine


class AgentRunRequest(BaseModel):
    task: str = Field(min_length=1, max_length=20_000)
    model: str = Field(min_length=1, max_length=128)
    workspace_id: str = Field(default="default", min_length=1, max_length=128)
    max_steps: int = Field(default=10, ge=1, le=50)
    max_tokens: int = Field(default=512, ge=16, le=8192)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    allowed_tools: list[str] | None = Field(default=None, max_length=32)


@router.post("/agent/run")
async def run_agent(body: AgentRunRequest) -> dict:
    """Run an agent task to completion (LLM ↔ tool loop)."""
    config = AgentConfig(
        model_id=body.model,
        workspace_id=body.workspace_id,
        max_steps=body.max_steps,
        max_tokens=body.max_tokens,
        temperature=body.temperature,
        allowed_tools=body.allowed_tools,
    )
    store = get_store()
    session = store.create(task=body.task, config=config)
    try:
        result = await get_engine().run(body.task, config, session)
    except ModelNotLoadedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        store.remove(session.id)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result.to_dict()


@router.get("/agent/tasks")
async def list_agent_tasks(limit: int = 50) -> dict:
    return {"tasks": get_store().list(limit=limit)}


@router.get("/agent/tasks/{task_id}")
async def get_agent_task(task_id: str) -> dict:
    session = get_store().get(task_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    if session.result is None:
        return session.summary()
    return session.result.to_dict()


@router.post("/agent/tasks/{task_id}/cancel")
async def cancel_agent_task(task_id: str) -> dict:
    session = get_store().get(task_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return {"task_id": task_id, "cancelled": session.cancel()}


@router.delete("/agent/tasks/{task_id}")
async def delete_agent_task(task_id: str) -> dict:
    if not get_store().remove(task_id):
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return {"deleted": task_id}


@router.get("/agent/health")
async def agent_health() -> dict:
    store = get_store()
    engine = get_engine()
    return {
        "status": "healthy",
        "sessions": store.count(),
        "tools": len(engine.tool_manager.list_tools()),
    }
