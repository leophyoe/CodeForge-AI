"""Tool interface — base class for all tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from .models import (
    PermissionLevel,
    ToolCategory,
    ToolExecutionContext,
    ToolResult,
    current_time_ms,
)

if TYPE_CHECKING:
    from codeforge.packages.tools.errors import ToolError


class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]: ...

    @property
    @abstractmethod
    def output_schema(self) -> dict[str, Any]: ...

    @property
    @abstractmethod
    def category(self) -> ToolCategory: ...

    @property
    @abstractmethod
    def permission_level(self) -> PermissionLevel: ...

    @abstractmethod
    def validate_input(self, arguments: dict[str, Any]) -> None: ...

    @abstractmethod
    def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult: ...

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "permission_level": self.permission_level.value,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }

    def _success(
        self,
        result: Any,
        context: ToolExecutionContext,
        start_ms: float,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            success=True,
            result=result,
            metadata=metadata or {},
            execution_time_ms=current_time_ms() - start_ms,
            request_id=context.request_id,
        )

    def _error(
        self,
        error: ToolError,
        context: ToolExecutionContext,
        start_ms: float,
    ) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            success=False,
            error=error.to_dict().get("message", str(error)),
            metadata={"error_code": error.code},
            execution_time_ms=current_time_ms() - start_ms,
            request_id=context.request_id,
        )
