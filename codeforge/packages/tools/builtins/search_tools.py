"""Built-in search tools for Phase 9."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from codeforge.packages.tools.errors import (
    InvalidToolInputError,
    PathTraversalError,
    ToolExecutionError,
)
from codeforge.packages.tools.models import (
    PermissionLevel,
    ToolCategory,
    ToolExecutionContext,
    ToolResult,
)
from codeforge.packages.tools.tool import Tool


class SearchFilesTool(Tool):
    @property
    def name(self) -> str:
        return "search_files"

    @property
    def description(self) -> str:
        return "Search file paths and names by pattern"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "pattern": {"type": "string"},
                "directory": {"type": "string", "default": "."},
                "limit": {"type": "integer", "default": 50},
            },
            "required": ["workspace_id", "pattern"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "matches": {"type": "array"},
                "total": {"type": "integer"},
            },
        }

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SEARCH

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ_ONLY

    def validate_input(self, arguments: dict[str, Any]) -> None:
        if not arguments.get("workspace_id"):
            raise InvalidToolInputError("workspace_id is required")
        if not arguments.get("pattern"):
            raise InvalidToolInputError("pattern is required")

    def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        start_ms = __import__("time").time() * 1000
        workspace_id = arguments["workspace_id"]
        pattern = arguments["pattern"]
        rel_dir = arguments.get("directory", ".")
        limit = arguments.get("limit", 50)

        workspace_path = Path("workspaces") / workspace_id
        search_dir = (workspace_path / rel_dir).resolve()
        if not str(search_dir).startswith(str(workspace_path.resolve())):
            return self._error(PathTraversalError(rel_dir), context, start_ms)

        if not search_dir.exists():
            return self._error(
                ToolExecutionError(f"Directory not found: {rel_dir}"),
                context,
                start_ms,
            )

        matches: list[str] = []
        try:
            for root, dirs, files in os.walk(search_dir):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                if len(matches) >= limit:
                    break
                for fname in files:
                    if len(matches) >= limit:
                        break
                    if re.search(pattern, fname, re.IGNORECASE):
                        full = Path(root) / fname
                        matches.append(str(full.relative_to(workspace_path)))
        except Exception as e:
            return self._error(
                ToolExecutionError(f"Search failed: {e}"),
                context,
                start_ms,
            )

        return self._success(
            {"matches": matches, "total": len(matches)},
            context,
            start_ms,
        )


class SearchCodeTool(Tool):
    @property
    def name(self) -> str:
        return "search_code"

    @property
    def description(self) -> str:
        return "Search code content with exact, substring, or regex matching"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "query": {"type": "string"},
                "path_filter": {"type": "string"},
                "language": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["workspace_id", "query"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "results": {"type": "array"},
                "total": {"type": "integer"},
            },
        }

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SEARCH

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ_ONLY

    def validate_input(self, arguments: dict[str, Any]) -> None:
        if not arguments.get("workspace_id"):
            raise InvalidToolInputError("workspace_id is required")
        if not arguments.get("query"):
            raise InvalidToolInputError("query is required")

    def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        start_ms = __import__("time").time() * 1000
        workspace_id = arguments["workspace_id"]
        query = arguments["query"]
        path_filter = arguments.get("path_filter")
        lang_filter = arguments.get("language")
        limit = arguments.get("limit", 20)

        workspace_path = Path("workspaces") / workspace_id
        if not workspace_path.exists():
            return self._error(
                ToolExecutionError(f"Workspace not found: {workspace_id}"),
                context,
                start_ms,
            )

        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error:
            pattern = re.compile(re.escape(query), re.IGNORECASE)

        lang_exts = {
            "python": {".py"},
            "javascript": {".js", ".jsx"},
            "typescript": {".ts", ".tsx"},
            "java": {".java"},
            "go": {".go"},
            "rust": {".rs"},
        }
        allowed_exts = lang_exts.get(lang_filter, set()) if lang_filter else set()

        results: list[dict[str, Any]] = []
        try:
            for root, dirs, files in os.walk(workspace_path):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                if len(results) >= limit:
                    break
                for fname in files:
                    if len(results) >= limit:
                        break
                    if allowed_exts and Path(fname).suffix not in allowed_exts:
                        continue
                    if path_filter and path_filter not in root:
                        continue
                    fpath = Path(root) / fname
                    try:
                        content = fpath.read_text(errors="replace")
                    except Exception:
                        continue
                    for i, line in enumerate(content.splitlines(), 1):
                        if pattern.search(line):
                            results.append(
                                {
                                    "file": str(fpath.relative_to(workspace_path)),
                                    "line": i,
                                    "content": line.strip()[:200],
                                }
                            )
                            if len(results) >= limit:
                                break
        except Exception as e:
            return self._error(
                ToolExecutionError(f"Search failed: {e}"),
                context,
                start_ms,
            )

        return self._success(
            {"results": results, "total": len(results)},
            context,
            start_ms,
        )
