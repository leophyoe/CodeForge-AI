"""Comprehensive tests for Phase 9 — Secure Tool System."""

from __future__ import annotations

import pytest

from codeforge.packages.tools import (
    InvalidToolInputError,
    PathTraversalError,
    PermissionLevel,
    SensitiveFileBlockedError,
    ToolAuditLogger,
    ToolCategory,
    ToolError,
    ToolExecutionContext,
    ToolManager,
    ToolNotFoundError,
    ToolPermissionError,
    ToolPolicy,
    ToolPolicyConfig,
    ToolRegistry,
    ToolResult,
    ToolTimeoutError,
    WorkspaceAccessError,
    current_time_ms,
    make_request_id,
)
from codeforge.packages.tools.builtins import (
    FindDependenciesTool,
    FindReferencesTool,
    FindSymbolTool,
    GetDiagnosticsTool,
    GetProjectStructureTool,
    GetSymbolTool,
    GitDiffTool,
    GitLogTool,
    GitStatusTool,
    ListDirectoryTool,
    ReadFileTool,
    SearchCodeTool,
    SearchFilesTool,
)


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "test_workspace"
    ws.mkdir()
    (ws / "src").mkdir()
    (ws / "src" / "auth.py").write_text(
        "class UserService:\n    def authenticate(self):\n        pass\n"
    )
    (ws / "src" / "main.py").write_text("from auth import UserService\n\ndef main():\n    pass\n")
    (ws / "README.md").write_text("# Test Project\n")
    (ws / ".env").write_text("SECRET=abc123\n")
    (ws / "private.key").write_text("-----BEGIN RSA PRIVATE KEY-----\n")
    return ws


@pytest.fixture
def registry():
    reg = ToolRegistry()
    reg.register(ReadFileTool())
    reg.register(ListDirectoryTool())
    reg.register(GetProjectStructureTool())
    reg.register(SearchFilesTool())
    reg.register(SearchCodeTool())
    reg.register(FindSymbolTool())
    reg.register(GetSymbolTool())
    reg.register(FindReferencesTool())
    reg.register(FindDependenciesTool())
    reg.register(GetDiagnosticsTool())
    reg.register(GitStatusTool())
    reg.register(GitDiffTool())
    reg.register(GitLogTool())
    return reg


@pytest.fixture
def manager(registry):
    return ToolManager(registry=registry)


@pytest.fixture
def context(workspace):
    return ToolExecutionContext(workspace_id=str(workspace))


# ── Tool Interface ────────────────────────────────────────────────────────


class TestToolInterface:
    def test_tool_has_required_properties(self):
        tool = ReadFileTool()
        assert tool.name == "read_file"
        assert tool.description
        assert tool.input_schema
        assert tool.output_schema
        assert tool.category == ToolCategory.READ
        assert tool.permission_level == PermissionLevel.READ_ONLY

    def test_tool_describe(self):
        tool = ReadFileTool()
        desc = tool.describe()
        assert desc["name"] == "read_file"
        assert "input_schema" in desc
        assert "output_schema" in desc

    def test_all_builtins_have_properties(self):
        tools = [
            ReadFileTool(),
            ListDirectoryTool(),
            GetProjectStructureTool(),
            SearchFilesTool(),
            SearchCodeTool(),
            FindSymbolTool(),
            GetSymbolTool(),
            FindReferencesTool(),
            FindDependenciesTool(),
            GetDiagnosticsTool(),
            GitStatusTool(),
            GitDiffTool(),
            GitLogTool(),
        ]
        for tool in tools:
            assert tool.name
            assert tool.description
            assert tool.input_schema
            assert tool.output_schema
            assert isinstance(tool.category, ToolCategory)
            assert isinstance(tool.permission_level, PermissionLevel)


# ── ToolResult ────────────────────────────────────────────────────────────


