from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from src.knowledge_base.config import get_settings

settings = get_settings()

# ── FSM states stored per session in a simple dict ──────────────────────────
# BookingFsmState: { intent, doctor_id, date, time, phone, client_id,
#                     slots_shown, step }

_STORE: dict[str, dict[str, Any]] = {}


def get_fsm(session_id: str) -> dict[str, Any]:
    return _STORE.setdefault(session_id, {"step": "idle"})


def clear_fsm(session_id: str) -> None:
    _STORE.pop(session_id, None)


_EXTRACT_SYSTEM = """You are a booking intent parser. Extract booking details from the user message.
Return ONLY a JSON object with these fields (all nullable):
- "intent" ("book" | "reschedule" | "cancel" | "check" | null)
- "doctor_id" (str or null): doctor ID if mentioned
- "doctor_name" (str or null): doctor name if mentioned
- "date" (str or null): date in YYYY-MM-DD format
- "time" (str or null): time in HH:MM format
- "patient_phone" (str or null)
- "appointment_id" (str or null): for reschedule/cancel
- "client_id" (str or null)
- "missing_info" (list[str]): fields the user still needs to provide"""


async def _extract_intent(llm, message: str) -> dict[str, Any]:
    """Single LLM call to extract booking intent and entities."""
    try:
        resp = await llm.chat.completions.create(
            model=settings.azure_openai_deployment_name,
            messages=[
                {"role": "system", "content": _EXTRACT_SYSTEM},
                {"role": "user", "content": message},
            ],
            max_tokens=300,
            temperature=0.0,
        )
        raw = resp.choices[0].message.content or ""
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"Booking LLM parse error: {e}")
        return {"intent": None, "missing_info": []}


async def execute_booking(
    llm,
    tool_map: dict[str, callable],
    message: str,
    session_id: str,
    tenant_id: str | None = None,
    client_id: str | None = None,
) -> str:
    """Booking FSM: extract → check → confirm → book."""
    fsm = get_fsm(session_id)

    # Extract intent and entities from the current message
    entities = await _extract_intent(llm, message)
    intent = entities.get("intent") or fsm.get("intent")

    if not intent:
        return "I can help you book, reschedule, or cancel an appointment. What would you like to do?"

    # Merge FSM state with new entities
    for key in ("doctor_id", "doctor_name", "date", "time", "patient_phone", "appointment_id", "client_id"):
        if entities.get(key):
            fsm[key] = entities[key]
    fsm["intent"] = intent

    if client_id and not fsm.get("client_id"):
        fsm["client_id"] = client_id

    # ── Cancel: deterministic, no FSM needed ──────────────────────────
    if intent == "cancel":
        missing = _missing(fsm, ["appointment_id", "client_id"])
        if missing:
            return f"To cancel, I need: {', '.join(missing)}."
        result = await tool_map["cancel_appointment"](
            appointment_id=fsm["appointment_id"], client_id=fsm["client_id"])
        clear_fsm(session_id)
        if "error" in result:
            return f"Could not cancel: {result['error']}"
        return f"Appointment {fsm['appointment_id']} has been cancelled."

    # ── Reschedule: deterministic, no FSM needed ──────────────────────
    if intent == "reschedule":
        missing = _missing(fsm, ["appointment_id", "new_date", "new_time", "client_id"])
        if missing:
            return f"To reschedule, I need: {', '.join(missing)}."
        result = await tool_map["reschedule_appointment"](
            appointment_id=fsm["appointment_id"],
            new_date=entities.get("new_date", fsm.get("new_date", fsm.get("date"))),
            new_time=entities.get("new_time", fsm.get("new_time", fsm.get("time"))),
            client_id=fsm["client_id"],
        )
        clear_fsm(session_id)
        if "error" in result:
            return f"Could not reschedule: {result['error']}"
        return f"Your appointment has been rescheduled."

    # ── Book: multi-step FSM ──────────────────────────────────────────
    if intent == "book":
        return await _handle_book(llm, tool_map, message, fsm, session_id)

    return "I'm not sure what you'd like to do. Would you like to book, reschedule, or cancel an appointment?"


async def _handle_book(llm, tool_map, message: str, fsm: dict, session_id: str) -> str:
    # Step 1: Collect required info
    required = ["doctor_id", "date", "time", "patient_phone", "client_id"]
    missing = _missing(fsm, required)
    if missing:
        # Check if we need doctor_id and have doctor_name instead — search for it
        if "doctor_id" in missing and fsm.get("doctor_name") and not fsm.get("doctor_id"):
            search_fn = tool_map.get("search_doctors")
            if search_fn:
                result = await search_fn(query=fsm["doctor_name"])
                docs = result if isinstance(result, list) else result.get("results", [])
                if docs:
                    fsm["doctor_id"] = docs[0].get("id") or docs[0].get("doctor_id", "")
                    missing.remove("doctor_id")
        if missing:
            return f"To book, I need: {', '.join(missing)}. Please provide them."

    # Step 2: Check availability
    if fsm.get("step") in ("idle", "collected"):
        fsm["step"] = "checking"
        result = await tool_map["check_availability"](
            doctor_id=fsm["doctor_id"], date=fsm["date"], client_id=fsm["client_id"])
        if "error" in result:
            return f"Could not check availability: {result['error']}"
        slots = result.get("slots", [])
        if not slots:
            return f"No available slots on {fsm['date']} for that doctor. Try a different date."
        fsm["slots"] = [s["time"] for s in slots if isinstance(s, dict)]
        fsm["step"] = "awaiting_confirmation"
        times = ", ".join(fsm["slots"][:5])
        return (f"Available slots on {fsm['date']}: {times}. "
                f"Shall I book {fsm['time']} or would you like a different time?")

    # Step 3: Awaiting confirmation — user has confirmed
    if fsm.get("step") == "awaiting_confirmation":
        result = await tool_map["book_appointment"](
            doctor_id=fsm["doctor_id"],
            patient_phone=fsm["patient_phone"],
            date=fsm["date"],
            time=fsm["time"],
            client_id=fsm["client_id"],
        )
        clear_fsm(session_id)
        if "error" in result:
            return f"Could not book: {result['error']}"
        apt_id = result.get("appointment_id", result.get("id", ""))
        return f"Appointment confirmed! Your booking reference is {apt_id}."

    return "Let me know your preferred time and I'll book it for you."


def _missing(fsm: dict, fields: list[str]) -> list[str]:
    return [f for f in fields if not fsm.get(f)]
