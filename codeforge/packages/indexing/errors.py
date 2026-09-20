class IndexingError(Exception):
    """Base indexing error."""


class WorkspaceError(IndexingError):
    """Workspace validation error."""


class UnauthorizedWorkspaceError(WorkspaceError):
    """Workspace not in allowed roots."""


class PathTraversalError(WorkspaceError):
    """Path traversal attempt detected."""


class SymlinkEscapeError(WorkspaceError):
    """Symlink resolves outside workspace."""


class ScannerError(IndexingError):
    """File scanning error."""


class ParseError(IndexingError):
    """Parse error."""


class StorageError(IndexingError):
    """Storage error."""


class JobError(IndexingError):
    """Indexing job error."""


class JobCancelledError(JobError):
    """Job was cancelled."""


class LanguageNotSupportedError(IndexingError):
    """Language not supported."""
