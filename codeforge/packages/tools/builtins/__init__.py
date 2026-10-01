"""Built-in tools for Phase 9."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .analysis_tools import (
    FindDependenciesTool,
    FindReferencesTool,
    FindSymbolTool,
    GetDiagnosticsTool,
    GetSymbolTool,
)
from .execution_tools import RunCommandTool
from .git_tools import GitDiffTool, GitLogTool, GitStatusTool
from .read_tools import GetProjectStructureTool, ListDirectoryTool, ReadFileTool
from .search_tools import SearchCodeTool, SearchFilesTool
from .write_tools import EditFileTool, WriteFileTool

if TYPE_CHECKING:
    from codeforge.packages.tools.manager import ToolManager

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
    "WriteFileTool",
    "EditFileTool",
    "RunCommandTool",
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
    WriteFileTool(),
    EditFileTool(),
    RunCommandTool(),
]

# Tools that mutate state — require USER_APPROVAL policy config to run.
APPROVAL_TOOLS = ("write_file", "edit_file", "run_command")


def build_tool_manager() -> ToolManager:
    """Fully wired ToolManager: all builtins registered + approval config.

    Shared by the API router and the CLI so policy stays identical.
    """
    from codeforge.packages.tools.manager import ToolManager
    from codeforge.packages.tools.models import PermissionLevel
    from codeforge.packages.tools.policy import ToolPolicyConfig

    manager = ToolManager()
    for tool in ALL_BUILTINS:
        manager.registry.register(tool)
    for name in APPROVAL_TOOLS:
        manager.policy.configure(name, ToolPolicyConfig(permission=PermissionLevel.USER_APPROVAL))
    return manager
