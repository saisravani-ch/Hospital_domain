from __future__ import annotations

from functools import lru_cache
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
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

# Tools that need patient_phone — injected from state (resolved WhatsApp
# identity) so the agent never asks the user for it.
_PHONE_TOOLS = {"book_appointment", "get_my_appointments"}


@lru_cache(1)
def _build_llm_cached():
    return build_llm(temperature=0.3, max_tokens=1024)


async def assistant_node(state: HospitalAgentState) -> dict[str, Any]:
    llm = _build_llm_cached().bind_tools(_BOOKING_TOOLS)
    system = SystemMessage(content=build_system(state, SYSTEM_PROMPT))
    messages = [system] + list(state["messages"])
    response = await llm.ainvoke(messages)
    cid = resolve_booking_client_id(state.get("tenant_id"), state.get("client_id"))
    phone = state.get("patient_phone")
    if isinstance(response, AIMessage) and isinstance(response.tool_calls, list) and (cid or phone):
        patched_calls = []
        for tc in response.tool_calls:
            args = tc.get("args") or {}
            changed = False
            if tc.get("name") in _CLIENT_ID_TOOLS and cid and "client_id" not in args:
                args = {**args, "client_id": cid}
                changed = True
            if (
                tc.get("name") in _PHONE_TOOLS
                and phone
                and not (args.get("patient_phone") or "").strip()
            ):
                args = {**args, "patient_phone": phone}
                changed = True
            if changed:
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
                    # Cancelled: the book_appointment tool never ran, so there is
                    # no ToolMessage for this tool_call. Append one so the LLM never
                    # sees a dangling tool_call (Azure OpenAI rejects those with 400).
                    return {
                        "current_phase": "booking_cancelled",
                        "messages": [
                            ToolMessage(
                                content=(
                                    "The user declined to confirm this appointment, so it was NOT booked. "
                                    "Politely acknowledge the cancellation and ask if you can help with anything else. "
                                    "Do not attempt to book again."
                                ),
                                tool_call_id=tc.get("id"),
                            )
                        ],
                    }
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
