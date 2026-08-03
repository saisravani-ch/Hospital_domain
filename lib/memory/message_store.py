from __future__ import annotations

from typing import Any

from .conversation_memory import ConversationMemory
from .models import Message


class MessageStore:
    """Thin CRUD wrapper over ConversationMemory."""

    def __init__(self, memory: ConversationMemory):
        self._memory = memory

    def save(self, session_id: str, role: str, content: str, **kwargs: Any) -> Message:
        return self._memory.add_message(session_id, role, content, **kwargs)

    def get_history(self, session_id: str) -> list[dict]:
        return self._memory.get_messages(session_id)

    def clear_history(self, session_id: str) -> None:
        self._memory.clear(session_id)
