"""File editing API endpoints — Phase 10."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from codeforge.packages.file_editing import get_file_edit_manager

router = APIRouter(tags=["files"])

_ERROR_STATUS: dict[str, int] = {
    "file_not_found": 404,
    "file_already_exists": 409,
    "replace_mismatch": 409,
    "path_traversal_error": 403,
    "workspace_access_error": 403,
    "sensitive_file_blocked": 403,
    "file_too_large": 413,
}


def _raise_for(result: dict) -> dict:
    if result.get("success"):
        return result
    code = result.get("error_code", "file_edit_error")
    status = _ERROR_STATUS.get(code, 422)
    raise HTTPException(
        status_code=status,
        detail={"code": code, "message": result.get("error", "file edit failed")},
    )


class FileReadRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=128)
    path: str = Field(min_length=1, max_length=1024)


class FileWriteRequest(FileReadRequest):
    content: str = Field(max_length=5_000_000)
    create_only: bool = False


class StrReplaceRequest(FileReadRequest):
    old: str = Field(min_length=1, max_length=100_000)
    new: str = Field(max_length=100_000)
    replace_all: bool = False


@router.post("/files/read")
async def read_file(body: FileReadRequest) -> dict:
    """Read a workspace file (policy: boundary + sensitive-file checks)."""
    manager = get_file_edit_manager()
    result = manager.read(body.workspace_id, body.path)
    return _raise_for(result.to_dict())


@router.post("/files/write")
async def write_file(body: FileWriteRequest) -> dict:
    """Create or overwrite a workspace file (atomic write)."""
    manager = get_file_edit_manager()
    result = manager.write(body.workspace_id, body.path, body.content, create_only=body.create_only)
    return _raise_for(result.to_dict())


@router.post("/files/str-replace")
async def str_replace(body: StrReplaceRequest) -> dict:
    """Exact-match string replacement with occurrence checks."""
    manager = get_file_edit_manager()
    result = manager.str_replace(
        body.workspace_id,
        body.path,
        body.old,
        body.new,
        replace_all=body.replace_all,
    )
    return _raise_for(result.to_dict())


@router.get("/files/policy")
async def files_policy() -> dict:
    """Active file-editing policy (workspace root, limits, patterns)."""
    return get_file_edit_manager().get_policy()
