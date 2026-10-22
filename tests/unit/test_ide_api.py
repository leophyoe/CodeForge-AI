"""Tests for the IDE endpoints and their prompt builders."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from codeforge.api import create_app
from codeforge.api.config import APIConfig, AppConfig, RateLimitConfig
from codeforge.api.routers import ide as ide_router
from codeforge.packages.generation.schemas import (
    FinishReason,
    GenerationResponse,
    StreamEvent,
    StreamEventType,
    UsageInfo,
)
from codeforge.packages.ide import (
    ASSIST_ACTIONS,
    IDEConfig,
    WorkspaceBridge,
    build_assist_prompt,
    build_completion_prompt,
    build_editor_context,
    clean_completion,
    is_valid_action,
    render_context,
    truncate_prefix,
    truncate_suffix,
)


def _make_app():
    config = AppConfig(
        api=APIConfig(docs_enabled=False, auth_required=False),
        rate_limit=RateLimitConfig(enabled=False),
    )
    return create_app(config)


class FakeService:
    """Canned generation service that records every request it receives."""

    def __init__(self, text: str = "completion") -> None:
        self.text = text
        self.stream_texts: list[str] = []
        self.requests: list = []
        self.prompts: list[str] = []

    def generate(self, request):
        self.requests.append(request)
        return GenerationResponse(
            text=self.text,
            finish_reason=FinishReason.STOP,
            usage=UsageInfo(prompt_tokens=1, completion_tokens=2, total_tokens=3),
            model_id=request.model_id,
        )

    def stream_generate(self, prompt, model_id, config=None):
        del model_id, config
        self.prompts.append(prompt)
        for token in self.stream_texts:
            yield StreamEvent(event_type=StreamEventType.TOKEN, text=token)
        yield StreamEvent(
            event_type=StreamEventType.END,
            is_end=True,
            usage=UsageInfo(total_tokens=5),
        )


@pytest.fixture
def client():
    return TestClient(_make_app(), raise_server_exceptions=False)


@pytest.fixture
def fake_service(monkeypatch):
    service = FakeService()
    monkeypatch.setattr(ide_router, "_service", service)
    return service


@pytest.fixture
def indexed_bridge(monkeypatch, tmp_path):
    """A WorkspaceBridge backed by a freshly indexed temp repository."""
    from codeforge.packages.indexing.manager import WorkspaceManager
    from codeforge.packages.indexing.storage import Storage

    root = tmp_path / "repo"
    root.mkdir()
    (root / "math_util.py").write_text(
        "def add_numbers(a, b):\n    return a + b\n", encoding="utf-8"
    )

    bridge = WorkspaceBridge(WorkspaceManager(Storage(str(tmp_path / "idx.db"))))
    monkeypatch.setattr(ide_router, "_bridge", bridge)
    return bridge, root


# ── config ────────────────────────────────────────────────────────────────


class TestIDEConfig:
    def test_defaults(self):
        config = IDEConfig()
        assert config.completion_enabled is True
        assert config.completion_max_prefix_chars == 2000
        assert config.assist_max_tokens == 512
        assert config.completion_stop

    def test_merge_ignores_unknown_keys(self):
        merged = IDEConfig().merge({"completion_enabled": False, "not_a_field": 1})
        assert merged.completion_enabled is False

    def test_from_env_overrides_bool(self, monkeypatch):
        monkeypatch.setenv("CODEFORGE_IDE_COMPLETION_ENABLED", "false")
        monkeypatch.setenv("CODEFORGE_IDE_COMPLETION_MAX_TOKENS", "16")
        config = IDEConfig.from_env()
        assert config.completion_enabled is False
        assert config.completion_max_tokens == 16

    def test_client_settings_beat_env(self, monkeypatch):
        monkeypatch.setenv("CODEFORGE_IDE_COMPLETION_MAX_TOKENS", "16")
        config = IDEConfig.from_env().merge({"completion_max_tokens": 4})
        assert config.completion_max_tokens == 4


# ── prompt builders ───────────────────────────────────────────────────────


class TestPromptBuilders:
    def test_completion_prompt_puts_suffix_before_prefix(self):
        config = IDEConfig()
        ctx = build_editor_context(
            config,
            file_path="a.py",
            language="python",
            prefix="def f():\n    total = ",
            suffix="\n    return total\n",
        )
        prompt = build_completion_prompt(ctx, config)
        assert prompt.index("return total") < prompt.index("total = ")

    def test_completion_prompt_truncates_long_prefix(self):
        config = IDEConfig(completion_max_prefix_chars=10)
        ctx = build_editor_context(config, prefix="x" * 500, suffix="")
        prompt = build_completion_prompt(ctx, config)
        assert "x" * 20 not in prompt

    def test_assist_prompt_rejects_unknown_action(self):
        with pytest.raises(ValueError, match="Unknown action"):
            build_assist_prompt("summarise", build_editor_context(IDEConfig()))

    def test_assist_prompt_includes_selection_and_language(self):
        ctx = build_editor_context(
            IDEConfig(), language="python", file_path="app.py", selection="return 1"
        )
        prompt = build_assist_prompt("explain", ctx)
        assert "Explain what the following python code does" in prompt
        assert "return 1" in prompt
        assert "app.py" in prompt

    def test_assist_prompt_uses_prefix_without_selection(self):
        ctx = build_editor_context(IDEConfig(), language="go", prefix="func main() {}")
        prompt = build_assist_prompt("refactor", ctx)
        assert "func main() {}" in prompt

    def test_actions_match_declared_actions(self):
        for action in ASSIST_ACTIONS:
            assert is_valid_action(action)
        assert not is_valid_action("deploy")


# ── completion cleanup ────────────────────────────────────────────────────


class TestCleanCompletion:
    def test_strips_stop_sequence(self):
        text = "answer = 1\n\ndef other():\n    pass"
        assert clean_completion(text, IDEConfig()) == "answer = 1"

    def test_strips_markdown_fences(self):
        text = "```python\nx = 1\n```"
        assert clean_completion(text, IDEConfig()) == "x = 1"

    def test_strips_echoed_suffix_line(self):
        config = IDEConfig()
        assert clean_completion("    return x", config, suffix="\n    return x\n") == ""

    def test_empty_text(self):
        assert clean_completion("", IDEConfig()) == ""


class TestTruncation:
    def test_prefix_keeps_tail(self):
        assert truncate_prefix("abcdef", 3) == "def"

    def test_suffix_keeps_head(self):
        assert truncate_suffix("abcdef", 3) == "abc"

    def test_no_truncation_when_within_limit(self):
        assert truncate_prefix("abc", 10) == "abc"


class TestRenderContext:
    def test_renders_file_selection_and_chunks(self):
        ctx = build_editor_context(IDEConfig(), file_path="a.py", language="python")
        text = render_context(
            ctx,
            chunks=[
                {
                    "relative_path": "a.py",
                    "start_line": 0,
                    "content": "def helper():\n    pass",
                    "language": "python",
                }
            ],
            symbols=[{"kind": "function", "name": "helper", "relative_path": "a.py"}],
        )
        assert "## File" in text
        assert "## Symbols" in text
        assert "## Related code" in text
        assert "def helper():" in text

    def test_respects_max_chars(self):
        ctx = build_editor_context(IDEConfig(), selection="z" * 4000)
        assert len(render_context(ctx, max_chars=120)) <= 120


# ── endpoints ─────────────────────────────────────────────────────────────


class TestIDEStatus:
    def test_status_reports_actions_and_config(self, client):
        response = client.get("/v1/ide/status")
        assert response.status_code == 200
        body = response.json()
        assert body["server"] == "codeforge"
        assert sorted(body["actions"]) == sorted(ASSIST_ACTIONS)
        assert "completion_max_tokens" in body["config"]
        assert isinstance(body["workspaces"], list)


class TestIDECompletions:
    def test_returns_cleaned_completion(self, client, fake_service):
        fake_service.text = "answer = a + b\n\ndef other():\n    pass"
        response = client.post(
            "/v1/ide/completions",
            json={
                "editor": {
                    "file_path": "math.py",
                    "language": "python",
                    "prefix": "def add(a, b):\n    ",
                    "suffix": "\n",
                },
                "model": "fake-model",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["text"] == "answer = a + b"
        assert body["model_id"] == "fake-model"
        assert body["usage"]["total_tokens"] == 3

        prompt = fake_service.requests[0].prompt
        assert "What comes after the cursor:" in prompt
        assert "Code up to the cursor:" in prompt
        assert "math.py" in prompt

    def test_disabled_setting_returns_400(self, client):
        response = client.post(
            "/v1/ide/completions",
            json={"editor": {}, "settings": {"completion_enabled": False}},
        )
        assert response.status_code == 400

    def test_no_model_available_returns_409(self, client, monkeypatch):
        monkeypatch.setattr(ide_router, "_first_model", lambda: "")
        response = client.post("/v1/ide/completions", json={"editor": {}})
        assert response.status_code == 409

    def test_model_not_loaded_returns_409(self, client):
        response = client.post(
            "/v1/ide/completions",
            json={"editor": {"prefix": "x = 1\n"}, "model": "nonexistent-model"},
        )
        assert response.status_code == 409


class TestIDEAssist:
    def test_unknown_action_returns_422(self, client):
        response = client.post("/v1/ide/assist", json={"action": "nope", "editor": {}})
        assert response.status_code == 422

    def test_explain_returns_text(self, client, fake_service):
        fake_service.text = "  Adds two numbers.  "
        response = client.post(
            "/v1/ide/assist",
            json={
                "action": "explain",
                "editor": {
                    "file_path": "math.py",
                    "language": "python",
                    "selection": "return a + b",
                },
                "model": "fake-model",
                "include_workspace": False,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["action"] == "explain"
        assert body["text"] == "Adds two numbers."
        prompt = fake_service.requests[0].prompt
        assert "return a + b" in prompt

    def test_stream_emits_sse_events(self, client, fake_service):
        fake_service.stream_texts = ["Hel", "lo"]
        response = client.post(
            "/v1/ide/assist",
            json={
                "action": "fix",
                "editor": {},
                "model": "fake-model",
                "include_workspace": False,
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = response.text
        assert '"type": "token"' in body
        assert '"text": "Hel"' in body
        assert "[DONE]" in body


class TestIDEContext:
    def test_requires_nothing_and_returns_editor(self, client):
        response = client.post("/v1/ide/context", json={"editor": {}})
        assert response.status_code == 200
        body = response.json()
        assert body["workspace_id"] == ""
        assert body["chunks"] == []
        assert "## File" in body["context"]

    def test_max_chars_truncates_context(self, client):
        response = client.post(
            "/v1/ide/context",
            json={"editor": {"selection": "q" * 4000}, "max_chars": 150},
        )
        assert response.status_code == 200
        assert len(response.json()["context"]) <= 150

    def test_returns_indexed_chunks_for_workspace(self, client, indexed_bridge):
        _bridge, root = indexed_bridge
        indexed = client.post(
            "/v1/ide/index", json={"root": str(root), "background": False}
        )
        assert indexed.status_code == 200

        response = client.post(
            "/v1/ide/context",
            json={
                "editor": {
                    "file_path": str(root / "math_util.py"),
                    "root_path": str(root),
                    "language": "python",
                },
                "query": "add_numbers",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["workspace_id"]
        assert body["chunks"], "expected chunks for the indexed file"
        assert any("add_numbers" in c["content"] for c in body["chunks"])
        assert "## Related code" in body["context"]


class TestIDEIndex:
    def test_requires_root_or_workspace(self, client):
        response = client.post("/v1/ide/index", json={})
        assert response.status_code == 422

    def test_indexes_root_path(self, client, indexed_bridge):
        _bridge, root = indexed_bridge
        response = client.post(
            "/v1/ide/index",
            json={"root": str(root), "background": False},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["index_status"] == "READY"
        assert body["job"]["status"] == "COMPLETED"
        assert body["stats"]["file_count"] >= 1
        assert body["stats"]["chunk_count"] >= 1

    def test_reindex_is_skipped_when_fresh(self, client, indexed_bridge):
        _bridge, root = indexed_bridge
        first = client.post("/v1/ide/index", json={"root": str(root), "background": False})
        second = client.post("/v1/ide/index", json={"root": str(root), "background": False})
        assert first.json()["job"] is not None
        assert second.json()["job"] is None
        assert second.json()["index_status"] == "READY"
