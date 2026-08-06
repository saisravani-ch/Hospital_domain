"""Seed demo appointments for the current week (receptionist dashboard preview).

Inserts realistic booked/checked-in/completed/cancelled appointments across
the current week into the shared SQLite DB, using real doctor IDs and real
time_slot IDs (the used slots are marked unavailable, consistent with the
booking flow). Safe to re-run: skips if the week already has >= MIN_BOOKED
booked appointments from today onwards.
"""

from __future__ import annotations

import random
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "db" / "knowledge_base.db"
CLIENT_ID = "gleneagles_001"
MIN_BOOKED = 20  # skip seeding when this many booked appts exist from today on

PATIENTS = [
    # (name, phone, age, gender, city, problem, history, prev_visit)
    ("Priya Sharma", "+919876543201", 34, "F", "Chennai", "Lower back pain, 2 weeks", "None significant", "No"),
    ("Rahul Verma", "+919876543202", 41, "M", "Chennai", "Knee pain while climbing stairs", "Diabetes (controlled)", "No"),
    ("Anjali Menon", "+919876543203", 28, "F", "Bengaluru", "Skin rash and itching", "Allergy to dust", "Yes — 3 months ago"),
    ("Vikram Singh", "+919876543204", 52, "M", "Chennai", "Follow-up for hypertension", "Hypertension", "Yes — 1 month ago"),
    ("Kavitha Krishnan", "+919876543205", 45, "F", "Chennai", "Recurring headaches", "Migraine", "Yes — 6 months ago"),
    ("Mohammed Irfan", "+919876543206", 38, "M", "Hyderabad", "Shoulder stiffness", "None", "No"),
    ("Lakshmi Narayanan", "+919876543207", 60, "F", "Chennai", "Diabetes review", "Type 2 diabetes", "Yes — 2 months ago"),
    ("Deepak Kumar", "+919876543208", 33, "M", "Bengaluru", "Digestive issues", "Gastritis", "No"),
    ("Sneha Reddy", "+919876543209", 29, "F", "Hyderabad", "Eye strain and blurring", "None", "No"),
    ("Arjun Nair", "+919876543210", 47, "M", "Chennai", "Chest discomfort on exertion", "Mild CAD", "Yes — 1 month ago"),
    ("Fatima Sheikh", "+919876543211", 55, "F", "Chennai", "Joint pain in hands", "Rheumatoid arthritis", "Yes — 4 months ago"),
    ("Ramesh Babu", "+919876543212", 63, "M", "Bengaluru", "Prostate check-up", "BPH", "No"),
    ("Divya Pillai", "+919876543213", 31, "F", "Chennai", "Thyroid follow-up", "Hypothyroidism", "Yes — 2 months ago"),
    ("Suresh Iyer", "+919876543214", 44, "M", "Chennai", "Sleep apnea consultation", "OSA (suspected)", "No"),
    ("Meena Kumari", "+919876543215", 50, "F", "Hyderabad", "Post-op review", "Gallstone surgery", "Yes — 3 weeks ago"),
    ("Harish Chandra", "+919876543216", 26, "M", "Bengaluru", "Sports injury — ankle", "None", "No"),
    ("Pooja Gupta", "+919876543217", 36, "F", "Chennai", "Fertility consultation", "PCOS", "No"),
    ("Naveen Kumar", "+919876543218", 58, "M", "Chennai", "Hearing difficulty", "None", "No"),
]

BOOKED_THROUGH = ["WhatsApp", "WhatsApp", "Reception", "Walk-in", "WhatsApp", "Reception"]


