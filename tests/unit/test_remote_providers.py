"""Tests for remote providers (OpenAI, Gemini) and provider switching."""

from __future__ import annotations

import json

import httpx
import pytest

from codeforge.packages.models.errors import ModelAlreadyLoadedError, ModelLoadError
from codeforge.packages.models.manager import ModelManager
from codeforge.packages.models.models import ModelFormat, ModelStatus
from codeforge.packages.models.provider import LocalPyTorchProvider
from codeforge.packages.models.remote import (
    GeminiProvider,
    OpenAIProvider,
    clear_remote_settings_cache,
    is_remote_model,
    list_remote_models,
    remote_metadata,
    reset_remote_providers,
    set_remote_provider,
    split_model_id,
)
from codeforge.packages.models.remote.settings import get_remote_settings

ALL_KEYS = (
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "CODEFORGE_OPENAI_API_KEY",
    "CODEFORGE_GEMINI_API_KEY",
)


@pytest.fixture(autouse=True)
def _clean_remote_state(monkeypatch: pytest.MonkeyPatch):
    from codeforge.api.dependencies import reset_singletons

    for key in ALL_KEYS:
        monkeypatch.delenv(key, raising=False)
    reset_remote_providers()
    clear_remote_settings_cache()
    yield
    reset_remote_providers()
    clear_remote_settings_cache()
    reset_singletons()


# ── catalog / settings ────────────────────────────────────────────────────


class TestCatalog:
    def test_split_valid(self) -> None:
        assert split_model_id("openai:gpt-4o-mini") == ("openai", "gpt-4o-mini")
        assert split_model_id("gemini:gemini-2.5-flash") == (
            "gemini",
            "gemini-2.5-flash",
        )

    def test_split_invalid(self) -> None:
        assert split_model_id("tiny-random-gpt2") is None
        assert split_model_id("foo:bar") is None
        assert split_model_id("openai:") is None

    def test_is_remote_model(self) -> None:
        assert is_remote_model("openai:gpt-4o") is True
        assert is_remote_model("tiny-random-gpt2") is False

    def test_list_remote_models_no_keys(self) -> None:
        assert list_remote_models() == []

    def test_list_remote_models_openai_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        clear_remote_settings_cache()
        entries = list_remote_models()
        ids = [e["model_id"] for e in entries]
        assert ids == ["openai:gpt-4o-mini", "openai:gpt-4o"]
        assert all(e["provider"] == "openai" for e in entries)
        assert all(e["format"] == "api" for e in entries)

    def test_list_remote_models_both_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("GEMINI_API_KEY", "gm-test")
        clear_remote_settings_cache()
        ids = [e["model_id"] for e in list_remote_models()]
        assert any(i.startswith("openai:") for i in ids)
        assert any(i.startswith("gemini:") for i in ids)

    def test_remote_metadata(self) -> None:
        meta = remote_metadata("openai", "gpt-4o-mini")
        assert meta.model_id == "openai:gpt-4o-mini"
        assert meta.provider == "openai"
        assert meta.format is ModelFormat.API
        assert meta.context_length == 128000

    def test_settings_fallback_codeforge_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CODEFORGE_OPENAI_API_KEY", "sk-fallback")
        clear_remote_settings_cache()
        assert get_remote_settings().openai_key() == "sk-fallback"


# ── OpenAI provider ───────────────────────────────────────────────────────


def _openai_ok(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    if body.get("stream"):
        sse = (
            'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n'
            'data: {"choices":[],'
            '"usage":{"prompt_tokens":7,"completion_tokens":2,'
            '"total_tokens":9}}\n\n'
            "data: [DONE]\n\n"
        )
        return httpx.Response(200, text=sse)
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Hi there"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 3,
                "total_tokens": 8,
            },
        },
    )


def _openai_unauthorized(request: httpx.Request) -> httpx.Response:
    del request
    return httpx.Response(401, json={"error": {"message": "Incorrect API key"}})


def _openai_provider(handler) -> OpenAIProvider:
    return OpenAIProvider(transport=httpx.MockTransport(handler))


def _load_openai(provider: OpenAIProvider, model_id: str = "openai:gpt-4o-mini"):
    from codeforge.packages.models.remote import remote_metadata as _meta

    prefix, name = split_model_id(model_id)  # type: ignore[misc]
    return provider.load_model(_meta(prefix, name))


