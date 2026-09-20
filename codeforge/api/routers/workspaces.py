from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from codeforge.packages.indexing.manager import WorkspaceManager
from codeforge.packages.indexing.models import IndexStatus

router = APIRouter(prefix="/v1/workspaces", tags=["workspaces"])

_manager: WorkspaceManager | None = None


def get_manager() -> WorkspaceManager:
    global _manager
    if _manager is None:
        _manager = WorkspaceManager()
    return _manager


class IndexRequest(BaseModel):
    root: str
    name: str = ""
    watch: bool = False


class WorkspaceResponse(BaseModel):
    workspace_id: str
    root_path: str
    name: str
    created_at: float
    updated_at: float
    index_status: str


class IndexJobResponse(BaseModel):
    job_id: str
    workspace_id: str
    status: str
    files_total: int
    files_processed: int
    files_failed: int
    symbols_extracted: int
    created_at: float
    started_at: float
    completed_at: float
    error_message: str


class SymbolResponse(BaseModel):
    symbol_id: str
    name: str
    kind: str
    language: str
    start_line: int
    end_line: int
    qualified_name: str
    file_id: str


@router.get("")
async def list_workspaces() -> list[WorkspaceResponse]:
    manager = get_manager()
    workspaces = manager.list_workspaces()
    return [
        WorkspaceResponse(
            workspace_id=ws.workspace_id,
            root_path=ws.root_path,
            name=ws.name,
            created_at=ws.created_at,
            updated_at=ws.updated_at,
            index_status=ws.index_status.value,
        )
        for ws in workspaces
    ]


@router.post("/index")
async def index_workspace(request: IndexRequest) -> dict:
    manager = get_manager()
    try:
        ws = manager.create_workspace(request.root, request.name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    job = manager.index_workspace(ws.workspace_id, background=True)
    return {
        "workspace_id": ws.workspace_id,
        "job_id": job.job_id,
        "status": "INDEXING",
    }


@router.get("/{workspace_id}")
async def get_workspace(workspace_id: str) -> WorkspaceResponse:
    manager = get_manager()
    ws = manager.get_workspace(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return WorkspaceResponse(
        workspace_id=ws.workspace_id,
        root_path=ws.root_path,
        name=ws.name,
        created_at=ws.created_at,
        updated_at=ws.updated_at,
        index_status=ws.index_status.value,
    )


@router.get("/{workspace_id}/files")
async def get_workspace_files(
    workspace_id: str,
    language: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
) -> dict:
    manager = get_manager()
    files = manager.find_files(workspace_id, language)
    total = len(files)
    start = (page - 1) * page_size
    end = start + page_size
    page_files = files[start:end]
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "files": [f.to_dict() for f in page_files],
    }


@router.get("/{workspace_id}/structure")
async def get_project_structure(workspace_id: str) -> dict:
    manager = get_manager()
    try:
        structure = manager.get_project_structure(workspace_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return structure


@router.get("/{workspace_id}/symbols")
async def get_workspace_symbols(
    workspace_id: str,
    name: str | None = None,
    kind: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
) -> dict:
    from ..packages.indexing.models import SymbolKind

    manager = get_manager()
    symbol_kind = SymbolKind(kind) if kind else None
    symbols = manager.find_symbols(workspace_id, name, symbol_kind)
    total = len(symbols)
    start = (page - 1) * page_size
    end = start + page_size
    page_symbols = symbols[start:end]
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "symbols": [s.to_dict() for s in page_symbols],
    }


@router.get("/{workspace_id}/symbols/{symbol_id}")
async def get_symbol(workspace_id: str, symbol_id: str) -> dict:
    manager = get_manager()
    symbols = manager.find_symbols(workspace_id)
    for s in symbols:
        if s.symbol_id == symbol_id:
            return s.to_dict()
    raise HTTPException(status_code=404, detail="Symbol not found")


@router.get("/{workspace_id}/dependencies")
async def get_dependencies(workspace_id: str) -> dict:
    manager = get_manager()
    deps = manager.get_dependencies(workspace_id)
    return {
        "dependencies": [d.to_dict() for d in deps],
    }


@router.post("/{workspace_id}/refresh")
async def refresh_workspace(workspace_id: str) -> dict:
    manager = get_manager()
    ws = manager.get_workspace(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    job = manager.index_workspace(workspace_id, background=True)
    return {
        "workspace_id": workspace_id,
        "job_id": job.job_id,
        "status": "INDEXING",
    }


@router.delete("/{workspace_id}")
async def delete_workspace(workspace_id: str) -> dict:
    manager = get_manager()
    deleted = manager.delete_workspace(workspace_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"deleted": True}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> IndexJobResponse:
    manager = get_manager()
    job = manager.indexer.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return IndexJobResponse(
        job_id=job.job_id,
        workspace_id=job.workspace_id,
        status=job.status.value,
        files_total=job.files_total,
        files_processed=job.files_processed,
        files_failed=job.files_failed,
        symbols_extracted=job.symbols_extracted,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
    )


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str) -> dict:
    manager = get_manager()
    cancelled = manager.indexer.cancel_job(job_id)
    return {"cancelled": cancelled}
