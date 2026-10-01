"""Write and edit tools (Phase 10) — approval-gated file mutations."""

from __future__ import annotations

import time
from typing import Any

from codeforge.packages.file_editing import (
    FileEditManager,
    FileEditResult,
    get_file_edit_manager,
)
from codeforge.packages.tools.errors import (
    InvalidToolInputError,
    ToolError,
    ToolExecutionError,
)
from codeforge.packages.tools.errors import (
    PathTraversalError as ToolPathTraversal,
)
from codeforge.packages.tools.errors import (
    SensitiveFileBlockedError as ToolSensitiveBlocked,
)
from codeforge.packages.tools.models import (
    PermissionLevel,
    ToolCategory,
    ToolExecutionContext,
    ToolResult,
)
from codeforge.packages.tools.tool import Tool

_ERROR_MAP: dict[str, type] = {
    "path_traversal_error": ToolPathTraversal,
    "sensitive_file_blocked": ToolSensitiveBlocked,
}


def _map_error(result: FileEditResult) -> ToolError:
    cls = _ERROR_MAP.get(result.error_code, ToolExecutionError)
    if cls in (ToolPathTraversal, ToolSensitiveBlocked):
        return cls(result.path or "unknown")
    return ToolExecutionError(result.error or "file edit failed")


class _FileToolBase(Tool):
    """Shared plumbing for write_file / edit_file."""

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WRITE

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.USER_APPROVAL

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "success": {"type": "boolean"},
                "bytes_written": {"type": "integer"},
                "replacements": {"type": "integer"},
                "lines_before": {"type": "integer"},
                "lines_after": {"type": "integer"},
                "diff": {"type": "string"},
            },
        }

    def validate_input(self, arguments: dict[str, Any]) -> None:
        if not arguments.get("path"):
            raise InvalidToolInputError("path is required")
        if not arguments.get("workspace_id"):
            raise InvalidToolInputError("workspace_id is required")

    @staticmethod
    def _manager() -> FileEditManager:
        return get_file_edit_manager()


class WriteFileTool(_FileToolBase):
    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Create or overwrite a file inside the workspace (atomic write)"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "path": {"type": "string"},
                "content": {"type": "string"},
                "create_only": {
                    "type": "boolean",
                    "description": "Fail if the file already exists",
                    "default": False,
                },
            },
            "required": ["workspace_id", "path", "content"],
        }

    def validate_input(self, arguments: dict[str, Any]) -> None:
        super().validate_input(arguments)
        if "content" not in arguments:
            raise InvalidToolInputError("content is required")

    def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        start_ms = time.time() * 1000
        result = self._manager().write(
            arguments["workspace_id"],
            arguments["path"],
            arguments.get("content", ""),
            create_only=bool(arguments.get("create_only", False)),
            request_id=context.request_id,
        )
        if not result.success:
            return self._error(_map_error(result), context, start_ms)
        return self._success(
            {
                "path": result.path,
                "success": True,
                "bytes_written": result.bytes_written,
                "lines_after": result.lines_after,
                "diff": result.diff,
            },
            context,
            start_ms,
        )


class EditFileTool(_FileToolBase):
    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return "Replace exact text in a file (str_replace with occurrence checks)"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "path": {"type": "string"},
                "old": {"type": "string", "description": "Exact text to find"},
                "new": {"type": "string", "description": "Replacement text"},
                "replace_all": {
                    "type": "boolean",
                    "description": "Replace every occurrence (default: first only)",
                    "default": False,
                },
            },
            "required": ["workspace_id", "path", "old", "new"],
        }

    def validate_input(self, arguments: dict[str, Any]) -> None:
        super().validate_input(arguments)
        if not arguments.get("old"):
            raise InvalidToolInputError("old is required")
        if "new" not in arguments:
            raise InvalidToolInputError("new is required")

    def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        start_ms = time.time() * 1000
        result = self._manager().str_replace(
            arguments["workspace_id"],
            arguments["path"],
            arguments["old"],
            arguments["new"],
            replace_all=bool(arguments.get("replace_all", False)),
            request_id=context.request_id,
        )
        if not result.success:
            return self._error(_map_error(result), context, start_ms)
        return self._success(
            {
                "path": result.path,
                "success": True,
                "replacements": result.replacements,
                "lines_before": result.lines_before,
                "lines_after": result.lines_after,
                "diff": result.diff,
            },
            context,
            start_ms,
        )


__all__ = ["EditFileTool", "WriteFileTool"]
