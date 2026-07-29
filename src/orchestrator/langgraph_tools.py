from __future__ import annotations

import json
from typing import Annotated, Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from src.tools import graphrag_tool, workflow_tool


@tool
async def search_doctors(
    query: str,
    specialization: str | None = None,
    doctor_name: str | None = None,
    language: str | None = None,
    min_experience: int | None = None,
    _state: Annotated[dict, InjectedState] = None,
    runtime: ToolRuntime = None,
) -> Command:
    """Search for doctors by specialty, symptoms, condition, doctor name, or natural language query."""
    tenant_id = (_state or {}).get("tenant_id")
    result = await graphrag_tool.search_doctors(
        query, tenant_id=tenant_id, specialization=specialization,
        doctor_name=doctor_name, language=language, min_experience=min_experience,
    )
    try:
        content = json.dumps(result, ensure_ascii=False)
    except Exception:
        content = str(result)
    updates: dict[str, Any] = {
        "messages": [ToolMessage(content=content, tool_call_id=runtime.tool_call_id if runtime else "")]
    }
    docs = result.get("doctors", [])
    if docs:
        updates["search_results"] = docs
        updates["current_phase"] = "searching"
    return Command(update=updates)


@tool
async def get_doctor_info(
    doctor_id: str,
    _state: Annotated[dict, InjectedState] = None,
    runtime: ToolRuntime = None,
) -> Command:
    """Get detailed information about a specific doctor by their ID."""
    tenant_id = (_state or {}).get("tenant_id")
    result = await graphrag_tool.get_doctor_info(doctor_id, tenant_id=tenant_id)
    try:
        content = json.dumps(result, ensure_ascii=False)
    except Exception:
        content = str(result)
    updates: dict[str, Any] = {
        "messages": [ToolMessage(content=content, tool_call_id=runtime.tool_call_id if runtime else "")]
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
    client_id: str | None = None,
    _state: Annotated[dict, InjectedState] = None,
    runtime: ToolRuntime = None,
) -> Command:
    """Check available appointment slots for a doctor.

    For a single date use *date* only. For a date range provide both
    *date* (start) and *date_to* (end, inclusive).
    """
    cid = client_id or (_state or {}).get("client_id", "gleneagles_001")
    result = await workflow_tool.check_availability(doctor_id, date, cid, date_to=date_to)
    try:
        content = json.dumps(result, ensure_ascii=False)
    except Exception:
        content = str(result)
    updates: dict[str, Any] = {
        "messages": [ToolMessage(content=content, tool_call_id=runtime.tool_call_id if runtime else "")]
    }
    slots = result.get("slots", [])
    if slots:
        updates["available_slots"] = slots
        updates["current_phase"] = "checking"
    return Command(update=updates)


@tool
async def book_appointment(
    doctor_id: str,
    patient_phone: str,
    date: str,
    time: str,
    client_id: str | None = None,
    notes: str | None = None,
    _state: Annotated[dict, InjectedState] = None,
    runtime: ToolRuntime = None,
) -> Command:
    """Book an appointment with a doctor at a specific date and time."""
    cid = client_id or (_state or {}).get("client_id", "gleneagles_001")
    result = await workflow_tool.book_appointment(doctor_id, patient_phone, date, time, cid, notes)
    try:
        content = json.dumps(result, ensure_ascii=False)
    except Exception:
        content = str(result)
    updates: dict[str, Any] = {
        "messages": [ToolMessage(content=content, tool_call_id=runtime.tool_call_id if runtime else "")]
    }
    if "error" not in result:
        updates["booking_result"] = result
        updates["current_phase"] = "done"
    return Command(update=updates)


@tool
async def reschedule_appointment(
    appointment_id: str,
    new_date: str,
    new_time: str,
    client_id: str | None = None,
    _state: Annotated[dict, InjectedState] = None,
    runtime: ToolRuntime = None,
) -> Command:
    """Reschedule an existing appointment to a new date and time."""
    cid = client_id or (_state or {}).get("client_id", "gleneagles_001")
    result = await workflow_tool.reschedule_appointment(appointment_id, new_date, new_time, cid)
    try:
        content = json.dumps(result, ensure_ascii=False)
    except Exception:
        content = str(result)
    updates: dict[str, Any] = {
        "messages": [ToolMessage(content=content, tool_call_id=runtime.tool_call_id if runtime else "")]
    }
    if "error" not in result:
        updates["current_phase"] = "done"
    return Command(update=updates)


@tool
async def cancel_appointment(
    appointment_id: str,
    client_id: str | None = None,
    _state: Annotated[dict, InjectedState] = None,
    runtime: ToolRuntime = None,
) -> Command:
    """Cancel an existing appointment."""
    cid = client_id or (_state or {}).get("client_id", "gleneagles_001")
    result = await workflow_tool.cancel_appointment(appointment_id, cid)
    try:
        content = json.dumps(result, ensure_ascii=False)
    except Exception:
        content = str(result)
    updates: dict[str, Any] = {
        "messages": [ToolMessage(content=content, tool_call_id=runtime.tool_call_id if runtime else "")]
    }
    if "error" not in result:
        updates["current_phase"] = "done"
    return Command(update=updates)
