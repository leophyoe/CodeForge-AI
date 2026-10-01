"""OpenAI Chat Completions API provider."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import httpx

from codeforge.packages.models.errors import ModelLoadError
from codeforge.packages.models.models import GenerationResult, ModelMetadata, StreamToken
from codeforge.packages.models.provider import ModelProvider

from .base import (
    RemoteModelInstance,
    error_result,
    iter_sse_json,
    make_client,
    parse_json_object,
)
from .settings import get_remote_settings

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)

_FINISH_MAP = {
    "stop": "stop",
    "length": "length",
    "content_filter": "error",
    "tool_calls": "stop",
    "function_call": "stop",
}


def _map_finish(reason: str | None) -> str:
    if not reason:
        return "stop"
    return _FINISH_MAP.get(reason, "stop")


class OpenAIProvider(ModelProvider):
    """Talks to the OpenAI Chat Completions API."""

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self._transport = transport
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = make_client(self._transport)
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def _instance(self, model_instance: object) -> RemoteModelInstance | None:
        if isinstance(model_instance, RemoteModelInstance):
            return model_instance
        return None

    @staticmethod
    def _headers(instance: RemoteModelInstance) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {instance.api_key}",
            "Content-Type": "application/json",
        }

    def _payload(
        self,
        instance: RemoteModelInstance,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
        top_p: float,
    ) -> dict[str, Any]:
        return {
            "model": instance.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
        }

    def _chat_request(
        self,
        instance: RemoteModelInstance,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
        top_p: float,
    ) -> GenerationResult:
        url = f"{instance.base_url}/chat/completions"
        payload = self._payload(instance, messages, max_tokens, temperature, top_p)
        try:
            response = self._get_client().post(
                url,
                headers=self._headers(instance),
                json=payload,
            )
        except httpx.HTTPError as exc:
            return error_result(f"OpenAI request failed: {exc}")
        if response.status_code != 200:
            return error_result(f"OpenAI API error {response.status_code}: {response.text[:500]}")
        try:
            data = response.json()
        except ValueError:
            return error_result("OpenAI API returned invalid JSON")
        choices = data.get("choices") or []
        if not choices:
            return error_result("OpenAI API returned no choices")
        choice = choices[0] if isinstance(choices[0], dict) else {}
        text = ((choice.get("message") or {}).get("content")) or ""
        usage = data.get("usage") or {}
        return GenerationResult(
            text=text,
            finish_reason=_map_finish(choice.get("finish_reason")),
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
        )

    def load_model(
        self, metadata: ModelMetadata, device: str = "auto", dtype: str = "auto"
    ) -> object:
        del device, dtype
        settings = get_remote_settings()
        key = settings.openai_key()
        if not key:
            raise ModelLoadError(metadata.model_id, "OPENAI_API_KEY is not configured")
        name = metadata.model_id.partition(":")[2] or metadata.model_id
        return RemoteModelInstance(
            provider_name="openai",
            model_name=name,
            api_key=key,
            base_url=settings.openai_base_url.rstrip("/"),
        )

    def unload_model(self, model_instance: object) -> None:
        del model_instance

    def is_loaded(self, model_instance: object) -> bool:
        return isinstance(model_instance, RemoteModelInstance)

    def generate(
        self,
        model_instance: object,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> GenerationResult:
        instance = self._instance(model_instance)
        if instance is None:
            return error_result("Model not loaded")
        messages = [{"role": "user", "content": prompt}]
        return self._chat_request(instance, messages, max_tokens, temperature, top_p)

    def stream_generate(
        self,
        model_instance: object,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> Iterator[StreamToken]:
        instance = self._instance(model_instance)
        if instance is None:
            yield StreamToken(text="", is_end=True, error="Model not loaded")
            return

        messages = [{"role": "user", "content": prompt}]
        payload: dict[str, Any] = {
            **self._payload(instance, messages, max_tokens, temperature, top_p),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        url = f"{instance.base_url}/chat/completions"
        try:
            with self._get_client().stream(
                "POST",
                url,
                headers=self._headers(instance),
                json=payload,
            ) as response:
                if response.status_code != 200:
                    body = response.read().decode("utf-8", errors="replace")
                    yield StreamToken(
                        text="",
                        is_end=True,
                        error=(f"OpenAI API error {response.status_code}: {body[:500]}"),
                    )
                    return
                prompt_tokens = 0
                for line in iter_sse_json(response.iter_lines()):
                    chunk = parse_json_object(line)
                    if chunk is None:
                        continue
                    usage = chunk.get("usage")
                    if isinstance(usage, dict) and usage.get("prompt_tokens"):
                        prompt_tokens = int(usage["prompt_tokens"])
                    for choice in chunk.get("choices") or []:
                        if not isinstance(choice, dict):
                            continue
                        delta = choice.get("delta") or {}
                        content = delta.get("content")
                        if isinstance(content, str) and content:
                            yield StreamToken(text=content, is_end=False)
                yield StreamToken(text="", is_end=True, prompt_tokens=prompt_tokens)
        except httpx.HTTPError as exc:
            yield StreamToken(text="", is_end=True, error=f"OpenAI request failed: {exc}")

    def chat(
        self,
        model_instance: object,
        messages: list[dict],
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> GenerationResult:
        instance = self._instance(model_instance)
        if instance is None:
            return error_result("Model not loaded")
        return self._chat_request(instance, messages, max_tokens, temperature, 0.9)

    def get_model_info(self, model_instance: object) -> dict:
        info: dict = {"loaded": self.is_loaded(model_instance)}
        instance = self._instance(model_instance)
        if instance is not None:
            info.update(
                {
                    "provider": "openai",
                    "model": instance.model_name,
                    "device": "cloud",
                    "dtype": "api",
                }
            )
        return info

    def estimate_memory(self, metadata: ModelMetadata) -> dict:
        del metadata
        return {
            "model_memory_gb": 0.0,
            "total_gb": 0.0,
            "device": "cloud",
            "dtype": "api",
        }

    def get_context_length(self, model_instance: object) -> int:
        return 128000 if self.is_loaded(model_instance) else 0

    def health_check(self, model_instance: object) -> dict:
        loaded = self.is_loaded(model_instance)
        return {
            "healthy": loaded,
            "loaded": loaded,
            "device": "cloud",
            "dtype": "api",
        }
