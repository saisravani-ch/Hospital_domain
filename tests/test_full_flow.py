"""
Multi-turn conversation flow tests.

Simulates a complete patient journey:
  search -> view doctor -> check availability -> book -> confirm
Uses a mock assistant that returns predefined LLM responses and mock tools.
The graph's routing (should_continue) and human_confirmation nodes run with
real logic -- only the LLM/tool implementations are stubbed.
Tools emit Command(update=...) to update graph state directly.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode, ToolRuntime
from langgraph.types import Command

from src.orchestrator.graph import MergingToolNode, create_graph
from tests.conftest import MOCK_BOOKING, MOCK_DOCTOR_INFO, MOCK_DOCTORS, MOCK_SLOTS


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


@tool
async def search_doctors(
    query: str,
    runtime: ToolRuntime = None,
) -> Command:
    """Search for doctors matching the query."""
    result = {"doctors": MOCK_DOCTORS, "booking_links": []}
    content = json.dumps(result, ensure_ascii=False)
    return Command(update={
        "search_results": MOCK_DOCTORS,
        "current_phase": "searching",
        "messages": [ToolMessage(content=content, tool_call_id=runtime.tool_call_id if runtime else "")],
    })


@tool
async def get_doctor_info(
    doctor_id: str,
    runtime: ToolRuntime = None,
) -> Command:
    """Get detailed info for a doctor by ID."""
    result = MOCK_DOCTOR_INFO if doctor_id == "dr-susan-george" else {"error": "Doctor not found"}
    content = json.dumps(result, ensure_ascii=False)
    updates: dict[str, Any] = {
        "messages": [ToolMessage(content=content, tool_call_id=runtime.tool_call_id if runtime else "")],
    }
    if "error" not in result:
        updates["selected_doctor_id"] = doctor_id
        updates["current_phase"] = "selecting"
    return Command(update=updates)


@tool
async def check_availability(
    doctor_id: str,
    date: str,
    date_to: str | None = None,
    runtime: ToolRuntime = None,
) -> Command:
    """Check available appointment slots."""
    slots = MOCK_SLOTS
    if date_to:
        slots = MOCK_SLOTS * 2  # simulate more slots for a range
    result = {"doctor_id": doctor_id, "date": date, "date_to": date_to, "slots_available": len(slots), "slots": slots}
    content = json.dumps(result, ensure_ascii=False)
    return Command(update={
        "available_slots": slots,
        "current_phase": "checking",
        "messages": [ToolMessage(content=content, tool_call_id=runtime.tool_call_id if runtime else "")],
    })


@tool
async def book_appointment(
    doctor_id: str,
    patient_phone: str,
    date: str,
    time: str,
    notes: str | None = None,
    runtime: ToolRuntime = None,
) -> Command:
    """Book an appointment with a doctor."""
    result = MOCK_BOOKING
    content = json.dumps(result, ensure_ascii=False)
    return Command(update={
        "booking_result": MOCK_BOOKING,
        "current_phase": "done",
        "messages": [ToolMessage(content=content, tool_call_id=runtime.tool_call_id if runtime else "")],
    })


@tool
async def reschedule_appointment(
    appointment_id: str,
    new_date: str,
    new_time: str,
    runtime: ToolRuntime = None,
) -> Command:
    """Reschedule an existing appointment."""
    result = {"status": "rescheduled"}
    content = json.dumps(result, ensure_ascii=False)
    return Command(update={
        "current_phase": "done",
        "messages": [ToolMessage(content=content, tool_call_id=runtime.tool_call_id if runtime else "")],
    })


@tool
async def cancel_appointment(
    appointment_id: str,
    runtime: ToolRuntime = None,
) -> Command:
    """Cancel an existing appointment."""
    result = {"status": "cancelled"}
    content = json.dumps(result, ensure_ascii=False)
    return Command(update={
        "current_phase": "done",
        "messages": [ToolMessage(content=content, tool_call_id=runtime.tool_call_id if runtime else "")],
    })


@pytest.fixture
def mock_tool_node():
    return MergingToolNode([search_doctors, get_doctor_info, check_availability, book_appointment, reschedule_appointment, cancel_appointment])


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
    }


@pytest.mark.asyncio
async def test_full_search_flow(mock_tool_node):
    """User asks for a heart doctor -> agent searches -> presents results."""
    responses = [
        AIMessage(
            content="",
            tool_calls=[{
                "name": "search_doctors",
                "args": {"query": "heart doctor"},
                "id": "call_search",
                "type": "tool_call",
            }],
        ),
        AIMessage(content="Here are the cardiologists available: Dr Susan George (30 yrs), Dr Gobu P (20 yrs)."),
    ]

    graph = create_graph(
        assistant_node_override=MockAssistant(responses),
        tool_node_override=mock_tool_node,
    )

    config = {"configurable": {"thread_id": "flow_test_search"}}
    result = await graph.ainvoke({
        **_initial_state("flow_test_search"),
        "messages": [HumanMessage(content="I need a heart doctor")],
    }, config)

    msgs = result.get("messages", [])
    assert any("Susan George" in (m.content or "") for m in msgs)
    assert result["current_phase"] == "searching"
    assert len(result["search_results"]) == 3


@pytest.mark.asyncio
async def test_full_availability_flow(mock_tool_node):
    """User has results, asks for availability -> agent checks slots."""
    responses = [
        AIMessage(
            content="",
            tool_calls=[{
                "name": "check_availability",
                "args": {"doctor_id": "dr-susan-george", "date": "2026-07-29"},
                "id": "call_avail",
                "type": "tool_call",
            }],
        ),
        AIMessage(content="Available slots on 2026-07-29: 10:30, 11:00, 14:00."),
    ]

    graph = create_graph(
        assistant_node_override=MockAssistant(responses),
        tool_node_override=mock_tool_node,
    )

    state = _initial_state("flow_test_avail")
    state["search_results"] = MOCK_DOCTORS
    state["current_phase"] = "searching"

    config = {"configurable": {"thread_id": "flow_test_avail"}}
    result = await graph.ainvoke({
        **state,
        "messages": [HumanMessage(content="Show me availability for Dr Susan George")],
    }, config)

    assert len(result["available_slots"]) == 3
    assert result["available_slots"][0]["time"] == "10:30"
    assert result["current_phase"] == "checking"


@pytest.mark.asyncio
async def test_full_booking_flow_with_confirmation(mock_tool_node):
    """
    Complete multi-turn booking flow:
    1. Search doctors
    2. Check availability
    3. Book with human confirmation
    4. Confirm -> booking executes
    """
    responses = [
        AIMessage(
            content="",
            tool_calls=[{
                "name": "search_doctors",
                "args": {"query": "cardiologist"},
                "id": "call_1",
                "type": "tool_call",
            }],
        ),
        AIMessage(content="Dr Susan George is a cardiologist with 30 years experience."),
        AIMessage(
            content="",
            tool_calls=[{
                "name": "check_availability",
                "args": {"doctor_id": "dr-susan-george", "date": "2026-07-29"},
                "id": "call_2",
                "type": "tool_call",
            }],
        ),
        AIMessage(content="Available: 10:30, 11:00, 14:00."),
        AIMessage(
            content="",
            tool_calls=[{
                "name": "book_appointment",
                "args": {
                    "doctor_id": "dr-susan-george",
                    "patient_phone": "+919999999999",
                    "date": "2026-07-29",
                    "time": "10:30",
                },
                "id": "call_3",
                "type": "tool_call",
            }],
        ),
        AIMessage(content="Your appointment with Dr Susan George is confirmed! ID: apt_a1b2c3d4"),
    ]

    assistant = MockAssistant(responses)
    graph = create_graph(
        assistant_node_override=assistant,
        tool_node_override=mock_tool_node,
    )

    config = {"configurable": {"thread_id": "flow_test_book"}}
    session = "flow_test_book"

    # Turn 1: Search
    r1 = await graph.ainvoke({**_initial_state(session), "messages": [HumanMessage(content="Find a cardiologist")]}, config)
    assert len(r1["search_results"]) == 3
    assert assistant.call_count == 2

    # Turn 2: Check availability
    r2 = await graph.ainvoke({"messages": [HumanMessage(content="Show me slots for Dr Susan George on 2026-07-29")]}, config)
    assert len(r2["available_slots"]) == 3
    assert assistant.call_count == 4

    # Turn 3: Book (should be intercepted by human_confirmation)
    r3 = await graph.ainvoke({"messages": [HumanMessage(content="Book the 10:30 slot")]}, config)
    assert r3["current_phase"] == "checking"  # set by check_availability tool on turn 2
    snapshot = graph.get_state(config)
    assert snapshot.next  # graph is paused

    # Turn 4: Confirm booking
    r4 = await graph.ainvoke(Command(resume="yes"), config)
    assert r4["booking_result"] is not None
    assert r4["booking_result"]["appointment_id"] == "apt_a1b2c3d4"
    assert r4["current_phase"] == "done"
    assert assistant.call_count == 6


@pytest.mark.asyncio
async def test_date_range_availability(mock_tool_node):
    """User asks for availability across a date range -> agent uses date_to param."""
    responses = [
        AIMessage(
            content="",
            tool_calls=[{
                "name": "check_availability",
                "args": {"doctor_id": "dr-susan-george", "date": "2026-07-29", "date_to": "2026-07-31"},
                "id": "call_range",
                "type": "tool_call",
            }],
        ),
        AIMessage(content="Available slots from 2026-07-29 to 2026-07-31: multiple options."),
    ]

    graph = create_graph(
        assistant_node_override=MockAssistant(responses),
        tool_node_override=mock_tool_node,
    )

    state = _initial_state("flow_test_daterange")
    state["search_results"] = MOCK_DOCTORS
    state["current_phase"] = "searching"

    config = {"configurable": {"thread_id": "flow_test_daterange"}}
    result = await graph.ainvoke({
        **state,
        "messages": [HumanMessage(content="Show me slots from 29th to 31st July")],
    }, config)

    assert len(result["available_slots"]) == 6  # MOCK_SLOTS * 2 (simulated range)
    assert result["current_phase"] == "checking"


@pytest.mark.asyncio
async def test_concurrent_availability_calls(mock_tool_node):
    """LLM calls check_availability twice in one turn — MergingToolNode prevents crash."""
    responses = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "check_availability",
                    "args": {"doctor_id": "dr-susan-george", "date": "2026-07-29"},
                    "id": "call_a1",
                    "type": "tool_call",
                },
                {
                    "name": "check_availability",
                    "args": {"doctor_id": "dr-susan-george", "date": "2026-07-30"},
                    "id": "call_a2",
                    "type": "tool_call",
                },
            ],
        ),
        AIMessage(content="Slots on both dates: ..."),
    ]

    graph = create_graph(
        assistant_node_override=MockAssistant(responses),
        tool_node_override=mock_tool_node,
    )

    state = _initial_state("flow_test_concurrent")
    state["search_results"] = MOCK_DOCTORS
    state["current_phase"] = "searching"

    config = {"configurable": {"thread_id": "flow_test_concurrent"}}
    result = await graph.ainvoke({
        **state,
        "messages": [HumanMessage(content="Show me slots for July 29 and July 30")],
    }, config)

    # Should NOT crash with InvalidUpdateError
    assert len(result["available_slots"]) == 3  # last-write-wins → one date's slots
    assert result["current_phase"] == "checking"


@pytest.mark.asyncio
async def test_booking_cancelled_by_user(mock_tool_node):
    """User initiates booking but then cancels when asked to confirm."""
    responses = [
        AIMessage(
            content="",
            tool_calls=[{
                "name": "book_appointment",
                "args": {
                    "doctor_id": "dr-susan-george",
                    "patient_phone": "+919999999999",
                    "date": "2026-07-29",
                    "time": "10:30",
                },
                "id": "call_book",
                "type": "tool_call",
            }],
        ),
        AIMessage(content="No problem. Is there anything else I can help you with?"),
    ]

    assistant = MockAssistant(responses)
    graph = create_graph(
        assistant_node_override=assistant,
        tool_node_override=mock_tool_node,
    )

    state = _initial_state("flow_test_cancel")
    state["search_results"] = MOCK_DOCTORS
    state["available_slots"] = MOCK_SLOTS
    state["current_phase"] = "checking"

    config = {"configurable": {"thread_id": "flow_test_cancel"}}

    # Initiate booking
    r1 = await graph.ainvoke({**state, "messages": [HumanMessage(content="Book the 10:30 slot")]}, config)
    snapshot = graph.get_state(config)
    assert snapshot.next  # paused at confirmation

    # User says no
    r2 = await graph.ainvoke(Command(resume="no"), config)
    assert r2["current_phase"] == "booking_cancelled"
    msgs = r2.get("messages", [])
    assert any("else" in (m.content or "") for m in msgs)
