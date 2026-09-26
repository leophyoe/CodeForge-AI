# Terminal Security Model

Phase 10 treats every command as hostile input. This document is the
authoritative description of the controls, what they defend against, and what
they deliberately do **not** defend against.

## Security pipeline

```
request validation      command token shape, arg count, timeout ceiling,
                        null-byte rejection, size limits
        ↓
workspace validation    workspace root must exist; relative workspace ids
                        cannot escape workspaces/; symlink escapes resolved
        ↓
command policy          classify → BLOCKED raises, DANGEROUS needs approval
        ↓
approval                approved=True required; require_approval=False on a
                        dangerous command is a permission error (no bypass)
        ↓
execution               no shell, sanitized env, restricted cwd, bounded
                        output, timeout, cancellable
```

## 1. No shell, ever

- Execution uses `asyncio.create_subprocess_exec` — **never `shell=True`**.
- `command` must be a single token matching `[A-Za-z0-9_+./\\:@%=-]+`;
  anything containing whitespace or shell metacharacters
  (`; | & > < $ \` ( ) …`) is rejected with `COMMAND_VALIDATION_ERROR`
  before any process exists.
- Because no shell is spawned, `&&`, `||`, `;`, `|`, `>`, `>>`, `*`, `?`,
  `$(…)`, backticks, `~` and `$HOME` in **arguments or paths are literal
  characters** — never expanded or interpreted. Verified by tests such as
  `test_shell_metacharacters_in_args_are_literal`.

## 2. Classification

| Level | Behavior | Examples |
|-------|----------|----------|
| BLOCKED | raises `DangerousCommandError`, process is **never created** | `sudo`, `su`, `doas`, `shutdown`, `reboot`, `poweroff`, `mkfs`, `dd`, `mount`, `systemctl`, `passwd`, `chpasswd`, `iptables`, `sh -c` / `bash -c` (shell-string execution) |
| DANGEROUS | runs only with `approved=True`; otherwise `waiting_approval` | `rm`, `mv`, `cp`, `chmod`, `chown`, `curl`, `wget`, `nc`, `ssh`, `scp`, `rsync`, `tar`, `xargs`, `git push/commit/reset/…`, `python -c`, `perl -e`, `find -delete` / `-exec` |
| RESTRICTED | runs, audited as restricted | `grep`, `find`, `sed`, `awk`, `python -m …`, `node`, `npm`, `make`, `gcc`, `cargo`, `docker`, `kill`, `ps` |
| SAFE | runs, audited as safe | `echo`, `ls`, `cat`, `git status`, `git diff` |

Defense in depth:

- **Wrapper unwrapping** — `env rm …`, `timeout 5 rm …`, `nice -n 10 curl …`,
  `busybox rm …` are re-classified by the *effective* command, so wrappers
  cannot launder a dangerous command.
- **Shell-string execution is blocked outright**, even with approval:
  `sh -c "touch x"` raises and the file is verified not created.
- **Inline code execution** (`python -c`, `perl -e`, `node -e`) is DANGEROUS
  (approval required), while `python -m pytest` stays RESTRICTED.
- **`enabled=False` does not disable enforcement** — the policy config flag is
  reported in diagnostics but security checks always run.

## 3. Approval

- BLOCKED commands cannot be approved: `approved=True` still raises.
- DANGEROUS commands without approval return `status=waiting_approval`,
  `executed=false` — verified that side effects did **not** happen
  (e.g. the target file still exists).
- Setting `require_approval=False` for a dangerous command raises
  `COMMAND_PERMISSION_DENIED`; there is no API to skip the gate.
- Approval state is recorded in the audit entry.

## 4. Workspace boundary

- The workspace root is the trust boundary:
  - relative `workspace_id` resolves under `workspaces/` and must stay there
    (`ws1/../../..` → `PATH_TRAVERSAL_ERROR`);
  - absolute `workspace_id` is accepted as a workspace root (this mirrors the
    Phase 9 tools convention) — **the caller chooses the root; the boundary
    prevents escaping it**. API clients are expected to pass a registered
    workspace.
- `working_directory` is resolved with `Path.resolve()` (symlinks collapsed)
  and must satisfy `is_relative_to(root)`:
  - `..`, `../..`, `../../etc` → rejected;
  - absolute paths outside the root (`/etc`, `/etc/passwd`) → rejected;
  - symlinks pointing outside the root → rejected;
  - `~`, `$HOME`, `$(whoami)` are **not expanded** (no shell), so they only
    match literal directories that do not exist → rejected.
