# Phase 10 — File Editing + Terminal

Phase 10 delivers safe, policy-gated file mutation and command execution.
The terminal half ships in [`docs/phase-10.md`](phase-10.md) /
`codeforge/packages/terminal/`; this document covers the **file editing**
half added with the `write_file` / `edit_file` / `run_command` tools.

## Package (`codeforge/packages/file_editing/`)

- `errors.py` — exception hierarchy: `FileEditingError` base with
  `PathTraversalError`, `WorkspaceAccessError`, `SensitiveFileBlockedError`,
  `FileNotFoundEditError`, `FileAlreadyExistsError`, `FileTooLargeError`,
  `InvalidEditError`, `StrReplaceMismatchError`. Every error carries a
  machine-readable `code` used for tool feedback and HTTP status mapping.
- `models.py` — `FileEditResult` (success/path/content/bytes_written/
  replacements/lines_before/lines_after/diff/error/error_code) and
  `FileReadResult`; both serialize via `to_dict()`.
- `policy.py` — `FileEditPolicy` resolves a workspace-relative path to an
  absolute `Path` and enforces:
  - workspace scoping (no `..`, no absolute paths, no symlink escapes),
  - sensitive-file deny list (`.env`, `.git/*`, keys, etc.),
  - `max_file_size_bytes` (default 2 MB) on read and write.
- `editor.py` — low-level primitives:
  - **atomic writes** — `tempfile.mkstemp` + `Path.replace()`, with cleanup
    on any failure (never leaves a partial file behind),
  - **exact-match `str_replace`** — requires the old text to match exactly
    (optionally `replace_all`), computes a unified diff, returns
    before/after line counts.
- `manager.py` — `FileEditManager` (`get_file_edit_manager()` singleton):
  `read()`, `write()`, `str_replace()`. All operations validate through the
  policy first, **never raise** (failures become `FileEditResult(success=False)`),
  and record an entry in the shared Phase 9 `ToolAuditLogger`
  (`file:read` / `file:write` / `file:str_replace` events with error codes,
  never file contents).

## Tools (`codeforge/packages/tools/builtins/`)

| Tool | Description | Permission |
|------|-------------|------------|
| `write_file` | Create/overwrite a workspace file (atomic, optional `create_only`) | `USER_APPROVAL` |
| `edit_file` | Exact-match `str_replace` with diff | `USER_APPROVAL` |
| `run_command` | Bridge to the Phase 10 `TerminalManager` — policy → approval → execution; dangerous commands can never self-approve | `USER_APPROVAL` |

All three are wired by `build_tool_manager()` (import from
`codeforge.packages.tools.builtins`), which registers every Phase 9 builtin
plus these three and applies the approval policy. The API router and the CLI
share this single factory so policy stays identical everywhere.

## API

| Endpoint | Description |
|----------|-------------|
| `POST /v1/files/read` | Read a workspace file (`{workspace_id, path}`) |
| `POST /v1/files/write` | Write a workspace file (atomic; `create_only` optional) |
| `POST /v1/files/str-replace` | Exact-match replace (`old`, `new`, `replace_all`) |
| `GET /v1/files/policy` | Effective policy (limits, deny list) |

Errors map to HTTP status: `path_traversal`/`workspace` → 403, file missing →
404, conflict (create-only) → 409, validation/size/mismatch → 400 — structured
`detail.code`, no stack traces.

## CLI

```bash
codeforge file read  src/app.py -w myws
codeforge file write notes.md -w myws -c "hello"      # or pipe via stdin
codeforge file write new.txt -w myws -c "x" --create-only
codeforge file edit src/app.py -w myws --old "old()" --new "new()"
codeforge file edit src/app.py -w myws --old "a" --new "c" --all
```

Failures print the `error_code` and exit non-zero; successful edits print
the unified diff.

## Tests

`tests/unit/test_file_editing.py` (50 tests) covers policy resolution,
editor primitives, manager operations, the three tools (including approval
gating and terminal bridging), the `/v1/files/*` API, and the CLI commands.
