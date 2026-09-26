"""Comprehensive tests for Phase 10 — Safe Terminal."""

from __future__ import annotations

import asyncio
import json
import os
import sys

import pytest
from starlette.testclient import TestClient

from codeforge.api import create_app
from codeforge.api.config import APIConfig, AppConfig, RateLimitConfig
from codeforge.packages.terminal import (
    BLOCKED_COMMANDS,
    DANGEROUS_COMMANDS,
    RESTRICTED_COMMANDS,
    CommandNotFoundError,
    CommandPermissionError,
    CommandPolicy,
    CommandPolicyConfig,
    CommandRequest,
    CommandResult,
    CommandStatus,
    CommandValidationError,
    DangerousCommandError,
    PathTraversalError,
    RiskLevel,
    TerminalError,
    TerminalManager,
    WorkspaceAccessError,
)

PY = sys.executable
IS_UNIX = os.name != "nt"


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / "workspaces" / "ws1"
    root.mkdir(parents=True)
    (root / "file.txt").write_text("content")
    (root / "src").mkdir()
    monkeypatch.chdir(tmp_path)
    return root


def _make_app():
    config = AppConfig(
        api=APIConfig(docs_enabled=True, auth_required=False),
        rate_limit=RateLimitConfig(enabled=False),
    )
    return create_app(config)


# ── CommandRequest / CommandResult ─────────────────────────────────────────


class TestModels:
    def test_request_defaults(self) -> None:
        request = CommandRequest(command="echo")
        assert request.arguments == []
        assert request.timeout_seconds == 30.0
        assert request.max_output_bytes == 100_000
        assert request.require_approval is True
        assert request.approved is False
        assert request.request_id

    def test_result_to_dict(self) -> None:
        result = CommandResult(command="echo", arguments=[], exit_code=0)
        data = result.to_dict()
        assert data["command"] == "echo"
        assert data["status"] == "completed"
        assert data["success"] is True
        assert data["security_classification"] == "safe"

    def test_result_success_requires_zero_exit(self) -> None:
        result = CommandResult(command="x", arguments=[], exit_code=1)
        assert result.success is False
        result.exit_code = 0
        assert result.success is True

    def test_result_success_requires_execution(self) -> None:
        result = CommandResult(command="x", arguments=[], executed=False, exit_code=0)
        assert result.success is False

    def test_execution_context_cancel(self) -> None:
        from codeforge.packages.terminal import CommandExecutionContext

        context = CommandExecutionContext()
        assert context.is_cancelled is False
        context.cancel()
        assert context.is_cancelled is True


# ── Classification ─────────────────────────────────────────────────────────


class TestClassification:
    def test_safe_command(self) -> None:
        policy = CommandPolicy()
        assert policy.classify("echo") == RiskLevel.SAFE

    def test_restricted_command(self) -> None:
        policy = CommandPolicy()
        assert policy.classify("grep") == RiskLevel.RESTRICTED
        assert policy.is_restricted("grep") is True

    def test_dangerous_command(self) -> None:
        policy = CommandPolicy()
        assert policy.classify("curl") == RiskLevel.DANGEROUS
        assert policy.is_dangerous("curl") is True

    def test_blocked_command(self) -> None:
        policy = CommandPolicy()
        assert policy.classify("sudo") == RiskLevel.BLOCKED
        assert policy.is_blocked("sudo") is True

    def test_sets_are_disjoint(self) -> None:
        assert not DANGEROUS_COMMANDS & BLOCKED_COMMANDS
        assert not RESTRICTED_COMMANDS & BLOCKED_COMMANDS

    def test_shell_with_string_flag_blocked(self) -> None:
        policy = CommandPolicy()
        for shell in ("sh", "bash", "zsh"):
            assert policy.classify(shell, ["-c", "ls"]) == RiskLevel.BLOCKED

    def test_shell_without_c_is_restricted_or_safe(self) -> None:
        policy = CommandPolicy()
        level = policy.classify("bash", ["--version"])
        assert level in (RiskLevel.SAFE, RiskLevel.RESTRICTED)

    def test_wrapper_cannot_launder_dangerous(self) -> None:
        policy = CommandPolicy()
        assert policy.classify("env", ["rm", "-rf", "x"]) == RiskLevel.DANGEROUS
        assert policy.classify("timeout", ["5", "rm", "-rf", "x"]) == RiskLevel.DANGEROUS
        assert policy.classify("nice", ["-n", "10", "curl", "http://x"]) == RiskLevel.DANGEROUS

    def test_git_write_is_dangerous(self) -> None:
        policy = CommandPolicy()
        assert policy.classify("git", ["push"]) == RiskLevel.DANGEROUS
        assert policy.classify("git", ["commit", "-m", "x"]) == RiskLevel.DANGEROUS
        assert policy.classify("git", ["status"]) == RiskLevel.SAFE
        assert policy.classify("git", ["diff"]) == RiskLevel.SAFE

    def test_inline_code_execution_is_dangerous(self) -> None:
        policy = CommandPolicy()
        assert policy.classify("python", ["-c", "print(1)"]) == RiskLevel.DANGEROUS
        assert policy.classify("python", ["-m", "pytest"]) == RiskLevel.RESTRICTED

    def test_find_mutating_flags_dangerous(self) -> None:
        policy = CommandPolicy()
        assert policy.classify("find", [".", "-delete"]) == RiskLevel.DANGEROUS
        assert policy.classify("find", [".", "-name", "*.py"]) == RiskLevel.RESTRICTED


