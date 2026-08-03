import sqlite3
conn = sqlite3.connect('data/db/knowledge_base.db')
c = conn.cursor()
c.execute("SELECT id, name FROM doctors WHERE name LIKE '%Susan%'")
for r in c.fetchall():
    print(f"Doctor: {r[0]} - {r[1]}")
    c.execute("SELECT COUNT(*) FROM time_slots WHERE doctor_id = ?", (r[0],))
    print(f"  slots: {c.fetchone()[0]}")
    c.execute("SELECT DISTINCT date FROM time_slots WHERE doctor_id = ? ORDER BY date", (r[0],))
    dates = [r2[0] for r2 in c.fetchall()]
    print(f"  dates: {dates[:5]}...")

# Also show what error the WF returns
import httpx
r = httpx.get("http://localhost:8001/appointments/availability", params={
    "client_id": "gleneagles_001",
    "doctor_id": "dr-susan-george--chn",
    "date": "2026-07-28"
}, timeout=10)
print(f"\nWF response: {r.status_code}")
print(f"  {r.json()}")

conn.close()
