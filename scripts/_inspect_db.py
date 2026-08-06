from apps.workflows.services.dashboard_service import DashboardService

d = DashboardService("gleneagles_001").build()
print("ops_date:", d["ops_date"])
print("ops_dates:", d["ops_dates"])
print("today_appointments:", len(d["today_appointments"]))
print("upcoming_appointments:", len(d["upcoming_appointments"]))
print("recent_appointments:", len(d["recent_appointments"]))
print("summary today_booked:", d["summary"]["today_booked"], "| today_appointments:", d["summary"]["today_appointments"], "| upcoming:", d["summary"]["upcoming"])
print("alerts:", [a["text"] for a in d["alerts"]])
for a in d["today_appointments"][:5]:
    print(" ", a["appointment_id"], a["patient_name"], a["date"], a["time"], a["status"], a["booked_through"], "|", a["doctor_name"])
