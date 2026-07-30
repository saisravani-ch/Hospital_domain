from __future__ import annotations

import json
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode, ToolRuntime
from langgraph.types import Command

from src.orchestrator.graph import build_test_graph
from src.orchestrator._shared import MergingToolNode
from src.orchestrator.skills.booking.graph import (
    after_confirmation,
    human_confirmation_node,
    should_continue as booking_should_continue,
)
from src.orchestrator.skills.search.graph import should_continue as search_should_continue
from src.orchestrator.state import HospitalAgentState
from tests.conftest import MOCK_BOOKING, MOCK_DOCTOR_INFO, MOCK_DOCTORS, MOCK_SLOTS

# ── Mock tools (named to match real tool names so should_continue recognizes them) ──


@tool
async def search_doctors(query: str, runtime: ToolRuntime = None) -> Command:
    """Search for doctors matching the query."""
    return Command(update={
        "search_results": MOCK_DOCTORS,
        "current_phase": "searching",
        "messages": [ToolMessage(content=json.dumps(MOCK_DOCTORS, ensure_ascii=False), tool_call_id=runtime.tool_call_id if runtime else "")],
    })


@tool
async def get_doctor_info(doctor_id: str, runtime: ToolRuntime = None) -> Command:
    """Get detailed info for a doctor by ID."""
    result = MOCK_DOCTOR_INFO if doctor_id == "dr-susan-george" else {"error": "Doctor not found"}
    updates: dict[str, Any] = {
        "current_phase": "selecting" if "error" not in result else "idle",
        "messages": [ToolMessage(content=json.dumps(result, ensure_ascii=False), tool_call_id=runtime.tool_call_id if runtime else "")],
    }
    if "error" not in result:
        updates["selected_doctor_id"] = doctor_id
    return Command(update=updates)


@tool
async def check_availability(doctor_id: str, date: str, date_to: str | None = None, runtime: ToolRuntime = None) -> Command:
    """Check available appointment slots."""
    slots = MOCK_SLOTS * 2 if date_to else MOCK_SLOTS
    result = {"doctor_id": doctor_id, "date": date, "date_to": date_to, "slots_available": len(slots), "slots": slots}
    return Command(update={
        "available_slots": slots,
        "current_phase": "checking",
        "messages": [ToolMessage(content=json.dumps(result, ensure_ascii=False), tool_call_id=runtime.tool_call_id if runtime else "")],
    })


@tool
async def book_appointment(doctor_id: str, patient_phone: str, date: str, time: str, notes: str | None = None, runtime: ToolRuntime = None) -> Command:
    """Book an appointment with a doctor."""
    return Command(update={
        "booking_result": MOCK_BOOKING,
        "current_phase": "done",
        "messages": [ToolMessage(content=json.dumps(MOCK_BOOKING, ensure_ascii=False), tool_call_id=runtime.tool_call_id if runtime else "")],
    })


@tool
async def reschedule_appointment(appointment_id: str, new_date: str, new_time: str, runtime: ToolRuntime = None) -> Command:
    """Reschedule an existing appointment."""
    return Command(update={
        "current_phase": "done",
        "messages": [ToolMessage(content=json.dumps({"status": "rescheduled"}, ensure_ascii=False), tool_call_id=runtime.tool_call_id if runtime else "")],
    })


@tool
async def cancel_appointment(appointment_id: str, runtime: ToolRuntime = None) -> Command:
    """Cancel an existing appointment."""
    return Command(update={
        "current_phase": "done",
        "messages": [ToolMessage(content=json.dumps({"status": "cancelled"}, ensure_ascii=False), tool_call_id=runtime.tool_call_id if runtime else "")],
    })


@tool
async def get_my_appointments(phone: str, runtime: ToolRuntime = None) -> Command:
    """Get appointments by phone number."""
    return Command(update={
        "messages": [ToolMessage(content=json.dumps({"appointments": []}, ensure_ascii=False), tool_call_id=runtime.tool_call_id if runtime else "")],
    })


