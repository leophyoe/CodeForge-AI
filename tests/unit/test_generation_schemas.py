"""Tests for generation schemas."""

import pytest

from codeforge.packages.generation.schemas import (
    ChatMessage,
    ChatRequest,
    FinishReason,
    GenerationConfig,
    GenerationRequest,
    GenerationResponse,
    StreamEvent,
    StreamEventType,
    UsageInfo,
)


class TestGenerationConfig:
    def test_defaults(self) -> None:
        c = GenerationConfig()
        assert c.max_tokens == 256
        assert c.temperature == 0.7
        assert c.top_p == 0.9
        assert c.top_k == 0
        assert c.repetition_penalty == 1.0
        assert c.do_sample is True
        assert c.stop_sequences == []

    def test_custom_values(self) -> None:
        c = GenerationConfig(max_tokens=512, temperature=0.5, top_p=0.95)
        assert c.max_tokens == 512
        assert c.temperature == 0.5
        assert c.top_p == 0.95

    def test_validate_valid(self) -> None:
        c = GenerationConfig()
        c.validate()

    def test_validate_max_tokens_zero(self) -> None:
        c = GenerationConfig(max_tokens=0)
        with pytest.raises(ValueError, match="max_tokens"):
            c.validate()

    def test_validate_max_tokens_too_large(self) -> None:
        c = GenerationConfig(max_tokens=100000)
        with pytest.raises(ValueError, match="max_tokens"):
            c.validate()

    def test_validate_negative_temperature(self) -> None:
        c = GenerationConfig(temperature=-0.1)
        with pytest.raises(ValueError, match="temperature"):
            c.validate()

    def test_validate_temperature_too_high(self) -> None:
        c = GenerationConfig(temperature=3.0)
        with pytest.raises(ValueError, match="temperature"):
            c.validate()

    def test_validate_top_p_out_of_range(self) -> None:
        c = GenerationConfig(top_p=1.5)
        with pytest.raises(ValueError, match="top_p"):
            c.validate()

    def test_validate_negative_repetition_penalty(self) -> None:
        c = GenerationConfig(repetition_penalty=-1.0)
        with pytest.raises(ValueError, match="repetition_penalty"):
            c.validate()

    def test_validate_boundary_values(self) -> None:
        c = GenerationConfig(max_tokens=1, temperature=0.0, top_p=0.0)
        c.validate()

    def test_validate_max_boundary(self) -> None:
        c = GenerationConfig(max_tokens=32768, temperature=2.0, top_p=1.0)
        c.validate()


class TestChatMessage:
    def test_defaults(self) -> None:
        m = ChatMessage()
        assert m.role == "user"
        assert m.content == ""

    def test_valid_message(self) -> None:
        m = ChatMessage(role="assistant", content="Hello!")
        m.validate()

    def test_invalid_role(self) -> None:
        m = ChatMessage(role="system", content="test")
        m.validate()

    def test_invalid_role_custom(self) -> None:
        m = ChatMessage(role="moderator", content="test")
        with pytest.raises(ValueError, match="Invalid role"):
            m.validate()

    def test_empty_content(self) -> None:
        m = ChatMessage(role="user", content="")
        with pytest.raises(ValueError, match="Content cannot be empty"):
            m.validate()

    def test_whitespace_content(self) -> None:
        m = ChatMessage(role="user", content="   ")
        with pytest.raises(ValueError, match="Content cannot be empty"):
            m.validate()


class TestGenerationRequest:
    def test_defaults(self) -> None:
        r = GenerationRequest()
        assert r.prompt == ""
        assert r.model_id == ""
        assert isinstance(r.config, GenerationConfig)

    def test_validate_empty_prompt(self) -> None:
        r = GenerationRequest(prompt="", model_id="test-model")
        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            r.validate()

    def test_validate_empty_model(self) -> None:
        r = GenerationRequest(prompt="Hello", model_id="")
        with pytest.raises(ValueError, match="model_id cannot be empty"):
            r.validate()

    def test_validate_valid(self) -> None:
        r = GenerationRequest(prompt="Hello", model_id="test-model")
        r.validate()


class TestChatRequest:
    def test_defaults(self) -> None:
        r = ChatRequest()
        assert r.messages == []
        assert r.model_id == ""

    def test_validate_empty_messages(self) -> None:
        r = ChatRequest(model_id="test-model")
        with pytest.raises(ValueError, match="Messages cannot be empty"):
            r.validate()

    def test_validate_empty_model(self) -> None:
        r = ChatRequest(messages=[ChatMessage(content="Hi")], model_id="")
        with pytest.raises(ValueError, match="model_id cannot be empty"):
            r.validate()

    def test_validate_valid(self) -> None:
        r = ChatRequest(
            messages=[ChatMessage(role="user", content="Hi")],
            model_id="test-model",
        )
        r.validate()

    def test_validate_invalid_message(self) -> None:
        r = ChatRequest(
            messages=[ChatMessage(role="bad", content="Hi")],
            model_id="test-model",
        )
        with pytest.raises(ValueError, match="Invalid role"):
            r.validate()


class TestUsageInfo:
    def test_defaults(self) -> None:
        u = UsageInfo()
        assert u.prompt_tokens == 0
        assert u.completion_tokens == 0
        assert u.total_tokens == 0

    def test_to_dict(self) -> None:
        u = UsageInfo(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        d = u.to_dict()
        assert d["prompt_tokens"] == 10
        assert d["completion_tokens"] == 20
        assert d["total_tokens"] == 30


class TestGenerationResponse:
    def test_defaults(self) -> None:
        r = GenerationResponse()
        assert r.text == ""
        assert r.finish_reason == FinishReason.STOP
        assert r.model_id == ""

    def test_to_dict(self) -> None:
        r = GenerationResponse(
            text="Hello",
            finish_reason=FinishReason.STOP,
            usage=UsageInfo(prompt_tokens=5, completion_tokens=10, total_tokens=15),
            model_id="test",
        )
        d = r.to_dict()
        assert d["text"] == "Hello"
        assert d["finish_reason"] == "stop"
        assert d["model_id"] == "test"
        assert d["usage"]["prompt_tokens"] == 5


class TestStreamEvent:
    def test_token_event(self) -> None:
        e = StreamEvent(event_type=StreamEventType.TOKEN, text="Hello")
        d = e.to_dict()
        assert d["event_type"] == "token"
        assert d["text"] == "Hello"

    def test_end_event(self) -> None:
        e = StreamEvent(event_type=StreamEventType.END, is_end=True)
        d = e.to_dict()
        assert d["is_end"] is True

    def test_error_event(self) -> None:
        e = StreamEvent(event_type=StreamEventType.ERROR, error="fail")
        d = e.to_dict()
        assert d["error"] == "fail"

    def test_event_with_usage(self) -> None:
        u = UsageInfo(prompt_tokens=5, completion_tokens=10, total_tokens=15)
        e = StreamEvent(event_type=StreamEventType.END, usage=u)
        d = e.to_dict()
        assert d["usage"]["prompt_tokens"] == 5


class TestFinishReason:
    def test_values(self) -> None:
        assert FinishReason.STOP.value == "stop"
        assert FinishReason.LENGTH.value == "length"
        assert FinishReason.ERROR.value == "error"
        assert FinishReason.CANCELLED.value == "cancelled"


class TestStreamEventType:
    def test_values(self) -> None:
        assert StreamEventType.TOKEN.value == "token"
        assert StreamEventType.START.value == "start"
        assert StreamEventType.END.value == "end"
        assert StreamEventType.ERROR.value == "error"
