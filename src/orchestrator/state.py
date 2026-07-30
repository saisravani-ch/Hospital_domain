from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class HospitalAgentState(TypedDict):
    messages: Annotated[list, add_messages]

    session_id: str
    tenant_id: str | None
    client_id: str | None

    search_results: list[dict]
    selected_doctor_id: str | None
    available_slots: list[dict]
    selected_slot: dict | None
    patient_phone: str | None
    booking_result: dict | None

    current_phase: str
    pending_skill: str | None
    user_location: str | None
