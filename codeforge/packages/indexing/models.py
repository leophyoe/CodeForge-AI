from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class FileStatus(str, Enum):
    DISCOVERED = "DISCOVERED"
    INDEXING = "INDEXING"
    INDEXED = "INDEXED"
    CHANGED = "CHANGED"
    DELETED = "DELETED"
    IGNORED = "IGNORED"
    TOO_LARGE = "TOO_LARGE"
    BINARY = "BINARY"
    ERROR = "ERROR"


class SymbolKind(str, Enum):
    MODULE = "module"
    NAMESPACE = "namespace"
    CLASS = "class"
    INTERFACE = "interface"
    STRUCT = "struct"
    ENUM = "enum"
    FUNCTION = "function"
    METHOD = "method"
    CONSTRUCTOR = "constructor"
    PROPERTY = "property"
    VARIABLE = "variable"
    CONSTANT = "constant"
    TYPE = "type"
    PARAMETER = "parameter"


class ImportKind(str, Enum):
    IMPORT = "import"
    FROM_IMPORT = "from_import"
    REQUIRE = "require"
    DYNAMIC_IMPORT = "dynamic_import"


class IndexStatus(str, Enum):
    NOT_INDEXED = "NOT_INDEXED"
    INDEXING = "INDEXING"
    READY = "READY"
    UPDATING = "UPDATING"
    ERROR = "ERROR"


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


def _now() -> float:
    return time.time()


def file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


@dataclass
class Workspace:
    workspace_id: str = field(default_factory=_new_id)
    root_path: str = ""
    name: str = ""
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)
    index_status: IndexStatus = IndexStatus.NOT_INDEXED

    def to_dict(self) -> dict:
        return {
            "workspace_id": self.workspace_id,
            "root_path": self.root_path,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "index_status": self.index_status.value,
        }


@dataclass
class FileRecord:
    file_id: str = field(default_factory=_new_id)
    workspace_id: str = ""
    relative_path: str = ""
    language: str = ""
    size: int = 0
    mtime: float = 0.0
    content_hash: str = ""
    status: FileStatus = FileStatus.DISCOVERED
    symbol_count: int = 0
    parse_status: str = "OK"
    is_binary: bool = False

    def to_dict(self) -> dict:
        return {
            "file_id": self.file_id,
            "workspace_id": self.workspace_id,
            "relative_path": self.relative_path,
            "language": self.language,
            "size": self.size,
            "mtime": self.mtime,
            "content_hash": self.content_hash,
            "status": self.status.value,
            "symbol_count": self.symbol_count,
            "parse_status": self.parse_status,
            "is_binary": self.is_binary,
        }


@dataclass
class Symbol:
    symbol_id: str = field(default_factory=_new_id)
    file_id: str = ""
    workspace_id: str = ""
    name: str = ""
    kind: SymbolKind = SymbolKind.FUNCTION
    language: str = ""
    start_line: int = 0
    start_column: int = 0
    end_line: int = 0
    end_column: int = 0
    parent_symbol_id: str = ""
    visibility: str = ""
    signature: str = ""
    documentation: str = ""
    qualified_name: str = ""

    def to_dict(self) -> dict:
        return {
            "symbol_id": self.symbol_id,
            "file_id": self.file_id,
            "workspace_id": self.workspace_id,
            "name": self.name,
            "kind": self.kind.value,
            "language": self.language,
            "start_line": self.start_line,
            "start_column": self.start_column,
            "end_line": self.end_line,
            "end_column": self.end_column,
            "parent_symbol_id": self.parent_symbol_id,
            "visibility": self.visibility,
            "signature": self.signature,
            "documentation": self.documentation,
            "qualified_name": self.qualified_name,
        }


@dataclass
class ImportReference:
    import_id: str = field(default_factory=_new_id)
    file_id: str = ""
    workspace_id: str = ""
    import_path: str = ""
    import_kind: ImportKind = ImportKind.IMPORT
    imported_names: list[str] = field(default_factory=list)
    line: int = 0

    def to_dict(self) -> dict:
        return {
            "import_id": self.import_id,
            "file_id": self.file_id,
            "workspace_id": self.workspace_id,
            "import_path": self.import_path,
            "import_kind": self.import_kind.value,
            "imported_names": self.imported_names,
            "line": self.line,
        }


@dataclass
class ExportReference:
    export_id: str = field(default_factory=_new_id)
    file_id: str = ""
    workspace_id: str = ""
    export_name: str = ""
    symbol_id: str = ""
    line: int = 0

    def to_dict(self) -> dict:
        return {
            "export_id": self.export_id,
            "file_id": self.file_id,
            "workspace_id": self.workspace_id,
            "export_name": self.export_name,
            "symbol_id": self.symbol_id,
            "line": self.line,
        }


@dataclass
class Dependency:
    dependency_id: str = field(default_factory=_new_id)
    source_file_id: str = ""
    target_file_id: str = ""
    workspace_id: str = ""
    import_path: str = ""
    resolved: bool = False

    def to_dict(self) -> dict:
        return {
            "dependency_id": self.dependency_id,
            "source_file_id": self.source_file_id,
            "target_file_id": self.target_file_id,
            "workspace_id": self.workspace_id,
            "import_path": self.import_path,
            "resolved": self.resolved,
        }


@dataclass
class IndexJob:
    job_id: str = field(default_factory=_new_id)
    workspace_id: str = ""
    status: JobStatus = JobStatus.QUEUED
    files_total: int = 0
    files_processed: int = 0
    files_failed: int = 0
    symbols_extracted: int = 0
    created_at: float = field(default_factory=_now)
    started_at: float = 0.0
    completed_at: float = 0.0
    error_message: str = ""
    cancel_requested: bool = False

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "workspace_id": self.workspace_id,
            "status": self.status.value,
            "files_total": self.files_total,
            "files_processed": self.files_processed,
            "files_failed": self.files_failed,
            "symbols_extracted": self.symbols_extracted,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
        }


@dataclass
class ProjectStructure:
    workspace_id: str = ""
    root_path: str = ""
    directories: list[str] = field(default_factory=list)
    files: list[dict] = field(default_factory=list)
    languages: dict[str, int] = field(default_factory=dict)
    statistics: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "workspace_id": self.workspace_id,
            "root_path": self.root_path,
            "directories": self.directories,
            "files": self.files,
            "languages": self.languages,
            "statistics": self.statistics,
        }
