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


class CheckInAppointmentRequest(BaseModel):
    client_id: str
    appointment_id: str


class CheckInAppointmentResponse(BaseModel):
    appointment_id: str
    status: str
    client_id: str
    checked_in_at: str


class UpcomingSlot(BaseModel):
    slot_id: int
    date: str
    time: str


class UpcomingSlotsResponse(BaseModel):
    doctor_id: str
    client_id: str
    slots: List[UpcomingSlot]


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


class AppointmentInfo(BaseModel):
    appointment_id: str
    patient_phone: str
    doctor_id: str
    doctor_name: str | None = None
    speciality: str | None = None
    date: str
    time: str
    status: str
    notes: str | None = None
    booked_at: str


class ListAppointmentsResponse(BaseModel):
    appointments: list[AppointmentInfo]
    client_id: str
    phone: str