class TestToolResult:
    def test_success_result(self):
        result = ToolResult(tool_name="test", success=True, result={"key": "value"})
        assert result.success
        d = result.to_dict()
        assert d["tool_name"] == "test"

    def test_error_result(self):
        result = ToolResult(tool_name="test", success=False, error="something went wrong")
        assert not result.success


# ── Tool Registry ─────────────────────────────────────────────────────────


class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        tool = ReadFileTool()
        reg.register(tool)
        assert reg.get("read_file") is tool

    def test_duplicate_registration_raises(self):
        reg = ToolRegistry()
        reg.register(ReadFileTool())
        with pytest.raises(ToolError, match="already registered"):
            reg.register(ReadFileTool())

    def test_unregister(self):
        reg = ToolRegistry()
        reg.register(ReadFileTool())
        assert reg.unregister("read_file") is True
        assert reg.get("read_file") is None

    def test_get_or_raise(self):
        reg = ToolRegistry()
        with pytest.raises(ToolNotFoundError):
            reg.get_or_raise("nonexistent")

    def test_list_tools(self):
        reg = ToolRegistry()
        reg.register(ReadFileTool())
        reg.register(ListDirectoryTool())
        assert reg.count() == 2

    def test_exists(self):
        reg = ToolRegistry()
        reg.register(ReadFileTool())
        assert reg.exists("read_file")
        assert not reg.exists("nonexistent")

    def test_get_schema(self):
        reg = ToolRegistry()
        reg.register(ReadFileTool())
        schema = reg.get_schema("read_file")
        assert schema is not None
        assert schema["name"] == "read_file"

    def test_clear(self):
        reg = ToolRegistry()
        reg.register(ReadFileTool())
        assert reg.clear() == 1
        assert reg.count() == 0


# ── Tool Policy ───────────────────────────────────────────────────────────


class TestToolPolicy:
    def test_default_enabled(self):
        policy = ToolPolicy()
        assert policy.is_enabled("read_file")

    def test_configure_tool(self):
        policy = ToolPolicy()
        policy.configure("read_file", ToolPolicyConfig(enabled=False))
        assert not policy.is_enabled("read_file")

    def test_permission_check(self):
        policy = ToolPolicy()
        assert policy.check_permission("read_file", PermissionLevel.READ_ONLY)

    def test_sensitive_file_detection(self):
        policy = ToolPolicy()
        assert policy.is_sensitive_file(".env")
        assert policy.is_sensitive_file("private.key")
        assert policy.is_sensitive_file("credentials.json")
        assert not policy.is_sensitive_file("readme.md")

    def test_path_validation(self, workspace):
        policy = ToolPolicy()
        assert policy.validate_path(str(workspace / "src"), str(workspace))
        assert not policy.validate_path(str(workspace / "../../etc/passwd"), str(workspace))

    def test_to_dict(self):
        policy = ToolPolicy()
        d = policy.to_dict()
        assert "defaults" in d
        assert "tools" in d


# ── Tool Audit Logger ─────────────────────────────────────────────────────


class TestToolAuditLogger:
    def test_log_entry(self):
        logger = ToolAuditLogger()
        logger.log(
            request_id="r1",
            workspace_id="ws1",
            tool_name="read_file",
            permission_level="read_only",
            success=True,
            duration_ms=5.0,
        )
        assert logger.count() == 1

    def test_get_entries(self):
        logger = ToolAuditLogger()
        logger.log("r1", "ws1", "read_file", "read_only", True, 5.0)
        logger.log("r2", "ws1", "list_dir", "read_only", True, 3.0)
        entries = logger.get_entries(tool_name="read_file")
        assert len(entries) == 1

    def test_max_entries(self):
        logger = ToolAuditLogger(max_entries=5)
        for i in range(10):
            logger.log(f"r{i}", "ws", "tool", "read_only", True, 1.0)
        assert logger.count() == 5

    def test_stats(self):
        logger = ToolAuditLogger()
        logger.log("r1", "ws", "t", "read_only", True, 1.0)
        logger.log("r2", "ws", "t", "read_only", False, 1.0)
        stats = logger.get_stats()
        assert stats["total"] == 2
        assert stats["success"] == 1
        assert stats["failure"] == 1


