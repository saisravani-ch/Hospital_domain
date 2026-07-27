"""
FastAPI application entry point for the Hospital Conversation Agent.
Routes user queries to RAG (knowledge discovery) or workflow (booking) tools.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel

from src.orchestrator.agent import Agent
from src.orchestrator.dependencies import (
    get_graphrag_engine,
    get_graph_engine,
    get_llm_client,
    get_memory,
)
from src.orchestrator.tools import build_tool_map

_agent: Agent | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _agent
    logger.info("Starting Hospital Conversation Agent API...")
    llm = get_llm_client()
    graphrag = await get_graphrag_engine()
    graph = await get_graph_engine()
    memory = get_memory()
    if llm is None:
        logger.warning("LLM client unavailable — agent will return fallback responses")
    tool_map = build_tool_map(graphrag, graph, memory)
    _agent = Agent(llm, tool_map)
    yield
    logger.info("Shutting down Conversation Agent API.")


app = FastAPI(
    title="Hospital Conversation Agent API",
    description=(
        "AI-powered conversation agent that routes user queries to "
        "RAG (doctor knowledge) or workflow (appointment booking) tools."
    ),
    version="1.0.0",
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


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> dict[str, Any]:
    """Main conversational endpoint. Routes user queries to RAG/workflow tools."""
    if _agent is None:
        return {"response": "Agent not initialized. Try again shortly.", "session_id": req.session_id or ""}

    session_id = req.session_id or f"session_{__import__('uuid').uuid4().hex[:8]}"
    memory = get_memory()
    memory.get_or_create(session_id, req.tenant_id, req.client_id)

    # Load history and append new message
    history = memory.get_messages(session_id)
    history.append({"role": "user", "content": req.message})

    # Run agent
    updated = await _agent.run(history, tenant_id=req.tenant_id)

    # Save only user + assistant messages (tool calls are ephemeral per turn)
    memory.clear(session_id)
    for m in updated:
        if m["role"] in ("user", "assistant"):
            memory.add_message(session_id, m["role"], m.get("content") or "")

    # Last assistant message is the response
    assistant_msgs = [m for m in updated if m["role"] == "assistant"]
    response = assistant_msgs[-1]["content"] if assistant_msgs else ""

    return {"response": response, "session_id": session_id}


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
