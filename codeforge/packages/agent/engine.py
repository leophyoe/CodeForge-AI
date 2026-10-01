"""AgentEngine — the LLM ↔ tool execution loop (Phase 11)."""

from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import uuid4

from codeforge.packages.generation import (
    ChatMessage,
    FinishReason,
    GenerationService,
    ModelNotLoadedError,
)
from codeforge.packages.generation.schemas import ChatRequest, GenerationConfig
from codeforge.packages.tools.manager import ToolManager
from codeforge.packages.tools.models import ToolExecutionContext

from .errors import AgentLLMError
from .models import AgentConfig, AgentResult, AgentStatus, AgentStep
from .parser import extract_final_text, parse_tool_call
from .prompt import build_system_prompt

if TYPE_CHECKING:
    from .session import AgentSession

_LLM_TEXT_LIMIT = 500


@runtime_checkable
class LLMClient(Protocol):
    """Minimal chat interface the engine depends on (fakeable in tests)."""

    def chat(
        self,
        messages: list[ChatMessage],
        model_id: str,
        *,
        max_tokens: int,
        temperature: float,
    ) -> str: ...


class GenerationLLM:
    """LLM adapter over GenerationService (local + remote models)."""

    def __init__(self, service: GenerationService | None = None) -> None:
        self._service = service or GenerationService()

    @property
    def service(self) -> GenerationService:
        return self._service

    def chat(
        self,
        messages: list[ChatMessage],
        model_id: str,
        *,
        max_tokens: int,
        temperature: float,
    ) -> str:
        request = ChatRequest(
            messages=messages,
            model_id=model_id,
            config=GenerationConfig(
                max_tokens=max_tokens,
                temperature=temperature,
                do_sample=temperature > 0,
            ),
        )
        response = self._service.chat(request)
        if response.finish_reason is FinishReason.ERROR:
            raise AgentLLMError(response.usage.error or "generation failed")
        return response.text


class AgentEngine:
    """Runs one task to completion: LLM turn → tool call → result → repeat."""

    def __init__(
        self,
        llm: LLMClient | None = None,
        tool_manager: ToolManager | None = None,
    ) -> None:
        self.llm = llm or GenerationLLM()
        self.tool_manager = tool_manager or ToolManager()

    def _visible_tools(self, config: AgentConfig) -> list[dict[str, Any]]:
        tools = self.tool_manager.list_tools()
        if config.allowed_tools is not None:
            allowed = set(config.allowed_tools)
            tools = [t for t in tools if t.get("name") in allowed]
        return tools

    async def run(
        self,
        task: str,
        config: AgentConfig,
        session: AgentSession | None = None,
    ) -> AgentResult:
        """Execute a task and return the full trajectory result."""
        config.validate()
        task_id = session.id if session is not None else uuid4().hex[:12]
        result = AgentResult(
            task_id=task_id,
            task=task,
            model_id=config.model_id,
            workspace_id=config.workspace_id,
        )
        if session is not None:
            session.result = result
            session.status = AgentStatus.RUNNING

        tools = self._visible_tools(config)
        tool_names = {t["name"] for t in tools}
        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=build_system_prompt(tools, config)),
            ChatMessage(role="user", content=task),
        ]
        last_text = ""

        for step_no in range(1, config.max_steps + 1):
            if session is not None and session.cancelled:
                result.status = AgentStatus.CANCELLED
                result.cancelled = True
                result.final_text = last_text
                break

            # ── LLM turn ────────────────────────────────────────────────
            started = time.perf_counter()
            try:
                text = await asyncio.to_thread(
                    self.llm.chat,
                    messages,
                    config.model_id,
                    max_tokens=config.max_tokens,
                    temperature=config.temperature,
                )
            except ModelNotLoadedError as exc:
                result.status = AgentStatus.FAILED
                result.error = str(exc)
                result.finished_at = time.time()
                if session is not None:
                    session.status = AgentStatus.FAILED
                raise
            except Exception as exc:  # noqa: BLE001 — surface as failed task
                duration = (time.perf_counter() - started) * 1000
                result.steps.append(
                    AgentStep(
                        index=step_no,
                        kind="llm",
                        error=str(exc),
                        duration_ms=duration,
                    )
                )
                result.status = AgentStatus.FAILED
                result.error = str(exc)
                break

            duration = (time.perf_counter() - started) * 1000
            result.llm_calls += 1
            last_text = text or ""
            messages.append(ChatMessage(role="assistant", content=last_text))
            result.steps.append(
                AgentStep(
                    index=len(result.steps) + 1,
                    kind="llm",
                    text=last_text[:_LLM_TEXT_LIMIT],
                    duration_ms=duration,
                )
            )

            # ── final answer? ───────────────────────────────────────────
            call = parse_tool_call(last_text)
            if call is None:
                result.status = AgentStatus.COMPLETED
                result.final_text = extract_final_text(last_text)
                break

            # ── tool turn ──────────────────────────────────────────────
            if call.name not in tool_names:
                reason = (
                    f"unknown or disallowed tool '{call.name}'; "
                    f"available: {', '.join(sorted(tool_names))}"
                )
                messages.append(ChatMessage(role="user", content=f"TOOL_RESULT error: {reason}"))
                result.steps.append(
                    AgentStep(
                        index=len(result.steps) + 1,
                        kind="tool",
                        tool_name=call.name,
                        arguments=call.arguments,
                        success=False,
                        error=reason,
                    )
                )
                continue

            started = time.perf_counter()
            try:
                tool_result = await self.tool_manager.execute_tool_async(
                    call.name,
                    call.arguments,
                    ToolExecutionContext(workspace_id=config.workspace_id),
                )
            except Exception as exc:  # noqa: BLE001 — never crash the loop
                tool_feedback = json.dumps({"success": False, "error": str(exc)})
                result.steps.append(
                    AgentStep(
                        index=len(result.steps) + 1,
                        kind="tool",
                        tool_name=call.name,
                        arguments=call.arguments,
                        success=False,
                        error=str(exc),
                        duration_ms=(time.perf_counter() - started) * 1000,
                    )
                )
            else:
                payload: dict[str, Any] = {
                    "success": tool_result.success,
                    "error": tool_result.error,
                }
                error_code = tool_result.metadata.get("error_code", "")
                if error_code:
                    payload["error_code"] = error_code
                if tool_result.success:
                    payload["result"] = tool_result.result
                tool_feedback = json.dumps(payload, default=str)
                result.tool_calls += 1
                result.steps.append(
                    AgentStep(
                        index=len(result.steps) + 1,
                        kind="tool",
                        tool_name=call.name,
                        arguments=call.arguments,
                        success=tool_result.success,
                        error=tool_result.error,
                        duration_ms=(time.perf_counter() - started) * 1000,
                    )
                )

            if len(tool_feedback) > config.tool_result_char_limit:
                tool_feedback = tool_feedback[: config.tool_result_char_limit] + "...(truncated)"
            messages.append(
                ChatMessage(role="user", content=f"TOOL_RESULT {call.name}:\n{tool_feedback}")
            )
        else:
            # exhausted all steps without a final answer
            result.status = AgentStatus.MAX_STEPS
            result.final_text = last_text

        if result.status is AgentStatus.RUNNING:
            result.status = AgentStatus.COMPLETED if not result.error else AgentStatus.FAILED
        result.finished_at = time.time()
        if session is not None:
            session.status = result.status
        return result


__all__ = ["AgentEngine", "GenerationLLM", "LLMClient", "AgentLLMError"]
