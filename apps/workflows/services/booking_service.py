from functools import lru_cache

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
import uuid
from apps.workflows.config import get_database_url, get_client_config


@lru_cache
def _get_engine(client_id: str) -> Engine:
    return create_engine(get_database_url(client_id), connect_args={"check_same_thread": False})


class AppointmentBookingService:
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.config = get_client_config(client_id)
        engine = _get_engine(client_id)
        self.db = sessionmaker(bind=engine)()

    def get_availability(self, doctor_id: str, date: str) -> list:
        try:
            slots = self.db.execute(
                text("SELECT id, time, period FROM time_slots WHERE doctor_id = :did AND date = :date AND available = 1 ORDER BY time"),
                {"did": doctor_id, "date": date}
            ).fetchall()
            return [{"slot_id": s[0], "time": s[1], "period": s[2]} for s in slots]
        finally:
            self.db.close()

    def get_appointments_by_phone(self, phone: str) -> list[dict]:
        try:
            rows = self.db.execute(
                text("""
                    SELECT a.id, a.patient_phone, a.doctor_id, d.name AS doctor_name,
                           d.speciality, a.date, a.time, a.status, a.notes, a.created_at
                    FROM appointments a
                    LEFT JOIN doctors d ON d.id = a.doctor_id
                    WHERE a.patient_phone = :phone AND a.client_id = :cid
                    ORDER BY a.created_at DESC
                """),
                {"phone": phone, "cid": self.client_id}
            ).fetchall()
            return [
                {
                    "appointment_id": r[0],
                    "patient_phone": r[1],
                    "doctor_id": r[2],
                    "doctor_name": r[3],
                    "speciality": r[4],
                    "date": r[5],
                    "time": r[6],
                    "status": r[7],
                    "notes": r[8],
                    "booked_at": r[9],
                }
                for r in rows
            ]
        finally:
            self.db.close()

    def book(self, phone: str, doctor_id: str, date: str, time: str, notes: str = None) -> dict:
        try:
            doctor = self.db.execute(
                text("SELECT name, speciality, experience_years FROM doctors WHERE id = :id"),
                {"id": doctor_id}
            ).fetchone()
            if not doctor:
                raise ValueError("Doctor not found")

            slot = self.db.execute(
                text("SELECT id FROM time_slots WHERE doctor_id = :did AND date = :date AND time = :time AND available = 1"),
                {"did": doctor_id, "date": date, "time": time}
            ).fetchone()
            if not slot:
                raise ValueError("Slot not available")

            self.db.execute(
                text("UPDATE time_slots SET available = 0 WHERE id = :id"),
                {"id": slot[0]}
            )

            appointment_id = f"apt_{uuid.uuid4().hex[:8]}"
            self.db.execute(
                text("INSERT INTO appointments (id, client_id, patient_phone, doctor_id, date, time, slot_id, status, notes, created_at) VALUES (:id, :cid, :phone, :doc, :date, :time, :slot, :status, :notes, :created)"),
                {
                    "id": appointment_id,
                    "cid": self.client_id,
                    "phone": phone,
                    "doc": doctor_id,
                    "date": date,
                    "time": time,
                    "slot": slot[0],
                    "status": "booked",
                    "notes": notes,
                    "created": datetime.now(timezone.utc).isoformat()
                }
            )
            self.db.commit()

            return {
                "appointment_id": appointment_id,
                "status": "booked",
                "doctor_name": doctor[0],
                "doctor_id": doctor_id,
                "speciality": doctor[1] or "General",
                "experience_years": doctor[2],
                "date": date,
                "time": time,
                "patient_phone": phone,
                "client_id": self.client_id,
                "client_name": self.config["name"],
                "notes": notes,
                "booked_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            self.db.rollback()
            raise
        finally:
            self.db.close()

    def reschedule(self, appointment_id: str, new_date: str, new_time: str) -> dict:
        try:
            existing = self.db.execute(
                text("SELECT slot_id, doctor_id FROM appointments WHERE id = :id AND client_id = :cid"),
                {"id": appointment_id, "cid": self.client_id}
            ).fetchone()
            if not existing:
                raise ValueError("Appointment not found")

            old_slot_id = existing[0]
            doctor_id = existing[1]

            new_slot = self.db.execute(
                text("SELECT id FROM time_slots WHERE doctor_id = :did AND date = :date AND time = :time AND available = 1"),
                {"did": doctor_id, "date": new_date, "time": new_time}
            ).fetchone()
            if not new_slot:
                raise ValueError("New slot not available")

            self.db.execute(
                text("UPDATE time_slots SET available = 1 WHERE id = :id"),
                {"id": old_slot_id}
            )

            self.db.execute(
                text("UPDATE time_slots SET available = 0 WHERE id = :id"),
                {"id": new_slot[0]}
            )

            self.db.execute(
                text("UPDATE appointments SET slot_id = :new_slot, date = :date, time = :time, status = 'rescheduled' WHERE id = :id"),
                {"new_slot": new_slot[0], "date": new_date, "time": new_time, "id": appointment_id}
            )
            self.db.commit()

            return {
                "appointment_id": appointment_id,
                "status": "rescheduled",
                "new_date": new_date,
                "new_time": new_time,
                "client_id": self.client_id,
                "rescheduled_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            self.db.rollback()
            raise
        finally:
            self.db.close()

    def cancel(self, appointment_id: str) -> dict:
        try:
            appointment = self.db.execute(
                text("SELECT slot_id, status FROM appointments WHERE id = :id AND client_id = :cid"),
                {"id": appointment_id, "cid": self.client_id}
            ).fetchone()
            if not appointment:
                raise ValueError("Appointment not found")

            slot_id = appointment[0]
            status = appointment[1]

            if status == "cancelled":
                raise ValueError("Appointment already cancelled")

            self.db.execute(
                text("UPDATE time_slots SET available = 1 WHERE id = :id"),
                {"id": slot_id}
            )

            self.db.execute(
                text("UPDATE appointments SET status = 'cancelled', cancelled_at = :cancelled WHERE id = :id"),
                {"cancelled": datetime.now(timezone.utc).isoformat(), "id": appointment_id}
            )
            self.db.commit()

            return {
                "appointment_id": appointment_id,
                "status": "cancelled",
                "client_id": self.client_id,
                "cancelled_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            self.db.rollback()
            raise
        finally:
            self.db.close()

    def check_in(self, appointment_id: str) -> dict:
        try:
            appointment = self.db.execute(
                text("SELECT status FROM appointments WHERE id = :id AND client_id = :cid"),
                {"id": appointment_id, "cid": self.client_id},
            ).fetchone()
            if not appointment:
                raise ValueError("Appointment not found")
            if appointment[0] == "cancelled":
                raise ValueError("Cannot check in a cancelled appointment")

            self.db.execute(
                text("UPDATE appointments SET status = 'checked_in' WHERE id = :id"),
                {"id": appointment_id},
            )
            self.db.commit()
            return {
                "appointment_id": appointment_id,
                "status": "checked_in",
                "client_id": self.client_id,
                "checked_in_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            self.db.rollback()
            raise
        finally:
            self.db.close()

    def get_upcoming_slots(self, doctor_id: str, days: int = 14) -> list[dict]:
        try:
            today = datetime.now(timezone.utc).date().isoformat()
            max_date = (datetime.now(timezone.utc).date() + timedelta(days=days)).isoformat()
            rows = self.db.execute(
                text("""
                    SELECT id, date, time FROM time_slots
                    WHERE doctor_id = :did AND available = 1
                          AND date >= :min AND date <= :max
                    ORDER BY date, time
                """),
                {"did": doctor_id, "min": today, "max": max_date},
            ).fetchall()
            return [{"slot_id": r[0], "date": r[1], "time": r[2]} for r in rows]
        finally:
            self.db.close()