"""System prompt construction for the agent loop."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import AgentConfig

_IDENTITY = (
    "You are CodeForge Agent, an autonomous coding assistant operating "
    'inside the workspace "{workspace}".'
)

_PROTOCOL = """TOOL CALL PROTOCOL (mandatory):
- To use a tool, respond with ONLY a fenced block and nothing else:

```tool_call
{{"tool": "<tool_name>", "arguments": {{...}}}}
```

- After you receive a "TOOL_RESULT" message, continue reasoning and either \
call another tool or reply with your final answer.
- When the task is done, respond with a plain text final answer (no fences).
- Only use the tools listed below; never invent tool names.
- File paths are relative to the workspace root.
- Be concise: final answers should be a short summary of what you did.

RULES:
1. Read before you edit: inspect files with read_file/list_directory first.
2. Make the smallest change that solves the task.
3. If a tool returns an error, adapt — do not repeat the same failing call.
4. Never attempt to access files outside the workspace.
"""


def build_system_prompt(tools: list[dict[str, Any]], config: AgentConfig) -> str:
    """Compose the system prompt with the available tool catalog."""
    sections = [
        _IDENTITY.format(workspace=config.workspace_id),
        "AVAILABLE TOOLS:",
    ]
    for tool in tools:
        name = tool.get("name", "")
        description = tool.get("description", "")
        schema = tool.get("input_schema", {})
        sections.append(
            f"- {name}: {description}\n  input_schema: {json.dumps(schema, separators=(',', ':'))}"
        )

    if config.allowed_tools is not None:
        sections.append(
            "RESTRICTED TOOL SET: you may ONLY call: " + ", ".join(sorted(config.allowed_tools))
        )
    sections.append(_PROTOCOL)
    return "\n".join(sections)
