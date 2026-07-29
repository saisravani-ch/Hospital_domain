from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

import httpx

WF_BASE = os.getenv("WF_URL", "http://localhost:8001")


async def _fetch_slots(doctor_id: str, d: str, client_id: str) -> list[dict] | None:
    """Fetch slots for a single date; returns None on error."""
    try:
        params = {"client_id": client_id, "doctor_id": doctor_id, "date": d}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{WF_BASE}/appointments/availability", params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get("slots", [])
    except httpx.HTTPError:
        return None


async def check_availability(
    doctor_id: str,
    date: str,
    client_id: str,
    date_to: str | None = None,
) -> dict[str, Any]:
    """Check available appointment slots via workflows HTTP API.

    If *date_to* is provided, aggregates slots across that date range.
    """
    dates = _date_range(date, date_to) if date_to else [date]

    all_slots: list[dict] = []
    date_slot_counts: dict[str, int] = {}

    for d in dates:
        slots = await _fetch_slots(doctor_id, d, client_id)
        if slots is None:
            continue
        n = len(slots)
        if n:
            all_slots.extend(slots)
            date_slot_counts[d] = n

    return {
        "doctor_id": doctor_id,
        "date": date,
        "date_to": date_to,
        "slots_available": len(all_slots),
        "slots": all_slots,
        "slots_by_date": date_slot_counts,
    }


def _date_range(start: str, end: str) -> list[str]:
    from_d = date.fromisoformat(start)
    to_d = date.fromisoformat(end)
    if to_d < from_d:
        return [start]
    return [
        (from_d + timedelta(days=i)).isoformat()
        for i in range((to_d - from_d).days + 1)
    ]


async def book_appointment(
    doctor_id: str,
    patient_phone: str,
    date: str,
    time: str,
    client_id: str,
    notes: str | None = None,
) -> dict[str, Any]:
    """Book an appointment via workflows HTTP API."""
    try:
        body = {
            "client_id": client_id,
            "patient_phone": patient_phone,
            "doctor_id": doctor_id,
            "date": date,
            "time": time,
        }
        if notes:
            body["notes"] = notes
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(f"{WF_BASE}/appointments/book", json=body)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        return {"error": str(e)}


async def reschedule_appointment(
    appointment_id: str,
    new_date: str,
    new_time: str,
    client_id: str,
) -> dict[str, Any]:
    """Reschedule an appointment via workflows HTTP API."""
    try:
        body = {
            "client_id": client_id,
            "appointment_id": appointment_id,
            "new_date": new_date,
            "new_time": new_time,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(f"{WF_BASE}/appointments/reschedule", json=body)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        return {"error": str(e)}


async def cancel_appointment(
    appointment_id: str,
    client_id: str,
) -> dict[str, Any]:
    """Cancel an appointment via workflows HTTP API."""
    try:
        body = {
            "client_id": client_id,
            "appointment_id": appointment_id,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(f"{WF_BASE}/appointments/cancel", json=body)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        return {"error": str(e)}
