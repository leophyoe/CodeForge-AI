"""Terminal API endpoints — Phase 10 safe command execution."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from codeforge.api.dependencies import get_request_id
from codeforge.api.errors import APIError
from codeforge.packages.terminal.errors import TerminalError
from codeforge.packages.terminal.manager import TerminalManager
from codeforge.packages.terminal.models import CommandRequest

router = APIRouter(prefix="/v1/terminal", tags=["terminal"])

_manager: TerminalManager | None = None

_ERROR_STATUS = {
    "COMMAND_VALIDATION_ERROR": 400,
    "WORKSPACE_ACCESS_ERROR": 400,
    "PATH_TRAVERSAL_ERROR": 400,
    "COMMAND_NOT_FOUND": 404,
    "DANGEROUS_COMMAND_BLOCKED": 403,
    "COMMAND_PERMISSION_DENIED": 403,
    "APPROVAL_REQUIRED": 403,
}


def get_manager() -> TerminalManager:
    global _manager
    if _manager is None:
        _manager = TerminalManager()
    return _manager


class TerminalExecuteRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=4096)
    command: str = Field(min_length=1, max_length=1024)
    arguments: list[str] = Field(default_factory=list, max_length=200)
    working_directory: str = Field(default="", max_length=4096)
    timeout: float | None = Field(default=None, gt=0)
    approved: bool = False
    require_approval: bool = True
    max_output_bytes: int | None = Field(default=None, gt=0)


class TerminalExecuteResponse(BaseModel):
    request_id: str
    success: bool
    status: str
    command: str
    arguments: list[str]
    workspace_id: str
    cwd: str = ""
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0
    timed_out: bool = False
    cancelled: bool = False
    truncated: bool = False
    executed: bool = True
    security_classification: str = "safe"
    approval_required: bool = False
    approved: bool = False
    error: str = ""


def _to_api_error(error: TerminalError) -> APIError:
    status_code = _ERROR_STATUS.get(error.code, 500)
    return APIError(
        code=error.code,
        message=str(error),
        status_code=status_code,
        request_id=error.request_id or None,
    )


@router.post("/execute", response_model=TerminalExecuteResponse)
async def execute_command(
    request: TerminalExecuteRequest,
    request_id: str = Depends(get_request_id),  # noqa: ARG001
) -> TerminalExecuteResponse:
    manager = get_manager()
    config = manager.policy.config

    command_request = CommandRequest(
        command=request.command,
        arguments=list(request.arguments),
        workspace_id=request.workspace_id,
        working_directory=request.working_directory,
        timeout_seconds=request.timeout or config.default_timeout,
        max_output_bytes=request.max_output_bytes or config.max_output_bytes,
        require_approval=request.require_approval,
        approved=request.approved,
    )

    try:
        result = await manager.execute(command_request)
    except TerminalError as error:
        raise _to_api_error(error) from error

    return TerminalExecuteResponse(
        request_id=result.request_id,
        success=result.success,
        status=result.status.value,
        command=result.command,
        arguments=result.arguments,
        workspace_id=request.workspace_id,
        cwd=result.cwd,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_ms=result.duration_ms,
        timed_out=result.timed_out,
        cancelled=result.cancelled,
        truncated=result.truncated,
        executed=result.executed,
        security_classification=result.security_classification.value,
        approval_required=result.approval_required,
        approved=result.approved,
        error=result.stderr if not result.success else "",
    )


@router.get("/policy")
async def get_policy(
    request_id: str = Depends(get_request_id),  # noqa: ARG001
) -> dict:
    manager = get_manager()
    return manager.get_policy()


@router.get("/health")
async def terminal_health(
    request_id: str = Depends(get_request_id),  # noqa: ARG001
) -> dict:
    manager = get_manager()
    return {
        "status": "healthy",
        "executor": "asyncio-subprocess",
        "shell_execution": False,
        "active_processes": manager.executor.active_count,
        "audit_entries": manager.audit.count(),
    }
