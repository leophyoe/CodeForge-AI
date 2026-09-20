"""Repository Intelligence & Code Indexing (Phase 7)."""

from .errors import (
    IndexingError,
    JobCancelledError,
    JobError,
    LanguageNotSupportedError,
    ParseError,
    PathTraversalError,
    ScannerError,
    StorageError,
    SymlinkEscapeError,
    UnauthorizedWorkspaceError,
    WorkspaceError,
)
from .indexer import Indexer
from .manager import WorkspaceManager
from .models import (
    Dependency,
    ExportReference,
    FileRecord,
    FileStatus,
    ImportKind,
    ImportReference,
    IndexJob,
    IndexStatus,
    JobStatus,
    ProjectStructure,
    Symbol,
    SymbolKind,
    Workspace,
    file_hash,
)
from .scanner import FileScanner
from .storage import Storage

__all__ = [
    "Dependency",
    "ExportReference",
    "FileRecord",
    "FileScanner",
    "FileStatus",
    "ImportKind",
    "ImportReference",
    "Indexer",
    "IndexJob",
    "IndexStatus",
    "IndexingError",
    "JobCancelledError",
    "JobError",
    "JobStatus",
    "LanguageNotSupportedError",
    "PathTraversalError",
    "ParseError",
    "ProjectStructure",
    "ScannerError",
    "Storage",
    "StorageError",
    "Symbol",
    "SymbolKind",
    "SymlinkEscapeError",
    "UnauthorizedWorkspaceError",
    "Workspace",
    "WorkspaceError",
    "WorkspaceManager",
    "file_hash",
]
