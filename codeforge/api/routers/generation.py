"""Generation router - chat, completions, and streaming endpoints."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from codeforge.api.dependencies import get_generation_service
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

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

router = APIRouter(tags=["generation"])


class ChatMessageAPI(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessageAPI]
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_new_tokens: int = Field(default=256, ge=1, le=32768)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    top_k: int = Field(default=0, ge=0)
    stream: bool = False
    stop: list[str] | None = None
    timeout: int | None = None


class CompletionRequest(BaseModel):
    model: str
    prompt: str
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_new_tokens: int = Field(default=256, ge=1, le=32768)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    stream: bool = False
    stop: list[str] | None = None
    timeout: int | None = None


def _validate_model_id(model_id: str) -> None:
    if ".." in model_id or "/" in model_id or "\\" in model_id:
        raise HTTPException(status_code=422, detail="Invalid model id")


def _create_sse_event(data: dict[str, Any] | str) -> str:
    payload = json.dumps(data) if isinstance(data, dict) else data
    return f"data: {payload}\n\n"


def _sse_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }


@router.post("/chat", response_model=None)
async def chat_completion(request: ChatCompletionRequest) -> dict[str, Any] | StreamingResponse:
    _validate_model_id(request.model)
    service = get_generation_service()

    config = GenerationConfig(
        temperature=request.temperature,
        max_tokens=request.max_new_tokens,
        top_p=request.top_p,
        top_k=request.top_k,
        stop_sequences=request.stop or [],
    )

    messages = [ChatMessage(role=m.role, content=m.content) for m in request.messages]
    chat_req = ChatRequest(model_id=request.model, messages=messages, config=config)

    if request.stream:

        async def _event_stream() -> AsyncIterator[str]:
            try:
                for event in service.stream_chat(messages, request.model, config):
                    if event.event_type.value == "token":
                        yield _create_sse_event({"type": "token", "text": event.text})
                    elif event.event_type.value == "error":
                        yield _create_sse_event({"type": "error", "error": event.error})
                        return
                usage_dict = {}
                for ev in reversed(list(service.stream_chat(messages, request.model, config))):
                    if ev.usage is not None:
                        usage_dict = ev.usage.to_dict()
                        break
                yield _create_sse_event(
                    {
                        "type": "end",
                        "finish_reason": "stop",
                        "usage": usage_dict,
                    }
                )
                yield _create_sse_event("[DONE]")
            except Exception as exc:
                yield _create_sse_event({"type": "error", "error": str(exc)})

        return StreamingResponse(
            _event_stream(), media_type="text/event-stream", headers=_sse_headers()
        )

    try:
        result = await asyncio.to_thread(service.chat, chat_req)
    except ModelNotLoadedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ContextLengthExceededError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (GenerationConfigError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    reason = result.finish_reason
    reason_val = reason.value if hasattr(reason, "value") else reason
    return {
        "text": result.text,
        "finish_reason": reason_val,
        "usage": result.usage.to_dict(),
        "model_id": result.model_id,
    }


@router.post("/completions", response_model=None)
async def completion(request: CompletionRequest) -> dict[str, Any] | StreamingResponse:
    _validate_model_id(request.model)
    service = get_generation_service()

    config = GenerationConfig(
        temperature=request.temperature,
        max_tokens=request.max_new_tokens,
        top_p=request.top_p,
        stop_sequences=request.stop or [],
    )

    gen_req = GenerationRequest(model_id=request.model, prompt=request.prompt, config=config)

    if request.stream:

        async def _event_stream() -> AsyncIterator[str]:
            try:
                for event in service.stream_generate(request.prompt, request.model, config):
                    if event.event_type.value == "token":
                        yield _create_sse_event({"type": "token", "text": event.text})
                    elif event.event_type.value == "error":
                        yield _create_sse_event({"type": "error", "error": event.error})
                        return
                yield _create_sse_event({"type": "end", "finish_reason": "stop", "usage": {}})
                yield _create_sse_event("[DONE]")
            except Exception as exc:
                yield _create_sse_event({"type": "error", "error": str(exc)})

        return StreamingResponse(
            _event_stream(), media_type="text/event-stream", headers=_sse_headers()
        )

    try:
        result = await asyncio.to_thread(service.generate, gen_req)
    except ModelNotLoadedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ContextLengthExceededError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (GenerationConfigError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    reason = result.finish_reason
    reason_val = reason.value if hasattr(reason, "value") else reason
    return {
        "text": result.text,
        "finish_reason": reason_val,
        "usage": result.usage.to_dict(),
        "model_id": result.model_id,
    }