_SEARCH_MOCK_TOOLS = [search_doctors, get_doctor_info]
_BOOKING_MOCK_TOOLS = [check_availability, book_appointment, reschedule_appointment, cancel_appointment, get_my_appointments]


class MockAssistant:
    """Returns predefined AIMessage responses in sequence."""

    def __init__(self, responses: list[AIMessage]):
        self._responses = responses
        self.call_count = 0

    async def __call__(self, state) -> dict[str, Any]:
        if self.call_count >= len(self._responses):
            return {"messages": [AIMessage(content="I have no more responses programmed.")]}
        resp = self._responses[self.call_count]
        self.call_count += 1
        return {"messages": [resp]}


# ── Router mocks ────────────────────────────────────────────────────────────


async def search_router(state: HospitalAgentState) -> Command:
    return Command(goto="search_skill")


async def booking_router(state: HospitalAgentState) -> Command:
    return Command(goto="booking_skill")


async def both_router(state: HospitalAgentState) -> Command:
    return Command(goto="search_skill")


async def chat_router(state: HospitalAgentState) -> Command:
    return Command(goto="__end__")


# ── Test sub-graph builders ─────────────────────────────────────────────────


def _build_search_test_graph(assistant, tools=None):
    wf = StateGraph(HospitalAgentState)
    wf.add_node("assistant", assistant)
    if tools is None:
        tools = _SEARCH_MOCK_TOOLS
    wf.add_node("tools", MergingToolNode(tools))
    wf.set_entry_point("assistant")
    wf.add_conditional_edges("assistant", search_should_continue, {"tools": "tools", "__end__": "__end__"})
    wf.add_edge("tools", "assistant")
    return wf.compile()


def _build_booking_test_graph(assistant, tools=None):
    wf = StateGraph(HospitalAgentState)
    wf.add_node("assistant", assistant)
    if tools is None:
        tools = _BOOKING_MOCK_TOOLS
    wf.add_node("tools", MergingToolNode(tools))
    wf.add_node("human_confirmation", human_confirmation_node)
    wf.set_entry_point("assistant")
    wf.add_conditional_edges("assistant", booking_should_continue, {"tools": "tools", "human_confirmation": "human_confirmation", "__end__": "__end__"})
    wf.add_edge("tools", "assistant")
    wf.add_conditional_edges("human_confirmation", after_confirmation, {"tools": "tools", "assistant": "assistant"})
    return wf.compile()


def _build_test_graph(router_override, *, search_assistant=None, booking_assistant=None):
    if search_assistant is None:
        search_assistant = MockAssistant([AIMessage(content="Search assistant ready.")])
    if booking_assistant is None:
        booking_assistant = MockAssistant([AIMessage(content="Booking assistant ready.")])
    search_g = _build_search_test_graph(search_assistant)
    booking_g = _build_booking_test_graph(booking_assistant)
    return build_test_graph(router_override=router_override, search_subgraph=search_g, booking_subgraph=booking_g)


def _initial_state(session_id: str = "flow_test") -> dict:
    return {
        "messages": [],
        "session_id": session_id,
        "tenant_id": None,
        "client_id": "gleneagles_001",
        "search_results": [],
        "selected_doctor_id": None,
        "available_slots": [],
        "selected_slot": None,
        "patient_phone": None,
        "booking_result": None,
        "current_phase": "idle",
        "pending_skill": None,
        "user_location": None,
    }


