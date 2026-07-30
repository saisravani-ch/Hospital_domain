from __future__ import annotations

import json
from typing import Annotated, Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from src.tools import workflow_tool


@tool
async def get_my_appointments(
    patient_phone: str,
    _state: Annotated[dict, InjectedState] = None,
    runtime: ToolRuntime = None,
) -> Command:
    """Look up existing appointments for a patient by their phone number.
    The client_id is automatically determined from your session — you do not need to provide it."""
    cid = (_state or {}).get("client_id")
    if not cid:
        return Command(update={"messages": [ToolMessage(content='{"error": "Client ID not set. Cannot look up appointments."}', tool_call_id=runtime.tool_call_id if runtime else "")]})
    result = await workflow_tool.get_appointments_by_phone(patient_phone, cid)
    try:
        content = json.dumps(result, ensure_ascii=False)
    except Exception:
        content = str(result)
    updates: dict[str, Any] = {
        "messages": [ToolMessage(content=content, tool_call_id=runtime.tool_call_id if runtime else "")]
    }
    if "error" not in result:
        updates["current_phase"] = "checking"
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
    """Check available appointment slots for a doctor. Only needs doctor_id and date.

    For a single date use *date* only. For a date range provide both
    *date* (start) and *date_to* (end, inclusive).
    Does NOT need a phone number — it is NOT required for availability checks.
    The client_id is automatically determined from your session if not provided."""
    cid = client_id or (_state or {}).get("client_id")
    if not cid:
        return Command(update={"messages": [ToolMessage(content='{"error": "Client ID not set."}', tool_call_id=runtime.tool_call_id if runtime else "")]})
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
    """Book an appointment with a doctor at a specific date and time.
    The client_id is automatically determined from your session if not provided."""
    cid = client_id or (_state or {}).get("client_id")
    if not cid:
        return Command(update={"messages": [ToolMessage(content='{"error": "Client ID not set."}', tool_call_id=runtime.tool_call_id if runtime else "")]})
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
    """Reschedule an existing appointment to a new date and time.
    The client_id is automatically determined from your session if not provided."""
    cid = client_id or (_state or {}).get("client_id")
    if not cid:
        return Command(update={"messages": [ToolMessage(content='{"error": "Client ID not set."}', tool_call_id=runtime.tool_call_id if runtime else "")]})
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
    """Cancel an existing appointment.
    The client_id is automatically determined from your session if not provided."""
    cid = client_id or (_state or {}).get("client_id")
    if not cid:
        return Command(update={"messages": [ToolMessage(content='{"error": "Client ID not set."}', tool_call_id=runtime.tool_call_id if runtime else "")]})
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
