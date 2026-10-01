"""Google Gemini generateContent API provider."""

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
    "STOP": "stop",
    "MAX": "length",
    "SAFETY": "error",
    "RECITATION": "error",
    "BLOCKLIST": "error",
    "PROHIBITED_CONTENT": "error",
    "SPII": "error",
}


def _map_finish(reason: str | None) -> str:
    if not reason:
        return "stop"
    return _FINISH_MAP.get(reason, "stop")


def _split_messages(messages: list[dict]) -> tuple[str | None, list[dict[str, Any]]]:
    """Map OpenAI-style messages to Gemini contents (+ system instruction)."""
    system_parts: list[str] = []
    contents: list[dict[str, Any]] = []
    for msg in messages:
        role = str(msg.get("role", "user"))
        content = str(msg.get("content", ""))
        if role == "system":
            system_parts.append(content)
            continue
        gemini_role = "model" if role == "assistant" else "user"
        contents.append({"role": gemini_role, "parts": [{"text": content}]})
    system_instruction = "\n".join(system_parts) if system_parts else None
    return system_instruction, contents


class GeminiProvider(ModelProvider):
    """Talks to the Google Gemini generateContent API."""

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
            "x-goog-api-key": instance.api_key,
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
        system_instruction, contents = _split_messages(messages)
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
                "topP": top_p,
            },
        }
        if system_instruction is not None:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        del instance
        return payload

    @staticmethod
    def _extract_text(data: dict) -> str:
        candidates = data.get("candidates") or []
        if not candidates or not isinstance(candidates[0], dict):
            return ""
        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []
        return "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict))

    @staticmethod
    def _extract_usage(data: dict) -> dict[str, int]:
        usage = data.get("usageMetadata") or {}
        prompt = int(usage.get("promptTokenCount", 0) or 0)
        completion = int(usage.get("candidatesTokenCount", 0) or 0)
        total = int(usage.get("totalTokenCount", prompt + completion) or 0)
        return {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": total,
        }

    @staticmethod
    def _extract_finish(data: dict) -> str:
        candidates = data.get("candidates") or []
        if not candidates or not isinstance(candidates[0], dict):
            return "error"
        return _map_finish(candidates[0].get("finishReason"))

    def _chat_request(
        self,
        instance: RemoteModelInstance,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
        top_p: float,
    ) -> GenerationResult:
        url = f"{instance.base_url}/models/{instance.model_name}:generateContent"
        payload = self._payload(instance, messages, max_tokens, temperature, top_p)
        try:
            response = self._get_client().post(
                url,
                headers=self._headers(instance),
                json=payload,
            )
        except httpx.HTTPError as exc:
            return error_result(f"Gemini request failed: {exc}")
        if response.status_code != 200:
            return error_result(f"Gemini API error {response.status_code}: {response.text[:500]}")
        try:
            data = response.json()
        except ValueError:
            return error_result("Gemini API returned invalid JSON")
        if not data.get("candidates"):
            block_reason = (data.get("promptFeedback") or {}).get(
                "blockReason", "no candidates returned"
            )
            return error_result(f"Gemini API: {block_reason}")
        return GenerationResult(
            text=self._extract_text(data),
            finish_reason=self._extract_finish(data),
            usage=self._extract_usage(data),
        )

    def load_model(
        self, metadata: ModelMetadata, device: str = "auto", dtype: str = "auto"
    ) -> object:
        del device, dtype
        settings = get_remote_settings()
        key = settings.gemini_key()
        if not key:
            raise ModelLoadError(metadata.model_id, "GEMINI_API_KEY is not configured")
        name = metadata.model_id.partition(":")[2] or metadata.model_id
        return RemoteModelInstance(
            provider_name="gemini",
            model_name=name,
            api_key=key,
            base_url=settings.gemini_base_url.rstrip("/"),
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
        payload = self._payload(instance, messages, max_tokens, temperature, top_p)
        url = f"{instance.base_url}/models/{instance.model_name}:streamGenerateContent?alt=sse"
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
                        error=(f"Gemini API error {response.status_code}: {body[:500]}"),
                    )
                    return
                prompt_tokens = 0
                for line in iter_sse_json(response.iter_lines()):
                    chunk = parse_json_object(line)
                    if chunk is None:
                        continue
                    usage = chunk.get("usageMetadata") or {}
                    if usage.get("promptTokenCount"):
                        prompt_tokens = int(usage["promptTokenCount"])
                    for part in self._stream_parts(chunk):
                        yield StreamToken(text=part, is_end=False)
                yield StreamToken(text="", is_end=True, prompt_tokens=prompt_tokens)
        except httpx.HTTPError as exc:
            yield StreamToken(text="", is_end=True, error=f"Gemini request failed: {exc}")

    @staticmethod
    def _stream_parts(chunk: dict) -> Iterator[str]:
        candidates = chunk.get("candidates") or []
        if not candidates or not isinstance(candidates[0], dict):
            return
        content = candidates[0].get("content") or {}
        for part in content.get("parts") or []:
            if isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str) and text:
                    yield text

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
                    "provider": "gemini",
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
        return 1048576 if self.is_loaded(model_instance) else 0

    def health_check(self, model_instance: object) -> dict:
        loaded = self.is_loaded(model_instance)
        return {
            "healthy": loaded,
            "loaded": loaded,
            "device": "cloud",
            "dtype": "api",
        }
