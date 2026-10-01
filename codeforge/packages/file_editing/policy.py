"""Security policy for file editing (workspace boundary + sensitive files)."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

from .errors import PathTraversalError, SensitiveFileBlockedError, WorkspaceAccessError

DEFAULT_SENSITIVE_PATTERNS = [
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "credentials.json",
    "secrets.json",
    "*.secret",
]


@dataclass
class FileEditPolicyConfig:
    """Limits and restrictions applied to every file edit."""

    workspace_root: str = "workspaces"
    max_file_size_bytes: int = 2_000_000
    max_write_bytes: int = 2_000_000
    sensitive_patterns: list[str] = field(default_factory=lambda: list(DEFAULT_SENSITIVE_PATTERNS))


class FileEditPolicy:
    """Resolves and validates paths against the workspace boundary."""

    def __init__(self, config: FileEditPolicyConfig | None = None) -> None:
        self.config = config or FileEditPolicyConfig()

    def resolve(self, workspace_id: str, rel_path: str) -> Path:
        """Resolve ``rel_path`` inside ``workspaces/<workspace_id>``.

        Raises :class:`WorkspaceAccessError` for empty ids and
        :class:`PathTraversalError` for escapes (symlink-safe via resolve()).
        """
        if not workspace_id:
            raise WorkspaceAccessError(workspace_id, rel_path)
        if not rel_path or not rel_path.strip():
            raise WorkspaceAccessError(workspace_id, rel_path)

        workspace = (Path(self.config.workspace_root) / workspace_id).resolve()
        candidate = (workspace / rel_path).resolve()
        if not candidate.is_relative_to(workspace):
            raise PathTraversalError(rel_path)
        return candidate

    def is_sensitive(self, rel_path: str) -> bool:
        """True if the path matches a sensitive-file pattern (.env, *.key...)."""
        basename = Path(rel_path).name
        for pattern in self.config.sensitive_patterns:
            if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(basename, pattern):
                return True
        return False

    def check_read(self, workspace_id: str, rel_path: str) -> Path:
        resolved = self.resolve(workspace_id, rel_path)
        if self.is_sensitive(rel_path):
            raise SensitiveFileBlockedError(rel_path)
        return resolved

    def check_write(self, workspace_id: str, rel_path: str) -> Path:
        resolved = self.resolve(workspace_id, rel_path)
        if self.is_sensitive(rel_path):
            raise SensitiveFileBlockedError(rel_path)
        return resolved

    def to_dict(self) -> dict:
        return {
            "workspace_root": self.config.workspace_root,
            "max_file_size_bytes": self.config.max_file_size_bytes,
            "max_write_bytes": self.config.max_write_bytes,
            "sensitive_patterns": list(self.config.sensitive_patterns),
        }
