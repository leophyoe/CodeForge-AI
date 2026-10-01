"""Tests for Phase 11 — agent engine (parser, loop, sessions, API)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient

from codeforge.packages.agent import (
    AgentConfig,
    AgentConfigError,
    AgentEngine,
    AgentSessionStore,
    AgentStatus,
    build_system_prompt,
    extract_final_text,
    parse_tool_call,
)
from codeforge.packages.generation import ChatMessage, ModelNotLoadedError
from codeforge.packages.tools.builtins import build_tool_manager

if TYPE_CHECKING:
    from pathlib import Path

WORKSPACE = "ws1"


# ── test doubles ──────────────────────────────────────────────────────────


class FakeLLM:
    """Scripted LLM: pops responses in order, records every call."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self.responses = list(responses or [])
        self.calls: list[list[ChatMessage]] = []

    def chat(
        self,
        messages: list[ChatMessage],
        model_id: str,
        *,
        max_tokens: int,
        temperature: float,
    ) -> str:
        del model_id, max_tokens, temperature
        self.calls.append(list(messages))
        return self.responses.pop(0) if self.responses else "done"


class RaisingLLM:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def chat(
        self,
        messages: list[ChatMessage],
        model_id: str,
        *,
        max_tokens: int,
        temperature: float,
    ) -> str:
        del messages, model_id, max_tokens, temperature
        raise self.error


def tool_call(name: str, arguments: dict[str, Any]) -> str:
    import json

    body = json.dumps({"tool": name, "arguments": arguments})
    return f"```tool_call\n{body}\n```"


def make_engine(responses: list[str]) -> AgentEngine:
    return AgentEngine(llm=FakeLLM(responses), tool_manager=build_tool_manager())


def run_engine(
    responses: list[str],
    task: str = "do the task",
    config: AgentConfig | None = None,
    session: Any = None,
):
    engine = make_engine(responses)
    config = config or AgentConfig(model_id="fake-model", workspace_id=WORKSPACE)
    return asyncio.run(engine.run(task, config, session))


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspaces" / WORKSPACE).mkdir(parents=True)
    return tmp_path


# ── parser ────────────────────────────────────────────────────────────────


class TestParser:
    def test_fenced_tool_call(self) -> None:
        text = (
            'thinking...\n```tool_call\n{"tool": "read_file", "arguments": {"path": "a.py"}}\n```'
        )
        call = parse_tool_call(text)
        assert call is not None
        assert call.name == "read_file"
        assert call.arguments == {"path": "a.py"}

    def test_fenced_json(self) -> None:
        text = '```json\n{"tool": "list_directory", "args": {"path": "."}}\n```'
        call = parse_tool_call(text)
        assert call is not None
        assert call.name == "list_directory"
        assert call.arguments == {"path": "."}

    def test_bare_json(self) -> None:
        call = parse_tool_call('{"name": "write_file", "input": {"path": "x"}}')
        assert call is not None
        assert call.name == "write_file"
        assert call.arguments == {"path": "x"}

    def test_alternate_keys(self) -> None:
        call = parse_tool_call('{"tool_name": "git_status", "parameters": {}}')
        assert call is not None
        assert call.name == "git_status"

    def test_plain_text_is_final(self) -> None:
        assert parse_tool_call("The answer is 42.") is None
        assert parse_tool_call("") is None
        assert parse_tool_call("   ") is None

    def test_fenced_non_tool_json_is_final(self) -> None:
        assert parse_tool_call('```json\n{"note": "just json"}\n```') is None

    def test_malformed_json_returns_none(self) -> None:
        assert parse_tool_call("```tool_call\n{broken\n```") is None

    def test_tool_key_with_whitespace_name(self) -> None:
        call = parse_tool_call('{"tool": "  read_file  ", "arguments": {}}')
        assert call is not None
        assert call.name == "read_file"

    def test_extract_final_text(self) -> None:
        text = 'Done!\n```tool_call\n{"tool": "x"}\n```'
        assert extract_final_text(text) == "Done!"
        assert extract_final_text("plain answer") == "plain answer"


# ── prompt + config ───────────────────────────────────────────────────────


