# Phase 10 Audit — Safe Terminal (Pre-Completion Snapshot)

Date: audited at ~60% completion, before the completion pass described here.

## Existing Implementation (as found)

| File | Lines | Contents |
|------|-------|----------|
| `codeforge/packages/terminal/__init__.py` | 51 | Package exports (errors, models, executor, manager, policy) |
| `codeforge/packages/terminal/models.py` | 110 | `CommandRequest`, `CommandResult`, `CommandExecutionContext`, `ApprovalRequest`, `CommandClassification`, `CommandStatus` |
| `codeforge/packages/terminal/errors.py` | 92 | `TerminalError` hierarchy (10 error types) |
| `codeforge/packages/terminal/policy.py` | 115 | `CommandPolicy`, `CommandPolicyConfig`, `RiskLevel`, dangerous/restricted command sets, env sanitization |
| `codeforge/packages/terminal/executor.py` | 223 | `ProcessExecutor` — `asyncio.create_subprocess_exec` (never `shell=True`), workspace cwd restriction, timeout, output truncation, process termination |
| `codeforge/packages/terminal/manager.py` | 47 | `TerminalManager` — validation → execution orchestration |

## Completed Functionality

- Command request/result abstractions with `to_dict()` serialization.
- Four-level risk classification: SAFE / RESTRICTED / DANGEROUS / BLOCKED.
- Policy validation: command length, argument count, timeout ceiling.
- Environment sanitization by allowlist (deny-by-default for secrets).
- Async subprocess execution without a shell, DEVNULL stdin, new session.
- Workspace-restricted working directory resolution with traversal checks.
- Timeout-based termination (SIGTERM, then SIGKILL via process group).
- Output truncation with `truncated` metadata.

## Bugs Found During Audit

1. **`executor.py:12-23` broken relative imports** — `..packages.terminal.models`
   resolves to `codeforge.packages.packages...` and violates the absolute-import
   rule (27 TID252 errors).
2. **E501 violations** at `executor.py:12` (131 chars) and `executor.py:179` (108 chars).
3. **Empty environment** — `sanitize_environment()` called with no arguments
   defaults `source_env` to `{}`, so executed processes received an empty env
   (no `PATH`; command lookup failed for bare names like `echo`).
4. **`NameError` on timeout** — the timeout branch reads `stdout_data`, which is
   never assigned because `communicate()` raised `TimeoutError`.
5. **Cancellation never killed the process** — `TerminalManager.cancel()` only
   removed the bookkeeping entry; the child kept running.
6. **No active-cancellation check during execution** — `context.cancelled` was
   only inspected *after* `communicate()` returned.
7. **Request settings ignored** — `CommandRequest.max_output_bytes` was not
   propagated into the default `CommandExecutionContext`.
8. **`startswith` path check** — `/ws2`.startswith(`/ws`) style prefix bug; must
   use `Path.is_relative_to`.
9. **DANGEROUS == BLOCKED conflation** — both used the same set, so the
   `WAITING_APPROVAL` branch was unreachable dead code; no approval flow existed.
10. **No shell-interpreter guard** — `sh -c "..."` classified as SAFE (arbitrary
    shell string would bypass `CommandPolicy`).
11. **Wrapper bypass** — `env rm ...`, `timeout 5 rm ...` classified by wrapper
    name only.
12. **`git push/commit/...` classified SAFE** — write operations ungoverned.
13. **`manager.cancel()` private-member access** (`SLF001`) and no audit trail.

## Remaining Gaps (handled in this pass)

| # | Gap | Action |
|---|-----|--------|
| 1 | API router missing | Create `codeforge/api/routers/terminal.py` (`POST /v1/terminal/execute`, `GET /v1/terminal/policy`, `GET /v1/terminal/health`) |
| 2 | Router not registered | Add to `_register_routers()` in `codeforge/api/app.py` |
| 3 | CLI missing | Add `codeforge terminal doctor / policy / execute` groups to `codeforge/cli.py` |
| 4 | Tests missing | Create `tests/unit/test_terminal.py` (validation, classification, workspace, timeout, cancellation, limits, env, approval, injection, API, CLI, security regressions) |
| 5 | Documentation missing | `docs/terminal.md`, `docs/terminal-security.md`, `docs/phase-10.md` |
| 6 | Ruff errors | Fix all terminal-package errors (27 in `executor.py`, 5 `manager.py`, 4 `policy.py`, `__init__.py`, `errors.py`) |
| 7 | Audit integration | Reuse Phase 9 `ToolAuditLogger` via `terminal/audit.py` (`TerminalAuditLogger`) |
| 8 | Bugs 3–13 above | Corrected in `policy.py`, `executor.py`, `manager.py`, `models.py` |

## Files To Modify

- Modify: `codeforge/packages/terminal/{models,errors,policy,executor,manager,__init__}.py`
- Create: `codeforge/packages/terminal/audit.py`
- Create: `codeforge/api/routers/terminal.py`
- Modify: `codeforge/api/app.py`, `codeforge/cli.py`
- Create: `tests/unit/test_terminal.py`
- Create: `docs/{terminal,terminal-security,phase-10}.md`

## Security Considerations

- Never `shell=True`; command must be a single validated token (no metacharacters).
- `sh -c`, `bash -c`, and equivalent shell-string execution are BLOCKED outright.
- Wrapper commands (`env`, `timeout`, `nice`, `busybox`, …) are unwrapped before
  classification so `env rm …` cannot launder a dangerous command.
- BLOCKED commands raise `DangerousCommandError` and are verifiably never spawned.
- DANGEROUS commands execute only with explicit `approved=True`; `require_approval=False`
  on a dangerous command is a `CommandPermissionError` (no approval bypass).
- Workspace root is the trust boundary: relative workspace ids cannot escape
  `workspaces/`, and `working_directory` (including symlinks, absolute paths,
  `../`) must resolve inside the root.
- Environment passed to children is an allowlist; secret-like names are rejected
  and never recorded in audit metadata.
- Audit records classification, approval state, duration, exit code — never
  stdout/stderr content, arguments, or environment values.
- Output is bounded per stream and combined; `truncated=True` marks clipping.
- Public APIs expose error `code` + message only — no stack traces.

## Platform Notes

- Developed/tested on Linux x86_64 (process-group SIGKILL, `start_new_session`).
- `start_new_session` and `os.killpg` are Unix-only; guarded by `os.name == "nt"`
  checks. Windows/macOS code paths exist but are **not executed in CI** — see
  `docs/terminal-security.md` for documented limitations.