# ── Tool Manager ──────────────────────────────────────────────────────────


class TestToolManager:
    def test_resolve_tool(self, manager):
        tool = manager.resolve("read_file")
        assert tool.name == "read_file"

    def test_resolve_nonexistent(self, manager):
        with pytest.raises(ToolNotFoundError):
            manager.resolve("nonexistent")

    def test_validate_input(self, manager):
        tool = manager.resolve("read_file")
        manager.validate(tool, {"workspace_id": "ws", "path": "src/main.py"})

    def test_validate_input_invalid(self, manager):
        tool = manager.resolve("read_file")
        with pytest.raises(InvalidToolInputError):
            manager.validate(tool, {})

    def test_execute_tool(self, manager, workspace):
        context = ToolExecutionContext(workspace_id=str(workspace))
        result = manager.execute_tool(
            "get_project_structure",
            {"workspace_id": str(workspace)},
            context,
        )
        assert result.success

    def test_execute_nonexistent_tool(self, manager, workspace):
        context = ToolExecutionContext(workspace_id=str(workspace))
        result = manager.execute_tool("nonexistent", {"workspace_id": str(workspace)}, context)
        assert not result.success

    def test_list_tools(self, manager):
        tools = manager.list_tools()
        assert len(tools) == 13

    def test_audit_logging(self, manager, workspace):
        context = ToolExecutionContext(workspace_id=str(workspace))
        manager.execute_tool(
            "get_project_structure",
            {"workspace_id": str(workspace)},
            context,
        )
        assert manager.audit.count() == 1


# ── Read File Tool ────────────────────────────────────────────────────────


class TestReadFileTool:
    def test_read_file(self, manager, workspace):
        result = manager.execute_tool(
            "read_file",
            {"workspace_id": str(workspace), "path": "src/auth.py"},
        )
        assert result.success
        assert "UserService" in result.result["content"]

    def test_read_file_with_line_range(self, manager, workspace):
        result = manager.execute_tool(
            "read_file",
            {
                "workspace_id": str(workspace),
                "path": "src/auth.py",
                "start_line": 1,
                "end_line": 1,
            },
        )
        assert result.success
        assert result.result["start_line"] == 1
        assert result.result["end_line"] == 1

    def test_read_file_not_found(self, manager, workspace):
        result = manager.execute_tool(
            "read_file",
            {"workspace_id": str(workspace), "path": "nonexistent.py"},
        )
        assert not result.success

    def test_read_file_sensitive_blocked(self, manager, workspace):
        result = manager.execute_tool(
            "read_file",
            {"workspace_id": str(workspace), "path": ".env"},
        )
        assert not result.success
        assert "sensitive" in result.error.lower() or "blocked" in result.error.lower()

    def test_read_file_private_key_blocked(self, manager, workspace):
        result = manager.execute_tool(
            "read_file",
            {"workspace_id": str(workspace), "path": "private.key"},
        )
        assert not result.success

    def test_read_file_path_traversal(self, manager, workspace):
        result = manager.execute_tool(
            "read_file",
            {"workspace_id": str(workspace), "path": "../../etc/passwd"},
        )
        assert not result.success


# ── List Directory Tool ───────────────────────────────────────────────────


class TestListDirectoryTool:
    def test_list_directory(self, manager, workspace):
        result = manager.execute_tool(
            "list_directory",
            {"workspace_id": str(workspace), "path": "."},
        )
        assert result.success
        assert result.result["total"] > 0

    def test_list_directory_with_entries(self, manager, workspace):
        result = manager.execute_tool(
            "list_directory",
            {"workspace_id": str(workspace), "path": ".", "max_entries": 2},
        )
        assert result.success
        assert result.result["total"] <= 2

    def test_list_directory_not_found(self, manager, workspace):
        result = manager.execute_tool(
            "list_directory",
            {"workspace_id": str(workspace), "path": "nonexistent"},
        )
        assert not result.success


