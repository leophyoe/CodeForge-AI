"""Built-in tools for Phase 9."""

from .analysis_tools import (
    FindDependenciesTool,
    FindReferencesTool,
    FindSymbolTool,
    GetDiagnosticsTool,
    GetSymbolTool,
)
from .git_tools import GitDiffTool, GitLogTool, GitStatusTool
from .read_tools import GetProjectStructureTool, ListDirectoryTool, ReadFileTool
from .search_tools import SearchCodeTool, SearchFilesTool

__all__ = [
    "ReadFileTool",
    "ListDirectoryTool",
    "GetProjectStructureTool",
    "SearchFilesTool",
    "SearchCodeTool",
    "FindSymbolTool",
    "GetSymbolTool",
    "FindReferencesTool",
    "FindDependenciesTool",
    "GetDiagnosticsTool",
    "GitStatusTool",
    "GitDiffTool",
    "GitLogTool",
]

ALL_BUILTINS = [
    ReadFileTool(),
    ListDirectoryTool(),
    GetProjectStructureTool(),
    SearchFilesTool(),
    SearchCodeTool(),
    FindSymbolTool(),
    GetSymbolTool(),
    FindReferencesTool(),
    FindDependenciesTool(),
    GetDiagnosticsTool(),
    GitStatusTool(),
    GitDiffTool(),
    GitLogTool(),
]
