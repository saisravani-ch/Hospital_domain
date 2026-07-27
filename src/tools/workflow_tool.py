from __future__ import annotations

import asyncio
from typing import Any

from src.workflows.services.booking_service import AppointmentBookingService


def _get_service(client_id: str) -> AppointmentBookingService:
    return AppointmentBookingService(client_id)


async def check_availability(
    doctor_id: str,
    date: str,
    client_id: str = "gleneagles_001",
) -> dict[str, Any]:
    """Check available appointment slots for a doctor on a given date."""
    service = _get_service(client_id)
    try:
        slots = await asyncio.to_thread(service.get_availability, doctor_id, date)
        return {"doctor_id": doctor_id, "date": date, "slots_available": len(slots), "slots": slots}
    except ValueError as e:
        return {"error": str(e)}


async def book_appointment(
    doctor_id: str,
    patient_phone: str,
    date: str,
    time: str,
    client_id: str = "gleneagles_001",
    notes: str | None = None,
) -> dict[str, Any]:
    """Book an appointment with a doctor at a specific date and time."""
    service = _get_service(client_id)
    try:
        result = await asyncio.to_thread(service.book, patient_phone, doctor_id, date, time, notes)
        return result
    except ValueError as e:
        return {"error": str(e)}


async def reschedule_appointment(
    appointment_id: str,
    new_date: str,
    new_time: str,
    client_id: str = "gleneagles_001",
) -> dict[str, Any]:
    """Reschedule an existing appointment to a new date and time."""
    service = _get_service(client_id)
    try:
        result = await asyncio.to_thread(service.reschedule, appointment_id, new_date, new_time)
        return result
    except ValueError as e:
        return {"error": str(e)}


async def cancel_appointment(
    appointment_id: str,
    client_id: str = "gleneagles_001",
) -> dict[str, Any]:
    """Cancel an existing appointment."""
    service = _get_service(client_id)
    try:
        result = await asyncio.to_thread(service.cancel, appointment_id)
        return result
    except ValueError as e:
        return {"error": str(e)}
