"""Generation metrics collection and reporting."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class GenerationMetrics:
    """Tracks timing and token metrics for a generation call."""

    start_time: float = 0.0
    end_time: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    first_token_time: float = 0.0
    _token_times: list[float] = field(default_factory=list)

    def start(self) -> None:
        self.start_time = time.monotonic()
        self.end_time = 0.0
        self._token_times.clear()

    def record_first_token(self) -> None:
        if self.first_token_time == 0.0:
            self.first_token_time = time.monotonic()

    def record_token(self) -> None:
        self._token_times.append(time.monotonic())

    def finish(self) -> None:
        self.end_time = time.monotonic()

    @property
    def total_time_s(self) -> float:
        if self.start_time == 0.0:
            return 0.0
        end = self.end_time if self.end_time > 0.0 else time.monotonic()
        return end - self.start_time

    @property
    def time_to_first_token_s(self) -> float:
        if self.first_token_time == 0.0 or self.start_time == 0.0:
            return 0.0
        return self.first_token_time - self.start_time

    @property
    def tokens_per_second(self) -> float:
        if self.total_time_s <= 0 or self.completion_tokens <= 0:
            return 0.0
        return self.completion_tokens / self.total_time_s

    @property
    def inter_token_latency_s(self) -> float:
        if len(self._token_times) < 2:
            return 0.0
        total = self._token_times[-1] - self._token_times[0]
        return total / (len(self._token_times) - 1)

    def to_dict(self) -> dict:
        return {
            "total_time_s": round(self.total_time_s, 4),
            "time_to_first_token_s": round(self.time_to_first_token_s, 4),
            "tokens_per_second": round(self.tokens_per_second, 2),
            "inter_token_latency_s": round(self.inter_token_latency_s, 4),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.prompt_tokens + self.completion_tokens,
        }
