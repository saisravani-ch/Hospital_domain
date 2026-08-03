"""
Populate consultation fees and regenerate time_slots for the next 2 weeks.

30-min intervals, weekdays only, 09:00-13:00 + 14:00-17:00 (lunch break).

Usage:
    python scripts/populate_schedule.py            # generate next 14 days
    python scripts/populate_schedule.py --days 7   # custom range
    python scripts/populate_schedule.py --fees-only
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import date, timedelta

DB_PATH = "data/db/knowledge_base.db"

# ── Fee tiers ──────────────────────────────────────────────────────────────────
FEE_TIERS = [(0, 500), (5, 800), (10, 1200), (15, 1500), (20, 2000), (30, 2500)]

def fee_for_experience(years):
    if years is None:
        return 800
    for threshold, fee in reversed(FEE_TIERS):
        if years >= threshold:
            return fee
    return 800

# ── 30-min intervals, 09:00-13:00 + 14:00-17:00 (lunch break 13:00-14:00) ─────
def build_slots():
    slots = []
    # Morning: 09:00-13:00 (8 slots × 30min)
    for m in range(9 * 60, 13 * 60, 30):
        h, mi = divmod(m, 60)
        slots.append((f"{h:02d}:{mi:02d}", "morning"))
    # Afternoon: 14:00-17:00 (6 slots × 30min)
    for m in range(14 * 60, 17 * 60, 30):
        h, mi = divmod(m, 60)
        slots.append((f"{h:02d}:{mi:02d}", "afternoon"))
    return slots


def populate(days=14, db_path=DB_PATH, fees_only=False):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    cur = conn.cursor()
    counts = {"fees_updated": 0, "days_created": 0, "slots_created": 0}

    # ── Step 1: Fill null consultation fees ─────────────────────────────────
    rows = cur.execute(
        "SELECT id, experience_years FROM doctors WHERE consultation_fee IS NULL OR consultation_fee = ''"
    ).fetchall()
    for doc_id, exp_years in rows:
        fee = fee_for_experience(exp_years)
        cur.execute("UPDATE doctors SET consultation_fee = ? WHERE id = ?", (str(fee), doc_id))
    conn.commit()
    counts["fees_updated"] = len(rows)
    print(f"  Fees: {counts['fees_updated']} doctors updated")

    if fees_only:
        conn.close()
        return counts

    # ── Step 2: Regenerate schedule ──────────────────────────────────────────
    SLOTS = build_slots()
    WEEKDAYS = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday"}
    start = date.today() + timedelta(days=1)
    end = date.today() + timedelta(days=days)
    doctor_ids = [r[0] for r in cur.execute("SELECT id FROM doctors").fetchall()]
    print(f"  Slots per day per doctor: {len(SLOTS)} ({SLOTS[0][0]}-{SLOTS[-1][0]}, 30-min)")
    print(f"  Range: {start} to {end} (weekdays only)")
    print(f"  Doctors: {len(doctor_ids)}")

    # Delete existing schedule_days + time_slots in this date range
    cur.execute("DELETE FROM time_slots WHERE date >= ? AND date <= ?", (start.isoformat(), end.isoformat()))
    deleted_slots = cur.rowcount
    cur.execute("DELETE FROM schedule_days WHERE date >= ? AND date <= ?", (start.isoformat(), end.isoformat()))
    deleted_days = cur.rowcount
    conn.commit()
    print(f"  Cleared: {deleted_days} days, {deleted_slots} old slots")

    slot_count = len(SLOTS)
    day_count = 0

    for n in range((end - start).days + 1):
        dt = start + timedelta(n)
        if dt.strftime("%A") not in WEEKDAYS:
            continue

        date_str = dt.isoformat()
        day_name = dt.strftime("%A")
        batch = []

        for doc_id in doctor_ids:
            cur.execute(
                "INSERT INTO schedule_days (doctor_id, date, day_name, total_slots, available_slots) VALUES (?, ?, ?, ?, ?)",
                (doc_id, date_str, day_name, slot_count, slot_count),
            )
            sday_id = cur.lastrowid

            for time_str, period in SLOTS:
                batch.append((sday_id, doc_id, date_str, time_str, period, 1, "DIRECT_CONSULT"))

        if batch:
            cur.executemany(
                "INSERT INTO time_slots (schedule_day_id, doctor_id, date, time, period, available, slot_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
                batch,
            )
            conn.commit()
            days_in_batch = len(batch) // slot_count
            day_count += days_in_batch
            print(f"    {date_str} ({day_name}): {days_in_batch} days, {len(batch)} slots")

    total_slots = day_count * slot_count
    counts["days_created"] = day_count
    counts["slots_created"] = total_slots
    print(f"\n  Schedule days: {day_count}, Time slots: {total_slots}")

    conn.close()
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--fees-only", action="store_true")
    args = parser.parse_args()

    print(f"Populating (fees_only={args.fees_only}, days={args.days})...")
    c = populate(days=args.days, db_path=args.db, fees_only=args.fees_only)
    print(f"Done: {c['fees_updated']} fees, {c['days_created']} days, {c['slots_created']} slots")
