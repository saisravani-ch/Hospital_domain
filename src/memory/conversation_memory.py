from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import Conversation, Message


class ConversationMemory:
    """In-memory conversation store. No external dependencies needed."""

    def __init__(self):
        self._sessions: dict[str, Conversation] = {}

    def get_or_create(self, session_id: str, tenant_id: str | None = None, client_id: str | None = None) -> Conversation:
        if session_id not in self._sessions:
            self._sessions[session_id] = Conversation(
                id=session_id,
                tenant_id=tenant_id,
                client_id=client_id or "",
            )
        return self._sessions[session_id]

    def get(self, session_id: str) -> Conversation | None:
        return self._sessions.get(session_id)

    def add_message(self, session_id: str, role: str, content: str, **kwargs: Any) -> Message:
        conv = self.get_or_create(session_id)
        msg = Message(role=role, content=content, **kwargs)
        conv.messages.append(msg)
        conv.updated_at = datetime.now(timezone.utc).isoformat()
        return msg

    def get_messages(self, session_id: str) -> list[dict]:
        conv = self.get(session_id)
        if not conv:
            return []
        return [m.model_dump(exclude={"timestamp"}) for m in conv.messages]

    def clear(self, session_id: str) -> None:
        if session_id in self._sessions:
            del self._sessions[session_id]