class TestPromptAndConfig:
    def test_prompt_contains_tools(self) -> None:
        config = AgentConfig(model_id="m", workspace_id="ws1")
        tools = [
            {
                "name": "read_file",
                "description": "Read files",
                "input_schema": {"type": "object"},
            }
        ]
        prompt = build_system_prompt(tools, config)
        assert "ws1" in prompt
        assert "read_file" in prompt
        assert "TOOL CALL PROTOCOL" in prompt
        assert "read_file" in prompt

    def test_protocol_at_end_survives_tail_truncation(self) -> None:
        config = AgentConfig(model_id="m", workspace_id="ws1")
        prompt = build_system_prompt(
            [{"name": "read_file", "description": "d", "input_schema": {}}], config
        )
        # tool catalog first, protocol last → truncating the head keeps it
        assert prompt.index("AVAILABLE TOOLS") < prompt.index("TOOL CALL PROTOCOL")
        assert prompt.rstrip().endswith("outside the workspace.")

    def test_prompt_restricted_set(self) -> None:
        config = AgentConfig(model_id="m", allowed_tools=["read_file", "edit_file"])
        prompt = build_system_prompt([], config)
        assert "RESTRICTED TOOL SET" in prompt
        assert "edit_file" in prompt

    def test_config_validate(self) -> None:
        AgentConfig(model_id="m").validate()
        with pytest.raises(AgentConfigError):
            AgentConfig(model_id="").validate()
        with pytest.raises(AgentConfigError):
            AgentConfig(model_id="m", max_steps=0).validate()
        with pytest.raises(AgentConfigError):
            AgentConfig(model_id="m", temperature=3.0).validate()
        with pytest.raises(AgentConfigError):
            AgentConfig(model_id="m", max_tokens=1).validate()


# ── sessions ──────────────────────────────────────────────────────────────


class TestSessionStore:
    def test_create_get_list_remove(self) -> None:
        store = AgentSessionStore()
        session = store.create("task a", AgentConfig(model_id="m"))
        assert store.get(session.id) is session
        assert store.get("nope") is None
        assert store.count() == 1

        summaries = store.list()
        assert summaries[0]["task_id"] == session.id
        assert summaries[0]["status"] == "running"

        assert store.remove(session.id) is True
        assert store.remove(session.id) is False
        assert store.count() == 0

    def test_clear(self) -> None:
        store = AgentSessionStore()
        store.create("a", AgentConfig(model_id="m"))
        store.create("b", AgentConfig(model_id="m"))
        assert store.clear() == 2
        assert store.count() == 0

    def test_cancel_semantics(self) -> None:
        store = AgentSessionStore()
        session = store.create("a", AgentConfig(model_id="m"))
        assert session.cancel() is True
        assert session.cancelled is True
        session.status = AgentStatus.COMPLETED
        assert session.cancel() is False

    def test_evicts_finished_sessions(self) -> None:
        store = AgentSessionStore(max_sessions=2)
        first = store.create("a", AgentConfig(model_id="m"))
        first.status = AgentStatus.COMPLETED
        store.create("b", AgentConfig(model_id="m"))
        store.create("c", AgentConfig(model_id="m"))  # triggers eviction
        assert store.count() == 2
        assert store.get(first.id) is None


# ── engine loop ───────────────────────────────────────────────────────────


