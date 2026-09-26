# Phase 10 — Safe Terminal (Complete)

Phase 10 delivers controlled, policy-gated command execution. It was ~60%
complete at audit time (see [phase-10-audit.md](phase-10-audit.md)); this
phase completes the package, API, CLI, tests, audit, and documentation.

## What was built

**Package** (`codeforge/packages/terminal/`)

- `models.py` — `CommandRequest` (+ `approved`, `max_total_output_bytes`),
  `CommandResult` (+ `executed`, `approval_required`, `success`),
  `CommandExecutionContext` (+ cancellation), `ApprovalRequest`.
- `errors.py` — `TerminalError` hierarchy incl. new `CommandValidationError`.
- `policy.py` — four-level classification (SAFE/RESTRICTED/DANGEROUS/BLOCKED),
  wrapper unwrapping (`env`, `timeout`, `nice`, `busybox`), shell-`-c`
  blocking, git write-subcommand detection, inline-code-execution gating,
  request validation, environment allowlist sanitization.
- `executor.py` — `asyncio.create_subprocess_exec` (never `shell=True`),
  workspace/symlink-safe cwd resolution (`is_relative_to`), approval gate,
  polling timeout with SIGTERM→SIGKILL, cooperative cancellation that actually
  kills the process, per-stream + combined byte-accurate output limits,
  process bookkeeping (`active_count`).
- `manager.py` — validation → workspace → policy → approval → execution order,
  audit on every outcome, `cancel()`, `get_policy()`, `doctor()`.
- `audit.py` — `TerminalAuditLogger` **reusing Phase 9 `ToolAuditLogger`**;
  records classification/approval/timing/exit codes, never output bodies,
  arguments, or environment values.

**API** (`codeforge/api/routers/terminal.py`, registered in `app.py`)

- `POST /v1/terminal/execute`, `GET /v1/terminal/policy`,
  `GET /v1/terminal/health`.
- Errors mapped to 400/403/404/500 with structured codes, no stack traces.

**CLI** (`codeforge/cli.py`)

- `codeforge terminal doctor | policy | execute`
  (`--arg/--workspace/--cwd/--timeout/--approved`), all through the same
  `TerminalManager` security layer.

**Tests** (`tests/unit/test_terminal.py`, 110 tests)

- Request/result models, all four classifications, validation, execution,
  workspace escape (traversal, absolute, symlink, shell-expansion literals),
  timeout, cancellation, output limits (stream + combined), environment
  sanitization, approval flow, wrapper/shell injection security regressions
  (verifying side effects did **not** occur), process cleanup, audit content,
  doctor/policy surfaces, API (success/validation/blocked/timeout/workspace/
  404/422/truncation/no-stack-trace), CLI (doctor/policy/execute/blocked/
  approval), plus `/v1/health` regression coverage.

**Documentation**

- `docs/terminal.md` — architecture, API, CLI, usage.
- `docs/terminal-security.md` — threat model, controls, limitations, platforms.
- `docs/phase-10-audit.md` — pre-completion audit (bugs found, gaps, fixes).

## Bugs fixed from the audit

Empty child environment; timeout `NameError`; cancellation never killing the
process; ignored request limits; `startswith` prefix bug; DANGEROUS/BLOCKED
conflation with dead approval code; shell-`-c`/wrapper/git write
misclassification; broken relative imports + all E501/TID252/F401 errors.

## Definition of done

- [x] terminal package works
- [x] command policy works
- [x] workspace security works
- [x] environment sanitization works
- [x] timeout works
- [x] cancellation works
- [x] output limits work
- [x] API router exists
- [x] API router registered
- [x] API tests pass
- [x] CLI terminal doctor works
- [x] CLI terminal policy works
- [x] security tests pass
- [x] audit works
- [x] documentation exists
- [x] Ruff has 0 errors
- [x] full test suite passes
- [x] no Phase 1–9 regressions

## Explicitly out of scope (not built)

File editing, patch/diff, testing loop, agent engine, autonomous execution,
autonomous planning, memory, Git commit/push/pull, `shell=True`, any approval
bypass, model downloads.
