"""Tests for GenerationService."""

import pytest

from codeforge.packages.generation.errors import GenerationConfigError, ModelNotLoadedError
from codeforge.packages.generation.schemas import (
    ChatMessage,
    ChatRequest,
    FinishReason,
    GenerationConfig,
    GenerationRequest,
    GenerationResponse,
    StreamEventType,
)
from codeforge.packages.generation.service import GenerationService, _map_finish_reason
from codeforge.packages.models.models import GenerationResult, ModelStatus, StreamToken


class MockProvider:
    def generate(self, instance, prompt, max_tokens=256, temperature=0.7, top_p=0.9):  # noqa: ARG002
        return GenerationResult(
            text="Generated text",
            tokens=[1, 2, 3],
            finish_reason="stop",
            usage={"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        )

    def chat(self, instance, messages, max_tokens=256, temperature=0.7):  # noqa: ARG002
        return GenerationResult(
            text="Chat response",
            tokens=[4, 5, 6],
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        )

    def stream_generate(self, instance, prompt, max_tokens=256, temperature=0.7, top_p=0.9):  # noqa: ARG002
        yield StreamToken(text="Hello", token_id=1, is_end=False)
        yield StreamToken(text=" World", token_id=2, is_end=False)
        yield StreamToken(text="", token_id=0, is_end=True)

    def get_context_length(self, instance):  # noqa: ARG002
        return 0

    def health_check(self, instance):  # noqa: ARG002
        return {"healthy": True, "device": "cpu", "dtype": "float32"}


class MockModelManager:
    def __init__(self) -> None:
        self._provider = MockProvider()
        self._statuses = {}
        self._loaded = {}

    def get_model_status(self, model_id):
        return self._statuses.get(model_id, ModelStatus.DISCOVERED)

    def get_provider(self):
        return self._provider

    def get_cache(self):
        return self

    def get(self, model_id):
        return self._loaded.get(model_id)

    def get_tokenizer_manager(self):
        return None

    def get_registry(self):
        return self

    def register_model(self, model_id, path):  # noqa: ARG002
        self._statuses[model_id] = ModelStatus.DISCOVERED


class TestMapFinishReason:
    def test_stop(self) -> None:
        assert _map_finish_reason("stop") == FinishReason.STOP

    def test_length(self) -> None:
        assert _map_finish_reason("length") == FinishReason.LENGTH

    def test_error(self) -> None:
        assert _map_finish_reason("error") == FinishReason.ERROR

    def test_unknown(self) -> None:
        assert _map_finish_reason("unknown") == FinishReason.STOP


class TestGenerationService:
    def _make_service(self, model_id="test-model", loaded=True):
        mm = MockModelManager()
        if loaded:
            mm._statuses[model_id] = ModelStatus.LOADED  # noqa: SLF001
            mm._loaded[model_id] = "mock_model_instance"  # noqa: SLF001
        return GenerationService(model_manager=mm), mm

    def test_generate(self) -> None:
        svc, _ = self._make_service()
        req = GenerationRequest(prompt="Hello", model_id="test-model")
        resp = svc.generate(req)
        assert isinstance(resp, GenerationResponse)
        assert resp.text == "Generated text"
        assert resp.finish_reason == FinishReason.STOP
        assert resp.usage.prompt_tokens == 5
        assert resp.usage.completion_tokens == 3
        assert resp.model_id == "test-model"

    def test_generate_model_not_loaded(self) -> None:
        svc, _ = self._make_service(loaded=False)
        req = GenerationRequest(prompt="Hello", model_id="test-model")
        with pytest.raises(ModelNotLoadedError):
            svc.generate(req)

    def test_generate_empty_prompt(self) -> None:
        svc, _ = self._make_service()
        req = GenerationRequest(prompt="", model_id="test-model")
        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            svc.generate(req)

    def test_chat(self) -> None:
        svc, _ = self._make_service()
        req = ChatRequest(
            messages=[ChatMessage(role="user", content="Hi")],
            model_id="test-model",
        )
        resp = svc.chat(req)
        assert isinstance(resp, GenerationResponse)
        assert resp.text == "Chat response"
        assert resp.usage.prompt_tokens == 10
        assert resp.usage.completion_tokens == 2

    def test_chat_model_not_loaded(self) -> None:
        svc, _ = self._make_service(loaded=False)
        req = ChatRequest(
            messages=[ChatMessage(role="user", content="Hi")],
            model_id="test-model",
        )
        with pytest.raises(ModelNotLoadedError):
            svc.chat(req)

    def test_stream_generate(self) -> None:
        svc, _ = self._make_service()
        events = list(svc.stream_generate("Hello", "test-model"))
        assert len(events) >= 3
        assert events[0].event_type == StreamEventType.START
        token_events = [e for e in events if e.event_type == StreamEventType.TOKEN]
        assert len(token_events) == 2

    def test_stream_generate_empty_prompt(self) -> None:
        svc, _ = self._make_service()
        with pytest.raises(GenerationConfigError, match="Prompt cannot be empty"):
            list(svc.stream_generate("", "test-model"))

    def test_stream_generate_empty_model(self) -> None:
        svc, _ = self._make_service()
        with pytest.raises(GenerationConfigError, match="model_id cannot be empty"):
            list(svc.stream_generate("Hello", ""))

    def test_stream_generate_model_not_loaded(self) -> None:
        svc, _ = self._make_service(loaded=False)
        with pytest.raises(ModelNotLoadedError):
            list(svc.stream_generate("Hello", "test-model"))

    def test_stream_chat(self) -> None:
        svc, _ = self._make_service()
        messages = [ChatMessage(role="user", content="Hi")]
        events = list(svc.stream_chat(messages, "test-model"))
        assert len(events) >= 3

    def test_stream_chat_empty_messages(self) -> None:
        svc, _ = self._make_service()
        with pytest.raises(GenerationConfigError, match="Messages cannot be empty"):
            list(svc.stream_chat([], "test-model"))

    def test_get_model_status_ready(self) -> None:
        svc, _ = self._make_service()
        status = svc.get_model_status("test-model")
        assert status["ready"] is True
        assert status["device"] == "cpu"

    def test_get_model_status_not_loaded(self) -> None:
        svc, _ = self._make_service(loaded=False)
        status = svc.get_model_status("test-model")
        assert status["ready"] is False

    def test_get_model_status_not_found(self) -> None:
        svc, _ = self._make_service()
        status = svc.get_model_status("nonexistent")
        assert status["ready"] is False
        reason = status.get("reason", "")
        assert "not found" in reason.lower()

    def test_generate_with_custom_config(self) -> None:
        svc, _ = self._make_service()
        config = GenerationConfig(max_tokens=100, temperature=0.5)
        req = GenerationRequest(prompt="Hello", model_id="test-model", config=config)
        resp = svc.generate(req)
        assert resp.text == "Generated text"

    def test_chat_with_custom_config(self) -> None:
        svc, _ = self._make_service()
        config = GenerationConfig(max_tokens=50, temperature=0.3)
        req = ChatRequest(
            messages=[ChatMessage(role="user", content="Hi")],
            model_id="test-model",
            config=config,
        )
        resp = svc.chat(req)
        assert resp.text == "Chat response"