class TestEngineLoop:
    def test_final_answer_without_tools(self, root: Path) -> None:
        del root
        result = run_engine(["42 is the answer."])
        assert result.status is AgentStatus.COMPLETED
        assert result.final_text == "42 is the answer."
        assert result.llm_calls == 1
        assert result.tool_calls == 0
        assert len(result.steps) == 1
        assert result.steps[0].kind == "llm"

    def test_tool_call_then_final(self, root: Path) -> None:
        responses = [
            tool_call(
                "write_file",
                {
                    "workspace_id": WORKSPACE,
                    "path": "out.txt",
                    "content": "made\n",
                },
            ),
            "Created out.txt.",
        ]
        result = run_engine(responses)
        assert result.status is AgentStatus.COMPLETED
        assert result.final_text == "Created out.txt."
        assert result.tool_calls == 1
        kinds = [(s.kind, s.tool_name, s.success) for s in result.steps]
        assert kinds == [("llm", "", True), ("tool", "write_file", True), ("llm", "", True)]
        assert (root / "workspaces" / WORKSPACE / "out.txt").read_text() == "made\n"

    def test_tool_result_fed_back_to_model(self) -> None:
        llm = FakeLLM(
            [
                tool_call("read_file", {"workspace_id": WORKSPACE, "path": "missing.txt"}),
                "No such file exists.",
            ]
        )
        engine = AgentEngine(llm=llm, tool_manager=build_tool_manager())
        config = AgentConfig(model_id="m", workspace_id=WORKSPACE)
        result = asyncio.run(engine.run("read it", config))
        assert result.status is AgentStatus.COMPLETED
        tool_msgs = [
            m.content
            for m in llm.calls[1]
            if m.role == "user" and m.content.startswith("TOOL_RESULT")
        ]
        assert tool_msgs
        assert "File not found" in tool_msgs[0]

    def test_unknown_tool_feedback(self) -> None:
        result = run_engine(
            [tool_call("hack_nasa", {}), "Understood, using available tools."],
            config=AgentConfig(model_id="m", workspace_id=WORKSPACE),
        )
        assert result.status is AgentStatus.COMPLETED
        assert result.tool_calls == 0
        failed = [s for s in result.steps if s.kind == "tool"]
        assert failed
        assert not failed[0].success
        assert "unknown or disallowed" in failed[0].error

    def test_allowed_tools_restriction(self) -> None:
        config = AgentConfig(
            model_id="m",
            workspace_id=WORKSPACE,
            allowed_tools=["read_file"],
        )
        llm = FakeLLM([tool_call("git_status", {}), "ok"])
        engine = AgentEngine(llm=llm, tool_manager=build_tool_manager())
        result = asyncio.run(engine.run("task", config))
        assert result.tool_calls == 0
        failed = [s for s in result.steps if s.kind == "tool"]
        assert failed
        assert "unknown or disallowed" in failed[0].error

    def test_max_steps_exhausted(self) -> None:
        # every turn asks for an unknown tool → loop keeps going until budget
        responses = [tool_call("nonexistent_tool", {}) for _ in range(5)]
        config = AgentConfig(model_id="m", workspace_id=WORKSPACE, max_steps=3)
        result = run_engine(responses, config=config)
        assert result.status is AgentStatus.MAX_STEPS
        assert result.llm_calls == 3
        assert result.tool_calls == 0
        assert result.final_text.startswith("```tool_call")

    def test_cancellation_before_first_step(self) -> None:
        store = AgentSessionStore()
        session = store.create("task", AgentConfig(model_id="m", workspace_id=WORKSPACE))
        session.cancel()
        llm = FakeLLM(["should not be called"])
        engine = AgentEngine(llm=llm, tool_manager=build_tool_manager())
        result = asyncio.run(engine.run("task", session.config, session))
        assert result.status is AgentStatus.CANCELLED
        assert result.cancelled is True
        assert llm.calls == []
        assert session.status is AgentStatus.CANCELLED

    def test_llm_failure_marks_failed(self) -> None:
        engine = AgentEngine(
            llm=RaisingLLM(RuntimeError("model exploded")),
            tool_manager=build_tool_manager(),
        )
        result = asyncio.run(engine.run("task", AgentConfig(model_id="m")))
        assert result.status is AgentStatus.FAILED
        assert "model exploded" in result.error
        assert result.steps[0].kind == "llm"
        assert "model exploded" in result.steps[0].error

    def test_model_not_loaded_propagates(self) -> None:
        engine = AgentEngine(
            llm=RaisingLLM(ModelNotLoadedError("tiny-random-gpt2")),
            tool_manager=build_tool_manager(),
        )
        with pytest.raises(ModelNotLoadedError):
            asyncio.run(engine.run("task", AgentConfig(model_id="m")))

    def test_failed_tool_then_recovery(self, root: Path) -> None:
        responses = [
            tool_call(
                "edit_file",
                {"workspace_id": WORKSPACE, "path": "x.txt", "old": "zz", "new": "y"},
            ),
            tool_call(
                "write_file",
                {"workspace_id": WORKSPACE, "path": "x.txt", "content": "fresh"},
            ),
            "Wrote the file.",
        ]
        result = run_engine(responses)
        assert result.status is AgentStatus.COMPLETED
        tool_steps = [s for s in result.steps if s.kind == "tool"]
        assert [s.success for s in tool_steps] == [False, True]
        assert (root / "workspaces" / WORKSPACE / "x.txt").read_text() == "fresh"

    def test_result_to_dict_shape(self) -> None:
        result = run_engine(["hello"])
        data = result.to_dict()
        for key in (
            "task_id",
            "task",
            "model_id",
            "status",
            "final_text",
            "error",
            "steps",
            "llm_calls",
            "tool_calls",
            "duration_s",
        ):
            assert key in data
        assert data["status"] == "completed"
        assert data["steps"][0]["kind"] == "llm"


