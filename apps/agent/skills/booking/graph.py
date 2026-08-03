from __future__ import annotations

from functools import lru_cache
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from apps.agent.shared import MergingToolNode, build_llm, build_system
from apps.agent.state import HospitalAgentState
from lib.config import resolve_booking_client_id
from apps.agent.skills.booking.prompts import SYSTEM_PROMPT
from apps.agent.skills.booking.tools import (
    check_availability,
    book_appointment,
    reschedule_appointment,
    cancel_appointment,
    get_my_appointments,
)
from apps.agent.skills.shared.doctor_tools import search_doctors, get_doctor_info

_BOOKING_TOOLS = [check_availability, book_appointment, reschedule_appointment, cancel_appointment, get_my_appointments, search_doctors, get_doctor_info]

# Tools whose schema accepts client_id — only these get it injected.
_CLIENT_ID_TOOLS = {
    t.name
    for t in _BOOKING_TOOLS
    if t.args_schema and "client_id" in (t.args_schema.model_fields or {})
}


@lru_cache(1)
def _build_llm_cached():
    return build_llm(temperature=0.3, max_tokens=1024)


async def assistant_node(state: HospitalAgentState) -> dict[str, Any]:
    llm = _build_llm_cached().bind_tools(_BOOKING_TOOLS)
    system = SystemMessage(content=build_system(state, SYSTEM_PROMPT))
    messages = [system] + list(state["messages"])
    response = await llm.ainvoke(messages)
    cid = resolve_booking_client_id(state.get("tenant_id"), state.get("client_id"))
    if isinstance(response, AIMessage) and isinstance(response.tool_calls, list) and cid:
        patched_calls = []
        for tc in response.tool_calls:
            args = tc.get("args") or {}
            if tc.get("name") in _CLIENT_ID_TOOLS and "client_id" not in args:
                args = {**args, "client_id": cid}
                tc = {**tc, "args": args}
            patched_calls.append(tc)
        response = AIMessage(
            content=response.content,
            tool_calls=patched_calls,
            id=response.id,
            response_metadata=response.response_metadata,
            additional_kwargs=response.additional_kwargs,
        )
    return {"messages": [response]}


def human_confirmation_node(state: HospitalAgentState) -> dict[str, Any]:
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.get("name") == "book_appointment":
                    args = tc.get("args", {})
                    msg_text = (
                        f"Please confirm the appointment:\n"
                        f"  Doctor ID: {args.get('doctor_id', 'unknown')}\n"
                        f"  Date: {args.get('date', 'unknown')}\n"
                        f"  Time: {args.get('time', 'unknown')}\n"
                        f"  Phone: {args.get('patient_phone', 'unknown')}\n"
                        f"\nReply 'yes' to confirm or 'no' to cancel."
                    )
                    confirmation = interrupt(msg_text)
                    if confirmation and str(confirmation).strip().lower()[:1] == "y":
                        return {"current_phase": "booking_confirmed"}
                    return {"current_phase": "booking_cancelled"}
    return {}


def should_continue(state: HospitalAgentState) -> str:
    if not state["messages"]:
        return END
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        for tc in last.tool_calls:
            if tc.get("name") == "book_appointment":
                return "human_confirmation"
        return "tools"
    return END


def after_confirmation(state: HospitalAgentState) -> str:
    phase = state.get("current_phase", "")
    if phase == "booking_confirmed":
        return "tools"
    return "assistant"


_booking_tool_node = MergingToolNode(_BOOKING_TOOLS)

_booking_workflow = StateGraph(HospitalAgentState)
_booking_workflow.add_node("assistant", assistant_node)
_booking_workflow.add_node("tools", _booking_tool_node)
_booking_workflow.add_node("human_confirmation", human_confirmation_node)
_booking_workflow.set_entry_point("assistant")
_booking_workflow.add_conditional_edges("assistant", should_continue, {
    "tools": "tools",
    "human_confirmation": "human_confirmation",
    END: END,
})
_booking_workflow.add_edge("tools", "assistant")
_booking_workflow.add_conditional_edges("human_confirmation", after_confirmation, {
    "tools": "tools",
    "assistant": "assistant",
})

booking_graph = _booking_workflow.compile()
