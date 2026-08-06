from fastapi import APIRouter, HTTPException, Query
from apps.workflows.services.booking_service import AppointmentBookingService
from apps.workflows.services.dashboard_service import DashboardService
from apps.workflows.api.schemas import (
    GetAvailabilityRequest, GetAvailabilityResponse,
    BookAppointmentRequest, BookAppointmentResponse,
    RescheduleAppointmentRequest, RescheduleAppointmentResponse,
    CancelAppointmentRequest, CancelAppointmentResponse,
    CheckInAppointmentRequest, CheckInAppointmentResponse,
    UpcomingSlot, UpcomingSlotsResponse,
    ListAppointmentsResponse, AppointmentInfo,
    AvailableSlot
)

router = APIRouter(prefix="/appointments", tags=["Appointments"])


def handle_service_error(error: Exception, client_id: str = None) -> None:
    if isinstance(error, ValueError):
        raise HTTPException(status_code=400, detail={"error": str(error)})
    else:
        raise HTTPException(status_code=500, detail={"error": str(error)})


def get_booking_service(client_id: str) -> AppointmentBookingService:
    try:
        return AppointmentBookingService(client_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e)})


@router.get("/availability", response_model=GetAvailabilityResponse)
def get_availability(
    client_id: str = Query(...),
    doctor_id: str = Query(...),
    date: str = Query(...),
) -> GetAvailabilityResponse:
    try:
        service = get_booking_service(client_id)
        slots = service.get_availability(doctor_id, date)
        return GetAvailabilityResponse(
            doctor_id=doctor_id,
            date=date,
            slots=[AvailableSlot(**slot) for slot in slots],
            client_id=client_id
        )
    except Exception as e:
        handle_service_error(e, client_id)


@router.post("/book", response_model=BookAppointmentResponse)
def book_appointment(req: BookAppointmentRequest) -> BookAppointmentResponse:
    try:
        service = get_booking_service(req.client_id)
        result = service.book(
            phone=req.patient_phone,
            doctor_id=req.doctor_id,
            date=req.date,
            time=req.time,
            notes=req.notes
        )
        return BookAppointmentResponse(**result)
    except Exception as e:
        handle_service_error(e, req.client_id)


@router.post("/reschedule", response_model=RescheduleAppointmentResponse)
def reschedule_appointment(req: RescheduleAppointmentRequest) -> RescheduleAppointmentResponse:
    try:
        service = get_booking_service(req.client_id)
        result = service.reschedule(
            appointment_id=req.appointment_id,
            new_date=req.new_date,
            new_time=req.new_time
        )
        return RescheduleAppointmentResponse(**result)
    except Exception as e:
        handle_service_error(e, req.client_id)


@router.post("/cancel", response_model=CancelAppointmentResponse)
def cancel_appointment(req: CancelAppointmentRequest) -> CancelAppointmentResponse:
    try:
        service = get_booking_service(req.client_id)
        result = service.cancel(req.appointment_id)
        return CancelAppointmentResponse(**result)
    except Exception as e:
        handle_service_error(e, req.client_id)


@router.get("", response_model=ListAppointmentsResponse)
def list_appointments(
    client_id: str = Query(...),
    phone: str = Query(...),
) -> ListAppointmentsResponse:
    """List appointments for a patient by phone number."""
    try:
        service = get_booking_service(client_id)
        appointments = service.get_appointments_by_phone(phone)
        return ListAppointmentsResponse(
            appointments=[AppointmentInfo(**a) for a in appointments],
            client_id=client_id,
            phone=phone,
        )
    except Exception as e:
        handle_service_error(e, client_id)


@router.post("/check-in", response_model=CheckInAppointmentResponse)
def check_in_appointment(req: CheckInAppointmentRequest) -> CheckInAppointmentResponse:
    """Receptionist check-in — marks the appointment as checked_in."""
    try:
        service = get_booking_service(req.client_id)
        result = service.check_in(req.appointment_id)
        return CheckInAppointmentResponse(**result)
    except Exception as e:
        handle_service_error(e, req.client_id)


@router.get("/upcoming-slots", response_model=UpcomingSlotsResponse)
def get_upcoming_slots(
    client_id: str = Query(...),
    doctor_id: str = Query(...),
) -> UpcomingSlotsResponse:
    """Available slots for a doctor over the next 14 days (reschedule picker)."""
    try:
        service = get_booking_service(client_id)
        slots = service.get_upcoming_slots(doctor_id)
        return UpcomingSlotsResponse(
            doctor_id=doctor_id,
            client_id=client_id,
            slots=[UpcomingSlot(**slot) for slot in slots],
        )
    except Exception as e:
        handle_service_error(e, client_id)


@router.get("/dashboard")
def get_dashboard(client_id: str = Query(...)) -> dict:
    """Monitoring dashboard payload for a receptionist / ops person.

    Aggregates today's + upcoming appointments, status rollups, doctor
    availability and network analytics from the shared knowledge base.
    """
    try:
        return DashboardService(client_id).build()
    except Exception as e:
        handle_service_error(e, client_id)


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}