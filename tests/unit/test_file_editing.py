"""Tests for Phase 10 — file editing package, tools, API, and CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from codeforge.packages.file_editing import (
    FileAlreadyExistsError,
    FileEditManager,
    FileEditPolicy,
    FileNotFoundEditError,
    FileTooLargeError,
    InvalidEditError,
    PathTraversalError,
    SensitiveFileBlockedError,
    StrReplaceMismatchError,
    WorkspaceAccessError,
    editor,
    get_file_edit_manager,
)
from codeforge.packages.tools.manager import ToolManager
from codeforge.packages.tools.models import PermissionLevel, ToolExecutionContext
from codeforge.packages.tools.policy import ToolPolicyConfig

if TYPE_CHECKING:
    from pathlib import Path

WORKSPACE = "ws1"


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run in an isolated cwd with a workspace directory."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspaces" / WORKSPACE).mkdir(parents=True)
    return tmp_path


@pytest.fixture
def manager(root: Path) -> FileEditManager:
    del root
    return FileEditManager()


@pytest.fixture
def tool_manager() -> ToolManager:
    from codeforge.api.routers.tools import get_manager, reset_manager

    reset_manager()
    mgr = get_manager()
    yield mgr
    reset_manager()


# ── editor (pure operations) ──────────────────────────────────────────────


class TestEditor:
    def test_write_creates_file(self, root: Path) -> None:
        path = root / "workspaces" / WORKSPACE / "a.txt"
        written, lines, diff = editor.write_file(
            path, "one\ntwo\n", create_only=False, max_bytes=1000
        )
        assert written == 8
        assert lines == 2
        assert diff == ""
        assert path.read_text() == "one\ntwo\n"

    def test_write_overwrite_diff(self, root: Path) -> None:
        path = root / "x.txt"
        path.write_text("old\n")
        written, _, diff = editor.write_file(path, "new\n", create_only=False, max_bytes=1000)
        assert written == 4
        assert "-old" in diff
        assert "+new" in diff

    def test_write_create_only_conflict(self, root: Path) -> None:
        path = root / "x.txt"
        path.write_text("existing")
        with pytest.raises(FileAlreadyExistsError):
            editor.write_file(path, "new", create_only=True, max_bytes=1000)

    def test_write_too_large(self, root: Path) -> None:
        with pytest.raises(FileTooLargeError):
            editor.write_file(root / "big.txt", "x" * 100, create_only=False, max_bytes=10)

    def test_write_leaves_no_temp_files(self, root: Path) -> None:
        path = root / "x.txt"
        editor.write_file(path, "data", create_only=False, max_bytes=1000)
        leftovers = [p.name for p in root.iterdir() if p.name.startswith(".cf-edit-")]
        assert leftovers == []

    def test_read_missing(self, root: Path) -> None:
        with pytest.raises(FileNotFoundEditError):
            editor.read_text(root / "nope.txt", max_bytes=1000)

    def test_str_replace_single(self, root: Path) -> None:
        path = root / "x.txt"
        path.write_text("alpha beta gamma\n")
        count, before, after, diff, updated = editor.str_replace(
            path, "alpha", "delta", replace_all=False, max_bytes=1000
        )
        assert count == 1
        assert updated == "delta beta gamma\n"
        assert (before, after) == (1, 1)
        assert "+delta" in diff

    def test_str_replace_all(self, root: Path) -> None:
        path = root / "x.txt"
        path.write_text("aa aa aa\n")
        count, _, _, _, updated = editor.str_replace(
            path, "aa", "bb", replace_all=True, max_bytes=1000
        )
        assert count == 3
        assert updated == "bb bb bb\n"

    def test_str_replace_multiple_without_all_errors(self, root: Path) -> None:
        path = root / "x.txt"
        path.write_text("dup dup\n")
        with pytest.raises(StrReplaceMismatchError) as exc:
            editor.str_replace(path, "dup", "x", replace_all=False, max_bytes=1000)
        assert exc.value.found == 2

    def test_str_replace_zero_matches(self, root: Path) -> None:
        path = root / "x.txt"
        path.write_text("text\n")
        with pytest.raises(StrReplaceMismatchError) as exc:
            editor.str_replace(path, "missing", "x", replace_all=False, max_bytes=1000)
        assert exc.value.found == 0

    def test_str_replace_invalid_inputs(self, root: Path) -> None:
        path = root / "x.txt"
        path.write_text("text\n")
        with pytest.raises(InvalidEditError):
            editor.str_replace(path, "", "x", replace_all=False, max_bytes=1000)
        with pytest.raises(InvalidEditError):
            editor.str_replace(path, "text", "text", replace_all=False, max_bytes=1000)


# ── policy (workspace boundary) ───────────────────────────────────────────


class TestPolicy:
    def test_resolves_inside_workspace(self, root: Path) -> None:
        policy = FileEditPolicy()
        resolved = policy.resolve(WORKSPACE, "src/main.py")
        assert resolved == (root / "workspaces" / WORKSPACE / "src/main.py").resolve()

    def test_blocks_traversal(self) -> None:
        policy = FileEditPolicy()
        with pytest.raises(PathTraversalError):
            policy.resolve(WORKSPACE, "../../etc/passwd")
        with pytest.raises(PathTraversalError):
            policy.resolve(WORKSPACE, "/etc/passwd")

    def test_blocks_symlink_escape(self, root: Path) -> None:
        policy = FileEditPolicy()
        outside = root / "outside.txt"
        outside.write_text("secret")
        link = root / "workspaces" / WORKSPACE / "link.txt"
        link.symlink_to(outside)
        with pytest.raises(PathTraversalError):
            policy.resolve(WORKSPACE, "link.txt")

    def test_blocks_empty_ids(self) -> None:
        policy = FileEditPolicy()
        with pytest.raises(WorkspaceAccessError):
            policy.resolve("", "a.txt")
        with pytest.raises(WorkspaceAccessError):
            policy.resolve(WORKSPACE, "  ")

    @pytest.mark.parametrize("name", [".env", "config/.env.local", "id_rsa.key", "secrets.json"])
    def test_blocks_sensitive_files(self, name: str) -> None:
        policy = FileEditPolicy()
        with pytest.raises(SensitiveFileBlockedError):
            policy.check_write(WORKSPACE, name)

    def test_sensitive_detection(self) -> None:
        policy = FileEditPolicy()
        assert policy.is_sensitive(".env")
        assert policy.is_sensitive("server.pem")
        assert not policy.is_sensitive("main.py")


# ── manager (policy + editor + audit) ─────────────────────────────────────


class TestFileEditManager:
    def test_write_read_roundtrip(self, manager: FileEditManager) -> None:
        result = manager.write(WORKSPACE, "notes.txt", "hello\n")
        assert result.success
        assert result.bytes_written == 6
        read = manager.read(WORKSPACE, "notes.txt")
        assert read.success
        assert read.content == "hello\n"
        assert read.total_lines == 1

    def test_str_replace_reports_diff(self, manager: FileEditManager) -> None:
        manager.write(WORKSPACE, "app.py", "value = 1\n")
        result = manager.str_replace(WORKSPACE, "app.py", "value = 1", "value = 2")
        assert result.success
        assert result.replacements == 1
        assert "-value = 1" in result.diff
        assert "+value = 2" in result.diff

    def test_error_codes(self, manager: FileEditManager) -> None:
        assert manager.read(WORKSPACE, "missing.txt").error_code == "file_not_found"
        assert manager.write(WORKSPACE, "../evil.txt", "x").error_code == "path_traversal_error"
        assert manager.write(WORKSPACE, ".env", "x").error_code == "sensitive_file_blocked"
        manager.write(WORKSPACE, "exists.txt", "a")
        assert (
            manager.write(WORKSPACE, "exists.txt", "b", create_only=True).error_code
            == "file_already_exists"
        )
        manager.write(WORKSPACE, "dup.txt", "aa")
        assert manager.str_replace(WORKSPACE, "dup.txt", "a", "b").error_code == "replace_mismatch"

    def test_audit_entries(self) -> None:
        mgr = FileEditManager()
        mgr.write(WORKSPACE, "audited.txt", "x")
        mgr.read(WORKSPACE, "audited.txt")
        entries = mgr.audit.get_entries(limit=10)
        names = {e.tool_name for e in entries}
        assert {"file:write", "file:read"} <= names

    def test_get_policy(self, manager: FileEditManager) -> None:
        policy = manager.get_policy()
        assert policy["workspace_root"] == "workspaces"
        assert policy["max_file_size_bytes"] > 0

    def test_singleton(self) -> None:
        assert get_file_edit_manager() is get_file_edit_manager()


# ── write_file / edit_file tools ──────────────────────────────────────────


class TestWriteTools:
    def _ctx(self) -> ToolExecutionContext:
        return ToolExecutionContext(workspace_id=WORKSPACE)

    def test_write_file_tool(self, root: Path, tool_manager: ToolManager) -> None:
        result = tool_manager.execute_tool(
            "write_file",
            {"workspace_id": WORKSPACE, "path": "tool.txt", "content": "made by tool\n"},
            self._ctx(),
        )
        assert result.success
        assert result.result["bytes_written"] == 13
        assert (root / "workspaces" / WORKSPACE / "tool.txt").exists()

    def test_edit_file_tool(self, tool_manager: ToolManager) -> None:
        get_file_edit_manager().write(WORKSPACE, "cfg.txt", "port=1\n")
        result = tool_manager.execute_tool(
            "edit_file",
            {
                "workspace_id": WORKSPACE,
                "path": "cfg.txt",
                "old": "port=1",
                "new": "port=8080",
            },
            self._ctx(),
        )
        assert result.success
        assert result.result["replacements"] == 1
        assert "port=8080" in get_file_edit_manager().read(WORKSPACE, "cfg.txt").content

    def test_write_blocked_by_default_policy(self) -> None:
        from codeforge.packages.tools.builtins import WriteFileTool

        manager = ToolManager()  # fresh registry, default READ_ONLY policy
        manager.registry.register(WriteFileTool())
        result = manager.execute_tool(
            "write_file",
            {"workspace_id": WORKSPACE, "path": "x.txt", "content": "x"},
            self._ctx(),
        )
        assert not result.success
        assert "Permission denied" in result.error

    def test_permission_can_be_raised(self, tool_manager: ToolManager) -> None:
        tool_manager.policy.configure(
            "write_file",
            ToolPolicyConfig(permission=PermissionLevel.PRIVILEGED, enabled=False),
        )
        result = tool_manager.execute_tool(
            "write_file",
            {"workspace_id": WORKSPACE, "path": "x.txt", "content": "x"},
            self._ctx(),
        )
        assert not result.success  # disabled wins
        tool_manager.policy.configure(
            "write_file", ToolPolicyConfig(permission=PermissionLevel.PRIVILEGED)
        )
        result = tool_manager.execute_tool(
            "write_file",
            {"workspace_id": WORKSPACE, "path": "x.txt", "content": "x"},
            self._ctx(),
        )
        assert result.success

    def test_write_tool_traversal_blocked(self, tool_manager: ToolManager) -> None:
        result = tool_manager.execute_tool(
            "write_file",
            {"workspace_id": WORKSPACE, "path": "../escape.txt", "content": "x"},
            self._ctx(),
        )
        assert not result.success
        assert "traversal" in result.error.lower()

    def test_edit_tool_mismatch_feedback(self, tool_manager: ToolManager) -> None:
        get_file_edit_manager().write(WORKSPACE, "s.txt", "abc\n")
        result = tool_manager.execute_tool(
            "edit_file",
            {"workspace_id": WORKSPACE, "path": "s.txt", "old": "zzz", "new": "y"},
            self._ctx(),
        )
        assert not result.success

    def test_input_validation(self, tool_manager: ToolManager) -> None:
        result = tool_manager.execute_tool("write_file", {"path": "x"}, self._ctx())
        assert not result.success
        result = tool_manager.execute_tool(
            "edit_file",
            {"workspace_id": WORKSPACE, "path": "x", "old": "", "new": "y"},
            self._ctx(),
        )
        assert not result.success


# ── run_command tool ──────────────────────────────────────────────────────


class TestRunCommandTool:
    def _ctx(self) -> ToolExecutionContext:
        return ToolExecutionContext(workspace_id=WORKSPACE)

    def test_safe_command(self, root: Path, tool_manager: ToolManager) -> None:
        del root
        result = tool_manager.execute_tool(
            "run_command",
            {"workspace_id": WORKSPACE, "command": "echo", "args": ["agent-ok"]},
            self._ctx(),
        )
        assert result.success
        assert result.result["stdout"].strip() == "agent-ok"
        assert result.result["exit_code"] == 0

    def test_dangerous_command_needs_approval(self, tool_manager: ToolManager) -> None:
        result = tool_manager.execute_tool(
            "run_command",
            {"workspace_id": WORKSPACE, "command": "rm", "args": ["-rf", "x"]},
            self._ctx(),
        )
        assert not result.success
        assert "approval_required" in result.error

    def test_failing_command_reports_stderr(self, tool_manager: ToolManager) -> None:
        result = tool_manager.execute_tool(
            "run_command",
            {"workspace_id": WORKSPACE, "command": "ls", "args": ["/definitely-missing"]},
            self._ctx(),
        )
        assert not result.success

    def test_input_validation(self, tool_manager: ToolManager) -> None:
        assert not tool_manager.execute_tool(
            "run_command", {"workspace_id": WORKSPACE, "command": ""}, self._ctx()
        ).success
        assert not tool_manager.execute_tool(
            "run_command",
            {"workspace_id": WORKSPACE, "command": "echo", "args": "not-a-list"},
            self._ctx(),
        ).success
        assert not tool_manager.execute_tool(
            "run_command", {"command": "echo"}, self._ctx()
        ).success

    def test_shell_interpreter_blocked(self, tool_manager: ToolManager) -> None:
        result = tool_manager.execute_tool(
            "run_command",
            {"workspace_id": WORKSPACE, "command": "bash", "args": ["-c", "echo hi"]},
            self._ctx(),
        )
        assert not result.success


# ── API ───────────────────────────────────────────────────────────────────


def _client() -> TestClient:
    from codeforge.api.app import create_app
    from codeforge.api.config import APIConfig, AppConfig, RateLimitConfig

    config = AppConfig(
        api=APIConfig(docs_enabled=True, auth_required=False),
        rate_limit=RateLimitConfig(enabled=False),
    )
    return TestClient(create_app(config))


class TestFilesAPI:
    @pytest.fixture(autouse=True)
    def _isolated(self, root: Path):
        from codeforge.api.routers.tools import reset_manager

        del root
        reset_manager()
        yield
        reset_manager()

    def test_write_read_roundtrip(self) -> None:
        client = _client()
        response = client.post(
            "/v1/files/write",
            json={"workspace_id": WORKSPACE, "path": "api.txt", "content": "via api\n"},
        )
        assert response.status_code == 200
        assert response.json()["bytes_written"] == 8

        read = client.post(
            "/v1/files/read",
            json={"workspace_id": WORKSPACE, "path": "api.txt"},
        )
        assert read.status_code == 200
        assert read.json()["content"] == "via api\n"

    def test_str_replace_endpoint(self) -> None:
        client = _client()
        client.post(
            "/v1/files/write",
            json={"workspace_id": WORKSPACE, "path": "s.txt", "content": "one two\n"},
        )
        response = client.post(
            "/v1/files/str-replace",
            json={
                "workspace_id": WORKSPACE,
                "path": "s.txt",
                "old": "one",
                "new": "1",
            },
        )
        assert response.status_code == 200
        assert response.json()["replacements"] == 1
        assert "-one" in response.json()["diff"]

    def test_error_status_codes(self) -> None:
        client = _client()
        assert (
            client.post(
                "/v1/files/read",
                json={"workspace_id": WORKSPACE, "path": "missing.txt"},
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/v1/files/write",
                json={"workspace_id": WORKSPACE, "path": "../evil.txt", "content": "x"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/v1/files/write",
                json={"workspace_id": WORKSPACE, "path": ".env", "content": "x"},
            ).status_code
            == 403
        )
        client.post(
            "/v1/files/write",
            json={"workspace_id": WORKSPACE, "path": "dup.txt", "content": "x"},
        )
        assert (
            client.post(
                "/v1/files/write",
                json={
                    "workspace_id": WORKSPACE,
                    "path": "dup.txt",
                    "content": "y",
                    "create_only": True,
                },
            ).status_code
            == 409
        )
        client.post(
            "/v1/files/write",
            json={"workspace_id": WORKSPACE, "path": "m.txt", "content": "aa aa"},
        )
        assert (
            client.post(
                "/v1/files/str-replace",
                json={
                    "workspace_id": WORKSPACE,
                    "path": "m.txt",
                    "old": "aa",
                    "new": "b",
                },
            ).status_code
            == 409
        )

    def test_files_policy(self) -> None:
        response = _client().get("/v1/files/policy")
        assert response.status_code == 200
        assert response.json()["workspace_root"] == "workspaces"


class TestToolsAPIPhase10:
    @pytest.fixture(autouse=True)
    def _isolated(self, root: Path):
        from codeforge.api.routers.tools import reset_manager

        del root
        reset_manager()
        yield
        reset_manager()

    def test_health_route_not_shadowed(self) -> None:
        response = _client().get("/v1/tools/health")
        assert response.status_code == 200
        assert response.json()["tools_registered"] >= 16

    def test_execute_write_file(self) -> None:
        response = _client().post(
            "/v1/tools/write_file/execute",
            json={
                "workspace_id": WORKSPACE,
                "arguments": {"workspace_id": WORKSPACE, "path": "t.txt", "content": "x"},
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["result"]["path"] == "t.txt"

    def test_policy_update(self) -> None:
        client = _client()
        response = client.put(
            "/v1/tools/policy",
            json={"tool_name": "write_file", "permission": "privileged", "enabled": True},
        )
        assert response.status_code == 200
        assert response.json()["config"]["permission"] == "privileged"

    def test_policy_update_errors(self) -> None:
        client = _client()
        assert (
            client.put(
                "/v1/tools/policy",
                json={"tool_name": "nope", "enabled": False},
            ).status_code
            == 404
        )
        assert (
            client.put(
                "/v1/tools/policy",
                json={"tool_name": "write_file", "permission": "root"},
            ).status_code
            == 422
        )
        assert client.put("/v1/tools/policy", json={"tool_name": "write_file"}).status_code == 422

    def test_new_tools_listed(self) -> None:
        tools = _client().get("/v1/tools").json()
        names = {t["name"] for t in tools}
        assert {"write_file", "edit_file", "run_command"} <= names
        write_tool = next(t for t in tools if t["name"] == "write_file")
        assert write_tool["permission_level"] == "user_approval"


# ── CLI ───────────────────────────────────────────────────────────────────


class TestFileCLI:
    def test_write_read_edit(self, root: Path) -> None:
        del root
        runner = CliRunner()
        from codeforge.cli import main

        result = runner.invoke(
            main,
            ["file", "write", "cli.txt", "-w", WORKSPACE, "-c", "hello world"],
        )
        assert result.exit_code == 0
        assert "wrote" in result.output

        result = runner.invoke(main, ["file", "read", "cli.txt", "-w", WORKSPACE])
        assert result.exit_code == 0
        assert "hello world" in result.output

        result = runner.invoke(
            main,
            [
                "file",
                "edit",
                "cli.txt",
                "-w",
                WORKSPACE,
                "--old",
                "world",
                "--new",
                "there",
            ],
        )
        assert result.exit_code == 0
        assert "1 replacement" in result.output

        result = runner.invoke(main, ["file", "read", "cli.txt", "-w", WORKSPACE])
        assert "hello there" in result.output

    def test_read_missing_exits_nonzero(self, root: Path) -> None:
        del root
        runner = CliRunner()
        from codeforge.cli import main

        result = runner.invoke(main, ["file", "read", "missing.txt", "-w", WORKSPACE])
        assert result.exit_code == 1
        assert "file_not_found" in result.output

    def test_edit_mismatch_exits_nonzero(self, root: Path) -> None:
        del root
        runner = CliRunner()
        from codeforge.cli import main

        runner.invoke(main, ["file", "write", "x.txt", "-w", WORKSPACE, "-c", "abc"])
        result = runner.invoke(
            main,
            ["file", "edit", "x.txt", "-w", WORKSPACE, "--old", "zzz", "--new", "q"],
        )
        assert result.exit_code == 1
        assert "replace_mismatch" in result.output
