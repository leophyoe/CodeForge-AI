"""Built-in analysis tools for Phase 9."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from codeforge.packages.tools.errors import InvalidToolInputError, ToolExecutionError
from codeforge.packages.tools.models import (
    PermissionLevel,
    ToolCategory,
    ToolExecutionContext,
    ToolResult,
)
from codeforge.packages.tools.tool import Tool


class FindSymbolTool(Tool):
    @property
    def name(self) -> str:
        return "find_symbol"

    @property
    def description(self) -> str:
        return "Find symbols by name, kind, or path"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "name": {"type": "string"},
                "kind": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": ["workspace_id", "name"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbols": {"type": "array"},
                "total": {"type": "integer"},
            },
        }

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ_ONLY

    def validate_input(self, arguments: dict[str, Any]) -> None:
        if not arguments.get("workspace_id"):
            raise InvalidToolInputError("workspace_id is required")
        if not arguments.get("name"):
            raise InvalidToolInputError("name is required")

    def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        start_ms = __import__("time").time() * 1000
        workspace_id = arguments["workspace_id"]
        name = arguments["name"]
        kind_filter = arguments.get("kind")
        path_filter = arguments.get("path")

        workspace_path = Path("workspaces") / workspace_id
        if not workspace_path.exists():
            return self._error(
                ToolExecutionError(f"Workspace not found: {workspace_id}"),
                context,
                start_ms,
            )

        patterns = [
            (r"(?:class|struct|interface|enum)\s+(\w+)", "class"),
            (r"(?:def|function|fn|func)\s+(\w+)", "function"),
            (r"(?:method)\s+(\w+)", "method"),
            (r"(?:const|let|var)\s+(\w+)", "variable"),
        ]

        symbols = []
        try:
            for root, dirs, files in os.walk(workspace_path):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for fname in files:
                    fpath = Path(root) / fname
                    rel = str(fpath.relative_to(workspace_path))
                    if path_filter and path_filter not in rel:
                        continue
                    try:
                        content = fpath.read_text(errors="replace")
                    except Exception:
                        continue
                    for i, line in enumerate(content.splitlines(), 1):
                        for pat, kind in patterns:
                            if kind_filter and kind != kind_filter:
                                continue
                            match = re.search(pat, line)
                            if match and name.lower() in match.group(1).lower():
                                symbols.append(
                                    {
                                        "name": match.group(1),
                                        "kind": kind,
                                        "file": rel,
                                        "line": i,
                                        "qualified_name": match.group(1),
                                    }
                                )
        except Exception as e:
            return self._error(
                ToolExecutionError(f"Symbol search failed: {e}"),
                context,
                start_ms,
            )

        return self._success(
            {"symbols": symbols[:100], "total": len(symbols)},
            context,
            start_ms,
        )


class GetSymbolTool(Tool):
    @property
    def name(self) -> str:
        return "get_symbol"

    @property
    def description(self) -> str:
        return "Get detailed symbol information by ID"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "symbol_id": {"type": "string"},
            },
            "required": ["workspace_id", "symbol_id"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {"type": "object"},
            },
        }

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ_ONLY

    def validate_input(self, arguments: dict[str, Any]) -> None:
        if not arguments.get("workspace_id"):
            raise InvalidToolInputError("workspace_id is required")
        if not arguments.get("symbol_id"):
            raise InvalidToolInputError("symbol_id is required")

    def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        start_ms = __import__("time").time() * 1000
        symbol_id = arguments["symbol_id"]

        parts = symbol_id.split(":")
        if len(parts) < 3:
            return self._error(
                ToolExecutionError(f"Invalid symbol_id format: {symbol_id}"),
                context,
                start_ms,
            )

        file_path, line_str, name = parts[0], parts[1], parts[2]
        try:
            line_num = int(line_str)
        except ValueError:
            return self._error(
                ToolExecutionError(f"Invalid line number: {line_str}"),
                context,
                start_ms,
            )

        workspace_path = Path("workspaces") / arguments["workspace_id"]
        full_path = workspace_path / file_path

        if not full_path.exists():
            return self._error(
                ToolExecutionError(f"File not found: {file_path}"),
                context,
                start_ms,
            )

        try:
            content = full_path.read_text(errors="replace")
            lines = content.splitlines()
            if line_num < 1 or line_num > len(lines):
                return self._error(
                    ToolExecutionError(f"Line {line_num} out of range"),
                    context,
                    start_ms,
                )
            context_line = lines[line_num - 1]
        except Exception as e:
            return self._error(
                ToolExecutionError(f"Failed to read: {e}"),
                context,
                start_ms,
            )

        return self._success(
            {
                "symbol": {
                    "name": name,
                    "file": file_path,
                    "line": line_num,
                    "context": context_line.strip(),
                    "qualified_name": name,
                }
            },
            context,
            start_ms,
        )


class FindReferencesTool(Tool):
    @property
    def name(self) -> str:
        return "find_references"

    @property
    def description(self) -> str:
        return "Find references to a symbol across the codebase"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "name": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
            "required": ["workspace_id", "name"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "references": {"type": "array"},
                "total": {"type": "integer"},
                "resolved": {"type": "boolean"},
            },
        }

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ_ONLY

    def validate_input(self, arguments: dict[str, Any]) -> None:
        if not arguments.get("workspace_id"):
            raise InvalidToolInputError("workspace_id is required")
        if not arguments.get("name"):
            raise InvalidToolInputError("name is required")

    def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        start_ms = __import__("time").time() * 1000
        workspace_id = arguments["workspace_id"]
        name = arguments["name"]
        limit = arguments.get("limit", 50)

        workspace_path = Path("workspaces") / workspace_id
        if not workspace_path.exists():
            return self._error(
                ToolExecutionError(f"Workspace not found: {workspace_id}"),
                context,
                start_ms,
            )

        refs = []
        try:
            for root, dirs, files in os.walk(workspace_path):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for fname in files:
                    fpath = Path(root) / fname
                    rel = str(fpath.relative_to(workspace_path))
                    try:
                        content = fpath.read_text(errors="replace")
                    except Exception:
                        continue
                    for i, line in enumerate(content.splitlines(), 1):
                        if name in line:
                            refs.append(
                                {
                                    "file": rel,
                                    "line": i,
                                    "content": line.strip()[:200],
                                    "resolution": "text_match",
                                }
                            )
                            if len(refs) >= limit:
                                break
                if len(refs) >= limit:
                    break
        except Exception as e:
            return self._error(
                ToolExecutionError(f"Reference search failed: {e}"),
                context,
                start_ms,
            )

        return self._success(
            {
                "references": refs,
                "total": len(refs),
                "resolved": False,
            },
            context,
            start_ms,
        )


class FindDependenciesTool(Tool):
    @property
    def name(self) -> str:
        return "find_dependencies"

    @property
    def description(self) -> str:
        return "Find imports and dependencies for a file or symbol"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "file_path": {"type": "string"},
            },
            "required": ["workspace_id", "file_path"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "imports": {"type": "array"},
                "total": {"type": "integer"},
            },
        }

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ_ONLY

    def validate_input(self, arguments: dict[str, Any]) -> None:
        if not arguments.get("workspace_id"):
            raise InvalidToolInputError("workspace_id is required")
        if not arguments.get("file_path"):
            raise InvalidToolInputError("file_path is required")

    def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        start_ms = __import__("time").time() * 1000
        workspace_id = arguments["workspace_id"]
        file_path = arguments["file_path"]

        workspace_path = Path("workspaces") / workspace_id
        full_path = workspace_path / file_path

        if not full_path.exists():
            return self._error(
                ToolExecutionError(f"File not found: {file_path}"),
                context,
                start_ms,
            )

        try:
            content = full_path.read_text(errors="replace")
        except Exception as e:
            return self._error(
                ToolExecutionError(f"Failed to read: {e}"),
                context,
                start_ms,
            )

        imports = []
        import_patterns = [
            r"(?:from|import)\s+([\w.]+)",
            r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
        ]

        for line in content.splitlines():
            for pat in import_patterns:
                match = re.search(pat, line)
                if match:
                    imports.append(
                        {
                            "module": match.group(1),
                            "line": content[: match.start()].count("\n") + 1,
                            "resolution": "unresolved",
                        }
                    )

        return self._success(
            {"imports": imports, "total": len(imports)},
            context,
            start_ms,
        )


class GetDiagnosticsTool(Tool):
    @property
    def name(self) -> str:
        return "get_diagnostics"

    @property
    def description(self) -> str:
        return "Get repository-level diagnostics and code quality checks"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "file_path": {"type": "string"},
            },
            "required": ["workspace_id"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "diagnostics": {"type": "array"},
                "total": {"type": "integer"},
            },
        }

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ_ONLY

    def validate_input(self, arguments: dict[str, Any]) -> None:
        if not arguments.get("workspace_id"):
            raise InvalidToolInputError("workspace_id is required")

    def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        start_ms = __import__("time").time() * 1000
        workspace_id = arguments["workspace_id"]
        file_path = arguments.get("file_path")

        workspace_path = Path("workspaces") / workspace_id
        if not workspace_path.exists():
            return self._error(
                ToolExecutionError(f"Workspace not found: {workspace_id}"),
                context,
                start_ms,
            )

        diagnostics = []
        try:
            target = workspace_path / file_path if file_path else workspace_path
            files = [target] if target.is_file() else list(target.rglob("*.py"))[:50]

            for fpath in files:
                try:
                    content = fpath.read_text(errors="replace")
                except Exception:
                    continue
                rel = str(fpath.relative_to(workspace_path))
                lines = content.splitlines()
                for i, line in enumerate(lines, 1):
                    if len(line) > 120:
                        diagnostics.append(
                            {
                                "severity": "warning",
                                "message": f"Line too long ({len(line)} > 120)",
                                "file": rel,
                                "line": i,
                                "source": "codeforge",
                            }
                        )
                    if line.rstrip() != line and line.strip():
                        diagnostics.append(
                            {
                                "severity": "info",
                                "message": "Trailing whitespace",
                                "file": rel,
                                "line": i,
                                "source": "codeforge",
                            }
                        )
        except Exception as e:
            return self._error(
                ToolExecutionError(f"Diagnostics failed: {e}"),
                context,
                start_ms,
            )

        return self._success(
            {"diagnostics": diagnostics[:200], "total": len(diagnostics)},
            context,
            start_ms,
        )