def target_dates() -> list[date]:
    """Weekdays from today up to +7 days (slots only exist on weekdays)."""
    out, d = [], date.today()
    while d <= date.today() + timedelta(days=7):
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def main() -> int:
    if not DB_PATH.exists():
        print(f"DB not found: {DB_PATH}")
        return 1

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    booked_existing = cur.execute(
        "SELECT COUNT(*) FROM appointments WHERE client_id = ? AND date >= ? AND status = 'booked'",
        (CLIENT_ID, date.today().isoformat()),
    ).fetchone()[0]
    if booked_existing >= MIN_BOOKED:
        print(f"Skipping: already {booked_existing} booked appointments from today onwards.")
        con.close()
        return 0

    dates = target_dates()
    doctors = cur.execute(
        "SELECT id, name, speciality FROM doctors WHERE id IN (SELECT DISTINCT doctor_id FROM time_slots WHERE date >= ?) ORDER BY name",
        (dates[0].isoformat(),),
    ).fetchall()
    if not doctors:
        print("No doctors with future slots found — run scripts/populate_schedule.py first.")
        con.close()
        return 1

    # Slots per (date, doctor) -> list of (slot_id, time)
    doc_meta = {doc_id: (name, spec) for doc_id, name, spec in doctors}
    slots_by_date_doctor: dict[tuple[str, str], list[tuple[int, str]]] = {}
    for d in dates:
        for doc_id, _, _ in doctors:
            rows = cur.execute(
                "SELECT id, time FROM time_slots WHERE doctor_id = ? AND date = ? AND available = 1 ORDER BY time",
                (doc_id, d.isoformat()),
            ).fetchall()
            if rows:
                slots_by_date_doctor[(d.isoformat(), doc_id)] = rows

    now = datetime.now()
    rng = random.Random(42)  # deterministic seed for reproducibility
    patient_idx = 0
    created_rows = 0

    def next_patient() -> tuple:
        nonlocal patient_idx
        p = PATIENTS[patient_idx % len(PATIENTS)]
        patient_idx += 1
        return p

    def created_at_for(appt_date: str, time_str: str) -> str:
        """Booked 1–5 days before the appointment."""
        appt = datetime.fromisoformat(f"{appt_date}T{time_str}")
        offset = timedelta(days=rng.randint(1, 5), hours=rng.randint(0, 8))
        ts = appt - offset
        if ts > now:
            ts = now - timedelta(hours=rng.randint(2, 20))
        return ts.isoformat(timespec="minutes")

    def insert(slot_id: int, doc_id: str, doc_name: str, spec: str, appt_date: str,
               time_str: str, status: str, booked_through: str) -> None:
        nonlocal created_rows
        name, phone, age, gender, city, problem, history, prev = next_patient()
        apt_id = f"apt_{rng.randrange(10**8):08d}"
        cur.execute(
            """INSERT INTO appointments
               (id, client_id, patient_phone, doctor_id, date, time, slot_id, status,
                notes, created_at, cancelled_at, patient_name, age, gender, city,
                booked_through, medical_history, previous_visit)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (apt_id, CLIENT_ID, phone, doc_id, appt_date, time_str, slot_id, status,
             problem, created_at_for(appt_date, time_str),
             now.isoformat(timespec="minutes") if status == "cancelled" else None,
             name, age, gender, city, booked_through, history, prev),
        )
        cur.execute("UPDATE time_slots SET available = 0 WHERE id = ?", (slot_id,))
        created_rows += 1

    # ── Today: full receptionist spread ─────────────────────────────────────
    today = date.today().isoformat()
    today_slots = [
        (doc_id, *doc_meta[doc_id], slot_id, time)
        for (d, doc_id), rows in slots_by_date_doctor.items()
        for slot_id, time in rows if d == today
    ]
    rng.shuffle(today_slots)
    today_statuses = (["completed"] * 2 + ["checked_in"] * 2 + ["booked"] * 5 + ["cancelled"] * 1)
    for (doc_id, doc_name, spec, slot_id, time_str), status in zip(today_slots, today_statuses):
        channel = "Reception" if status == "cancelled" else rng.choice(BOOKED_THROUGH)
        insert(slot_id, doc_id, doc_name, spec, today, time_str, status, channel)

    # ── Rest of the week: booked + one pending ──────────────────────────────
    for d in dates[1:]:
        day_slots = [
            (doc_id, *doc_meta[doc_id], slot_id, time)
            for (dd, doc_id), rows in slots_by_date_doctor.items()
            for slot_id, time in rows if dd == d.isoformat()
        ]
        rng.shuffle(day_slots)
        count = 4 if d.weekday() < 3 else 3
        for (doc_id, doc_name, spec, slot_id, time_str) in day_slots[:count]:
            status = "pending" if (d == dates[1] and rng.random() < 0.25) else "booked"
            insert(slot_id, doc_id, doc_name, spec, d.isoformat(), time_str, status,
                   "Walk-in" if status == "pending" else rng.choice(BOOKED_THROUGH))

    con.commit()
    total = cur.execute("SELECT COUNT(*) FROM appointments WHERE client_id = ?", (CLIENT_ID,)).fetchone()[0]
    by_date = cur.execute(
        "SELECT date, status, COUNT(*) FROM appointments WHERE client_id = ? AND date >= ? GROUP BY date, status ORDER BY date",
        (CLIENT_ID, dates[0].isoformat()),
    ).fetchall()
    con.close()

    print(f"Inserted {created_rows} appointments (total for client: {total}).")
    for row in by_date:
        print(f"  {row[0]} — {row[1]}: {row[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
