"""Agent engine errors."""

from __future__ import annotations


class AgentError(Exception):
    """Base error for the agent engine."""

    def __init__(self, message: str, code: str = "agent_error") -> None:
        super().__init__(message)
        self.code = code

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": str(self)}


class AgentLLMError(AgentError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="llm_error")


class AgentConfigError(AgentError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="agent_config_error")


class AgentCancelledError(AgentError):
    def __init__(self, task_id: str) -> None:
        super().__init__(f"Agent task cancelled: {task_id}", code="cancelled")
