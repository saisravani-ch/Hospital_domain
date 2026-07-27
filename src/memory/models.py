from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str  # system | user | assistant | tool
    content: str
    tool_call_id: str | None = None
    tool_calls: list[dict] | None = None
    name: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Conversation(BaseModel):
    id: str
    tenant_id: str | None = None
    client_id: str = ""
    messages: list[Message] = []
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AgentState(BaseModel):
    messages: list[dict]  # raw OpenAI-format messages
    session_id: str
    tenant_id: str | None = None
    client_id: str = ""
