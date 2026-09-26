"""Tool API endpoints — Phase 9 implementation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from codeforge.packages.tools.builtins import ALL_BUILTINS
from codeforge.packages.tools.manager import ToolManager
from codeforge.packages.tools.models import ToolExecutionContext

router = APIRouter(tags=["tools"])

_manager: ToolManager | None = None


def get_manager() -> ToolManager:
    global _manager
    if _manager is None:
        _manager = ToolManager()
        for tool in ALL_BUILTINS:
            _manager.registry.register(tool)
    return _manager


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

    result = manager.execute_tool(tool_name, request.arguments, context)

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


@router.get("/tools/health")
async def tools_health() -> dict:
    manager = get_manager()
    return {
        "status": "healthy",
        "tools_registered": manager.registry.count(),
        "audit_entries": manager.audit.count(),
    }
