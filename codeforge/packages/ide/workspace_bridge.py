"""Bridge between IDE requests and the workspace index.

Thin adapter over :class:`WorkspaceManager` so the IDE router never talks to
storage directly and so the index can be swapped out in tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from codeforge.packages.indexing.manager import WorkspaceManager
    from codeforge.packages.indexing.models import IndexJob, Workspace


class WorkspaceBridge:
    def __init__(self, manager: WorkspaceManager | None = None) -> None:
        self._manager = manager

    @property
    def manager(self) -> WorkspaceManager:
        if self._manager is None:
            from codeforge.packages.indexing.manager import WorkspaceManager

            self._manager = WorkspaceManager()
        return self._manager

    def set_manager(self, manager: WorkspaceManager | None) -> None:
        self._manager = manager

    def find_by_root(self, root_path: str) -> Workspace | None:
        """Return the workspace containing ``root_path``, if any."""
        if not root_path:
            return None
        target = str(root_path).rstrip("/\\")
        for ws in self.manager.list_workspaces():
            root = ws.root_path.rstrip("/\\")
            if not root:
                continue
            if target == root or target.startswith((root + "/", root + "\\")):
                return ws
        return None

    def get_or_create(self, root_path: str) -> Workspace:
        existing = self.find_by_root(root_path)
        if existing is not None:
            return existing
        return self.manager.create_workspace(root_path)

    def ensure_indexed(
        self,
        *,
        workspace_id: str | None = None,
        root_path: str | None = None,
        force: bool = False,
        background: bool = True,
    ) -> tuple[Workspace, IndexJob | None]:
        """Resolve a workspace and (re)index it when needed.

        Returns the workspace plus the job that was started, or ``None`` when
        the index was already fresh and ``force`` was not requested.
        """
        ws = self._resolve(workspace_id, root_path)
        if ws is None and root_path:
            ws = self.manager.create_workspace(root_path)
        if ws is None:
            raise LookupError("No workspace resolved for the requested path")

        if not force and not self._needs_index(ws):
            return ws, None
        job = self.manager.index_workspace(ws.workspace_id, background=background)
        # The job mutates a separately loaded Workspace, so re-read it to avoid
        # handing back a stale index_status.
        refreshed = self.manager.get_workspace(ws.workspace_id)
        return refreshed or ws, job

    def _resolve(self, workspace_id: str | None, root_path: str | None) -> Workspace | None:
        if workspace_id:
            return self.manager.get_workspace(workspace_id)
        if root_path:
            return self.find_by_root(root_path)
        return None

    @staticmethod
    def _needs_index(ws: Workspace) -> bool:
        return ws.index_status.value in ("NOT_INDEXED", "ERROR")

    def chunks_for_file(self, workspace_id: str, relative_path: str, limit: int = 8) -> list[dict]:
        chunks = [
            c
            for c in self.manager.get_workspace_chunks(workspace_id)
            if c.get("relative_path") == relative_path
        ]
        return chunks[:limit] if limit > 0 else chunks

    def symbols_for_file(self, workspace_id: str, relative_path: str) -> list[dict]:
        record = self.manager.find_file(workspace_id, relative_path)
        if record is None:
            return []
        return [s.to_dict() for s in self.manager.get_file_symbols(record.file_id)]

    def search(
        self,
        workspace_id: str,
        query: str,
        *,
        limit: int = 8,
        language: str | None = None,
        file_path: str | None = None,
    ) -> list[dict]:
        from codeforge.packages.search.lexical import LexicalSearch
        from codeforge.packages.search.models import SearchMode, SearchQuery

        if not workspace_id or not query.strip():
            return []
        chunks = self.manager.get_workspace_chunks(workspace_id)
        results = LexicalSearch().search(
            SearchQuery(
                workspace_id=workspace_id,
                query=query,
                mode=SearchMode.LEXICAL,
                limit=limit,
                language=language,
                file_path=file_path,
            ),
            chunks,
        )
        return [r.to_dict() for r in results]

    def stats(self, workspace_id: str) -> dict:
        return self.manager.get_workspace_stats(workspace_id)
