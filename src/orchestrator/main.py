"""
FastAPI entry point for the Hospital Conversation Agent.
LangGraph stateful agent that searches doctors and manages bookings via downstream services.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from loguru import logger
from pydantic import BaseModel

from src.orchestrator.graph import graph as agent_graph

_graph: Any = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graph
    logger.info("Starting Hospital Conversation Agent API...")
    _graph = agent_graph
    yield
    logger.info("Shutting down Conversation Agent API.")


app = FastAPI(
    title="Hospital Conversation Agent API",
    description="LangGraph stateful agent for doctor search and appointment booking.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    tenant_id: str | None = None
    client_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    status: str = "completed"


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> dict[str, Any]:
    if _graph is None:
        return {"response": "Agent not initialized. Try again shortly.", "session_id": req.session_id or ""}

    session_id = req.session_id or f"session_{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": session_id}}

    snapshot = _graph.get_state(config)
    is_resume = bool(snapshot.next)

    if is_resume:
        result = await _graph.ainvoke(Command(resume=req.message), config)
    else:
        existing = list(snapshot.values.get("messages", [])) if snapshot.values else []
        first_call = not existing and snapshot.next is None and not (snapshot.values or {}).get("messages")

        if first_call:
            result = await _graph.ainvoke(
                {
                    "messages": [HumanMessage(content=req.message)],
                    "session_id": session_id,
                    "tenant_id": req.tenant_id,
                    "client_id": req.client_id,
                    "search_results": [],
                    "selected_doctor_id": None,
                    "available_slots": [],
                    "selected_slot": None,
                    "patient_phone": None,
                    "booking_result": None,
                    "current_phase": "idle",
                    "pending_skill": None,
                    "user_location": None,
                },
                config,
            )
        else:
            result = await _graph.ainvoke({"messages": [HumanMessage(content=req.message)]}, config)

    snapshot = _graph.get_state(config)
    has_pending = bool(snapshot.next)
    msgs = result.get("messages", [])
    last = msgs[-1] if msgs else None
    content = last.content if hasattr(last, "content") else str(last or "")

    return ChatResponse(
        response=content,
        session_id=session_id,
        status="pending_confirmation" if has_pending else "completed",
    )


@app.get("/", tags=["health"])
async def root() -> dict[str, Any]:
    return {
        "service": "Hospital Conversation Agent",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