class TestOpenAIProvider:
    def test_load_missing_key(self) -> None:
        provider = _openai_provider(_openai_ok)
        with pytest.raises(ModelLoadError, match="OPENAI_API_KEY"):
            provider.load_model(remote_metadata("openai", "gpt-4o-mini"))

    def test_load_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        clear_remote_settings_cache()
        provider = _openai_provider(_openai_ok)
        instance = _load_openai(provider)
        assert provider.is_loaded(instance)
        info = provider.get_model_info(instance)
        assert info["provider"] == "openai"
        assert info["model"] == "gpt-4o-mini"
        assert provider.health_check(instance)["healthy"] is True
        assert provider.get_context_length(instance) == 128000

    def test_generate_maps_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        clear_remote_settings_cache()
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["auth"] = request.headers.get("authorization")
            seen["body"] = json.loads(request.content)
            return _openai_ok(request)

        provider = _openai_provider(handler)
        instance = _load_openai(provider)
        result = provider.generate(instance, "hello", max_tokens=5)
        assert result.text == "Hi there"
        assert result.finish_reason == "stop"
        assert result.usage["prompt_tokens"] == 5
        assert result.usage["completion_tokens"] == 3
        assert seen["url"].endswith("/chat/completions")
        assert seen["auth"] == "Bearer sk-test"
        assert seen["body"]["model"] == "gpt-4o-mini"
        assert seen["body"]["max_tokens"] == 5
        assert seen["body"]["messages"] == [{"role": "user", "content": "hello"}]

    def test_generate_api_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-wrong")
        clear_remote_settings_cache()
        provider = _openai_provider(_openai_unauthorized)
        instance = _load_openai(provider)
        result = provider.generate(instance, "hello")
        assert result.finish_reason == "error"
        assert "401" in str(result.usage.get("error"))

    def test_generate_not_loaded(self) -> None:
        provider = _openai_provider(_openai_ok)
        result = provider.generate(object(), "hello")
        assert result.finish_reason == "error"
        assert "not loaded" in str(result.usage.get("error"))

    def test_chat_forwards_messages(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        clear_remote_settings_cache()
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(request.content)
            return _openai_ok(request)

        provider = _openai_provider(handler)
        instance = _load_openai(provider)
        messages = [
            {"role": "system", "content": "be brief"},
            {"role": "user", "content": "hi"},
        ]
        result = provider.chat(instance, messages, max_tokens=10)
        assert result.text == "Hi there"
        assert seen["body"]["messages"] == messages

    def test_stream_generate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        clear_remote_settings_cache()
        provider = _openai_provider(_openai_ok)
        instance = _load_openai(provider)
        tokens = list(provider.stream_generate(instance, "hello", max_tokens=5))
        assert [t.text for t in tokens[:-1]] == ["Hel", "lo"]
        end = tokens[-1]
        assert end.is_end is True
        assert end.prompt_tokens == 7

    def test_stream_generate_api_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-wrong")
        clear_remote_settings_cache()
        provider = _openai_provider(_openai_unauthorized)
        instance = _load_openai(provider)
        tokens = list(provider.stream_generate(instance, "hello"))
        assert tokens[-1].is_end is True
        assert "401" in tokens[-1].error


# ── Gemini provider ───────────────────────────────────────────────────────


def _gemini_ok(request: httpx.Request) -> httpx.Response:
    if "streamGenerateContent" in str(request.url):
        sse = (
            'data: {"candidates":[{"content":{"parts":[{"text":"Xy"}]}}]}\n\n'
            'data: {"candidates":[{"content":{"parts":[{"text":"z"}]},'
            '"finishReason":"STOP"}],"usageMetadata":'
            '{"promptTokenCount":4,"candidatesTokenCount":2,'
            '"totalTokenCount":6}}\n\n'
        )
        return httpx.Response(200, text=sse)
    return httpx.Response(
        200,
        json={
            "candidates": [
                {
                    "content": {"parts": [{"text": "Hello from Gemini"}]},
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 6,
                "candidatesTokenCount": 4,
                "totalTokenCount": 10,
            },
        },
    )


def _gemini_bad_request(request: httpx.Request) -> httpx.Response:
    del request
    return httpx.Response(400, json={"error": {"message": "bad model"}})


def _gemini_provider(handler) -> GeminiProvider:
    return GeminiProvider(transport=httpx.MockTransport(handler))


def _load_gemini(provider: GeminiProvider):
    return provider.load_model(remote_metadata("gemini", "gemini-2.5-flash"))


class TestGeminiProvider:
    def test_load_missing_key(self) -> None:
        provider = _gemini_provider(_gemini_ok)
        with pytest.raises(ModelLoadError, match="GEMINI_API_KEY"):
            provider.load_model(remote_metadata("gemini", "gemini-2.5-flash"))

    def test_generate_request_and_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "gm-test")
        clear_remote_settings_cache()
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["key"] = request.headers.get("x-goog-api-key")
            seen["body"] = json.loads(request.content)
            return _gemini_ok(request)

        provider = _gemini_provider(handler)
        instance = _load_gemini(provider)
        messages = [
            {"role": "system", "content": "be brief"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "again"},
        ]
        result = provider.chat(instance, messages, max_tokens=8)
        assert result.text == "Hello from Gemini"
        assert result.finish_reason == "stop"
        assert result.usage == {
            "prompt_tokens": 6,
            "completion_tokens": 4,
            "total_tokens": 10,
        }
        assert ":generateContent" in seen["url"]
        assert "streamGenerateContent" not in seen["url"]
        assert seen["key"] == "gm-test"
        assert seen["body"]["systemInstruction"]["parts"][0]["text"] == "be brief"
        roles = [c["role"] for c in seen["body"]["contents"]]
        assert roles == ["user", "model", "user"]
        assert seen["body"]["generationConfig"]["maxOutputTokens"] == 8

    def test_generate_api_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "gm-test")
        clear_remote_settings_cache()
        provider = _gemini_provider(_gemini_bad_request)
        instance = _load_gemini(provider)
        result = provider.generate(instance, "hello")
        assert result.finish_reason == "error"
        assert "400" in str(result.usage.get("error"))

    def test_stream_generate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "gm-test")
        clear_remote_settings_cache()
        provider = _gemini_provider(_gemini_ok)
        instance = _load_gemini(provider)
        tokens = list(provider.stream_generate(instance, "hello", max_tokens=4))
        assert [t.text for t in tokens[:-1]] == ["Xy", "z"]
        end = tokens[-1]
        assert end.is_end is True
        assert end.prompt_tokens == 4

    def test_health_and_context(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "gm-test")
        clear_remote_settings_cache()
        provider = _gemini_provider(_gemini_ok)
        instance = _load_gemini(provider)
        assert provider.health_check(instance)["healthy"] is True
        assert provider.get_context_length(instance) == 1048576
        memory = provider.estimate_memory(remote_metadata("gemini", "x"))
        assert memory["device"] == "cloud"


