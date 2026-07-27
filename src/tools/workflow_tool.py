from __future__ import annotations

import os
from typing import Any

import httpx

WF_BASE = os.getenv("WF_URL", "http://localhost:8001")


async def check_availability(
    doctor_id: str,
    date: str,
    client_id: str,
) -> dict[str, Any]:
    """Check available appointment slots via workflows HTTP API."""
    try:
        params = {"client_id": client_id, "doctor_id": doctor_id, "date": date}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{WF_BASE}/appointments/availability", params=params)
            resp.raise_for_status()
            data = resp.json()
            return {
                "doctor_id": doctor_id,
                "date": date,
                "slots_available": len(data.get("slots", [])),
                "slots": data.get("slots", []),
            }
    except httpx.HTTPError as e:
        return {"error": str(e)}


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
