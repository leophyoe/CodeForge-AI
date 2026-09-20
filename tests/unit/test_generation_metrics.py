"""Tests for generation metrics."""

import time

from codeforge.packages.generation.metrics import GenerationMetrics


class TestGenerationMetrics:
    def test_defaults(self) -> None:
        m = GenerationMetrics()
        assert m.start_time == 0.0
        assert m.end_time == 0.0
        assert m.prompt_tokens == 0
        assert m.completion_tokens == 0
        assert m.first_token_time == 0.0
        assert m._token_times == []  # noqa: SLF001

    def test_start(self) -> None:
        m = GenerationMetrics()
        m.start()
        assert m.start_time > 0
        assert m.end_time == 0.0

    def test_record_first_token(self) -> None:
        m = GenerationMetrics()
        m.start()
        m.record_first_token()
        assert m.first_token_time > 0

    def test_record_first_token_only_once(self) -> None:
        m = GenerationMetrics()
        m.start()
        m.record_first_token()
        first = m.first_token_time
        time.sleep(0.001)
        m.record_first_token()
        assert m.first_token_time == first

    def test_record_token(self) -> None:
        m = GenerationMetrics()
        m.start()
        m.record_token()
        m.record_token()
        assert len(m._token_times) == 2  # noqa: SLF001

    def test_finish(self) -> None:
        m = GenerationMetrics()
        m.start()
        time.sleep(0.001)
        m.finish()
        assert m.end_time > 0
        assert m.total_time_s > 0

    def test_total_time_not_started(self) -> None:
        m = GenerationMetrics()
        assert m.total_time_s == 0.0

    def test_time_to_first_token(self) -> None:
        m = GenerationMetrics()
        m.start()
        time.sleep(0.001)
        m.record_first_token()
        assert m.time_to_first_token_s > 0

    def test_time_to_first_token_not_recorded(self) -> None:
        m = GenerationMetrics()
        m.start()
        assert m.time_to_first_token_s == 0.0

    def test_tokens_per_second(self) -> None:
        m = GenerationMetrics()
        m.start()
        m.completion_tokens = 10
        time.sleep(0.01)
        m.finish()
        tps = m.tokens_per_second
        assert tps > 0

    def test_tokens_per_second_no_tokens(self) -> None:
        m = GenerationMetrics()
        m.start()
        m.finish()
        assert m.tokens_per_second == 0.0

    def test_inter_token_latency(self) -> None:
        m = GenerationMetrics()
        m.start()
        m.record_token()
        time.sleep(0.001)
        m.record_token()
        assert m.inter_token_latency_s > 0

    def test_inter_token_latency_single_token(self) -> None:
        m = GenerationMetrics()
        m.start()
        m.record_token()
        assert m.inter_token_latency_s == 0.0

    def test_to_dict(self) -> None:
        m = GenerationMetrics()
        m.start()
        m.prompt_tokens = 10
        m.completion_tokens = 20
        m.record_first_token()
        m.record_token()
        m.record_token()
        m.finish()
        d = m.to_dict()
        assert d["prompt_tokens"] == 10
        assert d["completion_tokens"] == 20
        assert d["total_tokens"] == 30
        assert "total_time_s" in d
        assert "time_to_first_token_s" in d
        assert "tokens_per_second" in d
        assert "inter_token_latency_s" in d

    def test_total_time_running(self) -> None:
        m = GenerationMetrics()
        m.start()
        time.sleep(0.01)
        t = m.total_time_s
        assert t > 0
