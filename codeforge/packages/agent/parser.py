"""Parse tool calls from model output (fenced JSON protocol)."""

from __future__ import annotations

import json
import re
from typing import Any

from .models import ToolCall

# ```tool_call ...``` or ```json ...``` fenced blocks
_FENCE_RE = re.compile(
    r"```(?:tool_call|json|ToolCall)\s*\n(.*?)\n```",
    re.DOTALL,
)

_TOOL_KEYS = ("tool", "name", "tool_name")
_ARG_KEYS = ("arguments", "args", "input", "parameters")


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Parse the first balanced JSON object in ``text`` (or None)."""
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : index + 1]
                    try:
                        parsed = json.loads(candidate)
                    except (json.JSONDecodeError, ValueError):
                        break
                    if isinstance(parsed, dict):
                        return parsed
                    break
        start = text.find("{", start + 1)
    return None


def _as_call(candidate: dict[str, Any]) -> ToolCall | None:
    """Normalize a JSON object into a ToolCall if it looks like one."""
    name = ""
    for key in _TOOL_KEYS:
        value = candidate.get(key)
        if isinstance(value, str) and value.strip():
            name = value.strip()
            break
    if not name:
        return None

    arguments: dict[str, Any] = {}
    for key in _ARG_KEYS:
        value = candidate.get(key)
        if isinstance(value, dict):
            arguments = value
            break

    return ToolCall(name=name, arguments=arguments, raw=json.dumps(candidate))


def parse_tool_call(text: str) -> ToolCall | None:
    """Extract a tool call from model output.

    Recognizes fenced ```tool_call``` / ```json``` blocks first, then a bare
    JSON object containing ``tool``/``name`` + optional ``arguments``.
    Returns ``None`` when the output is a plain final answer.
    """
    if not text or not text.strip():
        return None

    for block in _FENCE_RE.findall(text):
        parsed = _extract_json_object(block)
        if parsed is not None:
            call = _as_call(parsed)
            if call is not None:
                return call

    parsed = _extract_json_object(text)
    if parsed is not None:
        call = _as_call(parsed)
        if call is not None:
            return call
    return None


def extract_final_text(text: str) -> str:
    """Strip tool-call fences, returning the model's plain answer."""
    cleaned = _FENCE_RE.sub("", text or "")
    return cleaned.strip()


def is_known_tool(call: ToolCall, tool_names: set[str]) -> bool:
    return call.name in tool_names
