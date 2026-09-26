# Tool System (Phase 9)

Secure, permission-aware, read-only tool framework for CodeForge AI.

## Architecture

```
Agent (Future)
      |
      v
Tool Registry
      |
      v
Tool Executor
      |
  +---+---+---+
  |       |       |
  v       v       v
Read    Search   Analysis
Tools   Tools    Tools
  |       |       |
  v       v       v
Phase 7  Phase 8  Phase 7
Index    Search   Index
```

## Components

| Component | Purpose |
|-----------|---------|
| `Tool` | Base interface for all tools |
| `ToolRegistry` | Manages tool registration and lookup |
| `ToolManager` | Orchestrates tool execution |
| `ToolPolicy` | Controls permissions and restrictions |
| `ToolAuditLogger` | Records tool execution for auditing |
| `ToolResult` | Structured tool execution result |
| `ToolExecutionContext` | Execution context with request ID, workspace, etc. |

## Tool Interface

```python
from codeforge.packages.tools import Tool, ToolCategory, PermissionLevel


class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "Does something useful"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": ["workspace_id", "path"],
        }

    @property
    def output_schema(self) -> dict:
        return {"type": "object", "properties": {"result": {"type": "string"}}}

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.READ

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ_ONLY

    def validate_input(self, arguments: dict) -> None:
        if not arguments.get("path"):
            raise InvalidToolInputError("path is required")

    def execute(self, arguments: dict, context: ToolExecutionContext) -> ToolResult:
        # Implementation here
        return self._success({"result": "data"}, context, start_ms)
```

## Tool Registry

```python
from codeforge.packages.tools import ToolRegistry

registry = ToolRegistry()
registry.register(MyTool())

# Lookup
tool = registry.get("my_tool")
tools = registry.list_tools()
exists = registry.exists("my_tool")

# Schema
schema = registry.get_schema("my_tool")
```

## Tool Manager

```python
from codeforge.packages.tools import ToolManager, ToolExecutionContext

manager = ToolManager(registry=registry)
context = ToolExecutionContext(workspace_id="ws1")

# Execute
result = manager.execute_tool("my_tool", {"path": "src/main.py"}, context)
print(result.success, result.result)
```

## Permissions

| Level | Description |
|-------|-------------|
| `NONE` | No permission required |
| `READ_ONLY` | Read-only access (Phase 9 default) |
| `USER_APPROVAL` | Requires user approval |
| `PRIVILEGED` | Elevated privileges |

## Tool Categories

| Category | Description | Phase 9 Status |
|----------|-------------|----------------|
| `READ` | Read file/directory | ✅ Implemented |
| `SEARCH` | Search code/files | ✅ Implemented |
| `ANALYSIS` | Analyze code structure | ✅ Implemented |
| `GIT` | Git read-only operations | ✅ Implemented |
| `WRITE` | Write/edit files | ❌ Phase 10+ |
| `EXECUTION` | Run commands | ❌ Phase 10+ |
| `EXTERNAL` | External integrations | ❌ Future |

## Built-in Tools

### Read Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read file contents with optional line range |
| `list_directory` | List directory contents with metadata |
| `get_project_structure` | Get project structure with markers |

### Search Tools

| Tool | Description |
|------|-------------|
| `search_files` | Search file paths by pattern |
| `search_code` | Search code content with regex |

### Analysis Tools

| Tool | Description |
|------|-------------|
| `find_symbol` | Find symbols by name/kind |
| `get_symbol` | Get detailed symbol info |
| `find_references` | Find symbol references |
| `find_dependencies` | Find file imports |
| `get_diagnostics` | Get code quality diagnostics |

### Git Tools

| Tool | Description |
|------|-------------|
| `git_status` | Get git status (read-only) |
| `git_diff` | Get git diff (read-only) |
| `git_log` | Get git log (read-only) |

## Security

### Workspace Isolation

All tools validate paths against workspace root:
- Path traversal (`../`) blocked
- Symlink escape blocked
- Absolute paths outside workspace blocked

