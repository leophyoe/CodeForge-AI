"""In-memory agent task sessions with cancellation support."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from time import time
from typing import Any
from uuid import uuid4

from .models import AgentConfig, AgentResult, AgentStatus


@dataclass
class AgentSession:
    """One agent task: lifecycle state + cancellation flag."""

    id: str
    task: str
    config: AgentConfig
    status: AgentStatus = AgentStatus.RUNNING
    created_at: float = field(default_factory=time)
    result: AgentResult | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)

    @property
    def cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def cancel(self) -> bool:
        if self.status is not AgentStatus.RUNNING:
            return False
        self.cancel_event.set()
        return True

    def summary(self) -> dict[str, Any]:
        return {
            "task_id": self.id,
            "task": self.task,
            "model_id": self.config.model_id,
            "status": self.status.value,
            "steps": len(self.result.steps) if self.result else 0,
            "created_at": self.created_at,
        }


class AgentSessionStore:
    """Thread-safe registry of agent sessions (bounded, evicts finished tasks)."""

    def __init__(self, max_sessions: int = 50) -> None:
        self._sessions: dict[str, AgentSession] = {}
        self._lock = threading.Lock()
        self._max_sessions = max_sessions

    def create(self, task: str, config: AgentConfig) -> AgentSession:
        session = AgentSession(id=uuid4().hex[:12], task=task, config=config)
        with self._lock:
            self._evict_locked()
            self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> AgentSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            sessions = sorted(self._sessions.values(), key=lambda s: s.created_at, reverse=True)
        return [s.summary() for s in sessions[:limit]]

    def remove(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def clear(self) -> int:
        with self._lock:
            count = len(self._sessions)
            self._sessions.clear()
            return count

    def count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def _evict_locked(self) -> None:
        if len(self._sessions) < self._max_sessions:
            return
        finished = [
            session
            for session in self._sessions.values()
            if session.status is not AgentStatus.RUNNING
        ]
        finished.sort(key=lambda s: s.created_at)
        for session in finished:
            if len(self._sessions) < self._max_sessions:
                break
            self._sessions.pop(session.id, None)