# ── Tests ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_full_search_flow():
    """Router -> search_skill: user asks for a heart doctor, tool runs, assistant responds."""
    responses = [
        AIMessage(content="", tool_calls=[{"name": "search_doctors", "args": {"query": "heart doctor"}, "id": "call_search", "type": "tool_call"}]),
        AIMessage(content="Here are the cardiologists available: Dr Susan George (30 yrs), Dr Gobu P (20 yrs)."),
    ]
    graph = _build_test_graph(search_router, search_assistant=MockAssistant(responses))
    config = {"configurable": {"thread_id": "flow_test_search"}}
    result = await graph.ainvoke({**_initial_state("flow_test_search"), "messages": [HumanMessage(content="I need a heart doctor")]}, config)
    msgs = result.get("messages", [])
    assert any("Susan George" in (m.content or "") for m in msgs)
    assert result["current_phase"] == "searching"
    assert len(result["search_results"]) == 3


@pytest.mark.asyncio
async def test_full_availability_flow():
    """Router -> booking_skill: user checks availability for a specific doctor."""
    responses = [
        AIMessage(content="", tool_calls=[{"name": "check_availability", "args": {"doctor_id": "dr-susan-george", "date": "2026-07-29"}, "id": "call_avail", "type": "tool_call"}]),
        AIMessage(content="Available slots on 2026-07-29: 10:30, 11:00, 14:00."),
    ]
    graph = _build_test_graph(booking_router, booking_assistant=MockAssistant(responses))
    state = _initial_state("flow_test_avail")
    state["search_results"] = MOCK_DOCTORS
    state["current_phase"] = "searching"
    config = {"configurable": {"thread_id": "flow_test_avail"}}
    result = await graph.ainvoke({**state, "messages": [HumanMessage(content="Show me availability for Dr Susan George")]}, config)
    assert len(result["available_slots"]) == 3
    assert result["available_slots"][0]["time"] == "10:30"
    assert result["current_phase"] == "checking"


@pytest.mark.asyncio
async def test_full_booking_flow_with_confirmation():
    """
    Router -> booking_skill: multi-turn booking with human confirmation.
    1. Check availability
    2. Book with human confirmation
    3. Confirm -> booking executes
    """
    responses = [
        AIMessage(content="", tool_calls=[{"name": "check_availability", "args": {"doctor_id": "dr-susan-george", "date": "2026-07-29"}, "id": "call_1", "type": "tool_call"}]),
        AIMessage(content="Available: 10:30, 11:00, 14:00."),
        AIMessage(content="", tool_calls=[{"name": "book_appointment", "args": {"doctor_id": "dr-susan-george", "patient_phone": "+919999999999", "date": "2026-07-29", "time": "10:30"}, "id": "call_2", "type": "tool_call"}]),
        AIMessage(content="Your appointment with Dr Susan George is confirmed! ID: apt_a1b2c3d4"),
    ]
    assistant = MockAssistant(responses)
    graph = _build_test_graph(booking_router, booking_assistant=assistant)
    config = {"configurable": {"thread_id": "flow_test_book"}}
    session = "flow_test_book"

    state = _initial_state(session)
    state["search_results"] = MOCK_DOCTORS
    state["selected_doctor_id"] = "dr-susan-george"
    state["current_phase"] = "searching"

    # Turn 1: Check availability
    r1 = await graph.ainvoke({**state, "messages": [HumanMessage(content="Show me slots for Dr Susan George on 2026-07-29")]}, config)
    assert len(r1["available_slots"]) == 3
    assert assistant.call_count == 2

    # Turn 2: Book (should be intercepted by human_confirmation)
    r2 = await graph.ainvoke({"messages": [HumanMessage(content="Book the 10:30 slot")]}, config)
    snapshot = graph.get_state(config)
    assert snapshot.next  # graph is paused

    # Turn 3: Confirm booking
    r3 = await graph.ainvoke(Command(resume="yes"), config)
    assert r3["booking_result"] is not None
    assert r3["booking_result"]["appointment_id"] == "apt_a1b2c3d4"
    assert r3["current_phase"] == "done"
    assert assistant.call_count == 4