# ── Project Structure Tool ────────────────────────────────────────────────


class TestProjectStructureTool:
    def test_get_structure(self, manager, workspace):
        result = manager.execute_tool(
            "get_project_structure",
            {"workspace_id": str(workspace)},
        )
        assert result.success
        assert "directories" in result.result
        assert "files" in result.result
        assert "languages" in result.result


# ── Search Files Tool ─────────────────────────────────────────────────────


class TestSearchFilesTool:
    def test_search_files(self, manager, workspace):
        result = manager.execute_tool(
            "search_files",
            {"workspace_id": str(workspace), "pattern": r"\.py$"},
        )
        assert result.success
        assert result.result["total"] > 0

    def test_search_files_no_match(self, manager, workspace):
        result = manager.execute_tool(
            "search_files",
            {"workspace_id": str(workspace), "pattern": "nonexistent"},
        )
        assert result.success
        assert result.result["total"] == 0


# ── Search Code Tool ──────────────────────────────────────────────────────


class TestSearchCodeTool:
    def test_search_code(self, manager, workspace):
        result = manager.execute_tool(
            "search_code",
            {"workspace_id": str(workspace), "query": "UserService"},
        )
        assert result.success
        assert result.result["total"] > 0

    def test_search_code_regex(self, manager, workspace):
        result = manager.execute_tool(
            "search_code",
            {"workspace_id": str(workspace), "query": "class\\s+\\w+"},
        )
        assert result.success

    def test_search_code_language_filter(self, manager, workspace):
        result = manager.execute_tool(
            "search_code",
            {"workspace_id": str(workspace), "query": "def", "language": "python"},
        )
        assert result.success


# ── Find Symbol Tool ──────────────────────────────────────────────────────


class TestFindSymbolTool:
    def test_find_symbol(self, manager, workspace):
        result = manager.execute_tool(
            "find_symbol",
            {"workspace_id": str(workspace), "name": "UserService"},
        )
        assert result.success
        assert result.result["total"] > 0

    def test_find_symbol_with_kind(self, manager, workspace):
        result = manager.execute_tool(
            "find_symbol",
            {"workspace_id": str(workspace), "name": "UserService", "kind": "class"},
        )
        assert result.success


# ── Find References Tool ──────────────────────────────────────────────────


class TestFindReferencesTool:
    def test_find_references(self, manager, workspace):
        result = manager.execute_tool(
            "find_references",
            {"workspace_id": str(workspace), "name": "UserService"},
        )
        assert result.success


# ── Find Dependencies Tool ────────────────────────────────────────────────


class TestFindDependenciesTool:
    def test_find_dependencies(self, manager, workspace):
        result = manager.execute_tool(
            "find_dependencies",
            {"workspace_id": str(workspace), "file_path": "src/main.py"},
        )
        assert result.success
        assert result.result["total"] > 0


# ── Get Diagnostics Tool ──────────────────────────────────────────────────


class TestGetDiagnosticsTool:
    def test_get_diagnostics(self, manager, workspace):
        result = manager.execute_tool(
            "get_diagnostics",
            {"workspace_id": str(workspace)},
        )
        assert result.success


# ── Git Tools ─────────────────────────────────────────────────────────────


class TestGitTools:
    def test_git_status_no_repo(self, manager, workspace):
        result = manager.execute_tool(
            "git_status",
            {"workspace_id": str(workspace)},
        )
        assert not result.success

    def test_git_diff_no_repo(self, manager, workspace):
        result = manager.execute_tool(
            "git_diff",
            {"workspace_id": str(workspace)},
        )
        assert not result.success

    def test_git_log_no_repo(self, manager, workspace):
        result = manager.execute_tool(
            "git_log",
            {"workspace_id": str(workspace)},
        )
        assert not result.success


