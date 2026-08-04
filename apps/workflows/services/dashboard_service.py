"""Dashboard / monitoring service for the receptionist & ops dashboard.

Aggregates appointments + doctor availability + analytics from the shared
SQLite DB (data/db/knowledge_base.db) for a given client (hospital group).
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from apps.workflows.config import get_database_url, get_client_config

_APPT_SELECT = """
    SELECT a.id, a.patient_phone, a.doctor_id, d.name AS doctor_name,
           d.speciality, a.date, a.time, a.status, a.notes,
           a.created_at, a.cancelled_at
    FROM appointments a
    LEFT JOIN doctors d ON d.id = a.doctor_id
"""


class DashboardService:
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.config = get_client_config(client_id)
        engine = create_engine(get_database_url(client_id), connect_args={"check_same_thread": False})
        self.db = sessionmaker(bind=engine)()

    def _row(self, sql: str, **params):
        return self.db.execute(text(sql), params).fetchone()

    def _rows(self, sql: str, **params):
        return self.db.execute(text(sql), params).fetchall()

    def _appointment(self, r) -> dict:
        return {
            "appointment_id": r[0],
            "patient_phone": r[1],
            "doctor_id": r[2],
            "doctor_name": r[3] or "Unknown",
            "speciality": r[4] or "General",
            "date": r[5],
            "time": r[6],
            "status": r[7],
            "notes": r[8],
            "created_at": r[9],
            "cancelled_at": r[10],
        }

    def build(self) -> dict:
        try:
            today = date.today().isoformat()
            week_start = (date.today() - timedelta(days=7)).isoformat()
            today_7 = (date.today() + timedelta(days=7)).isoformat()

            # ── Summary KPIs ────────────────────────────────────────────────
            k = self._row(
                """
                SELECT
                  (SELECT COUNT(*) FROM doctors) AS total_doctors,
                  (SELECT COUNT(*) FROM hospitals) AS total_hospitals,
                  (SELECT COUNT(DISTINCT speciality) FROM doctors
                     WHERE speciality IS NOT NULL AND speciality != '') AS specialties,
                  (SELECT COUNT(*) FROM time_slots
                     WHERE available = 1 AND date >= :today) AS open_slots_total,
                  (SELECT COUNT(DISTINCT doctor_id) FROM time_slots
                     WHERE available = 1 AND date >= :today) AS doctors_with_slots,
                  (SELECT COUNT(*) FROM time_slots
                     WHERE available = 1 AND date = :today) AS open_slots_today,
                  (SELECT COUNT(*) FROM time_slots
                     WHERE available = 1 AND date BETWEEN :today AND :today_7) AS open_slots_7d,
                  (SELECT AVG(experience_years) FROM doctors
                     WHERE experience_years IS NOT NULL) AS avg_experience,
                  (SELECT COUNT(*) FROM appointments WHERE client_id = :cid) AS total_appointments,
                  (SELECT COUNT(*) FROM appointments
                     WHERE client_id = :cid AND date = :today) AS today_appointments,
                  (SELECT COUNT(*) FROM appointments
                     WHERE client_id = :cid AND date = :today AND status = 'booked') AS today_booked,
                  (SELECT COUNT(*) FROM appointments
                     WHERE client_id = :cid AND date = :today AND status = 'cancelled') AS today_cancelled,
                  (SELECT COUNT(*) FROM appointments
                     WHERE client_id = :cid AND date > :today AND status = 'booked') AS upcoming,
                  (SELECT COUNT(*) FROM appointments
                     WHERE client_id = :cid AND status = 'cancelled') AS total_cancelled
                """,
                cid=self.client_id, today=today, today_7=today_7,
            )
            summary = {
                "total_doctors": int(k[0] or 0),
                "total_hospitals": int(k[1] or 0),
                "specialties": int(k[2] or 0),
                "open_slots_total": int(k[3] or 0),
                "doctors_with_slots": int(k[4] or 0),
                "open_slots_today": int(k[5] or 0),
                "open_slots_7d": int(k[6] or 0),
                "avg_experience": round(float(k[7]), 1) if k[7] else 0,
                "total_appointments": int(k[8] or 0),
                "today_appointments": int(k[9] or 0),
                "today_booked": int(k[10] or 0),
                "today_cancelled": int(k[11] or 0),
                "upcoming": int(k[12] or 0),
                "total_cancelled": int(k[13] or 0),
            }

            # ── Today's appointments ────────────────────────────────────────
            today_appts = [
                self._appointment(r)
                for r in self._rows(_APPT_SELECT + " WHERE a.client_id = :cid AND a.date = :today ORDER BY a.time",
                                    cid=self.client_id, today=today)
            ]

            # ── Upcoming booked appointments ────────────────────────────────
            upcoming_appts = [
                self._appointment(r)
                for r in self._rows(_APPT_SELECT + " WHERE a.client_id = :cid AND a.date >= :today AND a.status = 'booked' ORDER BY a.date, a.time LIMIT 50",
                                    cid=self.client_id, today=today)
            ]

            # ── Status breakdown ────────────────────────────────────────────
            status_rows = self._rows(
                "SELECT status, COUNT(*) FROM appointments WHERE client_id = :cid GROUP BY status",
                cid=self.client_id,
            )
            status_breakdown = {r[0] or "unknown": int(r[1]) for r in status_rows}

            # ── Recent activity (last 20 by created_at) ─────────────────────
            recent = []
            for r in self._rows(
                _APPT_SELECT + " WHERE a.client_id = :cid ORDER BY a.created_at DESC LIMIT 20",
                cid=self.client_id,
            ):
                apt = self._appointment(r)
                action = apt["status"]
                if apt["cancelled_at"]:
                    action = "cancelled"
                recent.append({**apt, "action": action})

            # ── Doctor availability (top by open slots, from time_slots) ────
            doc_avail = []
            for r in self._rows(
                """
                SELECT d.id, d.name, d.speciality, h.city, d.consultation_fee,
                       COUNT(t.id) AS open_slots, MIN(t.date) AS next_date
                FROM time_slots t
                JOIN doctors d ON d.id = t.doctor_id
                LEFT JOIN hospitals h ON h.location_id = d.location_id
                WHERE t.available = 1 AND t.date >= :today
                GROUP BY d.id, d.name, d.speciality, h.city, d.consultation_fee
                ORDER BY open_slots DESC, d.name
                LIMIT 15
                """,
                today=today,
            ):
                doc_avail.append({
                    "doctor_id": r[0],
                    "doctor_name": r[1] or "Unknown",
                    "speciality": r[2] or "General",
                    "city": r[3] or "Unknown",
                    "consultation_fee": r[4],
                    "open_slots": int(r[5] or 0),
                    "next_available": r[6] or "",
                })

            # ── Analytics: top specializations ──────────────────────────────
            spec_counts: Counter = Counter()
            for s in self._rows("SELECT specializations, speciality FROM doctors"):
                specs = [x.strip() for x in (s[0] or "").split(",") if x.strip()]
                if not specs:
                    specs = [s[1] or "General Medicine"]
                for sp in specs:
                    spec_counts[sp] += 1
            top_specializations = [
                {"name": name, "count": count}
                for name, count in spec_counts.most_common(15)
            ]

            # ── Analytics: slots + doctors by city ──────────────────────────
            slots_by_city = []
            for r in self._rows(
                """
                SELECT COALESCE(h.city, 'Unknown'),
                       COUNT(t.id),
                       COUNT(DISTINCT d.id)
                FROM time_slots t
                JOIN doctors d ON d.id = t.doctor_id
                LEFT JOIN hospitals h ON h.location_id = d.location_id
                WHERE t.available = 1 AND t.date >= :today
                GROUP BY h.city ORDER BY 2 DESC
                """,
                today=today,
            ):
                slots_by_city.append({
                    "city": r[0],
                    "slots": int(r[1] or 0),
                    "doctors": int(r[2] or 0),
                })

            # ── Analytics: designation mix ──────────────────────────────────
            designation_mix = [
                {"designation": r[0] or "Unknown", "count": int(r[1])}
                for r in self._rows(
                    "SELECT designation, COUNT(*) FROM doctors GROUP BY designation ORDER BY 2 DESC LIMIT 10"
                )
            ]

            # ── Analytics: languages ────────────────────────────────────────
            lang_counts: Counter = Counter()
            for (langs,) in self._rows("SELECT languages FROM doctors"):
                for lg in [l.strip() for l in (langs or "").split(",") if l.strip()]:
                    lang_counts[lg] += 1
            languages = [
                {"language": name, "count": count}
                for name, count in lang_counts.most_common(10)
            ]

            # ── Alerts ──────────────────────────────────────────────────────
            alerts = []
            if summary["today_cancelled"] > 0:
                alerts.append({
                    "level": "warn",
                    "text": f"{summary['today_cancelled']} appointment(s) cancelled today — consider reallocating slots.",
                })
            if summary["today_booked"] == 0:
                alerts.append({
                    "level": "info",
                    "text": "No appointments booked for today yet.",
                })
            if summary["upcoming"] == 0:
                alerts.append({
                    "level": "info",
                    "text": "No upcoming booked appointments on the horizon.",
                })
            if summary["doctors_with_slots"] == 0:
                alerts.append({
                    "level": "warn",
                    "text": "No doctors currently have open appointment slots.",
                })
            elif summary["open_slots_total"] < 100:
                alerts.append({
                    "level": "warn",
                    "text": f"Low open-slot inventory ({summary['open_slots_total']} total) across the network.",
                })

            return {
                "generated_at": datetime.now().astimezone().isoformat(),
                "client_id": self.client_id,
                "client_name": self.config.get("name", self.client_id),
                "today": today,
                "week_start": week_start,
                "summary": summary,
                "today_appointments": today_appts,
                "upcoming_appointments": upcoming_appts,
                "status_breakdown": status_breakdown,
                "recent_activity": recent,
                "doctor_availability": doc_avail,
                "analytics": {
                    "top_specializations": top_specializations,
                    "slots_by_city": slots_by_city,
                    "designation_mix": designation_mix,
                    "languages": languages,
                },
                "alerts": alerts,
            }
        finally:
            self.db.close()
