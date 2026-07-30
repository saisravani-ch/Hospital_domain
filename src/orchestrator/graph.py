from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import Any, Literal

from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import SystemMessage
from langchain_openai import AzureChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command
from loguru import logger
from pydantic import BaseModel

from src.config import get_settings
from src.orchestrator._shared import build_llm, get_tenant_config
from src.orchestrator.skills.search.graph import search_graph
from src.orchestrator.skills.booking.graph import booking_graph
from src.orchestrator.state import HospitalAgentState

settings = get_settings()

_CHAT_PROMPT = ("You are a friendly assistant for {brand_name}. "
                "Respond warmly to greetings, thanks, and casual conversation. "
                "Keep it brief and helpful. Do NOT offer medical advice.")


class RouterOutput(BaseModel):
    skill: Literal["search", "booking", "both", "chat"]
    reason: str = ""


_ROUTER_PROMPT = """You are a router for a hospital assistant system. Classify the user's latest message.

- "search" — User wants to find a doctor, describe symptoms, ask about specialties/conditions, or get doctor info
- "booking" — User wants to check availability, book, reschedule, or cancel an appointment
- "both" — User's request spans both search AND booking (e.g. "find a cardiologist and book for Tuesday")
- "chat" — Greetings, thanks, simple conversation, or anything not requiring a tool

IMPORTANT — Pending skill: {pending_context}
If the user's message is selecting a doctor, confirming details, or continuing the pending flow, route to "booking".
If the user starts a completely new request (e.g. new search topic, unrelated question), ignore the pending skill and classify normally.

Respond with ONLY the appropriate skill name and a brief reason."""


@lru_cache(1)
def _build_router_llm() -> AzureChatOpenAI:
    return AzureChatOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        deployment_name=settings.azure_openai_deployment_name,
        temperature=0,
        max_tokens=256,
    ).with_structured_output(RouterOutput)


async def router_node(state: HospitalAgentState) -> Command:
    msgs = state.get("messages", [])
    if not msgs:
        return Command(goto=END)

    last = msgs[-1]
    content = last.content if hasattr(last, "content") else str(last)

    if not content.strip():
        return Command(goto=END)

    pending = state.get("pending_skill")
    pending_context = f"There is a pending booking skill. The user was previously shown doctor search results and asked to pick one." if pending else "None."

    llm = _build_router_llm()
    system = SystemMessage(content=_ROUTER_PROMPT.format(pending_context=pending_context))
    history = list(msgs)[-4:]
    try:
        result: RouterOutput = await llm.ainvoke([system] + history)
        skill = result.skill
    except Exception as e:
        logger.warning(f"Router failed ({e}), defaulting to chat")
        skill = "chat"

    if skill == "both":
        return Command(goto="search_skill", update={"pending_skill": "booking_skill"})
    elif skill == "booking":
        return Command(goto="booking_skill", update={"pending_skill": None})
    elif skill == "search":
        return Command(goto="search_skill", update={"pending_skill": None})
    return Command(goto="chat_skill", update={"pending_skill": None})


@lru_cache(1)
def _build_chat_llm():
    return build_llm(temperature=0.7, max_tokens=256)


async def chat_node(state: HospitalAgentState) -> dict[str, Any]:
    llm = _build_chat_llm()
    tc = get_tenant_config(state.get("tenant_id"))
    prompt = tc.format(_CHAT_PROMPT)
    prompt += f"\nToday's date: {date.today().isoformat()}"
    system = SystemMessage(content=prompt)
    messages = [system] + list(state["messages"])
    response = await llm.ainvoke(messages)
    return {"messages": [response]}


workflow = StateGraph(HospitalAgentState)

workflow.add_node("router", router_node)
workflow.add_node("search_skill", search_graph)
workflow.add_node("booking_skill", booking_graph)
workflow.add_node("chat_skill", chat_node)

workflow.set_entry_point("router")

workflow.add_edge("search_skill", END)
workflow.add_edge("booking_skill", END)
workflow.add_edge("chat_skill", END)

graph = workflow.compile(checkpointer=MemorySaver())


def build_test_graph(
    *,
    router_override=None,
    search_subgraph=None,
    booking_subgraph=None,
) -> Any:
    wf = StateGraph(HospitalAgentState)
    wf.add_node("router", router_override or router_node)
    wf.add_node("search_skill", search_subgraph or search_graph)
    wf.add_node("booking_skill", booking_subgraph or booking_graph)
    wf.add_node("chat_skill", chat_node)
    wf.set_entry_point("router")
    wf.add_edge("search_skill", END)
    wf.add_edge("booking_skill", END)
    wf.add_edge("chat_skill", END)
    return wf.compile(checkpointer=MemorySaver())
