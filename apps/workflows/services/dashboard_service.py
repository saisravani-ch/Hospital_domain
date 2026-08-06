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
           a.created_at, a.cancelled_at,
           a.patient_name, a.age, a.gender, a.city, a.booked_through,
           a.medical_history, a.previous_visit, a.slot_id
    FROM appointments a
    LEFT JOIN doctors d ON d.id = a.doctor_id
"""


class DashboardService:
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.config = get_client_config(client_id)
        engine = create_engine(get_database_url(client_id), connect_args={"check_same_thread": False})
        self.db = sessionmaker(bind=engine)()
        self._ensure_appointment_columns()

    def _ensure_appointment_columns(self) -> None:
        """Idempotently add receptionist-facing patient columns (mirrors dashboard.py)."""
        for col, ddl in {
            "patient_name": "TEXT", "age": "INTEGER", "gender": "TEXT",
            "city": "TEXT", "booked_through": "TEXT",
            "medical_history": "TEXT", "previous_visit": "TEXT",
        }.items():
            try:
                self.db.execute(text(f"ALTER TABLE appointments ADD COLUMN {col} {ddl}"))
                self.db.commit()
            except Exception:
                pass

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
            "patient_name": r[11] or "",
            "age": r[12],
            "gender": r[13] or "",
            "city": r[14] or "",
            "booked_through": r[15] or "WhatsApp",
            "medical_history": r[16] or "",
            "previous_visit": r[17] or "",
            "slot_id": r[18],
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
                "avg_experience": round(float(k[7]), 1) if (k[7] is not None and str(k[7]).lower() != "nan") else 0,
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

            # ── Receptionist cockpit: recent appointments + active dates ────
            recent_appointments = [
                self._appointment(r)
                for r in self._rows(_APPT_SELECT + " WHERE a.client_id = :cid ORDER BY a.date DESC, a.time LIMIT 500",
                                    cid=self.client_id)
            ]
            ops_dates = [
                r[0]
                for r in self._rows(
                    "SELECT DISTINCT date FROM appointments WHERE client_id = :cid ORDER BY date DESC LIMIT 14",
                    cid=self.client_id,
                )
            ]
            ops_date = today if today_appts else (ops_dates[0] if ops_dates else today)

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

            # ── Analytics: hospital network ─────────────────────────────────
            hospital_network = [
                {
                    "id": r[0],
                    "name": (r[1] or "").split(",")[0],
                    "full_name": r[1] or "",
                    "city": r[2] or "Unknown",
                    "state": r[3] or "",
                    "doctor_count": int(r[4] or 0),
                    "total_slots": int(r[5] or 0),
                    "doctors_with_slots": int(r[6] or 0),
                }
                for r in self._rows(
                    """
                    SELECT h.id, h.name, h.city, h.state,
                           COUNT(DISTINCT d.id) AS doctor_count,
                           COALESCE(SUM(d.total_available_slots), 0) AS total_slots,
                           COUNT(DISTINCT CASE WHEN d.total_available_slots > 0 THEN d.id END) AS doctors_with_slots
                    FROM hospitals h
                    LEFT JOIN doctors d ON d.location_id = h.location_id
                    GROUP BY h.id, h.name, h.city, h.state
                    ORDER BY doctor_count DESC
                    """
                )
            ]

            # ── Analytics: experience distribution ──────────────────────────
            exp_buckets = {"0-5 yrs": 0, "5-10 yrs": 0, "10-15 yrs": 0, "15-20 yrs": 0, "20+ yrs": 0}
            for (exp,) in self._rows("SELECT experience_years FROM doctors WHERE experience_years IS NOT NULL"):
                try:
                    e = float(exp)
                    if e < 5: exp_buckets["0-5 yrs"] += 1
                    elif e < 10: exp_buckets["5-10 yrs"] += 1
                    elif e < 15: exp_buckets["10-15 yrs"] += 1
                    elif e < 20: exp_buckets["15-20 yrs"] += 1
                    else: exp_buckets["20+ yrs"] += 1
                except (ValueError, TypeError):
                    pass
            experience_distribution = [{"range": k, "count": v} for k, v in exp_buckets.items()]

            # ── Distinct Cities & Specialties from SQLite ───────────────────
            city_rows = self._rows(
                """
                SELECT DISTINCT city FROM hospitals WHERE city IS NOT NULL AND city != ''
                UNION
                SELECT DISTINCT h.city FROM doctors d JOIN hospitals h ON h.location_id = d.location_id WHERE h.city IS NOT NULL AND h.city != ''
                """
            )
            cities_from_sqlite = sorted(list(set(r[0] for r in city_rows if r[0])))

            spec_rows = self._rows(
                "SELECT DISTINCT speciality FROM doctors WHERE speciality IS NOT NULL AND speciality != '' ORDER BY speciality"
            )
            specialties_from_sqlite = sorted(list(set(r[0].strip() for r in spec_rows if r[0] and r[0].strip())))

            # ── Analytics: appointment types ────────────────────────────────
            appointment_types = [
                {"type": r[0] or "In-Person", "count": int(r[1])}
                for r in self._rows("SELECT COALESCE(appointment_type, 'In-Person'), COUNT(*) FROM doctors GROUP BY 1 ORDER BY 2 DESC")
            ]

            # ── All Doctors Directory list ──────────────────────────────────
            all_doctors = [
                {
                    "id": r[0],
                    "name": r[1] or "Unknown",
                    "designation": r[2] or "",
                    "speciality": r[3] or "General",
                    "qualifications": r[4] or "",
                    "languages": r[5] or "",
                    "experience_years": r[6],
                    "city": r[7] or "Unknown",
                    "open_slots": int(r[8] or 0),
                    "booking_url": r[9] or "",
                }
                for r in self._rows(
                    """
                    SELECT d.id, d.name, d.designation, d.speciality, d.qualifications,
                           d.languages, d.experience_years, h.city,
                           COALESCE(d.total_available_slots, 0), d.booking_url
                    FROM doctors d
                    LEFT JOIN hospitals h ON h.location_id = d.location_id
                    ORDER BY d.total_available_slots DESC, d.name
                    """
                )
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
                "ops_date": ops_date,
                "ops_dates": ops_dates,
                "summary": summary,
                "today_appointments": today_appts,
                "upcoming_appointments": upcoming_appts,
                "recent_appointments": recent_appointments,
                "status_breakdown": status_breakdown,
                "recent_activity": recent,
                "doctor_availability": doc_avail,
                "all_doctors": all_doctors,
                "hospital_network": hospital_network,
                "cities": cities_from_sqlite,
                "specialties": specialties_from_sqlite,
                "analytics": {
                    "top_specializations": top_specializations,
                    "slots_by_city": slots_by_city,
                    "designation_mix": designation_mix,
                    "languages": languages,
                    "experience_distribution": experience_distribution,
                    "appointment_types": appointment_types,
                },
                "alerts": alerts,
            }
        finally:
            self.db.close()