# ── API ───────────────────────────────────────────────────────────────────


def _client() -> TestClient:
    from codeforge.api.app import create_app
    from codeforge.api.config import APIConfig, AppConfig, RateLimitConfig

    config = AppConfig(
        api=APIConfig(docs_enabled=True, auth_required=False),
        rate_limit=RateLimitConfig(enabled=False),
    )
    return TestClient(create_app(config))


class TestAgentAPI:
    @pytest.fixture(autouse=True)
    def _injected(self, root: Path):
        from codeforge.api.routers.agent import reset_store, set_engine

        del root
        reset_store()
        set_engine(None)
        yield
        set_engine(None)
        reset_store()

    def _inject(self, responses: list[str]) -> None:
        from codeforge.api.routers.agent import set_engine

        set_engine(make_engine(responses))

    def test_run_task(self, root: Path) -> None:
        self._inject(
            [
                tool_call(
                    "write_file",
                    {
                        "workspace_id": WORKSPACE,
                        "path": "api.txt",
                        "content": "via agent\n",
                    },
                ),
                "Created api.txt via agent.",
            ]
        )
        response = _client().post(
            "/v1/agent/run",
            json={"task": "create api.txt", "model": "fake-model"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "completed"
        assert body["final_text"] == "Created api.txt via agent."
        assert body["tool_calls"] == 1
        assert (root / "workspaces" / WORKSPACE / "api.txt").read_text() == "via agent\n"

    def test_tasks_list_and_detail_and_delete(self) -> None:
        self._inject(["just an answer"])
        client = _client()
        run = client.post("/v1/agent/run", json={"task": "say it", "model": "fake-model"}).json()
        task_id = run["task_id"]

        listing = client.get("/v1/agent/tasks").json()["tasks"]
        assert any(t["task_id"] == task_id for t in listing)

        detail = client.get(f"/v1/agent/tasks/{task_id}").json()
        assert detail["final_text"] == "just an answer"

        assert client.delete(f"/v1/agent/tasks/{task_id}").status_code == 200
        assert client.get(f"/v1/agent/tasks/{task_id}").status_code == 404
        assert client.delete("/v1/agent/tasks/nope").status_code == 404

    def test_cancel_finished_task(self) -> None:
        self._inject(["answer"])
        client = _client()
        run = client.post("/v1/agent/run", json={"task": "t", "model": "fake-model"}).json()
        response = client.post(f"/v1/agent/tasks/{run['task_id']}/cancel")
        assert response.status_code == 200
        assert response.json()["cancelled"] is False  # already finished
        assert client.post("/v1/agent/tasks/nope/cancel").status_code == 404

    def test_model_not_loaded_maps_to_409(self) -> None:
        from codeforge.api.routers.agent import set_engine

        set_engine(
            AgentEngine(
                llm=RaisingLLM(ModelNotLoadedError("no model")),
                tool_manager=build_tool_manager(),
            )
        )
        response = _client().post("/v1/agent/run", json={"task": "t", "model": "missing-model"})
        assert response.status_code == 409

    def test_validation_errors(self) -> None:
        self._inject(["x"])
        client = _client()
        assert client.post("/v1/agent/run", json={"task": "", "model": "m"}).status_code == 422
        assert (
            client.post(
                "/v1/agent/run",
                json={"task": "t", "model": "m", "max_steps": 99},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/v1/agent/run",
                json={"task": "t", "model": "m", "temperature": 5},
            ).status_code
            == 422
        )

    def test_health(self) -> None:
        self._inject(["x"])
        response = _client().get("/v1/agent/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["tools"] >= 16

    def test_run_with_allowed_tools(self, root: Path) -> None:
        del root
        self._inject(["I will not use write_file."])
        response = _client().post(
            "/v1/agent/run",
            json={
                "task": "t",
                "model": "fake-model",
                "allowed_tools": ["read_file"],
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
