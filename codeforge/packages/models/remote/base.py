"""Shared building blocks for remote (API-backed) model providers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

from codeforge.packages.models.models import GenerationResult

if TYPE_CHECKING:
    from collections.abc import Iterator

REQUEST_TIMEOUT = httpx.Timeout(120.0, connect=10.0)


@dataclass
class RemoteModelInstance:
    """Handle to a remote model; 'loading' validates credentials."""

    provider_name: str
    model_name: str
    api_key: str
    base_url: str


def make_client(transport: httpx.BaseTransport | None = None) -> httpx.Client:
    """Create an HTTP client with sane timeouts (transport injectable for tests)."""
    return httpx.Client(timeout=REQUEST_TIMEOUT, transport=transport)


def iter_sse_json(lines: Iterator[str]) -> Iterator[str]:
    """Yield the ``data:`` payload strings from SSE lines, stopping at ``[DONE]``."""
    for line in lines:
        stripped = line.strip()
        if not stripped or not stripped.startswith("data:"):
            continue
        data = stripped[len("data:") :].strip()
        if data == "[DONE]":
            return
        yield data


def parse_json_object(data: str) -> dict | None:
    """Parse a JSON object, returning None on invalid input."""
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def error_result(message: str) -> GenerationResult:
    """Build an error GenerationResult (mirrors local provider contract)."""
    return GenerationResult(
        text="",
        finish_reason="error",
        usage={"error": message},
    )
