"""Tests for token streaming."""

from codeforge.packages.generation.schemas import StreamEventType
from codeforge.packages.generation.streamer import BlockingStreamer, TokenStreamer
from codeforge.packages.models.models import StreamToken


class MockProvider:
    def stream_generate(self, model_instance, prompt, max_tokens=256, temperature=0.7, top_p=0.9):  # noqa: ARG002
        yield StreamToken(text="Hello", token_id=1, is_end=False)
        yield StreamToken(text=" ", token_id=2, is_end=False)
        yield StreamToken(text="World", token_id=3, is_end=False)
        yield StreamToken(text="", token_id=0, is_end=True)


class MockProviderEmpty:
    def stream_generate(self, model_instance, prompt, max_tokens=256, temperature=0.7, top_p=0.9):  # noqa: ARG002
        yield StreamToken(text="", token_id=0, is_end=True)


class MockProviderError:
    def stream_generate(self, model_instance, prompt, max_tokens=256, temperature=0.7, top_p=0.9):  # noqa: ARG002
        raise RuntimeError("Generation failed")
        yield  # Make it a generator


class TestTokenStreamer:
    def test_stream_basic(self) -> None:
        streamer = TokenStreamer(MockProvider(), "model")
        events = list(streamer.stream("test prompt"))
        assert len(events) >= 3
        assert events[0].event_type == StreamEventType.START
        assert events[-1].event_type == StreamEventType.END

    def test_stream_token_events(self) -> None:
        streamer = TokenStreamer(MockProvider(), "model")
        events = list(streamer.stream("test"))
        token_events = [e for e in events if e.event_type == StreamEventType.TOKEN]
        assert len(token_events) == 3
        assert token_events[0].text == "Hello"
        assert token_events[1].text == " "
        assert token_events[2].text == "World"

    def test_stream_end_has_usage(self) -> None:
        streamer = TokenStreamer(MockProvider(), "model")
        events = list(streamer.stream("test"))
        end_event = events[-1]
        assert end_event.event_type == StreamEventType.END
        assert end_event.usage is not None

    def test_stream_empty(self) -> None:
        streamer = TokenStreamer(MockProviderEmpty(), "model")
        events = list(streamer.stream("test"))
        assert events[0].event_type == StreamEventType.START
        assert events[-1].event_type == StreamEventType.END

    def test_stream_error(self) -> None:
        streamer = TokenStreamer(MockProviderError(), "model")
        events = list(streamer.stream("test"))
        error_events = [e for e in events if e.event_type == StreamEventType.ERROR]
        assert len(error_events) == 1
        assert "Generation failed" in error_events[0].error

    def test_stream_with_stop_sequence(self) -> None:
        class StopProvider:
            def stream_generate(self, *args, **kwargs):  # noqa: ARG002
                yield StreamToken(text="Hello", token_id=1, is_end=False)
                yield StreamToken(text=" STOP", token_id=2, is_end=False)
                yield StreamToken(text=" World", token_id=3, is_end=False)
                yield StreamToken(text="", token_id=0, is_end=True)

        streamer = TokenStreamer(StopProvider(), "model")
        events = list(streamer.stream("test", stop_sequences=["STOP"]))
        token_events = [e for e in events if e.event_type == StreamEventType.TOKEN]
        assert len(token_events) == 2
        assert token_events[0].text == "Hello"
        assert token_events[1].text == " STOP"


class TestBlockingStreamer:
    def test_collect(self) -> None:
        bs = BlockingStreamer(TokenStreamer(MockProvider(), "model"))
        events = bs.collect("test")
        assert len(events) >= 3

    def test_get_text(self) -> None:
        bs = BlockingStreamer(TokenStreamer(MockProvider(), "model"))
        events = bs.collect("test")
        text = bs.get_text(events)
        assert text == "Hello World"

    def test_get_usage(self) -> None:
        bs = BlockingStreamer(TokenStreamer(MockProvider(), "model"))
        events = bs.collect("test")
        usage = bs.get_usage(events)
        assert usage is not None

    def test_get_finish_reason(self) -> None:
        from codeforge.packages.generation.schemas import FinishReason

        bs = BlockingStreamer(TokenStreamer(MockProvider(), "model"))
        events = bs.collect("test")
        reason = bs.get_finish_reason(events)
        assert reason == FinishReason.STOP

    def test_get_finish_reason_error(self) -> None:
        from codeforge.packages.generation.schemas import FinishReason

        bs = BlockingStreamer(TokenStreamer(MockProviderError(), "model"))
        events = bs.collect("test")
        reason = bs.get_finish_reason(events)
        assert reason == FinishReason.ERROR
