"""Tool API endpoints — Phase 9 implementation (+ Phase 10 policy control)."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from codeforge.packages.tools.builtins import build_tool_manager
from codeforge.packages.tools.models import PermissionLevel, ToolExecutionContext

if TYPE_CHECKING:
    from codeforge.packages.tools.manager import ToolManager

router = APIRouter(tags=["tools"])

_manager: ToolManager | None = None


def get_manager() -> ToolManager:
    global _manager
    if _manager is None:
        _manager = build_tool_manager()
    return _manager


def reset_manager() -> None:
    """Drop the singleton (tests)."""
    global _manager
    _manager = None


class ToolExecuteRequest(BaseModel):
    workspace_id: str
    arguments: dict = {}
    request_id: str = ""


class ToolExecuteResponse(BaseModel):
    tool_name: str
    success: bool
    result: dict | list | None = None
    error: str = ""
    metadata: dict = {}
    execution_time_ms: float = 0
    request_id: str = ""
    truncated: bool = False


class ToolPolicyUpdate(BaseModel):
    tool_name: str = Field(min_length=1, max_length=64)
    enabled: bool | None = None
    permission: str | None = None
    timeout_seconds: float | None = Field(default=None, ge=0.1, le=600)
    max_output_bytes: int | None = Field(default=None, ge=1_000, le=10_000_000)
    max_file_size_bytes: int | None = Field(default=None, ge=1_000, le=50_000_000)


# NOTE: static routes (health, policy) MUST be declared before /tools/{tool_name}.
@router.get("/tools/health")
async def tools_health() -> dict:
    manager = get_manager()
    return {
        "status": "healthy",
        "tools_registered": manager.registry.count(),
        "audit_entries": manager.audit.count(),
    }


@router.put("/tools/policy")
async def update_tool_policy(body: ToolPolicyUpdate) -> dict:
    """Enable/disable a tool or raise its permission level at runtime."""
    manager = get_manager()
    if not manager.registry.exists(body.tool_name):
        raise HTTPException(status_code=404, detail=f"Tool not found: {body.tool_name}")

    updates: dict = {}
    if body.enabled is not None:
        updates["enabled"] = body.enabled
    if body.permission is not None:
        try:
            updates["permission"] = PermissionLevel(body.permission)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"invalid permission {body.permission!r}; "
                f"expected {[p.value for p in PermissionLevel]}",
            ) from exc
    if body.timeout_seconds is not None:
        updates["timeout_seconds"] = body.timeout_seconds
    if body.max_output_bytes is not None:
        updates["max_output_bytes"] = body.max_output_bytes
    if body.max_file_size_bytes is not None:
        updates["max_file_size_bytes"] = body.max_file_size_bytes
    if not updates:
        raise HTTPException(status_code=422, detail="nothing to update")

    current = manager.policy.get_config(body.tool_name)
    manager.policy.configure(body.tool_name, replace(current, **updates))
    config = manager.policy.get_config(body.tool_name)
    return {
        "tool_name": body.tool_name,
        "config": {
            "enabled": config.enabled,
            "permission": config.permission.value,
            "timeout_seconds": config.timeout_seconds,
            "max_output_bytes": config.max_output_bytes,
            "max_file_size_bytes": config.max_file_size_bytes,
        },
    }


@router.get("/tools")
async def list_tools() -> list[dict]:
    manager = get_manager()
    return manager.list_tools()


@router.get("/tools/{tool_name}")
async def get_tool(tool_name: str) -> dict:
    manager = get_manager()
    schema = manager.get_tool_schema(tool_name)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")
    return schema


@router.post("/tools/{tool_name}/execute", response_model=ToolExecuteResponse)
async def execute_tool(tool_name: str, request: ToolExecuteRequest) -> ToolExecuteResponse:
    manager = get_manager()

    context = ToolExecutionContext(
        workspace_id=request.workspace_id,
    )
    if request.request_id:
        context.request_id = request.request_id

    result = await manager.execute_tool_async(tool_name, request.arguments, context)

    return ToolExecuteResponse(
        tool_name=result.tool_name,
        success=result.success,
        result=result.result,
        error=result.error,
        metadata=result.metadata,
        execution_time_ms=result.execution_time_ms,
        request_id=result.request_id,
        truncated=result.truncated,
    )
