"""Tool Manager — orchestrates tool resolution, validation, and execution."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from codeforge.packages.tools.audit import ToolAuditLogger
from codeforge.packages.tools.errors import (
    InvalidToolInputError,
    ToolError,
    ToolNotFoundError,
    ToolPermissionError,
)
from codeforge.packages.tools.models import ToolExecutionContext, ToolResult, current_time_ms
from codeforge.packages.tools.policy import ToolPolicy
from codeforge.packages.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from codeforge.packages.tools.tool import Tool


class ToolManager:
    def __init__(
        self,
        registry: ToolRegistry | None = None,
        policy: ToolPolicy | None = None,
        audit: ToolAuditLogger | None = None,
    ) -> None:
        self.registry = registry or ToolRegistry()
        self.policy = policy or ToolPolicy()
        self.audit = audit or ToolAuditLogger()

    def resolve(self, tool_name: str) -> Tool:
        tool = self.registry.get(tool_name)
        if tool is None:
            raise ToolNotFoundError(tool_name)
        if not self.policy.is_enabled(tool_name):
            raise ToolPermissionError(f"Tool is disabled: {tool_name}", tool_name=tool_name)
        return tool

    def validate(self, tool: Tool, arguments: dict[str, Any]) -> None:
        try:
            tool.validate_input(arguments)
        except Exception as e:
            raise InvalidToolInputError(
                f"Invalid input for {tool.name}: {e}", tool_name=tool.name
            ) from e

    def authorize(self, tool: Tool, context: ToolExecutionContext) -> None:
        if not self.policy.check_permission(tool.name, tool.permission_level):
            raise ToolPermissionError(
                f"Permission denied for {tool.name}",
                tool_name=tool.name,
                request_id=context.request_id,
            )

    def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: ToolExecutionContext | None = None,
    ) -> ToolResult:
        if context is None:
            context = ToolExecutionContext()

        start_ms = current_time_ms()

        try:
            tool = self.resolve(tool_name)
            self.validate(tool, arguments)
            self.authorize(tool, context)

            config = self.policy.get_config(tool_name)
            context.timeout_seconds = config.timeout_seconds
            context.max_output_bytes = config.max_output_bytes

            result = tool.execute(arguments, context)

            self.audit.log(
                request_id=context.request_id,
                workspace_id=context.workspace_id,
                tool_name=tool_name,
                permission_level=tool.permission_level.value,
                success=result.success,
                duration_ms=current_time_ms() - start_ms,
                error_code=result.metadata.get("error_code", ""),
            )

            return result

        except ToolError as e:
            self.audit.log(
                request_id=context.request_id,
                workspace_id=context.workspace_id,
                tool_name=tool_name,
                permission_level="",
                success=False,
                duration_ms=current_time_ms() - start_ms,
                error_code=e.code,
            )
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=e.to_dict().get("message", str(e)),
                metadata={"error_code": e.code},
                execution_time_ms=current_time_ms() - start_ms,
                request_id=context.request_id,
            )
        except Exception:
            self.audit.log(
                request_id=context.request_id,
                workspace_id=context.workspace_id,
                tool_name=tool_name,
                permission_level="",
                success=False,
                duration_ms=current_time_ms() - start_ms,
                error_code="internal_error",
            )
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error="An internal error occurred",
                metadata={"error_code": "internal_error"},
                execution_time_ms=current_time_ms() - start_ms,
                request_id=context.request_id,
            )

    async def execute_tool_async(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: ToolExecutionContext | None = None,
    ) -> ToolResult:
        if context is None:
            context = ToolExecutionContext()

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self.execute_tool, tool_name, arguments, context),
                timeout=context.timeout_seconds,
            )
        except asyncio.TimeoutError:
            self.audit.log(
                request_id=context.request_id,
                workspace_id=context.workspace_id,
                tool_name=tool_name,
                permission_level="",
                success=False,
                duration_ms=context.timeout_seconds * 1000,
                error_code="tool_timeout",
            )
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool timed out after {context.timeout_seconds}s",
                metadata={"error_code": "tool_timeout"},
                execution_time_ms=context.timeout_seconds * 1000,
                request_id=context.request_id,
            )

    def list_tools(self) -> list[dict[str, Any]]:
        return [tool.describe() for tool in self.registry.list_tools()]

    def get_tool_schema(self, tool_name: str) -> dict[str, Any] | None:
        return self.registry.get_schema(tool_name)
