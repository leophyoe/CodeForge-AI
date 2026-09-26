"""Built-in git read-only tools for Phase 9."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from codeforge.packages.tools.errors import InvalidToolInputError, ToolExecutionError
from codeforge.packages.tools.models import (
    PermissionLevel,
    ToolCategory,
    ToolExecutionContext,
    ToolResult,
)
from codeforge.packages.tools.tool import Tool


def _run_git(args: list[str], cwd: str) -> tuple[int, str, str]:
    try:
        result = subprocess.run(  # noqa: S603
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return -1, "", "git not found"
    except subprocess.TimeoutExpired:
        return -2, "", "git timed out"
    except Exception as e:
        return -3, "", str(e)


class GitStatusTool(Tool):
    @property
    def name(self) -> str:
        return "git_status"

    @property
    def description(self) -> str:
        return "Get git repository status (read-only)"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
            },
            "required": ["workspace_id"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "branch": {"type": "string"},
                "modified": {"type": "array"},
                "added": {"type": "array"},
                "deleted": {"type": "array"},
                "untracked": {"type": "array"},
            },
        }

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.GIT

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ_ONLY

    def validate_input(self, arguments: dict[str, Any]) -> None:
        if not arguments.get("workspace_id"):
            raise InvalidToolInputError("workspace_id is required")

    def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        start_ms = __import__("time").time() * 1000
        workspace_id = arguments["workspace_id"]
        workspace_path = str(Path("workspaces") / workspace_id)

        code, stdout, stderr = _run_git(["status", "--porcelain"], workspace_path)
        if code != 0:
            return self._error(
                ToolExecutionError(f"git status failed: {stderr}"),
                context,
                start_ms,
            )

        code2, branch_out, _ = _run_git(["branch", "--show-current"], workspace_path)
        branch = branch_out.strip() if code2 == 0 else "unknown"

        modified = []
        added = []
        deleted = []
        untracked = []

        for line in stdout.splitlines():
            if len(line) < 3:
                continue
            status = line[:2]
            path = line[3:].strip()
            if status[0] == "M":
                modified.append(path)
            elif status[0] == "A":
                added.append(path)
            elif status[0] == "D":
                deleted.append(path)
            elif status == "??":
                untracked.append(path)

        return self._success(
            {
                "branch": branch,
                "modified": modified,
                "added": added,
                "deleted": deleted,
                "untracked": untracked,
            },
            context,
            start_ms,
        )


class GitDiffTool(Tool):
    @property
    def name(self) -> str:
        return "git_diff"

    @property
    def description(self) -> str:
        return "Get git diff (read-only, working tree)"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": ["workspace_id"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "diff": {"type": "string"},
                "truncated": {"type": "boolean"},
            },
        }

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.GIT

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ_ONLY

    def validate_input(self, arguments: dict[str, Any]) -> None:
        if not arguments.get("workspace_id"):
            raise InvalidToolInputError("workspace_id is required")

    def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        start_ms = __import__("time").time() * 1000
        workspace_id = arguments["workspace_id"]
        path = arguments.get("path")
        workspace_path = str(Path("workspaces") / workspace_id)

        args = ["diff"]
        if path:
            args.extend(["--", path])

        code, stdout, stderr = _run_git(args, workspace_path)
        if code != 0:
            return self._error(
                ToolExecutionError(f"git diff failed: {stderr}"),
                context,
                start_ms,
            )

        truncated = len(stdout) > context.max_output_bytes
        if truncated:
            stdout = stdout[: context.max_output_bytes] + "\n... (truncated)"

        return self._success(
            {"diff": stdout, "truncated": truncated},
            context,
            start_ms,
        )


class GitLogTool(Tool):
    @property
    def name(self) -> str:
        return "git_log"

    @property
    def description(self) -> str:
        return "Get git log (read-only)"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "max_commits": {"type": "integer", "default": 20},
            },
            "required": ["workspace_id"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "commits": {"type": "array"},
                "total": {"type": "integer"},
            },
        }

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.GIT

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ_ONLY

    def validate_input(self, arguments: dict[str, Any]) -> None:
        if not arguments.get("workspace_id"):
            raise InvalidToolInputError("workspace_id is required")

    def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        start_ms = __import__("time").time() * 1000
        workspace_id = arguments["workspace_id"]
        max_commits = arguments.get("max_commits", 20)
        workspace_path = str(Path("workspaces") / workspace_id)

        code, stdout, stderr = _run_git(
            ["log", f"--max-count={max_commits}", "--format=%H|%an|%ai|%s"],
            workspace_path,
        )
        if code != 0:
            return self._error(
                ToolExecutionError(f"git log failed: {stderr}"),
                context,
                start_ms,
            )

        commits = []
        for line in stdout.splitlines():
            parts = line.split("|", 3)
            if len(parts) == 4:
                commits.append(
                    {
                        "hash": parts[0][:12],
                        "author": parts[1],
                        "date": parts[2],
                        "subject": parts[3],
                    }
                )

        return self._success(
            {"commits": commits, "total": len(commits)},
            context,
            start_ms,
        )
