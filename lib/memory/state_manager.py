from __future__ import annotations

from typing import Any

from .conversation_memory import ConversationMemory
from .models import AgentState, Message


class StateManager:
    """Manages AgentState lifecycle - load, save, update."""

    def __init__(self, memory: ConversationMemory):
        self._memory = memory

    def load(self, session_id: str, tenant_id: str | None = None, client_id: str | None = None) -> AgentState:
        conv = self._memory.get_or_create(session_id, tenant_id, client_id)
        raw_messages = [m.model_dump(exclude={"timestamp"}) for m in conv.messages]
        return AgentState(
            messages=raw_messages,
            session_id=session_id,
            tenant_id=tenant_id or conv.tenant_id,
            client_id=client_id or conv.client_id,
        )

    def save(self, state: AgentState) -> None:
        conv = self._memory.get_or_create(state.session_id, state.tenant_id, state.client_id)
        conv.messages = [
            Message(**m) for m in state.messages
        ]
