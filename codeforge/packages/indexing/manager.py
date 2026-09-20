from __future__ import annotations

from pathlib import Path

from .errors import UnauthorizedWorkspaceError
from .indexer import Indexer
from .models import Workspace
from .storage import Storage


class WorkspaceManager:
    def __init__(
        self,
        storage: Storage | None = None,
        allowed_roots: list[str] | None = None,
    ) -> None:
        self.storage = storage or Storage()
        self.indexer = Indexer(self.storage)
        self.allowed_roots = [Path(r).resolve() for r in (allowed_roots or [])]

    def validate_workspace_path(self, root_path: str) -> Path:
        resolved = Path(root_path).resolve()

        if not self.allowed_roots:
            return resolved

        for allowed in self.allowed_roots:
            try:
                resolved.relative_to(allowed)
                return resolved
            except ValueError:
                continue

        raise UnauthorizedWorkspaceError(
            f"Workspace path '{root_path}' is not inside any allowed root. "
            f"Allowed roots: {[str(r) for r in self.allowed_roots]}"
        )

    def check_symlink_escape(self, path: Path, root: Path) -> bool:
        try:
            resolved = path.resolve()
            root_resolved = root.resolve()
            str(resolved).startswith(str(root_resolved))
            return True
        except (OSError, ValueError):
            return False

    def create_workspace(self, root_path: str, name: str = "") -> Workspace:
        validated = self.validate_workspace_path(root_path)
        return self.indexer.create_workspace(str(validated), name)

    def get_workspace(self, workspace_id: str) -> Workspace | None:
        return self.indexer.get_workspace(workspace_id)

    def list_workspaces(self) -> list[Workspace]:
        return self.indexer.list_workspaces()

    def delete_workspace(self, workspace_id: str) -> bool:
        return self.indexer.delete_workspace(workspace_id)

    def index_workspace(self, workspace_id: str, background: bool = True):
        return self.indexer.index_workspace(workspace_id, background)

    def refresh_file(self, workspace_id: str, relative_path: str):
        return self.indexer.refresh_file(workspace_id, relative_path)

    def get_project_structure(self, workspace_id: str) -> dict:
        return self.indexer.get_project_structure(workspace_id)

    def get_workspace_stats(self, workspace_id: str) -> dict:
        return self.storage.get_workspace_stats(workspace_id)

    def find_symbols(
        self,
        workspace_id: str,
        name: str | None = None,
        kind=None,
        qualified_name: str | None = None,
    ):
        return self.indexer.storage.find_symbols(workspace_id, name, kind, qualified_name)

    def find_file(self, workspace_id: str, relative_path: str):
        return self.storage.get_file_by_path(workspace_id, relative_path)

    def find_files(self, workspace_id: str, language: str | None = None):
        files = self.storage.get_workspace_files(workspace_id)
        if language:
            files = [f for f in files if f.language == language]
        return files

    def get_file_symbols(self, file_id: str):
        return self.storage.get_file_symbols(file_id)

    def get_dependencies(self, workspace_id: str):
        return self.storage.get_workspace_dependencies(workspace_id)
