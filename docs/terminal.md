# Terminal — Safe Command Execution

Phase 10 provides **controlled terminal execution**: every command passes
through validation, workspace restriction, a security policy, and an approval
gate before a subprocess is ever created. It does **not** provide autonomous
agent execution.

## Architecture

```
CLI / API request
      │
      ▼
TerminalManager
      ├── CommandPolicy.validate()      request validation
      ├── workspace resolution          workspace boundary
      ├── CommandPolicy.classify()      SAFE / RESTRICTED / DANGEROUS / BLOCKED
      ├── approval gate                 DANGEROUS needs approved=True
      ▼
ProcessExecutor (asyncio.create_subprocess_exec, never shell=True)
      ├── sanitized environment (allowlist)
      ├── workspace-restricted cwd
      ├── timeout / cancellation polling
      ├── bounded output (per stream + total)
      ▼
CommandResult  +  TerminalAuditLogger (reuses Phase 9 ToolAuditLogger)
```

| Component | File |
|-----------|------|
| Models (`CommandRequest`, `CommandResult`, `CommandExecutionContext`) | `codeforge/packages/terminal/models.py` |
| Errors (`TerminalError` hierarchy) | `codeforge/packages/terminal/errors.py` |
| Policy (classification, validation, env sanitization) | `codeforge/packages/terminal/policy.py` |
| Executor (subprocess lifecycle) | `codeforge/packages/terminal/executor.py` |
| Manager (orchestration + audit) | `codeforge/packages/terminal/manager.py` |
| Audit (reuses Phase 9 audit) | `codeforge/packages/terminal/audit.py` |
| API | `codeforge/api/routers/terminal.py` |

## Command policy

See [terminal-security.md](terminal-security.md) for the full model. Summary:

- **BLOCKED** — never executed, raises `DangerousCommandError`
  (`sudo`, `shutdown`, `mkfs`, `dd`, `sh -c`, …).
- **DANGEROUS** — executed only with `approved=True`
  (`rm`, `curl`, `git push`, `python -c`, `find -delete`, …). Without
  approval the result status is `waiting_approval` and nothing runs.
- **RESTRICTED** — runs, audited (`grep`, `python -m pytest`, `make`, …).
- **SAFE** — everything else (`echo`, `ls`, `git status`, …).

Wrapper commands (`env`, `timeout`, `nice`, `busybox`, …) are unwrapped before
classification, so `env rm …` is still DANGEROUS.

## Request / result

```python
from codeforge.packages.terminal import CommandRequest, TerminalManager

manager = TerminalManager()
result = await manager.execute(
    CommandRequest(
        command="pytest",
        arguments=["-q"],
        workspace_id="my-workspace",
        working_directory="tests",
        timeout_seconds=60,
    )
)
result.status  # CommandStatus.COMPLETED / FAILED / TIMED_OUT /
# CANCELLED / WAITING_APPROVAL
result.exit_code
result.stdout, result.stderr
result.truncated  # output hit configured limits
result.security_classification
```

Errors raised (all subclass `TerminalError`, all carry `.code`):

| Error | Code | Meaning |
|-------|------|---------|
| `CommandValidationError` | `COMMAND_VALIDATION_ERROR` | bad command/args/timeout |
| `WorkspaceAccessError` | `WORKSPACE_ACCESS_ERROR` | workspace or cwd missing |
| `PathTraversalError` | `PATH_TRAVERSAL_ERROR` | path escapes workspace |
| `CommandNotFoundError` | `COMMAND_NOT_FOUND` | executable not found |
| `DangerousCommandError` | `DANGEROUS_COMMAND_BLOCKED` | BLOCKED command |
| `CommandPermissionError` | `COMMAND_PERMISSION_DENIED` | approval bypass attempt |

## API

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/terminal/execute` | run a command |
| GET | `/v1/terminal/policy` | classification policy + limits |
| GET | `/v1/terminal/health` | executor/audit health |

Request:

```json
{
  "workspace_id": "my-workspace",
  "command": "pytest",
  "arguments": ["-q"],
  "working_directory": "tests",
  "timeout": 60,
  "approved": false
}
```

Response (200 for run outcomes):

```json
{
  "request_id": "...",
  "success": true,
  "status": "completed",
  "command": "pytest",
  "exit_code": 0,
  "stdout": "...",
  "stderr": "...",
  "duration_ms": 812.4,
  "timed_out": false,
  "cancelled": false,
  "truncated": false,
  "executed": true,
  "security_classification": "restricted",
  "approval_required": false,
  "approved": false
}
```

Error mapping: validation/workspace → **400**, blocked/permission → **403**,
not found → **404**, spawn failure → **500**. Bodies use the standard API error
shape (`{"error": {"code", "message", "request_id"}}`) — never stack traces.

## CLI

```
codeforge terminal doctor     # configuration report (no secrets)
codeforge terminal policy     # SAFE / RESTRICTED / DANGEROUS / BLOCKED tables
codeforge terminal execute CMD [--arg X]... -w WORKSPACE [--cwd DIR]
                             [--timeout N] [--approved]
```

`execute` goes through the exact same policy layer as the API. Exit codes:
`0` success, `1` error/blocked/failed, `2` approval required.

## Timeout, cancellation, output limits

- Timeout: request value must be ≤ `max_timeout` (default 300 s); the executor
  polls, then SIGTERMs and SIGKILLs the process group (Unix).
- Cancellation: `await manager.cancel(request_id)` sets a cancel event and
  signals the process; the result status is `cancelled`.
- Output: bounded per stream (`max_output_bytes`) and combined
  (`max_total_output_bytes`); `truncated=true` marks clipping and a
  `... (output truncated)` marker is appended.

## Audit

Every execution and every rejection is recorded through
`TerminalAuditLogger`, which reuses the Phase 9 `ToolAuditLogger`. Recorded:
request id, workspace, command, classification, approval state, duration,
exit code, status, timeouts, cancellations, output byte counts.
**Never recorded:** stdout/stderr bodies, argument values, environment values,
tokens, or passwords.

## Platform support

| Platform | Status |
|----------|--------|
| Linux x86_64 | fully implemented and tested (development platform) |
| macOS | same code paths as Linux (POSIX signals); not executed in CI |
| Windows | guarded (`os.name == "nt"`: no `start_new_session`, `terminate()`/`kill()` instead of process groups, extra env allowlist); **not executed in CI** |

See [terminal-security.md](terminal-security.md) for limitations.
