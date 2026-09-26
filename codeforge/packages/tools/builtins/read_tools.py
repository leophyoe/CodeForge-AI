"""Built-in read-only tools for Phase 9."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from codeforge.packages.tools.errors import (
    InvalidToolInputError,
    PathTraversalError,
    SensitiveFileBlockedError,
    ToolExecutionError,
)
from codeforge.packages.tools.models import (
    PermissionLevel,
    ToolCategory,
    ToolExecutionContext,
    ToolResult,
)
from codeforge.packages.tools.tool import Tool


class ReadFileTool(Tool):
    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read file contents with optional line range"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "path": {"type": "string"},
                "start_line": {"type": "integer", "minimum": 1},
                "end_line": {"type": "integer", "minimum": 1},
            },
            "required": ["workspace_id", "path"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "language": {"type": "string"},
                "start_line": {"type": "integer"},
                "end_line": {"type": "integer"},
                "content": {"type": "string"},
                "total_lines": {"type": "integer"},
            },
        }

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.READ

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ_ONLY

    def validate_input(self, arguments: dict[str, Any]) -> None:
        if not arguments.get("path"):
            raise InvalidToolInputError("path is required")
        if not arguments.get("workspace_id"):
            raise InvalidToolInputError("workspace_id is required")

    def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        start_ms = __import__("time").time() * 1000
        workspace_id = arguments["workspace_id"]
        rel_path = arguments["path"]
        start_line = arguments.get("start_line")
        end_line = arguments.get("end_line")

        sensitive = [
            ".env",
            ".env.*",
            "*.pem",
            "*.key",
            "*.p12",
            "*.pfx",
            "credentials.json",
            "secrets.json",
        ]
        import fnmatch

        basename = Path(rel_path).name
        for pat in sensitive:
            if fnmatch.fnmatch(basename, pat) or fnmatch.fnmatch(rel_path, pat):
                return self._error(SensitiveFileBlockedError(rel_path), context, start_ms)

        workspace_path = Path("workspaces") / workspace_id
        full_path = (workspace_path / rel_path).resolve()
        if not str(full_path).startswith(str(workspace_path.resolve())):
            return self._error(PathTraversalError(rel_path), context, start_ms)

        if not full_path.exists():
            return self._error(
                ToolExecutionError(f"File not found: {rel_path}"),
                context,
                start_ms,
            )

        try:
            content = full_path.read_text(errors="replace")
        except Exception as e:
            return self._error(
                ToolExecutionError(f"Failed to read file: {e}"),
                context,
                start_ms,
            )

        lines = content.splitlines()
        total = len(lines)

        if start_line is not None:
            s = max(1, start_line) - 1
            end_idx = end_line if end_line else total
            end_idx = min(end_idx, total)
            lines = lines[s:end_idx]
            content = "\n".join(lines)

        ext = full_path.suffix.lstrip(".")
        lang_map = {
            "py": "python",
            "js": "javascript",
            "ts": "typescript",
            "java": "java",
            "go": "go",
            "rs": "rust",
            "c": "c",
            "cpp": "cpp",
            "h": "c",
            "rb": "ruby",
        }
        language = lang_map.get(ext, ext)

        return self._success(
            {
                "path": rel_path,
                "language": language,
                "start_line": start_line or 1,
                "end_line": end_line or total,
                "content": content,
                "total_lines": total,
            },
            context,
            start_ms,
        )


class ListDirectoryTool(Tool):
    @property
    def name(self) -> str:
        return "list_directory"

    @property
    def description(self) -> str:
        return "List directory contents with metadata"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "path": {"type": "string", "default": "."},
                "max_entries": {"type": "integer", "default": 100},
                "depth": {"type": "integer", "default": 1},
            },
            "required": ["workspace_id"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "directories": {"type": "array"},
                "files": {"type": "array"},
                "total": {"type": "integer"},
            },
        }

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.READ

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ_ONLY

    def validate_input(self, arguments: dict[str, Any]) -> None:
        if not arguments.get("workspace_id"):
            raise InvalidToolInputError("workspace_id is required")

    def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        start_ms = __import__("time").time() * 1000
        workspace_id = arguments["workspace_id"]
        rel_path = arguments.get("path", ".")
        max_entries = arguments.get("max_entries", 100)

        workspace_path = Path("workspaces") / workspace_id
        full_path = (workspace_path / rel_path).resolve()
        if not str(full_path).startswith(str(workspace_path.resolve())):
            return self._error(PathTraversalError(rel_path), context, start_ms)

        if not full_path.exists() or not full_path.is_dir():
            return self._error(
                ToolExecutionError(f"Directory not found: {rel_path}"),
                context,
                start_ms,
            )

        dirs = []
        files = []
        count = 0
        try:
            for entry in sorted(full_path.iterdir()):
                if count >= max_entries:
                    break
                name = entry.name
                if name.startswith("."):
                    continue
                if entry.is_dir():
                    dirs.append({"name": name, "type": "directory"})
                else:
                    stat = entry.stat()
                    files.append(
                        {
                            "name": name,
                            "type": "file",
                            "size": stat.st_size,
                        }
                    )
                count += 1
        except PermissionError as e:
            return self._error(
                ToolExecutionError(f"Permission denied: {e}"),
                context,
                start_ms,
            )

        return self._success(
            {
                "path": rel_path,
                "directories": dirs,
                "files": files,
                "total": len(dirs) + len(files),
            },
            context,
            start_ms,
        )


class GetProjectStructureTool(Tool):
    @property
    def name(self) -> str:
        return "get_project_structure"

    @property
    def description(self) -> str:
        return "Get project structure with important markers"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
            },
            "required": ["workspace_id"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "directories": {"type": "array"},
                "files": {"type": "array"},
                "languages": {"type": "array"},
                "markers": {"type": "array"},
            },
        }

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.READ

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ_ONLY

    def validate_input(self, arguments: dict[str, Any]) -> None:
        if not arguments.get("workspace_id"):
            raise InvalidToolInputError("workspace_id is required")

    def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        start_ms = __import__("time").time() * 1000
        workspace_id = arguments["workspace_id"]
        workspace_path = Path("workspaces") / workspace_id

        if not workspace_path.exists():
            return self._error(
                ToolExecutionError(f"Workspace not found: {workspace_id}"),
                context,
                start_ms,
            )

        dirs = []
        files = []
        languages = set()
        markers = []

        marker_files = [
            "pyproject.toml",
            "package.json",
            "Cargo.toml",
            "go.mod",
            "pom.xml",
            "Makefile",
            "Dockerfile",
            ".gitignore",
            "README.md",
            "LICENSE",
        ]

        def walk(path: Path, depth: int = 0) -> None:
            if depth > 3:
                return
            try:
                for entry in sorted(path.iterdir()):
                    if entry.name.startswith("."):
                        continue
                    if entry.is_dir():
                        dirs.append(str(entry.relative_to(workspace_path)))
                        walk(entry, depth + 1)
                    else:
                        rel = str(entry.relative_to(workspace_path))
                        files.append(rel)
                        ext = entry.suffix.lstrip(".")
                        if ext:
                            languages.add(ext)
                        if entry.name in marker_files:
                            markers.append(rel)
            except PermissionError:
                pass

        walk(workspace_path)

        return self._success(
            {
                "directories": dirs[:200],
                "files": files[:500],
                "languages": sorted(languages),
                "markers": markers,
            },
            context,
            start_ms,
        )