- Nonexistent workspace / cwd / cwd-that-is-a-file → `WORKSPACE_ACCESS_ERROR`.
- Tested with the malicious paths from the security checklist
  (`../../`, `/etc/passwd`, `~/`, `$(command)`, backticks, `&&`, `;`, `|`, `>`).

## 5. Environment sanitization

- Children receive **only allowlisted variables**: `PATH`, `HOME`, `USER`,
  `LANG`, `LC_ALL`, `LC_CTYPE`, `TERM`, `SHELL`, `PWD`, `TMPDIR`
  (plus `SYSTEMROOT`, `COMSPEC`, `TEMP`, … on Windows). `PATH` is guaranteed
  with `os.defpath` fallback.
- Deny patterns (`KEY`, `SECRET`, `TOKEN`, `PASSWORD`, `CREDENTIAL`, `AWS_`,
  `GCP_`, `AZURE_`) are re-checked even inside the allowlist.
- Secrets in the parent environment are therefore **never visible to child
  processes** — verified by a test asserting `MY_API_KEY` never appears in
  the child's environment.
- The API and `terminal doctor` never print environment values.

## 6. Output, timeout, cancellation

- Per-stream limit (`max_output_bytes`, default 100 000) and combined limit
  (`max_total_output_bytes`, default 400 000). Truncated results are marked
  and clipped byte-safely — oversized output cannot be used to exhaust memory.
- Timeout hierarchy: request timeout must be positive and ≤ policy
  `max_timeout` (default 300 s); on expiry the process group is SIGTERMed,
  then SIGKILLed (Unix). Test processes are verified to be reaped
  (`active_count == 0`).
- Cancellation (`manager.cancel(request_id)`) signals the process and returns
  `status=cancelled`; processes are cleaned up; cancelling an unknown id
  returns `False`.

## 7. Audit (what is and is not recorded)

Recorded: request id, workspace id, command, classification, approval state,
working directory, duration, exit code, status, timeout/cancel flags, output
**byte counts**, argument **count**.

Never recorded: stdout/stderr bodies, argument values, environment values,
tokens, passwords, API keys. Metadata keys that look secret-shaped
(`secret`, `token`, `password`, `key`) are dropped defensively.
Tested: a secret printed by a command appears in `result.stdout` but never in
the audit entry.

## 8. API hardening

- Structured errors only (`code`, `message`, `request_id`) — no stack traces,
  no internal paths leaked beyond what the caller supplied.
- Pydantic validation: required fields, length caps, `timeout > 0`,
  `max_output_bytes > 0`.
- Status mapping: 400 validation/workspace, 403 blocked/permission,
  404 not found, 500 spawn failure.
- Output size is bounded before it ever reaches the client.
- Existing request-id, timing, security-headers, and rate-limit middleware
  from Phase 5 still wrap the terminal routes.

## 9. Untrusted test output

Test/command output is **data**: it is captured, bounded, and displayed. It is
never parsed for instructions, never executed, and never used to construct a
command. (Phase 12 must keep this property when it adds diagnostics parsing.)

## Known limitations

- **No OS-level sandbox.** Workspace restriction is a path policy, not a
  kernel sandbox: a RESTRICTED command like `python script.py` can, in
  principle, access the whole filesystem with the user's own permissions.
  Approval-gating arbitrary-code flags (`python -c`) narrows but does not
  eliminate this. A future phase may add containers/OS sandboxing.
- **No network isolation.** `curl` is DANGEROUS (approval) but approved
  commands are not network-restricted.
- **`make`, `docker`, `perl` (RESTRICTED)** can run arbitrary side effects by
  design — they are audited, not blocked.
- **Local trust model.** Like Phase 9 tools, the API trusts its local caller
  to name valid workspace roots; it prevents escaping a root, not choosing one.

## Platform differences

| Concern | Linux | macOS | Windows |
|---------|-------|-------|---------|
| Process-group SIGKILL | yes | yes | no — `terminate()`/`kill()` per process |
| `start_new_session` | yes | yes | disabled (`os.name == "nt"`) |
| Extra env allowlist (`SYSTEMROOT`, `COMSPEC`, …) | no | no | yes |
| `.exe` suffix stripped during classification | no | no | yes |
| Test status | **executed in CI** | not executed | not executed |

Windows/macOS code paths exist and are guarded, but have **not** been
execution-tested here; do not assume them verified.
