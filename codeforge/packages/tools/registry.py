"""Tool Registry — manages tool registration and lookup."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from codeforge.packages.tools.errors import ToolError, ToolNotFoundError

if TYPE_CHECKING:
    from codeforge.packages.tools.tool import Tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ToolError(
                f"Tool already registered: {tool.name}",
                code="duplicate_tool",
                tool_name=tool.name,
            )
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> bool:
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def get_or_raise(self, name: str) -> Tool:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolNotFoundError(name)
        return tool

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def exists(self, name: str) -> bool:
        return name in self._tools

    def get_schema(self, name: str) -> dict[str, Any] | None:
        tool = self._tools.get(name)
        return tool.describe() if tool else None

    def count(self) -> int:
        return len(self._tools)

    def clear(self) -> int:
        count = len(self._tools)
        self._tools.clear()
        return count
