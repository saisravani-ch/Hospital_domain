from __future__ import annotations

from typing import Any

from src.memory.conversation_memory import ConversationMemory


def get_conversation_history(
    session_id: str,
    memory: ConversationMemory,
    limit: int = 20,
) -> dict[str, Any]:
    """Retrieve recent conversation history for a session."""
    messages = memory.get_messages(session_id)
    return {
        "session_id": session_id,
        "message_count": len(messages),
        "messages": [
            {"role": m["role"], "content": m["content"]}
            for m in messages[-limit:]
        ] if limit else [],
    }


def clear_conversation(
    session_id: str,
    memory: ConversationMemory,
) -> dict[str, Any]:
    """Clear all conversation history for a session."""
    memory.clear(session_id)
    return {"status": "cleared", "session_id": session_id}
