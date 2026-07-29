from fastapi import APIRouter, HTTPException, Query
from src.workflows.services.booking_service import AppointmentBookingService
from src.workflows.api.schemas import (
    GetAvailabilityRequest, GetAvailabilityResponse,
    BookAppointmentRequest, BookAppointmentResponse,
    RescheduleAppointmentRequest, RescheduleAppointmentResponse,
    CancelAppointmentRequest, CancelAppointmentResponse,
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


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}