from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .errors import UnauthorizedWorkspaceError
from .indexer import Indexer
from .storage import Storage

if TYPE_CHECKING:
    from .models import Dependency, FileRecord, IndexJob, Symbol, SymbolKind, Workspace


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
        """Return True when path resolves safely inside root (no escape).

        Uses Path.is_relative_to so a sibling directory sharing the root's
        name prefix (e.g. /tmp/ws-evil vs /tmp/ws) cannot pass as inside.
        """
        try:
            resolved = path.resolve()
            root_resolved = root.resolve()
        except (OSError, ValueError):
            return False
        return resolved.is_relative_to(root_resolved)

    def create_workspace(self, root_path: str, name: str = "") -> Workspace:
        validated = self.validate_workspace_path(root_path)
        return self.indexer.create_workspace(str(validated), name)

    def get_workspace(self, workspace_id: str) -> Workspace | None:
        return self.indexer.get_workspace(workspace_id)

    def list_workspaces(self) -> list[Workspace]:
        return self.indexer.list_workspaces()

    def delete_workspace(self, workspace_id: str) -> bool:
        return self.indexer.delete_workspace(workspace_id)

    def index_workspace(self, workspace_id: str, background: bool = True) -> IndexJob:
        return self.indexer.index_workspace(workspace_id, background)

    def refresh_file(self, workspace_id: str, relative_path: str) -> FileRecord | None:
        return self.indexer.refresh_file(workspace_id, relative_path)

    def get_project_structure(self, workspace_id: str) -> dict:
        return self.indexer.get_project_structure(workspace_id)

    def get_workspace_stats(self, workspace_id: str) -> dict:
        return self.storage.get_workspace_stats(workspace_id)

    def find_symbols(
        self,
        workspace_id: str,
        name: str | None = None,
        kind: SymbolKind | None = None,
        qualified_name: str | None = None,
    ) -> list[Symbol]:
        return self.indexer.storage.find_symbols(workspace_id, name, kind, qualified_name)

    def find_file(self, workspace_id: str, relative_path: str) -> FileRecord | None:
        return self.storage.get_file_by_path(workspace_id, relative_path)

    def find_files(self, workspace_id: str, language: str | None = None) -> list[FileRecord]:
        files = self.storage.get_workspace_files(workspace_id)
        if language:
            files = [f for f in files if f.language == language]
        return files

    def get_file_symbols(self, file_id: str) -> list[Symbol]:
        return self.storage.get_file_symbols(file_id)

    def get_dependencies(self, workspace_id: str) -> list[Dependency]:
        return self.storage.get_workspace_dependencies(workspace_id)