# ── manager dispatch + service auto-load ──────────────────────────────────


class TestManagerDispatch:
    def test_load_and_unload_remote(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        clear_remote_settings_cache()
        provider = _openai_provider(_openai_ok)
        set_remote_provider("openai", provider)

        mm = ModelManager()
        result = mm.load_model("openai:gpt-4o-mini")
        assert result["status"] == "loaded"
        assert result["provider"] == "openai"
        assert mm.get_model_status("openai:gpt-4o-mini") is ModelStatus.LOADED
        assert "openai:gpt-4o-mini" in mm.get_loaded_models()
        assert mm.get_provider_for_model("openai:gpt-4o-mini") is provider

        with pytest.raises(ModelAlreadyLoadedError):
            mm.load_model("openai:gpt-4o-mini")

        unload = mm.unload_model("openai:gpt-4o-mini")
        assert unload["status"] == "unloaded"
        assert mm.get_model_status("openai:gpt-4o-mini") is ModelStatus.UNLOADED

    def test_local_provider_unchanged(self) -> None:
        mm = ModelManager()
        assert isinstance(mm.get_provider_for_model("tiny-random-gpt2"), LocalPyTorchProvider)

    def test_load_remote_without_key(self) -> None:
        mm = ModelManager()
        with pytest.raises(ModelLoadError, match="OPENAI_API_KEY"):
            mm.load_model("openai:gpt-4o-mini")
        assert mm.get_model_status("openai:gpt-4o-mini") is ModelStatus.FAILED


class TestServiceAutoLoad:
    def test_chat_autoloads_remote(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from codeforge.packages.generation import (
            ChatMessage,
            ChatRequest,
            GenerationService,
        )

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        clear_remote_settings_cache()
        set_remote_provider("openai", _openai_provider(_openai_ok))

        mm = ModelManager()
        svc = GenerationService(model_manager=mm)
        request = ChatRequest(
            model_id="openai:gpt-4o-mini",
            messages=[ChatMessage(role="user", content="hi")],
        )
        response = svc.chat(request)
        assert response.text == "Hi there"
        assert response.usage.completion_tokens == 3
        assert mm.get_model_status("openai:gpt-4o-mini") is ModelStatus.LOADED

    def test_stream_chat_autoloads_remote(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from codeforge.packages.generation import (
            ChatMessage,
            GenerationConfig,
            GenerationService,
        )

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        clear_remote_settings_cache()
        set_remote_provider("openai", _openai_provider(_openai_ok))

        svc = GenerationService(model_manager=ModelManager())
        events = list(
            svc.stream_chat(
                [ChatMessage(role="user", content="hi")],
                "openai:gpt-4o-mini",
                GenerationConfig(max_tokens=5),
            )
        )
        token_texts = [e.text for e in events if e.event_type.value == "token"]
        assert token_texts == ["Hel", "lo"]
        end_events = [e for e in events if e.usage is not None]
        assert end_events
        assert end_events[-1].usage.prompt_tokens == 7

    def test_chat_error_surfaces_usage(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from codeforge.packages.generation import (
            ChatMessage,
            ChatRequest,
            GenerationService,
        )

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        clear_remote_settings_cache()
        set_remote_provider("openai", _openai_provider(_openai_unauthorized))
        svc = GenerationService(model_manager=ModelManager())
        request = ChatRequest(
            model_id="openai:gpt-4o-mini",
            messages=[ChatMessage(role="user", content="hi")],
        )
        response = svc.chat(request)
        assert response.finish_reason.value == "error"
        assert "401" in response.usage.error

    def test_remote_without_key_raises(self) -> None:
        from codeforge.packages.generation import (
            ChatMessage,
            ChatRequest,
            GenerationService,
        )

        svc = GenerationService(model_manager=ModelManager())
        request = ChatRequest(
            model_id="openai:gpt-4o-mini",
            messages=[ChatMessage(role="user", content="hi")],
        )
        with pytest.raises(ModelLoadError, match="OPENAI_API_KEY"):
            svc.chat(request)

    def test_local_not_loaded_still_409(self) -> None:
        from codeforge.packages.generation import (
            ChatMessage,
            ChatRequest,
            GenerationService,
            ModelNotLoadedError,
        )

        svc = GenerationService(model_manager=ModelManager())
        request = ChatRequest(
            model_id="tiny-random-gpt2",
            messages=[ChatMessage(role="user", content="hi")],
        )
        with pytest.raises(ModelNotLoadedError):
            svc.chat(request)


# ── API integration ───────────────────────────────────────────────────────


class TestAPIRemoteModels:
    @staticmethod
    def _app():
        from codeforge.api.app import create_app
        from codeforge.api.config import APIConfig, AppConfig, RateLimitConfig

        config = AppConfig(
            api=APIConfig(docs_enabled=True, auth_required=False),
            rate_limit=RateLimitConfig(enabled=False),
        )
        return create_app(config)

    def test_models_list_includes_remote(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from fastapi.testclient import TestClient

        from codeforge.api.dependencies import reset_singletons

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        clear_remote_settings_cache()
        reset_singletons()
        client = TestClient(self._app())
        response = client.get("/v1/models")
        assert response.status_code == 200
        ids = [m["id"] for m in response.json()["data"]]
        assert "openai:gpt-4o-mini" in ids

    def test_remote_model_detail_and_load(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from fastapi.testclient import TestClient

        from codeforge.api.dependencies import reset_singletons

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        clear_remote_settings_cache()
        reset_singletons()
        set_remote_provider("openai", _openai_provider(_openai_ok))
        client = TestClient(self._app())

        detail = client.get("/v1/models/openai:gpt-4o-mini")
        assert detail.status_code == 200
        assert detail.json()["provider"] == "openai"

        loaded = client.post("/v1/models/openai:gpt-4o-mini/load", json={})
        assert loaded.status_code == 200
        assert loaded.json()["status"] == "loaded"

        chat = client.post(
            "/v1/chat/completions",
            json={
                "model": "openai:gpt-4o-mini",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 5,
            },
        )
        assert chat.status_code == 200
        assert chat.json()["choices"][0]["message"]["content"] == "Hi there"

    def test_remote_chat_without_explicit_load(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from fastapi.testclient import TestClient

        from codeforge.api.dependencies import reset_singletons

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        clear_remote_settings_cache()
        reset_singletons()
        set_remote_provider("openai", _openai_provider(_openai_ok))
        client = TestClient(self._app())

        chat = client.post(
            "/v1/chat",
            json={
                "model": "openai:gpt-4o-mini",
                "messages": [{"role": "user", "content": "hi"}],
                "max_new_tokens": 5,
            },
        )
        assert chat.status_code == 200
        assert chat.json()["usage"]["completion_tokens"] == 3

    def test_unconfigured_gemini_detail_404(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from fastapi.testclient import TestClient

        from codeforge.api.dependencies import reset_singletons

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        clear_remote_settings_cache()
        reset_singletons()
        client = TestClient(self._app())
        response = client.get("/v1/models/gemini:gemini-2.5-flash")
        assert response.status_code == 404