@pytest.mark.asyncio
async def test_date_range_availability():
    """booking_skill: user asks for availability across a date range -> date_to param."""
    responses = [
        AIMessage(content="", tool_calls=[{"name": "check_availability", "args": {"doctor_id": "dr-susan-george", "date": "2026-07-29", "date_to": "2026-07-31"}, "id": "call_range", "type": "tool_call"}]),
        AIMessage(content="Available slots from 2026-07-29 to 2026-07-31: multiple options."),
    ]
    graph = _build_test_graph(booking_router, booking_assistant=MockAssistant(responses))
    state = _initial_state("flow_test_daterange")
    state["search_results"] = MOCK_DOCTORS
    state["current_phase"] = "searching"
    config = {"configurable": {"thread_id": "flow_test_daterange"}}
    result = await graph.ainvoke({**state, "messages": [HumanMessage(content="Show me slots from 29th to 31st July")]}, config)
    assert len(result["available_slots"]) == 6
    assert result["current_phase"] == "checking"


@pytest.mark.asyncio
async def test_concurrent_availability_calls():
    """LLM calls check_availability twice — MergingToolNode prevents crash."""
    responses = [
        AIMessage(content="", tool_calls=[
            {"name": "check_availability", "args": {"doctor_id": "dr-susan-george", "date": "2026-07-29"}, "id": "call_a1", "type": "tool_call"},
            {"name": "check_availability", "args": {"doctor_id": "dr-susan-george", "date": "2026-07-30"}, "id": "call_a2", "type": "tool_call"},
        ]),
        AIMessage(content="Slots on both dates: ..."),
    ]
    graph = _build_test_graph(booking_router, booking_assistant=MockAssistant(responses))
    state = _initial_state("flow_test_concurrent")
    state["search_results"] = MOCK_DOCTORS
    state["current_phase"] = "searching"
    config = {"configurable": {"thread_id": "flow_test_concurrent"}}
    result = await graph.ainvoke({**state, "messages": [HumanMessage(content="Show me slots for July 29 and July 30")]}, config)
    assert len(result["available_slots"]) == 3
    assert result["current_phase"] == "checking"


@pytest.mark.asyncio
async def test_booking_cancelled_by_user():
    """booking_skill: user initiates booking but cancels when asked to confirm."""
    responses = [
        AIMessage(content="", tool_calls=[{"name": "book_appointment", "args": {"doctor_id": "dr-susan-george", "patient_phone": "+919999999999", "date": "2026-07-29", "time": "10:30"}, "id": "call_book", "type": "tool_call"}]),
        AIMessage(content="No problem. Is there anything else I can help you with?"),
    ]
    assistant = MockAssistant(responses)
    graph = _build_test_graph(booking_router, booking_assistant=assistant)
    state = _initial_state("flow_test_cancel")
    state["search_results"] = MOCK_DOCTORS
    state["available_slots"] = MOCK_SLOTS
    state["current_phase"] = "checking"
    config = {"configurable": {"thread_id": "flow_test_cancel"}}
    r1 = await graph.ainvoke({**state, "messages": [HumanMessage(content="Book the 10:30 slot")]}, config)
    snapshot = graph.get_state(config)
    assert snapshot.next  # paused at confirmation
    r2 = await graph.ainvoke(Command(resume="no"), config)
    assert r2["current_phase"] == "booking_cancelled"
    msgs = r2.get("messages", [])
    assert any("else" in (m.content or "") for m in msgs)


@pytest.mark.asyncio
async def test_both_returns_search_skill():
    """Router returns 'both' -> routes to search_skill."""
    result = await both_router({"messages": [HumanMessage(content="Find a heart doctor and book for Tuesday")]})
    assert result.goto == "search_skill"


@pytest.mark.asyncio
async def test_chat_no_skill():
    """Router returns END for simple chat."""
    graph = build_test_graph(router_override=chat_router)
    config = {"configurable": {"thread_id": "flow_test_chat"}}
    result = await graph.ainvoke({**_initial_state("flow_test_chat"), "messages": [HumanMessage(content="Hello!")]}, config)
    assert result.get("current_phase") == "idle"