### Sensitive File Protection

Default blocked patterns:
- `.env`, `.env.*`
- `*.pem`, `*.key`
- `*.p12`, `*.pfx`
- `credentials.json`, `secrets.json`

### Prompt Injection Defense

Tool output is treated as untrusted data:
- Clearly delimited with `<tool_result>` tags
- Never elevated to system instructions
- No permission escalation through file content

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/tools` | List all enabled tools |
| GET | `/v1/tools/{name}` | Get tool schema |
| POST | `/v1/tools/{name}/execute` | Execute a tool |
| GET | `/v1/tools/health` | Tool system health |

### Execute Tool Request

```json
{
    "workspace_id": "...",
    "arguments": {
        "path": "src/auth.py",
        "start_line": 1,
        "end_line": 50
    },
    "request_id": "optional-uuid"
}
```

### Execute Tool Response

```json
{
    "tool_name": "read_file",
    "success": true,
    "result": {
        "path": "src/auth.py",
        "language": "python",
        "content": "...",
        "total_lines": 100
    },
    "metadata": {},
    "execution_time_ms": 4.2,
    "request_id": "uuid",
    "truncated": false
}
```

## Audit Logging

```python
from codeforge.packages.tools import ToolAuditLogger

logger = ToolAuditLogger()
logger.log(
    request_id="r1",
    workspace_id="ws1",
    tool_name="read_file",
    permission_level="read_only",
    success=True,
    duration_ms=5.0,
)

entries = logger.get_entries(tool_name="read_file")
stats = logger.get_stats()
```

## Configuration

```yaml
tools:
    enabled: true
    defaults:
        timeout_seconds: 10
        max_output_bytes: 100000
        max_file_size_bytes: 2000000
    read_file:
        enabled: true
    write_file:
        enabled: false
    run_command:
        enabled: false
```

## Tests

73 tests covering:
- Tool interface and properties
- Tool registry operations
- Tool manager execution
- Tool policy and permissions
- Audit logging
- Read file tool
- List directory tool
- Project structure tool
- Search files tool
- Search code tool
- Find symbol tool
- Find references tool
- Find dependencies tool
- Diagnostics tool
- Git tools (status, diff, log)
- Security (path traversal, sensitive files, disabled tools)
- Error types
- Execution context

```bash
python -m pytest tests/unit/test_tools.py -v
```

## Phase 9 Definition of Done

- [x] Tool interface exists
- [x] Tool Registry exists
- [x] Tool Manager exists
- [x] Tool permissions exist
- [x] Tool policy exists
- [x] Workspace security is enforced
- [x] read_file works
- [x] list_directory works
- [x] project_structure works
- [x] search_files works
- [x] search_code works
- [x] find_symbol works
- [x] get_symbol works
- [x] find_references works
- [x] find_dependencies works
- [x] get_diagnostics works
- [x] git_status works
- [x] git_diff works
- [x] git_log works
- [x] Tool schemas exist
- [x] Tool API exists
- [x] Tool timeouts exist
- [x] Output limits exist
- [x] Tool cancellation exists
- [x] Tool audit logging exists
- [x] Tool result validation exists
- [x] Prompt injection boundary exists
- [x] Sensitive file protection exists
- [x] Path traversal protection works
- [x] Workspace isolation works
- [x] No write tools exist
- [x] No shell tools exist
- [x] No autonomous chaining exists
- [x] Tests pass (73 new + 515 existing)
- [x] Security tests pass
- [x] Documentation created

## What's NOT Implemented (Phase 10+)

- `write_file` / `edit_file` — File modification
- `run_command` / `execute_shell` — Shell execution
- `delete_file` / `move_file` — File operations
- Git write operations (commit, push, pull)
- Autonomous agent planning
- Tool chaining/composition

## Known Limitations

- In-memory vector store (no persistence)
- Regex-based symbol parsing (no tree-sitter)
- Text-match references (not semantic resolution)
- Limited diagnostics (no compiler integration)
- No VS Code extension integration yet
