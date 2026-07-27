from pydantic import BaseModel, Field
from typing import Optional, List


class GetAvailabilityRequest(BaseModel):
    client_id: str
    doctor_id: str
    date: str


class BookAppointmentRequest(BaseModel):
    client_id: str
    patient_phone: str
    doctor_id: str
    date: str
    time: str
    notes: Optional[str] = None


class RescheduleAppointmentRequest(BaseModel):
    client_id: str
    appointment_id: str
    new_date: str
    new_time: str


class CancelAppointmentRequest(BaseModel):
    client_id: str
    appointment_id: str


class AvailableSlot(BaseModel):
    slot_id: int
    time: str
    period: str


class GetAvailabilityResponse(BaseModel):
    doctor_id: str
    date: str
    slots: List[AvailableSlot]
    client_id: str


class BookAppointmentResponse(BaseModel):
    appointment_id: str
    status: str
    doctor_name: str
    doctor_id: str
    speciality: str
    experience_years: Optional[int]
    date: str
    time: str
    patient_phone: str
    client_id: str
    client_name: str
    notes: Optional[str]
    booked_at: str


class RescheduleAppointmentResponse(BaseModel):
    appointment_id: str
    status: str
    new_date: str
    new_time: str
    client_id: str
    rescheduled_at: str


class CancelAppointmentResponse(BaseModel):
    appointment_id: str
    status: str
    client_id: str
    cancelled_at: str