# ── Validation ─────────────────────────────────────────────────────────────


class TestValidation:
    def test_empty_command(self) -> None:
        manager = TerminalManager()
        request = CommandRequest(command="   ", workspace_id="x")
        with pytest.raises(CommandValidationError):
            _run(manager.execute(request))

    def test_command_too_long(self) -> None:
        policy = CommandPolicy(CommandPolicyConfig(max_command_length=10))
        errors = policy.validate(CommandRequest(command="a" * 11))
        assert "Command too long" in errors

    def test_too_many_arguments(self) -> None:
        policy = CommandPolicy(CommandPolicyConfig(max_args=2))
        errors = policy.validate(CommandRequest(command="echo", arguments=["a", "b", "c"]))
        assert "Too many arguments" in errors

    def test_timeout_exceeds_maximum(self) -> None:
        policy = CommandPolicy(CommandPolicyConfig(max_timeout=5))
        errors = policy.validate(CommandRequest(command="echo", timeout_seconds=10))
        assert "Timeout exceeds maximum" in errors

    def test_timeout_must_be_positive(self) -> None:
        policy = CommandPolicy()
        errors = policy.validate(CommandRequest(command="echo", timeout_seconds=0))
        assert "Timeout must be positive" in errors

    @pytest.mark.parametrize(
        "command",
        [
            "echo hi && rm -rf /",
            "echo hi; rm -rf /",
            "echo hi | rm",
            "echo `id`",
            "echo $(whoami)",
            "echo > /etc/passwd",
            "echo && ls",
            "echo || ls",
        ],
    )
    def test_shell_metacharacters_rejected(self, command: str) -> None:
        manager = TerminalManager()
        request = CommandRequest(command=command, workspace_id="x")
        with pytest.raises(CommandValidationError):
            _run(manager.execute(request))

    def test_null_byte_rejected(self) -> None:
        policy = CommandPolicy()
        errors = policy.validate(CommandRequest(command="echo\x00bad"))
        assert any("null byte" in e for e in errors)

    def test_null_byte_argument_rejected(self) -> None:
        policy = CommandPolicy()
        errors = policy.validate(CommandRequest(command="echo", arguments=["a\x00b"]))
        assert any("null byte" in e for e in errors)

    def test_nonpositive_output_limit(self) -> None:
        policy = CommandPolicy()
        errors = policy.validate(CommandRequest(command="echo", max_output_bytes=0))
        assert any("max_output_bytes" in e for e in errors)


# ── Execution ──────────────────────────────────────────────────────────────


