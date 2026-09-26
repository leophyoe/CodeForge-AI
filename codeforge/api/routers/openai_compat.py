from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from codeforge.api.dependencies import (
    get_generation_service,
    validate_model_id,
)
from codeforge.packages.generation.errors import (
    ContextLengthExceededError,
    GenerationConfigError,
    ModelNotLoadedError,
)
from codeforge.packages.generation.schemas import (
    ChatMessage,
    ChatRequest,
    GenerationConfig,
    GenerationRequest,
)

router = APIRouter(tags=["openai-compat"])


class OAIChatMessage(BaseModel):
    role: str = "user"
    content: str | None = None


class OAIChatCompletionRequest(BaseModel):
    model: str
    messages: list[OAIChatMessage]
    stream: bool = False
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=32768)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)


class OAICompletionRequest(BaseModel):
    model: str
    prompt: str | list[str] = ""
    stream: bool = False
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=32768)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)


def _build_generation_config(
    temperature: float | None,
    max_tokens: int | None,
    top_p: float | None,
) -> GenerationConfig:
    return GenerationConfig(
        temperature=temperature if temperature is not None else 0.7,
        max_tokens=max_tokens if max_tokens is not None else 256,
        top_p=top_p if top_p is not None else 0.9,
    )


def _sse_chat_chunk(
    chunk_id: str,
    model: str,
    created: int,
    delta: dict[str, Any],
    finish_reason: str | None,
) -> str:
    obj = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
            }
        ],
    }
    return f"data: {json.dumps(obj)}\n\n"


def _sse_completion_chunk(
    chunk_id: str,
    model: str,
    created: int,
    text: str,
    finish_reason: str | None,
) -> str:
    obj = {
        "id": chunk_id,
        "object": "text_completion",
        "created": created,
        "model": model,
        "choices": [
            {
                "text": text,
                "index": 0,
                "finish_reason": finish_reason,
            }
        ],
    }
    return f"data: {json.dumps(obj)}\n\n"


async def _stream_chat_response(
    request: OAIChatCompletionRequest,
) -> AsyncIterator[str]:
    model_id = validate_model_id(request.model)
    service = get_generation_service()
    created = int(time.time())
    chunk_id = f"chatcmpl-{uuid4().hex}"

    messages = [ChatMessage(role=m.role, content=m.content or "") for m in request.messages]
    config = _build_generation_config(
        request.temperature,
        request.max_tokens,
        request.top_p,
    )

    yield _sse_chat_chunk(
        chunk_id,
        model_id,
        created,
        {"role": "assistant", "content": ""},
        None,
    )

    for event in service.stream_chat(messages, model_id, config):
        if event.text:
            yield _sse_chat_chunk(
                chunk_id,
                model_id,
                created,
                {"content": event.text},
                None,
            )

    yield _sse_chat_chunk(chunk_id, model_id, created, {}, "stop")
    yield "data: [DONE]\n\n"


async def _stream_completion_response(
    request: OAICompletionRequest,
) -> AsyncIterator[str]:
    model_id = validate_model_id(request.model)
    service = get_generation_service()
    created = int(time.time())
    chunk_id = f"cmpl-{uuid4().hex}"

    prompt_text = request.prompt if isinstance(request.prompt, str) else request.prompt[0]
    config = _build_generation_config(
        request.temperature,
        request.max_tokens,
        request.top_p,
    )

    for event in service.stream_generate(prompt_text, model_id, config):
        if event.text:
            yield _sse_completion_chunk(
                chunk_id,
                model_id,
                created,
                event.text,
                None,
            )

    yield _sse_completion_chunk(chunk_id, model_id, created, "", "stop")
    yield "data: [DONE]\n\n"


SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.post("/chat/completions", response_model=None)
async def chat_completions(
    request: OAIChatCompletionRequest,
) -> StreamingResponse | dict[str, Any]:
    model_id = validate_model_id(request.model)
    service = get_generation_service()

    if request.stream:
        return StreamingResponse(
            _stream_chat_response(request),
            media_type="text/event-stream",
            headers=SSE_HEADERS,
        )

    messages = [ChatMessage(role=m.role, content=m.content or "") for m in request.messages]
    config = _build_generation_config(
        request.temperature,
        request.max_tokens,
        request.top_p,
    )
    chat_req = ChatRequest(
        messages=messages,
        model_id=model_id,
        config=config,
    )

    try:
        response = await asyncio.to_thread(service.chat, chat_req)
    except ModelNotLoadedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ContextLengthExceededError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (ValueError, GenerationConfigError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "id": f"chatcmpl-{uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_id,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response.text,
                },
                "finish_reason": response.finish_reason.value,
            }
        ],
        "usage": response.usage.to_dict(),
    }


@router.post("/completions", response_model=None)
async def completions(
    request: OAICompletionRequest,
) -> StreamingResponse | dict[str, Any]:
    model_id = validate_model_id(request.model)
    service = get_generation_service()

    if request.stream:
        return StreamingResponse(
            _stream_completion_response(request),
            media_type="text/event-stream",
            headers=SSE_HEADERS,
        )

    prompt_text = request.prompt if isinstance(request.prompt, str) else request.prompt[0]
    config = _build_generation_config(
        request.temperature,
        request.max_tokens,
        request.top_p,
    )
    gen_req = GenerationRequest(
        prompt=prompt_text,
        model_id=model_id,
        config=config,
    )

    try:
        response = await asyncio.to_thread(service.generate, gen_req)
    except ModelNotLoadedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ContextLengthExceededError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (ValueError, GenerationConfigError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "id": f"cmpl-{uuid4().hex}",
        "object": "text_completion",
        "created": int(time.time()),
        "model": model_id,
        "choices": [
            {
                "text": response.text,
                "index": 0,
                "finish_reason": response.finish_reason.value,
            }
        ],
        "usage": response.usage.to_dict(),
    }