# ── Security Tests ────────────────────────────────────────────────────────


class TestSecurity:
    def test_path_traversal_blocked(self, manager, workspace):
        paths = [
            "../../etc/passwd",
            "../../../etc/shadow",
            "src/../../etc/passwd",
        ]
        for path in paths:
            result = manager.execute_tool(
                "read_file",
                {"workspace_id": str(workspace), "path": path},
            )
            assert not result.success, f"Path traversal not blocked: {path}"

    def test_sensitive_files_blocked(self, manager, workspace):
        sensitive = [".env", "private.key"]
        for path in sensitive:
            result = manager.execute_tool(
                "read_file",
                {"workspace_id": str(workspace), "path": path},
            )
            assert not result.success, f"Sensitive file not blocked: {path}"

    def test_disabled_tool_blocked(self, workspace):
        registry = ToolRegistry()
        registry.register(ReadFileTool())
        policy = ToolPolicy()
        policy.configure("read_file", ToolPolicyConfig(enabled=False))
        manager = ToolManager(registry=registry, policy=policy)
        result = manager.execute_tool(
            "read_file",
            {"workspace_id": str(workspace), "path": "README.md"},
        )
        assert not result.success

    def test_unknown_tool_returns_error(self, manager, workspace):
        result = manager.execute_tool(
            "nonexistent_tool",
            {"workspace_id": str(workspace)},
        )
        assert not result.success


# ── Execution Context ─────────────────────────────────────────────────────


class TestToolExecutionContext:
    def test_context_creation(self):
        ctx = ToolExecutionContext(workspace_id="ws1")
        assert ctx.workspace_id == "ws1"
        assert ctx.request_id

    def test_context_cancellation(self):
        ctx = ToolExecutionContext()
        assert not ctx.is_cancelled
        ctx.cancel()
        assert ctx.is_cancelled

    def test_request_id_unique(self):
        ids = {make_request_id() for _ in range(100)}
        assert len(ids) == 100


# ── Models ────────────────────────────────────────────────────────────────


class TestModels:
    def test_tool_category(self):
        assert ToolCategory.READ.value == "read"
        assert ToolCategory.WRITE.value == "write"

    def test_permission_level(self):
        assert PermissionLevel.READ_ONLY.value == "read_only"
        assert PermissionLevel.PRIVILEGED.value == "privileged"

    def test_current_time_ms(self):
        t = current_time_ms()
        assert t > 0

    def test_make_request_id(self):
        rid = make_request_id()
        assert len(rid) == 36


# ── Error Types ───────────────────────────────────────────────────────────


class TestErrorTypes:
    def test_tool_error(self):
        e = ToolError("test", code="test_code", tool_name="t")
        assert e.code == "test_code"
        d = e.to_dict()
        assert d["code"] == "test_code"

    def test_invalid_input(self):
        e = InvalidToolInputError("bad input")
        assert e.code == "invalid_tool_input"

    def test_not_found(self):
        e = ToolNotFoundError("my_tool")
        assert "my_tool" in str(e)

    def test_permission(self):
        e = ToolPermissionError("denied")
        assert e.code == "tool_permission_error"

    def test_timeout(self):
        e = ToolTimeoutError("t", 10.0)
        assert "10.0" in str(e)

    def test_workspace_access(self):
        e = WorkspaceAccessError("ws1", "/bad/path")
        assert e.code == "workspace_access_error"

    def test_path_traversal(self):
        e = PathTraversalError("../../etc/passwd")
        assert e.code == "path_traversal_error"

    def test_sensitive_file(self):
        e = SensitiveFileBlockedError(".env")
        assert e.code == "sensitive_file_blocked"