class TestExecution:
    @pytest.mark.skipif(not IS_UNIX, reason="echo not on Windows")
    def test_safe_execution(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(command="echo", arguments=["hello"], workspace_id="ws1")
        result = _run(manager.execute(request))
        assert result.status == CommandStatus.COMPLETED
        assert result.exit_code == 0
        assert result.stdout.strip() == "hello"
        assert result.security_classification.value == "safe"
        assert result.success is True

    def test_nonzero_exit_is_failed(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(
            command=PY,
            arguments=["-c", "import sys; sys.exit(3)"],
            workspace_id="ws1",
            approved=True,
        )
        result = _run(manager.execute(request))
        assert result.status == CommandStatus.FAILED
        assert result.exit_code == 3
        assert result.success is False

    def test_stderr_captured(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(
            command=PY,
            arguments=["-c", "import sys; sys.stderr.write('oops')"],
            workspace_id="ws1",
            approved=True,
        )
        result = _run(manager.execute(request))
        assert "oops" in result.stderr

    def test_command_not_found(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(command="definitely-not-a-real-command-xyz", workspace_id="ws1")
        with pytest.raises(CommandNotFoundError):
            _run(manager.execute(request))

    def test_subdirectory_cwd(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(
            command=PY,
            arguments=["-c", "import os; print(os.getcwd())"],
            workspace_id="ws1",
            working_directory="src",
            approved=True,
        )
        result = _run(manager.execute(request))
        assert result.stdout.strip().endswith("src")

    def test_absolute_workspace_id(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(
            command=PY,
            arguments=["-c", "print('ok')"],
            workspace_id=str(workspace),
            approved=True,
        )
        result = _run(manager.execute(request))
        assert result.stdout.strip() == "ok"


# ── Workspace security ─────────────────────────────────────────────────────


class TestWorkspaceSecurity:
    def test_missing_workspace(self) -> None:
        manager = TerminalManager()
        request = CommandRequest(command="echo", workspace_id="no-such-ws")
        with pytest.raises(WorkspaceAccessError):
            _run(manager.execute(request))

    @pytest.mark.parametrize("workspace_id", ["../../..", "..", "ws1/../../../etc"])
    def test_workspace_escape_rejected(self, workspace, workspace_id) -> None:
        manager = TerminalManager()
        request = CommandRequest(command="echo", workspace_id=workspace_id)
        with pytest.raises((PathTraversalError, WorkspaceAccessError)):
            _run(manager.execute(request))

    @pytest.mark.parametrize("rel", ["..", "../..", "../../etc", "/etc/passwd", "/etc"])
    def test_working_directory_escape_rejected(self, workspace, rel) -> None:
        manager = TerminalManager()
        request = CommandRequest(command="echo", workspace_id="ws1", working_directory=rel)
        with pytest.raises((PathTraversalError, WorkspaceAccessError)):
            _run(manager.execute(request))

    def test_symlink_escape_rejected(self, workspace, tmp_path) -> None:
        if os.name == "nt":
            pytest.skip("symlink creation may require privileges on Windows")
        outside = tmp_path / "outside"
        outside.mkdir()
        link = workspace / "link"
        link.symlink_to(outside)
        manager = TerminalManager()
        request = CommandRequest(command="echo", workspace_id="ws1", working_directory="link")
        with pytest.raises(PathTraversalError):
            _run(manager.execute(request))

    def test_missing_working_directory(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(
            command="echo", workspace_id="ws1", working_directory="does-not-exist"
        )
        with pytest.raises(WorkspaceAccessError):
            _run(manager.execute(request))

    def test_working_directory_must_be_directory(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(command="echo", workspace_id="ws1", working_directory="file.txt")
        with pytest.raises(WorkspaceAccessError):
            _run(manager.execute(request))

    def test_empty_workspace_id(self) -> None:
        manager = TerminalManager()
        request = CommandRequest(command="echo", workspace_id="")
        with pytest.raises(WorkspaceAccessError):
            _run(manager.execute(request))

    @pytest.mark.parametrize("rel", ["~", "$HOME", "$(whoami)", "`id`", "${USER}"])
    def test_shell_expansion_not_performed(self, workspace, rel, tmp_path) -> None:
        manager = TerminalManager()
        request = CommandRequest(command="echo", workspace_id="ws1", working_directory=rel)
        with pytest.raises((PathTraversalError, WorkspaceAccessError)):
            _run(manager.execute(request))
        assert not (tmp_path / rel).exists()


# ── Timeout ────────────────────────────────────────────────────────────────


class TestTimeout:
    def test_timeout_terminates_process(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(
            command=PY,
            arguments=["-c", "import time; time.sleep(20)"],
            workspace_id="ws1",
            timeout_seconds=0.5,
            approved=True,
        )
        result = _run(manager.execute(request))
        assert result.status == CommandStatus.TIMED_OUT
        assert result.timed_out is True
        assert result.cancelled is False
        assert result.duration_ms < 5000
        assert manager.executor.active_count == 0

    def test_timeout_within_bounds_not_triggered(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(
            command=PY,
            arguments=["-c", "print('fast')"],
            workspace_id="ws1",
            timeout_seconds=10,
            approved=True,
        )
        result = _run(manager.execute(request))
        assert result.timed_out is False
        assert result.status == CommandStatus.COMPLETED


# ── Cancellation ───────────────────────────────────────────────────────────


class TestCancellation:
    def test_cancel_running_process(self, workspace) -> None:
        async def scenario():
            manager = TerminalManager()
            request = CommandRequest(
                command=PY,
                arguments=["-c", "import time; time.sleep(20)"],
                workspace_id="ws1",
                approved=True,
            )
            task = asyncio.create_task(manager.execute(request))
            await asyncio.sleep(0.4)
            cancelled = await manager.cancel(request.request_id)
            result = await task
            return cancelled, result, manager.executor.active_count

        cancelled, result, active = _run(scenario())
        assert cancelled is True
        assert result.status == CommandStatus.CANCELLED
        assert result.cancelled is True
        assert active == 0

    def test_cancel_unknown_request(self, workspace) -> None:
        manager = TerminalManager()
        assert _run(manager.cancel("nope")) is False

    def test_pre_cancelled_context(self, workspace) -> None:
        from codeforge.packages.terminal import CommandExecutionContext

        manager = TerminalManager()
        request = CommandRequest(
            command=PY,
            arguments=["-c", "print(1)"],
            workspace_id="ws1",
            approved=True,
        )
        context = CommandExecutionContext(request_id=request.request_id)
        context.cancel()
        result = _run(manager.execute(request, context))
        assert result.status == CommandStatus.CANCELLED
        assert result.executed is False
        assert manager.executor.active_count == 0


# ── Output limits ──────────────────────────────────────────────────────────


class TestOutputLimits:
    def test_stdout_limit(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(
            command=PY,
            arguments=["-c", "print('a' * 50000)"],
            workspace_id="ws1",
            max_output_bytes=500,
            approved=True,
        )
        result = _run(manager.execute(request))
        assert result.truncated is True
        assert len(result.stdout) < 2000
        assert "(output truncated)" in result.stdout
        assert manager.executor.active_count == 0

    def test_stderr_limit(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(
            command=PY,
            arguments=[
                "-c",
                "import sys; sys.stderr.write('b' * 50000)",
            ],
            workspace_id="ws1",
            max_output_bytes=400,
            approved=True,
        )
        result = _run(manager.execute(request))
        assert result.truncated is True
        assert len(result.stderr) < 2000

    def test_combined_output_limit(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(
            command=PY,
            arguments=[
                "-c",
                ("import sys; sys.stdout.write('a' * 600); sys.stderr.write('b' * 600)"),
            ],
            workspace_id="ws1",
            max_output_bytes=500,
            max_total_output_bytes=700,
            approved=True,
        )
        result = _run(manager.execute(request))
        assert result.truncated is True
        marker_allowance = 100
        assert len(result.stdout) + len(result.stderr) <= 700 + marker_allowance

    def test_small_output_not_truncated(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(
            command=PY,
            arguments=["-c", "print('tiny')"],
            workspace_id="ws1",
            approved=True,
        )
        result = _run(manager.execute(request))
        assert result.truncated is False
        assert "tiny" in result.stdout


# ── Environment sanitization ───────────────────────────────────────────────


class TestEnvironmentSanitization:
    def test_environment_is_allowlisted(self, workspace, monkeypatch) -> None:
        monkeypatch.setenv("MY_API_KEY", "super-secret-value-xyz")
        manager = TerminalManager()
        allowed = set(manager.policy.allowed_env_vars)
        request = CommandRequest(
            command=PY,
            arguments=[
                "-c",
                "import os, json; print(json.dumps(sorted(os.environ)))",
            ],
            workspace_id="ws1",
            approved=True,
        )
        result = _run(manager.execute(request))
        keys = set(json.loads(result.stdout.strip()))
        assert "MY_API_KEY" not in keys
        assert "super-secret-value-xyz" not in result.stdout
        assert keys <= allowed
        assert "PATH" in keys

    def test_sanitize_environment_defaults_to_process_env(self, monkeypatch) -> None:
        monkeypatch.setenv("CUSTOM_ALLOWED_THING", "value")
        policy = CommandPolicy()
        clean = policy.sanitize_environment()
        assert "PATH" in clean
        assert "CUSTOM_ALLOWED_THING" not in clean

    def test_denied_environment_names(self) -> None:
        policy = CommandPolicy()
        assert policy.is_safe_environment({"PATH": "/bin"}) is True
        assert policy.is_safe_environment({"AWS_SECRET_ACCESS_KEY": "x"}) is False
        assert policy.is_safe_environment({"MY_TOKEN": "x"}) is False
        assert policy.is_safe_environment({"DB_PASSWORD": "x"}) is False


# ── Approval flow ──────────────────────────────────────────────────────────


class TestApprovalFlow:
    @pytest.mark.skipif(not IS_UNIX, reason="rm not on Windows")
    def test_dangerous_command_requires_approval(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(command="rm", arguments=["file.txt"], workspace_id="ws1")
        result = _run(manager.execute(request))
        assert result.status == CommandStatus.WAITING_APPROVAL
        assert result.executed is False
        assert result.approval_required is True
        assert (workspace / "file.txt").exists()

    @pytest.mark.skipif(not IS_UNIX, reason="rm not on Windows")
    def test_dangerous_command_with_approval_runs(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(
            command="rm",
            arguments=["file.txt"],
            workspace_id="ws1",
            approved=True,
        )
        result = _run(manager.execute(request))
        assert result.status == CommandStatus.COMPLETED
        assert result.executed is True
        assert not (workspace / "file.txt").exists()

    @pytest.mark.skipif(not IS_UNIX, reason="rm not on Windows")
    def test_approval_cannot_be_disabled(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(
            command="rm",
            arguments=["file.txt"],
            workspace_id="ws1",
            require_approval=False,
        )
        with pytest.raises(CommandPermissionError):
            _run(manager.execute(request))
        assert (workspace / "file.txt").exists()

    @pytest.mark.skipif(not IS_UNIX, reason="echo not on Windows")
    def test_safe_command_needs_no_approval(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(command="echo", arguments=["ok"], workspace_id="ws1")
        result = _run(manager.execute(request))
        assert result.status == CommandStatus.COMPLETED


# ── Security regressions ───────────────────────────────────────────────────


class TestSecurityRegressions:
    @pytest.mark.skipif(not IS_UNIX, reason="echo not on Windows")
    def test_shell_metacharacters_in_args_are_literal(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(
            command="echo",
            arguments=["a", "&&", "touch", "pwned.txt"],
            workspace_id="ws1",
        )
        result = _run(manager.execute(request))
        assert result.status == CommandStatus.COMPLETED
        assert "pwned.txt" in result.stdout
        assert not (workspace / "pwned.txt").exists()

    @pytest.mark.skipif(not IS_UNIX, reason="echo not on Windows")
    def test_redirect_and_pipe_are_literal(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(
            command="echo",
            arguments=[">", "out.txt", "|", "cat"],
            workspace_id="ws1",
        )
        result = _run(manager.execute(request))
        assert ">" in result.stdout
        assert not (workspace / "out.txt").exists()

    @pytest.mark.skipif(not IS_UNIX, reason="echo not on Windows")
    def test_command_substitution_is_literal(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(
            command="echo",
            arguments=["$(id)", "`hostname`", "${HOME}"],
            workspace_id="ws1",
        )
        result = _run(manager.execute(request))
        assert "$(id)" in result.stdout
        assert "`hostname`" in result.stdout
        assert "${HOME}" in result.stdout

    @pytest.mark.skipif(not IS_UNIX, reason="touch unavailable")
    def test_shell_c_never_executes(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(
            command="sh",
            arguments=["-c", "touch pwned.txt"],
            workspace_id="ws1",
            approved=True,
        )
        with pytest.raises(DangerousCommandError):
            _run(manager.execute(request))
        assert not (workspace / "pwned.txt").exists()

    @pytest.mark.skipif(not IS_UNIX, reason="sudo unavailable")
    def test_blocked_command_never_executes(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(
            command="sudo",
            arguments=["touch", "pwned.txt"],
            workspace_id="ws1",
            approved=True,
        )
        with pytest.raises(DangerousCommandError):
            _run(manager.execute(request))
        assert not (workspace / "pwned.txt").exists()
        error = DangerousCommandError("sudo")
        assert error.code == "DANGEROUS_COMMAND_BLOCKED"

    @pytest.mark.skipif(not IS_UNIX, reason="env unavailable")
    def test_env_wrapper_cannot_launder(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(
            command="env",
            arguments=["rm", "file.txt"],
            workspace_id="ws1",
        )
        result = _run(manager.execute(request))
        assert result.status == CommandStatus.WAITING_APPROVAL
        assert (workspace / "file.txt").exists()

    @pytest.mark.skipif(not IS_UNIX, reason="grep unavailable")
    def test_restricted_command_runs_without_approval(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(
            command="grep", arguments=["content", "file.txt"], workspace_id="ws1"
        )
        result = _run(manager.execute(request))
        assert result.status == CommandStatus.COMPLETED
        assert "content" in result.stdout

    def test_policy_disabled_does_not_disable_security(self, workspace) -> None:
        policy = CommandPolicy(CommandPolicyConfig(enabled=False))
        manager = TerminalManager(policy=policy)
        request = CommandRequest(command="sudo", arguments=["ls"], workspace_id="ws1")
        with pytest.raises(DangerousCommandError):
            _run(manager.execute(request))

    def test_error_payloads_have_no_stack_traces(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(command="nope-command-xyz", workspace_id="ws1")
        with pytest.raises(TerminalError) as excinfo:
            _run(manager.execute(request))
        payload = excinfo.value.to_dict()
        assert "Traceback" not in str(payload)
        assert set(payload) == {"code", "message", "command", "request_id"}


# ── Process cleanup ────────────────────────────────────────────────────────


class TestProcessCleanup:
    def test_active_count_returns_to_zero(self, workspace) -> None:
        manager = TerminalManager()
        for _ in range(3):
            request = CommandRequest(command=PY, arguments=["-c", "print(1)"], workspace_id="ws1")
            _run(manager.execute(request))
        assert manager.executor.active_count == 0

    def test_cleanup_all(self, workspace) -> None:
        manager = TerminalManager()
        assert manager.executor.cleanup_all() == 0


# ── Audit ──────────────────────────────────────────────────────────────────


class TestAudit:
    @pytest.mark.skipif(not IS_UNIX, reason="echo not on Windows")
    def test_execution_is_audited(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(command="echo", arguments=["x"], workspace_id="ws1")
        _run(manager.execute(request))
        assert manager.audit.count() == 1
        entry = manager.audit.get_entries(limit=10)[0]
        assert entry.tool_name == "terminal:echo"
        assert entry.metadata["status"] == "completed"
        assert entry.metadata["exit_code"] == 0

    def test_rejection_is_audited(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(command="sudo", arguments=["ls"], workspace_id="ws1")
        with pytest.raises(DangerousCommandError):
            _run(manager.execute(request))
        assert manager.audit.count() == 1
        entry = manager.audit.get_entries(limit=10)[0]
        assert entry.success is False
        assert entry.error_code == "DANGEROUS_COMMAND_BLOCKED"

    def test_audit_records_no_secret_output(self, workspace, monkeypatch) -> None:
        monkeypatch.setenv("AUDIT_SECRET_TOKEN", "env-secret-should-not-run")
        manager = TerminalManager()
        request = CommandRequest(
            command=PY,
            arguments=[
                "-c",
                (
                    "import os; print('leaked-secret-value-123'); "
                    "print(os.environ.get('AUDIT_SECRET_TOKEN'))"
                ),
            ],
            workspace_id="ws1",
            approved=True,
        )
        result = _run(manager.execute(request))
        assert "leaked-secret-value-123" in result.stdout
        assert "env-secret-should-not-run" not in result.stdout
        entry = manager.audit.get_entries(limit=10)[0]
        dumped = str(entry.metadata) + str(entry.tool_name)
        assert "leaked-secret-value-123" not in dumped
        assert "stdout" not in entry.metadata

    def test_audit_stats(self, workspace) -> None:
        manager = TerminalManager()
        request = CommandRequest(
            command=PY,
            arguments=["-c", "print('x')"],
            workspace_id="ws1",
            approved=True,
        )
        _run(manager.execute(request))
        stats = manager.audit.stats()
        assert stats["total"] == 1
        assert stats["success"] == 1


# ── Doctor / policy surfaces ───────────────────────────────────────────────


class TestDoctorAndPolicy:
    def test_doctor_reports_configuration(self) -> None:
        manager = TerminalManager()
        info = manager.doctor()
        assert info["terminal_enabled"] is True
        assert info["shell_execution"] is False
        assert info["executor"] == "asyncio-subprocess"
        assert info["default_timeout"] > 0
        assert info["max_timeout"] >= info["default_timeout"]
        assert info["max_output_bytes"] > 0
        assert "PATH" in info["environment_policy"]

    def test_doctor_has_no_secrets(self, monkeypatch) -> None:
        monkeypatch.setenv("DOCTOR_SECRET_KEY", "secret-doctor-value")
        manager = TerminalManager()
        dumped = str(manager.doctor())
        assert "secret-doctor-value" not in dumped

    def test_policy_dict_structure(self) -> None:
        data = CommandPolicy().to_dict()
        assert data["enabled"] is True
        assert data["approval_required"] is True
        assert "sudo" in data["blocked_commands"]
        assert "rm" in data["dangerous_commands"]
        assert "grep" in data["restricted_commands"]
        assert "PATH" in data["environment_allowed_variables"]
        assert data["max_timeout"] > 0


# ── API ────────────────────────────────────────────────────────────────────


class TestTerminalAPI:
    def test_health_still_works(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_terminal_health(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/terminal/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["shell_execution"] is False

    def test_terminal_policy_endpoint(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/terminal/policy")
        assert response.status_code == 200
        body = response.json()
        assert "blocked_commands" in body
        assert "dangerous_commands" in body

    @pytest.mark.skipif(not IS_UNIX, reason="echo not on Windows")
    def test_execute_success(self, tmp_path) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/terminal/execute",
            json={
                "workspace_id": str(tmp_path),
                "command": "echo",
                "arguments": ["api-ok"],
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["status"] == "completed"
        assert "api-ok" in body["stdout"]
        assert body["security_classification"] == "safe"

    def test_execute_validation_failure(self, tmp_path) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/terminal/execute",
            json={
                "workspace_id": str(tmp_path),
                "command": "echo hi && touch x",
            },
        )
        assert response.status_code == 400
        error = response.json()["error"]
        assert error["code"] == "COMMAND_VALIDATION_ERROR"
        assert "Traceback" not in response.text

    def test_execute_blocked_command(self, tmp_path) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        marker = tmp_path / "api-pwned.txt"
        response = client.post(
            "/v1/terminal/execute",
            json={
                "workspace_id": str(tmp_path),
                "command": "sh",
                "arguments": ["-c", f"touch {marker}"],
                "approved": True,
            },
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "DANGEROUS_COMMAND_BLOCKED"
        assert not marker.exists()

    def test_execute_workspace_error(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/terminal/execute",
            json={"workspace_id": "missing-workspace-zzz", "command": "echo"},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "WORKSPACE_ACCESS_ERROR"

    def test_execute_path_traversal(self, tmp_path) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/terminal/execute",
            json={
                "workspace_id": str(tmp_path),
                "command": "echo",
                "working_directory": "../../etc",
            },
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "PATH_TRAVERSAL_ERROR"

    def test_execute_command_not_found(self, tmp_path) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/terminal/execute",
            json={
                "workspace_id": str(tmp_path),
                "command": "not-a-real-cmd-abc",
            },
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "COMMAND_NOT_FOUND"

    @pytest.mark.skipif(not IS_UNIX, reason="rm not on Windows")
    def test_execute_waiting_approval(self, tmp_path) -> None:
        (tmp_path / "victim.txt").write_text("keep")
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/terminal/execute",
            json={
                "workspace_id": str(tmp_path),
                "command": "rm",
                "arguments": ["victim.txt"],
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "waiting_approval"
        assert body["executed"] is False
        assert (tmp_path / "victim.txt").exists()

    def test_execute_timeout(self, tmp_path) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/terminal/execute",
            json={
                "workspace_id": str(tmp_path),
                "command": PY,
                "arguments": ["-c", "import time; time.sleep(20)"],
                "timeout": 0.4,
                "approved": True,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "timed_out"
        assert body["timed_out"] is True

    def test_execute_truncation(self, tmp_path) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/terminal/execute",
            json={
                "workspace_id": str(tmp_path),
                "command": PY,
                "arguments": ["-c", "print('z' * 40000)"],
                "max_output_bytes": 300,
                "approved": True,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["truncated"] is True
        assert len(body["stdout"]) < 2000

    def test_execute_missing_required_fields(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post("/v1/terminal/execute", json={"command": "echo"})
        assert response.status_code == 422

    def test_no_stack_traces_in_errors(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/terminal/execute",
            json={"workspace_id": "nope-ws", "command": "echo"},
        )
        assert "Traceback" not in response.text
        assert 'File "' not in response.text


# ── CLI ────────────────────────────────────────────────────────────────────


class TestTerminalCLI:
    def test_terminal_doctor(self, monkeypatch) -> None:
        from click.testing import CliRunner

        from codeforge.cli import main

        monkeypatch.setenv("CLI_SECRET_VALUE", "cli-secret-abc-123")
        runner = CliRunner()
        result = runner.invoke(main, ["terminal", "doctor"])
        assert result.exit_code == 0
        assert "Terminal Doctor" in result.output
        assert "cli-secret-abc-123" not in result.output

    def test_terminal_policy(self) -> None:
        from click.testing import CliRunner

        from codeforge.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["terminal", "policy"])
        assert result.exit_code == 0
        assert "BLOCKED" in result.output
        assert "DANGEROUS" in result.output
        assert "RESTRICTED" in result.output
        assert "SAFE" in result.output

    @pytest.mark.skipif(not IS_UNIX, reason="echo not on Windows")
    def test_terminal_execute_safe(self, tmp_path) -> None:
        from click.testing import CliRunner

        from codeforge.cli import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "terminal",
                "execute",
                "echo",
                "--arg",
                "cli-ok",
                "-w",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0
        assert "cli-ok" in result.output
        assert "COMPLETED" in result.output

    def test_terminal_execute_blocked(self, tmp_path) -> None:
        from click.testing import CliRunner

        from codeforge.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["terminal", "execute", "sudo", "-w", str(tmp_path)])
        assert result.exit_code == 1
        assert "DANGEROUS_COMMAND_BLOCKED" in result.output

    @pytest.mark.skipif(not IS_UNIX, reason="rm not on Windows")
    def test_terminal_execute_needs_approval(self, tmp_path) -> None:
        from click.testing import CliRunner

        from codeforge.cli import main

        (tmp_path / "file.txt").write_text("keep")
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "terminal",
                "execute",
                "rm",
                "--arg",
                "file.txt",
                "-w",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 2
        assert "Approval required" in result.output
        assert (tmp_path / "file.txt").exists()

    @pytest.mark.skipif(not IS_UNIX, reason="rm not on Windows")
    def test_terminal_execute_approved(self, tmp_path) -> None:
        from click.testing import CliRunner

        from codeforge.cli import main

        (tmp_path / "file.txt").write_text("remove me")
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "terminal",
                "execute",
                "rm",
                "--arg",
                "file.txt",
                "-w",
                str(tmp_path),
                "--approved",
            ],
        )
        assert result.exit_code == 0
        assert not (tmp_path / "file.txt").exists()
