"""
Gleneagles Doctor Appointment Knowledge Base — Dashboard
Run:  streamlit run dashboard.py
"""
from __future__ import annotations

import json
import math
import random
import sqlite3
import urllib.parse
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Gleneagles · Doctor KB",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design system ─────────────────────────────────────────────────────────────
C_BG       = "#0d1117"
C_SURFACE  = "#161b22"
C_SURFACE2 = "#1c2128"
C_BORDER   = "#30363d"
C_BORDER2  = "#3d444d"
C_TEXT     = "#e6edf3"
C_MUTED    = "#8b949e"
C_BLUE     = "#58a6ff"
C_GREEN    = "#3fb950"
C_AMBER    = "#e3b341"
C_PURPLE   = "#d2a8ff"
C_RED      = "#f85149"

CHART_BG   = C_BG
PAPER_BG   = C_SURFACE
GRID_COLOR = C_BORDER
FONT_COLOR = C_TEXT

CHART_LAYOUT = dict(
    paper_bgcolor=PAPER_BG,
    plot_bgcolor=CHART_BG,
    font=dict(color=FONT_COLOR, family="Inter, Segoe UI, sans-serif", size=12),
    margin=dict(t=30, b=20, l=20, r=20),
    xaxis=dict(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR, color=C_MUTED),
    yaxis=dict(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR, color=C_MUTED),
)

CITY_COLORS = {
    "Chennai":   C_BLUE,
    "Bengaluru": C_GREEN,
    "Mumbai":    C_AMBER,
    "Hyderabad": C_PURPLE,
}

STATUS_META = {
    "booked":      ("Booked",      "badge-blue"),
    "checked_in":  ("Checked In",  "badge-green"),
    "completed":   ("Completed",   "badge-green"),
    "cancelled":   ("Cancelled",   "badge-red"),
    "rescheduled": ("Rescheduled", "badge-amber"),
    "pending":     ("Pending",     "badge-amber"),
}

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

*, html, body {{ font-family: 'Inter', 'Segoe UI', sans-serif !important; }}

[data-testid="stAppViewContainer"]  {{ background: {C_BG}; }}
[data-testid="stSidebar"]           {{ background: {C_SURFACE}; border-right: 1px solid {C_BORDER}; }}
[data-testid="stSidebarNav"]        {{ display: none; }}
[data-testid="stHeader"]            {{ background: transparent; }}
[data-testid="stToolbar"]           {{ display: none; }}
footer                              {{ display: none; }}

/* ── Metric cards ── */
[data-testid="metric-container"] {{
    background: {C_SURFACE};
    border: 1px solid {C_BORDER};
    border-radius: 16px;
    padding: 1.1rem 1.3rem;
    transition: border-color .2s;
}}
[data-testid="metric-container"]:hover {{ border-color: {C_BLUE}; }}
[data-testid="metric-container"] label {{
    color: {C_MUTED} !important;
    font-size: 0.75rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: .05em;
}}
[data-testid="stMetricValue"] {{
    color: {C_TEXT} !important;
    font-size: 1.9rem !important;
    font-weight: 700 !important;
    line-height: 1.2 !important;
}}
[data-testid="stMetricDelta"] {{ font-size: 0.78rem !important; }}

/* ── Section header ── */
.sh {{
    display: flex; align-items: center; gap: .55rem;
    font-size: 1rem; font-weight: 600; color: {C_TEXT};
    margin: 1.6rem 0 .8rem;
}}
.sh::before {{
    content: ''; display: inline-block;
    width: 3px; height: 1.1em;
    background: {C_BLUE}; border-radius: 2px;
}}

/* ── Page hero ── */
.hero {{
    background: linear-gradient(135deg, {C_SURFACE} 0%, #0d1f3c 100%);
    border: 1px solid {C_BORDER};
    border-radius: 20px;
    padding: 2rem 2.5rem;
    margin-bottom: 1.5rem;
}}
.hero h1 {{ color: {C_TEXT}; font-size: 1.8rem; font-weight: 700; margin: 0 0 .3rem; }}
.hero p  {{ color: {C_MUTED}; font-size: .9rem; margin: 0; }}
.hero-badge {{
    display: inline-block; background: rgba(88,166,255,.12);
    color: {C_BLUE}; border: 1px solid rgba(88,166,255,.3);
    border-radius: 20px; font-size: .72rem; font-weight: 600;
    padding: 3px 10px; margin-right: 6px;
}}

/* ── Card grid ── */
.card-grid-3 {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: .75rem;
    align-items: start;
    margin-top: .5rem;
}}
.card-grid-2 {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: .75rem;
    align-items: start;
    margin-top: .5rem;
}}
@media (max-width: 900px) {{
    .card-grid-3, .card-grid-2 {{ grid-template-columns: 1fr 1fr; }}
}}
@media (max-width: 600px) {{
    .card-grid-3, .card-grid-2 {{ grid-template-columns: 1fr; }}
}}

/* ── Doctor card ── */
.dcard {{
    background: {C_SURFACE};
    border: 1px solid {C_BORDER};
    border-radius: 14px;
    padding: 1rem 1.1rem;
    transition: border-color .2s, box-shadow .2s;
    position: relative;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    gap: .45rem;
}}
.dcard::before {{
    content: ''; position: absolute; top:0; left:0; right:0;
    height: 2px;
    background: linear-gradient(90deg, {C_BLUE}, {C_PURPLE});
    opacity: 0;
    transition: opacity .2s;
}}
.dcard:hover {{ border-color: {C_BLUE}; box-shadow: 0 4px 20px rgba(88,166,255,.08); }}
.dcard:hover::before {{ opacity: 1; }}

.avatar {{
    width: 40px; height: 40px; border-radius: 50%;
    background: linear-gradient(135deg, #1f3a5c, #0d2137);
    border: 1.5px solid {C_BLUE};
    display: flex; align-items: center; justify-content: center;
    font-size: .85rem; font-weight: 700; color: {C_BLUE};
    flex-shrink: 0;
}}
.dcard-top {{ display: flex; align-items: center; gap: .6rem; }}
.dcard-info {{ flex: 1; min-width: 0; }}
.dname  {{ font-size: .9rem; font-weight: 600; color: {C_TEXT}; margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.ddesig {{ font-size: .7rem; color: {C_BLUE}; margin: .1rem 0 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.dspec  {{ font-size: .75rem; color: {C_MUTED}; margin: 0; }}

.badge {{
    display: inline-flex; align-items: center; gap: 4px;
    border-radius: 20px; font-size: .68rem; font-weight: 600;
    padding: 2px 9px; margin: 2px 3px 0 0;
}}
.badge-default {{ background: {C_SURFACE2}; color: {C_MUTED}; border: 1px solid {C_BORDER}; }}
.badge-blue    {{ background: rgba(88,166,255,.1); color: {C_BLUE}; border: 1px solid rgba(88,166,255,.25); }}
.badge-green   {{ background: rgba(63,185,80,.1); color: {C_GREEN}; border: 1px solid rgba(63,185,80,.25); }}
.badge-amber   {{ background: rgba(227,179,65,.1); color: {C_AMBER}; border: 1px solid rgba(227,179,65,.25); }}
.badge-purple  {{ background: rgba(210,168,255,.1); color: {C_PURPLE}; border: 1px solid rgba(210,168,255,.25); }}

.avail-dot {{
    width: 7px; height: 7px; border-radius: 50%;
    display: inline-block; margin-right: 4px;
}}
.dot-green {{ background: {C_GREEN}; box-shadow: 0 0 6px {C_GREEN}; }}
.dot-red   {{ background: {C_MUTED}; }}

.book-btn {{
    display: inline-block; margin-top: .65rem;
    background: linear-gradient(135deg, #1a7f37, #238636);
    color: #fff !important;
    border-radius: 8px; padding: 5px 14px;
    font-size: .75rem; font-weight: 600;
    text-decoration: none; transition: opacity .15s;
}}
.book-btn:hover {{ opacity: .88; }}

/* ── Hospital card ── */
.hcard {{
    background: {C_SURFACE};
    border: 1px solid {C_BORDER};
    border-radius: 16px;
    padding: 1.25rem 1.4rem;
    margin-bottom: .75rem;
    transition: border-color .2s;
}}
.hcard:hover {{ border-color: {C_AMBER}; }}
.htitle {{ font-size: 1rem; font-weight: 600; color: {C_TEXT}; margin: 0 0 .2rem; }}
.hloc   {{ font-size: .78rem; color: {C_MUTED}; margin: 0 0 .6rem; }}
.hbar   {{
    background: {C_BORDER}; border-radius: 4px; height: 6px; margin: .5rem 0 .3rem;
}}
.hbar-fill {{
    height: 6px; border-radius: 4px;
    background: linear-gradient(90deg, {C_BLUE}, {C_PURPLE});
    transition: width .4s;
}}

/* ── Sidebar nav ── */
.nav-item {{
    display: flex; align-items: center; gap: .6rem;
    padding: .5rem .75rem; border-radius: 8px;
    font-size: .875rem; color: {C_MUTED};
    cursor: pointer; margin: 2px 0;
    transition: background .15s, color .15s;
}}
.nav-item:hover {{ background: {C_SURFACE2}; color: {C_TEXT}; }}
.nav-item.active {{ background: rgba(88,166,255,.12); color: {C_BLUE}; font-weight: 600; }}

/* ── Stat chip in sidebar ── */
.stat-chip {{
    display: flex; justify-content: space-between; align-items: center;
    background: {C_SURFACE2}; border: 1px solid {C_BORDER};
    border-radius: 10px; padding: .45rem .75rem; margin: .35rem 0;
    font-size: .8rem;
}}
.stat-chip span:first-child {{ color: {C_MUTED}; }}
.stat-chip span:last-child  {{ color: {C_TEXT}; font-weight: 600; }}

/* ── Divider ── */
hr {{ border-color: {C_BORDER} !important; margin: .75rem 0 !important; }}

/* ── Expander ── */
[data-testid="stExpander"] {{
    background: {C_SURFACE} !important;
    border: 1px solid {C_BORDER} !important;
    border-radius: 12px !important;
    margin-bottom: .5rem;
}}
[data-testid="stExpander"] summary {{
    font-size: .875rem; color: {C_TEXT}; padding: .6rem 1rem;
}}

/* ── Inputs ── */
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] select {{
    background: {C_SURFACE2} !important;
    border: 1px solid {C_BORDER} !important;
    color: {C_TEXT} !important;
    border-radius: 8px !important;
}}

/* ── Receptionist: KPI cards ── */
.kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: .65rem;
    margin-top: .5rem;
}}
.kpi-card {{
    background: {C_SURFACE};
    border: 1px solid {C_BORDER};
    border-top: 2px solid {C_BLUE};
    border-radius: 14px;
    padding: .85rem 1rem;
    transition: border-color .2s;
}}
.kpi-card:hover {{ border-color: {C_BLUE}; }}
.kpi-label {{ font-size: .68rem; color: {C_MUTED}; text-transform: uppercase; letter-spacing: .05em; font-weight: 600; }}
.kpi-value {{ font-size: 1.65rem; font-weight: 700; color: {C_TEXT}; line-height: 1.3; }}
.kpi-sub   {{ font-size: .7rem; color: {C_MUTED}; }}

/* ── Receptionist: appointment table ── */
.appt-head, .appt-row {{
    display: grid;
    grid-template-columns: 1.1fr 2fr 2fr 1.3fr .7fr;
    gap: .6rem;
    align-items: center;
    padding: .55rem .9rem;
}}
.appt-head {{
    color: {C_MUTED};
    font-size: .72rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: .05em;
    border-bottom: 1px solid {C_BORDER};
    margin-top: .4rem;
}}
.appt-row {{
    border-bottom: 1px solid {C_BORDER};
    font-size: .85rem; color: {C_TEXT};
    transition: background .15s;
}}
.appt-row:hover {{ background: {C_SURFACE2}; }}

/* ── Receptionist: doctor availability table ── */
.doc-head, .doc-row {{
    display: grid;
    grid-template-columns: 2.2fr 2.2fr 1fr;
    gap: .6rem;
    align-items: center;
    padding: .5rem .9rem;
}}
.doc-head {{
    color: {C_MUTED};
    font-size: .72rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: .05em;
    border-bottom: 1px solid {C_BORDER};
    margin-top: .4rem;
}}
.doc-row {{
    border-bottom: 1px solid {C_BORDER};
    font-size: .85rem; color: {C_TEXT};
    transition: background .15s;
}}
.doc-row:hover {{ background: {C_SURFACE2}; }}

.badge-red {{ background: rgba(248,81,73,.1); color: {C_RED}; border: 1px solid rgba(248,81,73,.25); }}

/* ── Receptionist: appointment detail panel ── */
.detail-panel {{
    background: {C_SURFACE};
    border: 1px solid {C_BLUE};
    border-radius: 16px;
    padding: 1.3rem 1.5rem;
    margin-top: .9rem;
}}
.detail-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: .55rem 1.6rem;
    margin: .9rem 0;
}}
.detail-item {{ display: flex; gap: .6rem; font-size: .85rem; }}
.detail-item .k {{ color: {C_MUTED}; min-width: 128px; flex-shrink: 0; }}
.detail-item .v {{ color: {C_TEXT}; font-weight: 600; }}
.detail-sep {{ border-top: 1px dashed {C_BORDER}; margin: .8rem 0; }}
.detail-block .bk {{ font-size: .72rem; color: {C_BLUE}; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; margin-bottom: .25rem; }}
.detail-block .bv {{ font-size: .88rem; color: {C_TEXT}; margin-bottom: .6rem; }}
</style>
""", unsafe_allow_html=True)


# ── DB helpers ─────────────────────────────────────────────────────────────────
_DB_PATH = "data/db/knowledge_base.db"

def _conn():
    if not Path(_DB_PATH).exists():
        return None
    c = sqlite3.connect(_DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _ensure_appointment_columns() -> None:
    """Idempotently add receptionist-facing columns to the appointments table."""
    conn = _conn()
    if conn is None:
        return
    try:
        existing = {r[1] for r in conn.execute("PRAGMA table_info(appointments)")}
        for col, ddl in {
            "patient_name":    "TEXT",
            "age":             "INTEGER",
            "gender":          "TEXT",
            "city":            "TEXT",
            "booked_through":  "TEXT",
            "medical_history": "TEXT",
            "previous_visit":  "TEXT",
        }.items():
            if col not in existing:
                conn.execute(f"ALTER TABLE appointments ADD COLUMN {col} {ddl}")
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


# ── Data loaders ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_doctors() -> pd.DataFrame:
    conn = _conn()
    if conn is None:
        return pd.DataFrame()
    try:
        df = pd.read_sql_query("""
            SELECT d.id, d.name, d.first_name, d.last_name, d.gender,
                   d.designation, d.speciality, d.specializations,
                   d.qualifications, d.languages, d.experience_years,
                   d.consultation_fee, d.bio, d.booking_url, d.profile_url,
                   d.numeric_doctor_id, d.location_id, d.appointment_type,
                   d.profile_image_url,
                   d.next_available, d.total_available_slots,
                   d.consultation_types, d.working_days,
                   h.id AS hospital_id, h.name AS hospital_name,
                   h.city, h.state
            FROM doctors d
            LEFT JOIN hospitals h ON h.location_id = d.location_id
            ORDER BY d.name
        """, conn)

        str_cols = ["specializations","qualifications","languages",
                    "hospital_name","city","state","designation","bio",
                    "booking_url","profile_url","consultation_types","working_days"]
        for c in str_cols:
            if c in df.columns:
                df[c] = df[c].fillna("")

        df["hospital_name"] = df["hospital_name"].replace("", "Unknown Hospital")
        df["hospitals"] = df["hospital_name"]
        df["cities"]    = df["city"]

        df["specialization"] = df["specializations"].str.split(",").str[0].str.strip()
        df["specialization"] = df["specialization"].where(
            df["specialization"] != "", df["speciality"]
        ).fillna("General Medicine")

        df["experience_years"] = pd.to_numeric(df["experience_years"], errors="coerce")
        df["has_slots"] = (df["total_available_slots"].fillna(0) > 0)
        return df
    except Exception as exc:
        st.error(f"DB error: {exc}")
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=300)
def load_stats() -> dict:
    conn = _conn()
    if conn is None:
        return {}
    try:
        cur = conn.cursor()
        out = {}
        for k, sql in {
            "total_doctors":          "SELECT COUNT(*) FROM doctors",
            "total_hospitals":        "SELECT COUNT(*) FROM hospitals",
            "doctors_with_schedules": "SELECT COUNT(*) FROM doctors WHERE next_available IS NOT NULL",
            "doctors_with_slots":     "SELECT COUNT(*) FROM doctors WHERE total_available_slots > 0",
            "total_available_slots":  "SELECT COALESCE(SUM(total_available_slots),0) FROM doctors",
            "total_schedule_days":    "SELECT COUNT(*) FROM schedule_days",
            "total_time_slots":       "SELECT COUNT(*) FROM time_slots",
        }.items():
            out[k] = cur.execute(sql).fetchone()[0]
        return out
    finally:
        conn.close()


@st.cache_data(ttl=300)
def load_hospitals() -> pd.DataFrame:
    conn = _conn()
    if conn is None:
        return pd.DataFrame()
    try:
        return pd.read_sql_query("""
            SELECT h.id, h.name, h.branch, h.city, h.state, h.location_id,
                   COUNT(DISTINCT d.id) AS doctor_count,
                   COALESCE(SUM(d.total_available_slots), 0) AS total_slots,
                   COUNT(DISTINCT CASE WHEN d.total_available_slots > 0 THEN d.id END) AS doctors_with_slots
            FROM hospitals h
            LEFT JOIN doctors d ON d.location_id = h.location_id
            GROUP BY h.id
            ORDER BY doctor_count DESC
        """, conn)
    finally:
        conn.close()


@st.cache_data(ttl=300)
def load_schedules() -> pd.DataFrame:
    conn = _conn()
    if conn is None:
        return pd.DataFrame()
    try:
        df = pd.read_sql_query("""
            SELECT d.id AS doctor_id,
                   d.name AS doctor_name,
                   d.numeric_doctor_id,
                   h.name AS location_name,
                   h.city AS location_city,
                   d.booking_url,
                   COALESCE(d.consultation_types, '') AS consultation_types,
                   COALESCE(d.working_days, '')       AS working_days,
                   COALESCE(d.next_available, '')     AS next_available,
                   d.total_available_slots,
                   (SELECT COUNT(*) FROM schedule_days sd WHERE sd.doctor_id = d.id) AS days_count
            FROM doctors d
            LEFT JOIN hospitals h ON h.location_id = d.location_id
            WHERE d.next_available IS NOT NULL OR d.total_available_slots > 0
            ORDER BY d.total_available_slots DESC
        """, conn)
        for c in ["location_name","location_city","booking_url",
                  "consultation_types","working_days","next_available"]:
            if c in df.columns:
                df[c] = df[c].fillna("")
        return df
    except Exception as exc:
        st.error(f"Schedule load error: {exc}")
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=300)
def load_schedule_days() -> pd.DataFrame:
    """Returns raw schedule_days rows; joined to sched_df in-page to avoid Arrow serialization issues."""
    conn = _conn()
    if conn is None:
        return pd.DataFrame()
    try:
        return pd.read_sql_query("""
            SELECT doctor_id, date, day_name, available_slots, total_slots
            FROM schedule_days WHERE available_slots > 0 ORDER BY date
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=15)
def load_appointments() -> pd.DataFrame:
    conn = _conn()
    if conn is None:
        return pd.DataFrame()
    try:
        df = pd.read_sql_query("""
            SELECT a.id AS appointment_id, a.client_id, a.patient_phone,
                   a.patient_name, a.age, a.gender, a.city, a.booked_through,
                   a.medical_history, a.previous_visit, a.date, a.time,
                   a.status, a.notes, a.slot_id, a.created_at, a.cancelled_at,
                   a.doctor_id, d.name AS doctor_name, d.speciality AS department
            FROM appointments a
            LEFT JOIN doctors d ON d.id = a.doctor_id
            ORDER BY a.date DESC, a.time
        """, conn)
        for col in ["patient_name", "city", "gender", "medical_history", "previous_visit"]:
            df[col] = df[col].fillna("")
        # Legacy rows were created by the WhatsApp agent.
        df["booked_through"] = df["booked_through"].fillna("WhatsApp")
        return df
    except Exception as exc:
        st.error(f"Appointments load error: {exc}")
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=30)
def load_doctor_availability(min_date: str) -> pd.DataFrame:
    conn = _conn()
    if conn is None:
        return pd.DataFrame()
    try:
        return pd.read_sql_query("""
            SELECT d.name AS doctor_name, d.speciality AS department,
                   COUNT(t.id) AS open_slots, MIN(t.date) AS next_available
            FROM time_slots t
            JOIN doctors d ON d.id = t.doctor_id
            WHERE t.available = 1 AND t.date >= :min
            GROUP BY d.id, d.name, d.speciality
            ORDER BY open_slots DESC, doctor_name
            LIMIT 15
        """, conn, params={"min": min_date})
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=15)
def load_available_slots(doctor_id: str, min_date: str) -> pd.DataFrame:
    conn = _conn()
    if conn is None:
        return pd.DataFrame()
    try:
        return pd.read_sql_query("""
            SELECT id AS slot_id, date, time
            FROM time_slots
            WHERE doctor_id = :did AND available = 1
                  AND date >= :min AND date <= :max
            ORDER BY date, time
        """, conn, params={
            "did": doctor_id,
            "min": min_date,
            "max": (datetime.strptime(min_date, "%Y-%m-%d") + timedelta(days=14)).isoformat(),
        })
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

def initials(name: str) -> str:
    parts = name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper() if name else "DR"

def city_color(city: str) -> str:
    return CITY_COLORS.get(city, C_MUTED)

def slot_badge(slots) -> str:
    n = int(slots) if pd.notna(slots) else 0
    if n > 0:
        return f'<span class="badge badge-green"><span class="avail-dot dot-green"></span>{n} slots</span>'
    return f'<span class="badge badge-default"><span class="avail-dot dot-red"></span>No slots</span>'

def specialty_avail(doctors_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, d in doctors_df.iterrows():
        specs = [s.strip() for s in (d["specializations"] or "").split(",") if s.strip()]
        if not specs:
            specs = [d.get("speciality") or "General Medicine"]
        avail = d.get("total_available_slots") or 0
        for s in specs:
            rows.append({"specialization": s, "avail": avail, "doctor_id": d["id"]})
    if not rows:
        return pd.DataFrame()
    tmp = pd.DataFrame(rows)
    return (
        tmp.groupby("specialization")
        .agg(doctor_count=("doctor_id","nunique"),
             total_slots=("avail","sum"),
             doctors_with_slots=("avail", lambda x: (x>0).sum()))
        .reset_index()
        .sort_values("total_slots", ascending=False)
    )


# ── Receptionist dashboard ────────────────────────────────────────────────────

def fmt_date(d) -> str:
    try:
        return datetime.strptime(str(d), "%Y-%m-%d").strftime("%d %b %Y")
    except ValueError:
        return str(d or "—")


def fmt_time(t) -> str:
    try:
        h, m = str(t).split(":")
        hh, mm = int(h), int(m)
        return f"{hh % 12 or 12:02d}:{mm:02d} {'AM' if hh < 12 else 'PM'}"
    except (ValueError, TypeError):
        return str(t or "—")


def patient_label(a) -> str:
    return a["patient_name"] or str(a["patient_phone"])


def status_badge_html(status: str) -> str:
    label, cls = STATUS_META.get(status, (str(status).title() or "Unknown", "badge-default"))
    return f'<span class="badge {cls}">{label}</span>'


def kpi_card(label: str, value: int, color: str, sub: str = "") -> str:
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return f"""
<div class="kpi-card" style="border-top-color:{color}">
  <div class="kpi-label">{label}</div>
  <div class="kpi-value">{value:,}</div>{sub_html}
</div>"""


# ── Receptionist actions (direct SQLite writes) ───────────────────────────────

def update_appointment_status(appt_id: str, status: str) -> None:
    conn = _conn()
    try:
        conn.execute("UPDATE appointments SET status = ? WHERE id = ?", (status, appt_id))
        conn.commit()
    finally:
        conn.close()


def cancel_appointment(appt_id: str) -> None:
    conn = _conn()
    try:
        row = conn.execute("SELECT slot_id FROM appointments WHERE id = ?", (appt_id,)).fetchone()
        if row and row[0]:
            conn.execute("UPDATE time_slots SET available = 1 WHERE id = ?", (row[0],))
        conn.execute(
            "UPDATE appointments SET status = 'cancelled', cancelled_at = ? WHERE id = ?",
            (datetime.now().isoformat(), appt_id),
        )
        conn.commit()
    finally:
        conn.close()


def reschedule_appointment(appt_id: str, new_slot_id: int, new_date: str, new_time: str) -> None:
    conn = _conn()
    try:
        row = conn.execute("SELECT slot_id FROM appointments WHERE id = ?", (appt_id,)).fetchone()
        if row and row[0]:
            conn.execute("UPDATE time_slots SET available = 1 WHERE id = ?", (row[0],))
        conn.execute("UPDATE time_slots SET available = 0 WHERE id = ?", (new_slot_id,))
        conn.execute(
            "UPDATE appointments SET slot_id = ?, date = ?, time = ?, status = 'rescheduled' WHERE id = ?",
            (new_slot_id, new_date, new_time, appt_id),
        )
        conn.commit()
    finally:
        conn.close()


def refresh_appointments(msg: str) -> None:
    load_appointments.clear()
    load_doctor_availability.clear()
    load_available_slots.clear()
    st.toast(msg)
    st.rerun()


def whatsapp_reminder_url(a) -> str:
    phone = str(a["patient_phone"]).lstrip("+").replace(" ", "")
    msg = (f"Dear {a['patient_name'] or 'Patient'}, this is a reminder for your appointment "
           f"with {a['doctor_name']} at Gleneagles Hospitals on {fmt_date(a['date'])} "
           f"at {fmt_time(a['time'])}. Appointment ID: {a['appointment_id']}. "
           f"Please arrive 15 minutes early.")
    return f"https://wa.me/{phone}?text={urllib.parse.quote(msg)}"


def render_token(a) -> None:
    """Print-friendly OPD token card (window.print() prints only this iframe)."""
    token_no = f"TK-{str(a['appointment_id'])[-6:].upper()}"
    html = f"""<div style="font-family:'Inter',sans-serif;background:#ffffff;color:#1f2328;max-width:340px;margin:0 auto;border-radius:16px;padding:1.3rem 1.5rem;text-align:center">
  <div style="font-size:1.05rem;font-weight:800;letter-spacing:.05em">GLENEAGLES HOSPITALS</div>
  <div style="font-size:.7rem;color:#57606a;margin-top:.15rem">OPD APPOINTMENT TOKEN</div>
  <div style="font-size:1.5rem;font-weight:800;letter-spacing:.12em;color:#0969da;border:2px dashed #0969da;border-radius:10px;padding:.4rem 0;margin:.75rem 0 1rem">{token_no}</div>
  <table style="width:100%;font-size:.82rem;border-collapse:collapse">
    <tr><td style="padding:.2rem 0;color:#57606a">Patient</td><td style="padding:.2rem 0;font-weight:600;text-align:right">{patient_label(a)}</td></tr>
    <tr><td style="padding:.2rem 0;color:#57606a">Doctor</td><td style="padding:.2rem 0;font-weight:600;text-align:right">{a['doctor_name']}</td></tr>
    <tr><td style="padding:.2rem 0;color:#57606a">Department</td><td style="padding:.2rem 0;font-weight:600;text-align:right">{a['department'] or '—'}</td></tr>
    <tr><td style="padding:.2rem 0;color:#57606a">Date</td><td style="padding:.2rem 0;font-weight:600;text-align:right">{fmt_date(a['date'])}</td></tr>
    <tr><td style="padding:.2rem 0;color:#57606a">Time</td><td style="padding:.2rem 0;font-weight:600;text-align:right">{fmt_time(a['time'])}</td></tr>
  </table>
  <div style="font-size:.66rem;color:#8b949e;margin-top:.85rem">Please arrive 15 minutes early and carry this token</div>
</div>
<div style="text-align:center;margin-top:.9rem">
  <button onclick="window.print()" style="background:#0969da;color:#fff;border:0;border-radius:8px;padding:.55rem 1.4rem;font-size:.85rem;font-weight:600;cursor:pointer">🖨️ Print Token</button>
</div>"""
    components.html(html, height=420)


def render_appointment_panel(a, op_date: str) -> None:
    """Detail view + actions for one appointment (opened via the View button)."""
    aid = a["appointment_id"]
    label, _ = STATUS_META.get(a["status"], (a["status"], "badge-default"))
    age = f"{int(a['age'])}" if pd.notna(a["age"]) else "—"

    st.markdown(f"""
    <div class="detail-panel">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:.5rem;flex-wrap:wrap">
        <div style="font-size:1.05rem;font-weight:700;color:{C_TEXT}">📋 Appointment Details</div>
        {status_badge_html(a['status'])}
      </div>
      <div class="detail-grid">
        <div class="detail-item"><span class="k">Appointment ID</span><span class="v">{aid}</span></div>
        <div class="detail-item"><span class="k">Patient Name</span><span class="v">{patient_label(a)}</span></div>
        <div class="detail-item"><span class="k">Age</span><span class="v">{age}</span></div>
        <div class="detail-item"><span class="k">Gender</span><span class="v">{a['gender'] or '—'}</span></div>
        <div class="detail-item"><span class="k">Mobile</span><span class="v">{a['patient_phone']}</span></div>
        <div class="detail-item"><span class="k">City</span><span class="v">{a['city'] or '—'}</span></div>
        <div class="detail-item"><span class="k">Department</span><span class="v">{a['department'] or '—'}</span></div>
        <div class="detail-item"><span class="k">Doctor</span><span class="v">{a['doctor_name']}</span></div>
        <div class="detail-item"><span class="k">Appointment Date</span><span class="v">{fmt_date(a['date'])}</span></div>
        <div class="detail-item"><span class="k">Time Slot</span><span class="v">{fmt_time(a['time'])}</span></div>
        <div class="detail-item"><span class="k">Status</span><span class="v">{label}</span></div>
        <div class="detail-item"><span class="k">Booked Through</span><span class="v">{a['booked_through'] or '—'}</span></div>
      </div>
      <div class="detail-sep"></div>
      <div class="detail-block">
        <div class="bk">Medical History</div>
        <div class="bv">{a['medical_history'] or '—'}</div>
        <div class="bk">Previous Visit</div>
        <div class="bv">{a['previous_visit'] or '—'}</div>
        <div class="bk">Remarks</div>
        <div class="bv">{a['notes'] or '—'}</div>
      </div>
    </div>""", unsafe_allow_html=True)

    st.markdown(f'<div style="font-size:.72rem;color:{C_MUTED};text-transform:uppercase;font-weight:700;letter-spacing:.06em;margin:.85rem 0 .4rem">Actions</div>',
                unsafe_allow_html=True)
    ac = st.columns(6)
    with ac[0]:
        if st.button("✅ Check-In", key=f"ci_{aid}", use_container_width=True):
            update_appointment_status(aid, "checked_in")
            refresh_appointments("Patient checked in ✅")
    with ac[1]:
        if st.button("🔄 Reschedule", key=f"rs_{aid}", use_container_width=True):
            st.session_state["resched_for"] = aid
            st.rerun()
    with ac[2]:
        if st.button("❌ Cancel Appointment", key=f"cn_{aid}", use_container_width=True):
            cancel_appointment(aid)
            refresh_appointments("Appointment cancelled ❌")
    with ac[3]:
        if st.button("🖨️ Print Token", key=f"pt_{aid}", use_container_width=True):
            render_token(a)
    with ac[4]:
        st.link_button("💬 WhatsApp Reminder", whatsapp_reminder_url(a), use_container_width=True)
    with ac[5]:
        if st.button("✕ Close", key=f"cl_{aid}", use_container_width=True):
            st.session_state.pop("selected_appt", None)
            st.session_state.pop("resched_for", None)
            st.rerun()

    # ── Reschedule flow ──
    if st.session_state.get("resched_for") == aid:
        slots = load_available_slots(a["doctor_id"], op_date)
        if slots.empty:
            st.warning("No available slots for this doctor in the next 14 days.")
            return
        labels = [f"{fmt_date(r['date'])} · {fmt_time(r['time'])}" for _, r in slots.iterrows()]
        st.selectbox("Select new slot", labels, key=f"slot_{aid}")
        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button("Confirm Reschedule", key=f"cf_{aid}", type="primary", use_container_width=True):
                r = slots.iloc[labels.index(st.session_state[f"slot_{aid}"])]
                reschedule_appointment(aid, int(r["slot_id"]), r["date"], r["time"])
                st.session_state.pop("resched_for", None)
                refresh_appointments(f"Rescheduled to {fmt_date(r['date'])} {fmt_time(r['time'])} 🔄")
        with c2:
            if st.button("Cancel", key=f"cx_{aid}", use_container_width=True):
                st.session_state.pop("resched_for", None)
                st.rerun()


def render_receptionist_dashboard(appts_df: pd.DataFrame) -> None:
    """Receptionist cockpit: today's summary, queue, search & quick actions."""
    today = date.today().isoformat()
    if appts_df.empty:
        op_date = today
    elif not (appts_df["date"] == today).any():
        op_date = appts_df["date"].max()   # demo-friendly: fall back to data date
    else:
        op_date = today

    op_date = st.date_input(
        "Operations date",
        value=datetime.strptime(op_date, "%Y-%m-%d").date(),
    ).isoformat()
    op_label = fmt_date(op_date)
    day = appts_df[appts_df["date"] == op_date]

    def count(mask) -> int:
        return int(mask.sum())

    # ── Today's summary ──
    summary = [
        ("Appointments Booked", count(day["status"] == "booked"),            C_BLUE),
        ("Completed",           count(day["status"] == "completed"),         C_GREEN),
        ("Checked In",          count(day["status"] == "checked_in"),        C_GREEN),
        ("Cancelled",           count(day["status"] == "cancelled"),         C_RED),
        ("Rescheduled",         count(day["status"] == "rescheduled"),       C_AMBER),
        ("Pending",             count(day["status"] == "pending"),           C_AMBER),
        ("Walk-in Patients",    count(day["booked_through"] == "Walk-in"),   C_PURPLE),
        ("WhatsApp Bookings",   count(day["booked_through"] == "WhatsApp"),  C_GREEN),
        ("Reception Bookings",  count(day["booked_through"] == "Reception"), C_BLUE),
    ]
    st.markdown(f'<div class="sh">Today\'s Summary · {op_label}</div>', unsafe_allow_html=True)
    st.markdown('<div class="kpi-grid">' + "".join(kpi_card(l, v, c) for l, v, c in summary) + '</div>',
                unsafe_allow_html=True)

    # ── Overview cards ──
    avail = load_doctor_availability(op_date)
    overview = [
        ("Today's Appointments",   len(day),                                                       C_BLUE),
        ("Checked-In Patients",    count(day["status"] == "checked_in"),                           C_GREEN),
        ("Upcoming Appointments",  count((appts_df["date"] > op_date) & (appts_df["status"] == "booked")), C_PURPLE),
        ("Cancelled Appointments", count(day["status"] == "cancelled"),                            C_RED),
        ("Doctors Available",      len(avail),                                                     C_GREEN),
        ("Pending Requests",       count(appts_df["status"] == "pending"),                         C_AMBER),
    ]
    st.markdown('<div class="sh">Overview</div>', unsafe_allow_html=True)
    st.markdown('<div class="kpi-grid">' + "".join(kpi_card(l, v, c) for l, v, c in overview) + '</div>',
                unsafe_allow_html=True)

    # ── Search patient ──
    st.markdown('<div class="sh">Search Patient</div>', unsafe_allow_html=True)
    q = st.text_input("🔍 Search Patient", placeholder="Name or phone number…", label_visibility="collapsed")
    rows = day.sort_values("time")
    if q:
        ql = q.strip().lower()
        rows = rows[
            rows["patient_name"].str.lower().str.contains(ql, na=False)
            | rows["patient_phone"].str.contains(ql, na=False)
        ]

    # ── Today's appointments ──
    st.markdown('<div class="sh">Today\'s Appointments</div>', unsafe_allow_html=True)
    if rows.empty:
        st.info("No appointments found." + (f" Matching “{q.strip()}”." if q else ""))
    else:
        st.markdown(
            '<div class="appt-head"><span>Time</span><span>Patient</span><span>Doctor</span><span>Status</span><span>View</span></div>',
            unsafe_allow_html=True,
        )
        for _, a in rows.head(50).iterrows():
            cols = st.columns([1.1, 2, 2, 1.3, 0.7])
            cols[0].markdown(f'<div style="font-weight:600;color:{C_TEXT};white-space:nowrap">{fmt_time(a["time"])}</div>',
                             unsafe_allow_html=True)
            cols[1].markdown(f'<div style="color:{C_TEXT}">{patient_label(a)}'
                             f'<div style="font-size:.72rem;color:{C_MUTED}">{a["patient_phone"]}</div></div>',
                             unsafe_allow_html=True)
            cols[2].markdown(f'<div style="color:{C_TEXT}">{a["doctor_name"]}'
                             f'<div style="font-size:.72rem;color:{C_MUTED}">{a["department"] or ""}</div></div>',
                             unsafe_allow_html=True)
            cols[3].markdown(status_badge_html(a["status"]), unsafe_allow_html=True)
            if cols[4].button("👁", key=f"view_{a['appointment_id']}", help="View appointment details"):
                st.session_state["selected_appt"] = a["appointment_id"]

    # ── Doctor availability ──
    st.markdown('<div class="sh">Doctor Availability</div>', unsafe_allow_html=True)
    if avail.empty:
        st.info("No open slots from this date onwards.")
    else:
        st.markdown(
            '<div class="doc-head"><span>Doctor</span><span>Department</span><span>Slots</span></div>',
            unsafe_allow_html=True,
        )
        for _, r in avail.iterrows():
            st.markdown(
                f'<div class="doc-row"><span style="color:{C_TEXT};font-weight:600">{r["doctor_name"]}</span>'
                f'<span style="color:{C_MUTED}">{r["department"]}</span>'
                f'<span>{slot_badge(r["open_slots"])}</span></div>',
                unsafe_allow_html=True,
            )

    # ── Selected appointment panel ──
    selected = st.session_state.get("selected_appt")
    if selected:
        sel = appts_df[appts_df["appointment_id"] == selected]
        if sel.empty:
            st.session_state.pop("selected_appt", None)
        else:
            render_appointment_panel(sel.iloc[0], op_date)


@st.fragment(run_every="30s")
def receptionist_cockpit() -> None:
    """Receptionist cockpit with auto-refresh — reloads fresh data every 30s
    so bookings made elsewhere (chat, WhatsApp, other windows) appear without
    manual interaction."""
    render_receptionist_dashboard(load_appointments())


# ── Load all data ─────────────────────────────────────────────────────────────

df          = load_doctors()
stats       = load_stats()
hosp_df     = load_hospitals()
sched_df    = load_schedules()
sched_days  = load_schedule_days()

_ensure_appointment_columns()

all_cities = sorted(df["city"].dropna().unique()) if not df.empty else []


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(f"""
    <div style="padding:.75rem 0 .5rem">
      <div style="font-size:1.4rem;font-weight:800;color:{C_TEXT};letter-spacing:-.02em">
        🏥 Gleneagles
      </div>
      <div style="font-size:.75rem;color:{C_MUTED};margin-top:.1rem">Doctor Knowledge Base</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    page = st.radio("nav", [
        "📊  Overview",
        "🏥  Hospitals",
        "👨‍⚕️  Doctor Directory",
        "📅  Schedules",
        "🕸️  Knowledge Graph",
        "🔍  Specialty Explorer",
    ], label_visibility="collapsed")

    st.divider()

    n_doc  = stats.get("total_doctors", len(df))
    n_hosp = stats.get("total_hospitals", len(hosp_df))
    n_spec = df["specialization"].nunique() if not df.empty else 0
    n_avail = stats.get("total_available_slots", 0)

    for label, val in [
        ("Doctors",    f"{n_doc:,}"),
        ("Hospitals",  str(n_hosp)),
        ("Specialties",str(n_spec)),
        ("Open Slots", f"{n_avail:,}"),
    ]:
        st.markdown(f"""
        <div class="stat-chip">
          <span>{label}</span><span>{val}</span>
        </div>""", unsafe_allow_html=True)

    st.divider()
    db_ok = Path(_DB_PATH).exists()
    st.markdown(f"""
    <div style="font-size:.75rem;color:{C_MUTED}">
      <div style="margin-bottom:.3rem;font-weight:600;color:{C_TEXT}">Data Sources</div>
      <div style="margin:.25rem 0">{'🟢' if db_ok else '🔴'} SQLite · {stats.get('total_time_slots',0):,} time slots</div>
      <div style="margin:.25rem 0">🟢 Neo4j · semantic graph</div>
      <div style="margin:.25rem 0">🟢 ChromaDB · vector search</div>
    </div>
    """, unsafe_allow_html=True)


if df.empty:
    st.error("No data. Run `python scripts/rebuild_all.py` first.")
    st.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════

if page == "📊  Overview":
    st.markdown(f"""
    <div class="hero">
      <h1>📊 Knowledge Base Overview</h1>
      <p>Real-time analytics across all Gleneagles hospitals and indexed doctors.</p>
      <div style="margin-top:.75rem">
        {"".join(f'<span class="hero-badge">{c}</span>' for c in all_cities)}
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Receptionist cockpit (auto-refreshes every 30s) ──────────────────────
    receptionist_cockpit()

    # ── KPI row 1 ─────────────────────────────────────────────────────────────
    exp_data = pd.to_numeric(df["experience_years"], errors="coerce").dropna()
    avg_exp_val = exp_data.mean() if len(exp_data) > 0 and not pd.isna(exp_data.mean()) else None
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Doctors",    f"{stats.get('total_doctors', len(df)):,}")
    c2.metric("Hospitals",        stats.get("total_hospitals", len(hosp_df)))
    c3.metric("Specialties",      n_spec)
    c4.metric("Avg Experience",   f"{avg_exp_val:.1f} yrs" if avg_exp_val is not None else "—")
    c5.metric("Languages",        df["languages"].str.split(",").explode().str.strip().nunique())

    # ── KPI row 2 ─────────────────────────────────────────────────────────────
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Scheduled",       f"{stats.get('doctors_with_schedules',0):,}")
    s2.metric("With Open Slots", f"{stats.get('doctors_with_slots',0):,}")
    s3.metric("Available Slots", f"{stats.get('total_available_slots',0):,}")
    s4.metric("Schedule Days",   f"{stats.get('total_schedule_days',0):,}")
    s5.metric("Time Slot Rows",  f"{stats.get('total_time_slots',0):,}")

    st.markdown('<div class="sh">Hospital Network</div>', unsafe_allow_html=True)

    max_docs = hosp_df["doctor_count"].max() if not hosp_df.empty else 1
    hosp_mini_html = ""
    for _, h in hosp_df.iterrows():
        pct = int(h["doctor_count"] / max_docs * 100) if max_docs else 0
        cc  = city_color(h["city"])
        hosp_mini_html += f"""
<div class="hcard" style="border-top:2px solid {cc};margin:0">
  <div class="htitle">{h['name'].split(',')[0]}</div>
  <div class="hloc">📍 {h['city']} · {h['state']}</div>
  <div class="hbar"><div class="hbar-fill" style="width:{pct}%;background:{cc}"></div></div>
  <div style="display:flex;justify-content:space-between;font-size:.78rem">
    <span style="color:{cc};font-weight:600">{int(h['doctor_count'])} doctors</span>
    <span style="color:{C_MUTED}">{int(h.get('total_slots',0)):,} slots</span>
  </div>
</div>"""
    st.markdown(
        f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:.65rem;align-items:start">'
        f'{hosp_mini_html}</div>',
        unsafe_allow_html=True,
    )

    # ── Charts row 1 ──────────────────────────────────────────────────────────
    col_l, col_r = st.columns([3, 2])

    with col_l:
        st.markdown('<div class="sh">Top 15 Specializations</div>', unsafe_allow_html=True)
        sc = df["specialization"].value_counts().head(15).reset_index()
        sc.columns = ["Specialization", "Count"]
        fig = px.bar(sc.sort_values("Count"), x="Count", y="Specialization",
                     orientation="h", color="Count", color_continuous_scale="Blues", text="Count")
        fig.update_traces(textposition="outside", textfont_size=11)
        fig.update_coloraxes(showscale=False)
        fig.update_layout(**CHART_LAYOUT, height=460)
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown('<div class="sh">Designation Mix</div>', unsafe_allow_html=True)
        dc = df["designation"].replace("", "Unknown").value_counts().head(8).reset_index()
        dc.columns = ["Designation", "Count"]
        fig2 = px.pie(dc, values="Count", names="Designation", hole=0.58,
                      color_discrete_sequence=px.colors.qualitative.Pastel)
        fig2.update_traces(textposition="inside", textinfo="percent", textfont_size=11)
        fig2.update_layout(**CHART_LAYOUT, height=340, showlegend=True,
                           legend=dict(font=dict(size=10, color=C_MUTED), bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig2, use_container_width=True)

        st.markdown('<div class="sh">Appointment Type</div>', unsafe_allow_html=True)
        at = df["appointment_type"].fillna("Unknown").value_counts().reset_index()
        at.columns = ["Type", "Count"]
        fig_at = px.bar(at, x="Type", y="Count", color="Type",
                        color_discrete_sequence=[C_BLUE, C_GREEN, C_AMBER],
                        text="Count")
        fig_at.update_traces(textposition="outside")
        fig_at.update_layout(**CHART_LAYOUT, height=220, showlegend=False)
        st.plotly_chart(fig_at, use_container_width=True)

    # ── Charts row 2 ──────────────────────────────────────────────────────────
    col_l2, col_r2 = st.columns([3, 2])

    with col_l2:
        st.markdown('<div class="sh">Experience Distribution</div>', unsafe_allow_html=True)
        exp_df2 = df[df["experience_years"].notna()]
        fig3 = px.histogram(exp_df2, x="experience_years", nbins=18,
                            color_discrete_sequence=[C_BLUE],
                            labels={"experience_years": "Years of Experience", "count": "Doctors"})
        fig3.update_layout(**CHART_LAYOUT, height=280, bargap=0.06)
        fig3.update_traces(marker_line_color=C_BORDER, marker_line_width=1)
        st.plotly_chart(fig3, use_container_width=True)

    with col_r2:
        st.markdown('<div class="sh">Languages Spoken</div>', unsafe_allow_html=True)
        lang_s = df["languages"].str.split(",").explode().str.strip()
        lang_c = lang_s[lang_s != ""].value_counts().reset_index()
        lang_c.columns = ["Language", "Doctors"]
        fig4 = px.bar(lang_c, x="Language", y="Doctors",
                      color="Doctors", color_continuous_scale="Blues", text="Doctors")
        fig4.update_traces(textposition="outside")
        fig4.update_coloraxes(showscale=False)
        fig4.update_layout(**CHART_LAYOUT, height=280)
        st.plotly_chart(fig4, use_container_width=True)

    # ── Specialty availability ─────────────────────────────────────────────────
    spec_avail = specialty_avail(df)
    if not spec_avail.empty and spec_avail["total_slots"].sum() > 0:
        st.markdown('<div class="sh">Specialty Availability (top 15)</div>', unsafe_allow_html=True)
        top_sa = spec_avail[spec_avail["total_slots"] > 0].head(15)
        fig_sa = px.bar(top_sa.sort_values("total_slots"),
                        x="total_slots", y="specialization", orientation="h",
                        color="doctors_with_slots", color_continuous_scale="Greens",
                        text="total_slots",
                        labels={"total_slots": "Available Slots", "specialization": "",
                                "doctors_with_slots": "Drs w/ slots"})
        fig_sa.update_traces(textposition="outside")
        fig_sa.update_coloraxes(showscale=False)
        fig_sa.update_layout(**CHART_LAYOUT, height=440)
        st.plotly_chart(fig_sa, use_container_width=True)

    # ── Heatmap ───────────────────────────────────────────────────────────────
    st.markdown('<div class="sh">Specialization × Language Matrix</div>', unsafe_allow_html=True)
    top_specs = df["specialization"].value_counts().head(10).index.tolist()
    top_langs = ["Tamil", "English", "Hindi", "Telugu", "Kannada", "Marathi", "Malayalam"]
    heat_rows = []
    for sp in top_specs:
        sdf = df[df["specialization"] == sp]
        for lg in top_langs:
            heat_rows.append({"Spec": sp, "Lang": lg,
                              "N": int(sdf["languages"].str.contains(lg, na=False).sum())})
    heat_piv = pd.DataFrame(heat_rows).pivot(index="Spec", columns="Lang", values="N").fillna(0)
    fig_hm = px.imshow(heat_piv, color_continuous_scale="Blues",
                       text_auto=True, aspect="auto", labels={"color": "Drs"})
    fig_hm.update_layout(**CHART_LAYOUT, height=380)
    fig_hm.update_coloraxes(showscale=False)
    st.plotly_chart(fig_hm, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — HOSPITALS
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "🏥  Hospitals":
    st.markdown(f"""
    <div class="hero">
      <h1>🏥 Hospital Network</h1>
      <p>Gleneagles multi-city network across India · {len(hosp_df)} locations · {len(all_cities)} cities</p>
    </div>""", unsafe_allow_html=True)

    if hosp_df.empty:
        st.warning("No hospital data. Run `python scripts/rebuild_all.py`")
        st.stop()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Hospitals",       len(hosp_df))
    c2.metric("Cities",          hosp_df["city"].nunique())
    c3.metric("Total Doctors",   f"{int(hosp_df['doctor_count'].sum()):,}")
    c4.metric("Total Slots",     f"{int(hosp_df['total_slots'].sum()):,}")

    st.markdown('<div class="sh">Doctors & Availability by Hospital</div>', unsafe_allow_html=True)

    fig_h = go.Figure()
    fig_h.add_trace(go.Bar(
        name="Total Doctors",
        x=hosp_df["name"].str.split(",").str[0],
        y=hosp_df["doctor_count"],
        marker_color=C_BLUE,
        text=hosp_df["doctor_count"],
        textposition="outside",
    ))
    fig_h.add_trace(go.Bar(
        name="With Open Slots",
        x=hosp_df["name"].str.split(",").str[0],
        y=hosp_df["doctors_with_slots"],
        marker_color=C_GREEN,
        text=hosp_df["doctors_with_slots"],
        textposition="outside",
    ))
    fig_h.update_layout(**CHART_LAYOUT, height=360, barmode="group",
                        legend=dict(font=dict(color=C_MUTED), bgcolor="rgba(0,0,0,0)"))
    st.plotly_chart(fig_h, use_container_width=True)

    st.markdown('<div class="sh">Hospital Details</div>', unsafe_allow_html=True)
    max_d = hosp_df["doctor_count"].max()
    for _, h in hosp_df.iterrows():
        cc  = city_color(h["city"])
        pct = int(h["doctor_count"] / max_d * 100) if max_d else 0
        avail_pct = int(h["doctors_with_slots"] / h["doctor_count"] * 100) if h["doctor_count"] else 0
        st.markdown(f"""
        <div class="hcard" style="border-left: 3px solid {cc}">
          <div style="display:flex;justify-content:space-between;align-items:flex-start">
            <div>
              <div class="htitle">{h['name']}</div>
              <div class="hloc">📍 {h['city']}, {h['state']}
                &nbsp;·&nbsp; Branch: {h.get('branch') or '—'}
                &nbsp;·&nbsp; <span style="font-family:monospace;font-size:.7rem">{h['id']}</span>
              </div>
            </div>
            <div style="text-align:right">
              <span class="badge badge-blue">{int(h['doctor_count'])} doctors</span>
              <span class="badge badge-green">{int(h['total_slots']):,} slots</span>
            </div>
          </div>
          <div style="margin-top:.7rem">
            <div style="display:flex;justify-content:space-between;font-size:.72rem;color:{C_MUTED};margin-bottom:.25rem">
              <span>Doctor coverage</span><span>{pct}% of network max</span>
            </div>
            <div class="hbar"><div class="hbar-fill" style="width:{pct}%;background:{cc}"></div></div>
            <div style="display:flex;justify-content:space-between;font-size:.72rem;color:{C_MUTED};margin:.4rem 0 .15rem">
              <span>Slot availability</span><span>{avail_pct}% of doctors have open slots</span>
            </div>
            <div class="hbar">
              <div class="hbar-fill" style="width:{avail_pct}%;background:{C_GREEN}"></div>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — DOCTOR DIRECTORY
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "👨‍⚕️  Doctor Directory":
    st.markdown(f"""
    <div class="hero">
      <h1>👨‍⚕️ Doctor Directory</h1>
      <p>Browse and filter all {len(df):,} indexed doctors across the Gleneagles network.</p>
    </div>""", unsafe_allow_html=True)

    # ── Filters ───────────────────────────────────────────────────────────────
    f1, f2, f3 = st.columns(3)
    with f1: search   = st.text_input("🔍 Search name", placeholder="e.g. Kumar, Sharma…")
    with f2: sel_spec = st.selectbox("Specialization", ["All"] + sorted(df["specialization"].unique()))
    with f3: sel_city = st.selectbox("City", ["All"] + all_cities)

    f4, f5, f6 = st.columns(3)
    with f4:
        sel_desig = st.selectbox("Designation", ["All"] + sorted(df["designation"].replace("","Unknown").unique()))
    with f5:
        exp_max_v = int(df["experience_years"].max(skipna=True) or 45)
        exp_range = st.slider("Experience (yrs)", 0, exp_max_v, (0, exp_max_v))
    with f6:
        sel_langs = st.multiselect("Languages", ["Tamil","English","Hindi","Telugu","Kannada","Marathi","Malayalam","Odia"])

    # Only-with-slots toggle
    only_slots = st.toggle("Show only doctors with available appointment slots", value=False)

    # Apply filters
    fdf = df.copy()
    if search:   fdf = fdf[fdf["name"].str.contains(search, case=False, na=False)]
    if sel_spec != "All": fdf = fdf[fdf["specialization"] == sel_spec]
    if sel_city != "All": fdf = fdf[fdf["city"] == sel_city]
    if sel_desig != "All": fdf = fdf[fdf["designation"] == sel_desig]
    fdf = fdf[(fdf["experience_years"].isna()) | (fdf["experience_years"].between(*exp_range))]
    for lg in sel_langs:
        fdf = fdf[fdf["languages"].str.contains(lg, na=False)]
    if only_slots:
        fdf = fdf[fdf["has_slots"]]

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:.75rem;margin:.75rem 0">
      <span style="font-size:1.1rem;font-weight:700;color:{C_TEXT}">{len(fdf)}</span>
      <span style="color:{C_MUTED};font-size:.875rem">doctors match · {len(df)-len(fdf)} filtered out</span>
    </div>""", unsafe_allow_html=True)

    view = st.radio("View", ["🃏 Cards", "📋 Table"], horizontal=True, label_visibility="collapsed")

    if "Table" in view:
        tdf = fdf[["name","designation","specialization","qualifications",
                   "experience_years","languages","hospital_name","city",
                   "total_available_slots","next_available"]].copy()
        tdf.columns = ["Doctor","Designation","Specialization","Qualifications",
                       "Exp (yrs)","Languages","Hospital","City","Open Slots","Next Available"]
        st.dataframe(tdf, use_container_width=True, height=560,
                     column_config={"Open Slots": st.column_config.NumberColumn(format="%d"),
                                    "Exp (yrs)": st.column_config.NumberColumn(format="%d")})
    else:
        PAGE_SIZE = 48
        total = len(fdf)
        page_num = st.session_state.get("dir_page", 0)
        page_df  = fdf.iloc[page_num * PAGE_SIZE : (page_num + 1) * PAGE_SIZE]

        cards_html = ""
        for _, row in page_df.iterrows():
            ini     = initials(row["name"])
            cc      = city_color(row["city"])
            exp     = f"{int(row['experience_years'])} yrs" if pd.notna(row.get("experience_years")) else ""
            specs   = row["specialization"] or "—"
            city_v  = row["city"] or "—"
            booking = row.get("booking_url") or row.get("profile_url") or ""
            qual_list = [q.strip() for q in (row["qualifications"] or "").split(",") if q.strip()][:3]
            lang_list = [l.strip() for l in (row["languages"]     or "").split(",") if l.strip()]

            qual_html = "".join(f'<span class="badge badge-default">{q}</span>' for q in qual_list)
            lang_html = "".join(f'<span class="badge badge-blue">{l}</span>'    for l in lang_list)
            meta_html = slot_badge(row.get("total_available_slots"))
            if exp:
                meta_html += f'<span class="badge badge-amber">🕐 {exp}</span>'
            meta_html += f'<span class="badge badge-default">📍 {city_v}</span>'

            btn_html = (f'<a class="book-btn" href="{booking}" target="_blank">📅 Book</a>'
                        if booking else "")

            cards_html += f"""
<div class="dcard">
  <div class="dcard-top">
    <div class="avatar" style="border-color:{cc};color:{cc}">{ini}</div>
    <div class="dcard-info">
      <div class="dname" title="{row['name']}">{row['name']}</div>
      <div class="ddesig">{row.get('designation') or ''}</div>
    </div>
  </div>
  <div class="dspec">📋 {specs}</div>
  <div style="line-height:1.8">{meta_html}</div>
  {'<div style="line-height:1.8">'+qual_html+'</div>' if qual_html else ''}
  {'<div style="line-height:1.8">'+lang_html+'</div>' if lang_html else ''}
  {btn_html}
</div>"""

        st.markdown(f'<div class="card-grid-3">{cards_html}</div>', unsafe_allow_html=True)

        if total > PAGE_SIZE:
            max_page = (total - 1) // PAGE_SIZE
            pv1, pv2, pv3 = st.columns([1, 3, 1])
            with pv1:
                if page_num > 0 and st.button("← Prev"):
                    st.session_state["dir_page"] = page_num - 1
                    st.rerun()
            with pv2:
                st.markdown(
                    f'<div style="text-align:center;color:{C_MUTED};font-size:.82rem;padding:.5rem 0">'
                    f'Page {page_num+1} of {max_page+1} · {total} doctors total</div>',
                    unsafe_allow_html=True,
                )
            with pv3:
                if page_num < max_page and st.button("Next →"):
                    st.session_state["dir_page"] = page_num + 1
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — SCHEDULES
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "📅  Schedules":
    st.markdown(f"""
    <div class="hero">
      <h1>📅 Appointment Availability</h1>
      <p>Real-time slot availability across {stats.get('doctors_with_slots',0)} doctors · {stats.get('total_available_slots',0):,} open slots · next 30 days.</p>
    </div>""", unsafe_allow_html=True)

    if sched_df.empty:
        st.warning("No schedule data. Run `python scripts/scrape_schedules.py`")
        st.stop()

    # Filters
    sf1, sf2, sf3 = st.columns(3)
    with sf1: ss = st.text_input("🔍 Search doctor", placeholder="e.g. Kumar", key="ss")
    with sf2:
        loc_cities = sorted(sched_df["location_city"].dropna().unique())
        sel_lc = st.selectbox("City", ["All"] + list(loc_cities))
    with sf3: avail_only = st.toggle("Only with open slots", value=True)

    vsched = sched_df.copy()
    if ss:           vsched = vsched[vsched["doctor_name"].str.contains(ss, case=False, na=False)]
    if sel_lc != "All": vsched = vsched[vsched["location_city"] == sel_lc]
    if avail_only:   vsched = vsched[vsched["total_available_slots"] > 0]
    vsched = vsched.reset_index(drop=True)

    # Reset page when filters change
    filter_sig = (ss, sel_lc, avail_only)
    if st.session_state.get("_sched_filter") != filter_sig:
        st.session_state["_sched_filter"] = filter_sig
        st.session_state["sched_page"] = 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Scheduled", len(sched_df))
    k2.metric("With Open Slots", len(sched_df[sched_df["total_available_slots"] > 0]))
    k3.metric("Available Slots", f"{int(sched_df['total_available_slots'].sum()):,}")
    k4.metric("Showing",         len(vsched))

    # Charts
    cl, cr = st.columns([3, 2])

    with cl:
        st.markdown('<div class="sh">Top 20 Doctors by Available Slots</div>', unsafe_allow_html=True)
        top20 = vsched.nlargest(20, "total_available_slots")
        if not top20.empty:
            colors = [city_color(c) for c in top20["location_city"]]
            fig_s = go.Figure(go.Bar(
                x=top20["total_available_slots"],
                y=top20["doctor_name"],
                orientation="h",
                marker_color=colors,
                text=top20["total_available_slots"],
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>Slots: %{x}<extra></extra>",
            ))
            fig_s.update_layout(**CHART_LAYOUT, height=500)
            fig_s.update_yaxes(autorange="reversed")
            st.plotly_chart(fig_s, use_container_width=True)

    with cr:
        st.markdown('<div class="sh">Slots by City</div>', unsafe_allow_html=True)
        city_slots = (sched_df.groupby("location_city")["total_available_slots"]
                      .sum().reset_index().sort_values("total_available_slots", ascending=False))
        fig_cs = px.pie(city_slots, values="total_available_slots", names="location_city",
                        hole=0.55,
                        color="location_city",
                        color_discrete_map=CITY_COLORS)
        fig_cs.update_traces(textposition="inside", textinfo="percent+label", textfont_size=11)
        fig_cs.update_layout(**CHART_LAYOUT, height=260, showlegend=False)
        st.plotly_chart(fig_cs, use_container_width=True)

        st.markdown('<div class="sh">Working Days</div>', unsafe_allow_html=True)
        day_ord = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
        day_c: dict = {}
        for wd in sched_df["working_days"]:
            for d in (wd or "").split(","):
                d = d.strip()[:3]
                if d: day_c[d] = day_c.get(d, 0) + 1
        day_df2 = pd.DataFrame([(d, day_c.get(d, 0)) for d in day_ord], columns=["Day","Doctors"])
        fig_wd = px.bar(day_df2, x="Day", y="Doctors", color="Doctors",
                        color_continuous_scale="Blues", text="Doctors")
        fig_wd.update_traces(textposition="outside")
        fig_wd.update_coloraxes(showscale=False)
        fig_wd.update_layout(**CHART_LAYOUT, height=230)
        st.plotly_chart(fig_wd, use_container_width=True)

    # Build schedule_days lookup from the separately-loaded (Arrow-safe) DataFrame
    days_map: dict = {}
    if not sched_days.empty:
        for _, r in sched_days.iterrows():
            days_map.setdefault(str(r["doctor_id"]), []).append({
                "date": r["date"], "day_name": r["day_name"],
                "available_slots": int(r["available_slots"]),
                "total_slots": int(r["total_slots"]),
            })

    # Pagination — 20 expanders per page avoids browser overload
    PAGE_SIZE = 20
    total_pages = max(1, (len(vsched) + PAGE_SIZE - 1) // PAGE_SIZE)
    if "sched_page" not in st.session_state:
        st.session_state["sched_page"] = 0
    if st.session_state["sched_page"] >= total_pages:
        st.session_state["sched_page"] = 0

    pa, pb, pc = st.columns([1, 6, 1])
    with pa:
        if st.button("◀ Prev", key="sp_prev", disabled=st.session_state["sched_page"] == 0):
            st.session_state["sched_page"] -= 1
            st.rerun()
    with pb:
        cur_p = st.session_state["sched_page"]
        st.markdown(
            f'<div class="sh">Doctor Schedule Details  ·  {len(vsched)} shown  ·  '
            f'page {cur_p + 1} / {total_pages}</div>',
            unsafe_allow_html=True,
        )
    with pc:
        if st.button("Next ▶", key="sp_next", disabled=st.session_state["sched_page"] >= total_pages - 1):
            st.session_state["sched_page"] += 1
            st.rerun()

    start = st.session_state["sched_page"] * PAGE_SIZE
    page_rows = vsched.iloc[start : start + PAGE_SIZE]

    for idx, row in page_rows.iterrows():
        did = str(row["doctor_id"])
        cc = city_color(str(row.get("location_city", "")))
        with st.expander(
            f"🩺 {row['doctor_name']}  ·  {row.get('location_city') or row.get('location_name') or ''}  "
            f"·  Next: {row['next_available'] or '—'}  ·  {row['total_available_slots']} slots"
        ):
            dc1, dc2 = st.columns([2, 3])
            with dc1:
                nd = row['numeric_doctor_id']
                nd_str = str(int(nd)) if pd.notna(nd) else "—"
                st.markdown(f"""
                <div style="font-size:.82rem;line-height:1.9;color:{C_MUTED}">
                  <div><b style="color:{C_TEXT}">Hospital</b>  {row.get('location_name') or '—'}</div>
                  <div><b style="color:{C_TEXT}">City</b>  {row.get('location_city') or '—'}</div>
                  <div><b style="color:{C_TEXT}">Doctor ID</b>  <code>{nd_str}</code></div>
                  <div><b style="color:{C_TEXT}">Consult type</b>  {row['consultation_types']}</div>
                  <div><b style="color:{C_TEXT}">Working days</b>  {row['working_days']}</div>
                  <div><b style="color:{C_TEXT}">Available slots</b>
                    <span style="color:{C_GREEN};font-weight:700">{row['total_available_slots']}</span>
                    across {int(row.get('days_count', 0) or 0)} day(s)</div>
                </div>""", unsafe_allow_html=True)
                if row.get("booking_url"):
                    st.link_button("📅 Open Booking Page", str(row["booking_url"]))

            with dc2:
                days = days_map.get(did, [])
                if days:
                    dtab = pd.DataFrame([{
                        "Date": d["date"], "Day": d["day_name"],
                        "Available": d["available_slots"], "Total": d["total_slots"],
                    } for d in days[:21]])
                    if not dtab.empty and dtab["Available"].sum() > 0:
                        fig_d = px.bar(dtab, x="Date", y="Available",
                                       color_discrete_sequence=[cc or C_GREEN], text="Available")
                        fig_d.update_traces(textposition="outside")
                        fig_d.update_layout(**CHART_LAYOUT, height=210)
                        fig_d.update_layout(margin=dict(t=10, b=40, l=0, r=0))
                        fig_d.update_xaxes(tickangle=-35)
                        st.plotly_chart(fig_d, use_container_width=True, key=f"sched_{did}_{idx}")
                    else:
                        st.info("No available slots in calendar data.")
                else:
                    st.info("No calendar data.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 5 — KNOWLEDGE GRAPH
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "🕸️  Knowledge Graph":
    st.markdown(f"""
    <div class="hero">
      <h1>🕸️ Knowledge Graph</h1>
      <p>Interactive graph — Doctor nodes connected by Specialization, Language, or Qualification clusters.</p>
    </div>""", unsafe_allow_html=True)

    gc1, gc2, gc3, gc4 = st.columns(4)
    with gc1: node_limit = st.slider("Max doctors", 20, min(250, len(df)), 80)
    with gc2: rel_type   = st.selectbox("Cluster by", ["Specialization", "Language", "Qualification"])
    with gc3: city_f     = st.selectbox("City filter", ["All"] + all_cities)
    with gc4: min_exp    = st.slider("Min experience (yrs)", 0, 30, 0)

    sub = df.copy()
    if city_f != "All": sub = sub[sub["city"] == city_f]
    if min_exp > 0:     sub = sub[sub["experience_years"].fillna(0) >= min_exp]
    sub = sub.head(node_limit)

    node_x, node_y, node_text, node_color, node_size = [], [], [], [], []
    node_hover = []
    edge_x, edge_y = [], []
    random.seed(42)

    REL_COLORS = {"Specialization": C_BLUE, "Language": C_PURPLE, "Qualification": C_GREEN}
    gcolor = REL_COLORS[rel_type]

    if rel_type == "Specialization":
        groups = sub["specialization"].dropna().unique()
    elif rel_type == "Qualification":
        groups = sub["qualifications"].str.split(",").explode().str.strip().dropna().unique()
        groups = [g for g in groups if g]
    else:
        groups = sub["languages"].str.split(",").explode().str.strip().dropna().unique()
        groups = [g for g in groups if g]

    group_pos: dict = {}
    r1 = 4
    for idx, g in enumerate(groups):
        a = 2 * math.pi * idx / max(len(groups), 1)
        gx, gy = r1 * math.cos(a), r1 * math.sin(a)
        group_pos[g] = (gx, gy)
        node_x.append(gx); node_y.append(gy)
        node_text.append(f"<b>{g}</b>")
        node_hover.append(f"<b>{g}</b><br>{rel_type}")
        node_color.append(gcolor); node_size.append(18)

    r2 = 1.6
    for _, row in sub.iterrows():
        if rel_type == "Specialization":
            matched = [row["specialization"]] if row["specialization"] in group_pos else []
        elif rel_type == "Qualification":
            matched = [q.strip() for q in (row["qualifications"] or "").split(",") if q.strip() in group_pos]
        else:
            matched = [l.strip() for l in (row["languages"] or "").split(",") if l.strip() in group_pos]
        if not matched: continue

        gx, gy = group_pos[matched[0]]
        a  = random.uniform(0, 2 * math.pi)
        dx = gx + r2 * math.cos(a) * random.uniform(0.4, 1.0)
        dy = gy + r2 * math.sin(a) * random.uniform(0.4, 1.0)
        exp = row.get("experience_years")
        sz  = 9 + (int(exp) // 4 if pd.notna(exp) else 0)
        dc  = city_color(row["city"])

        node_x.append(dx); node_y.append(dy)
        hover = (f"<b>{row['name']}</b><br>{row.get('designation','')}<br>"
                 f"{row['specialization']}<br>📍 {row['city']}"
                 + (f"<br>🕐 {int(exp)} yrs exp" if pd.notna(exp) else "")
                 + (f"<br>✅ {int(row.get('total_available_slots',0))} slots"
                    if row.get("has_slots") else ""))
        node_text.append(""); node_hover.append(hover)
        node_color.append(dc); node_size.append(sz)

        for m in matched:
            mgx, mgy = group_pos[m]
            edge_x += [mgx, dx, None]; edge_y += [mgy, dy, None]

    fig_g = go.Figure(data=[
        go.Scatter(x=edge_x, y=edge_y, mode="lines",
                   line=dict(color=C_BORDER2, width=0.7), hoverinfo="none", showlegend=False),
        go.Scatter(x=node_x, y=node_y, mode="markers",
                   hoverinfo="text", hovertext=node_hover,
                   marker=dict(color=node_color, size=node_size,
                               line=dict(color=C_BG, width=1.2)),
                   showlegend=False),
    ])
    fig_g.update_layout(
        paper_bgcolor=PAPER_BG, plot_bgcolor=C_BG,
        height=650, margin=dict(t=10,b=10,l=10,r=10),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        hovermode="closest",
    )
    st.plotly_chart(fig_g, use_container_width=True)

    legend_items = (
        f'<span style="margin-right:1.5rem"><span style="color:{gcolor}">⬤</span>'
        f' <span style="color:{C_MUTED};font-size:.8rem">{rel_type} cluster</span></span>'
    )
    for city, cc2 in CITY_COLORS.items():
        legend_items += (
            f'<span style="margin-right:1.5rem"><span style="color:{cc2}">⬤</span>'
            f' <span style="color:{C_MUTED};font-size:.8rem">{city}</span></span>'
        )
    st.markdown(
        f'<div style="padding:.5rem 0;display:flex;flex-wrap:wrap;gap:.25rem">{legend_items}</div>',
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 6 — SPECIALTY EXPLORER
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "🔍  Specialty Explorer":
    st.markdown(f"""
    <div class="hero">
      <h1>🔍 Specialty Explorer</h1>
      <p>Deep-dive into any medical specialty across all {len(hosp_df)} Gleneagles locations.</p>
    </div>""", unsafe_allow_html=True)

    spec_list = sorted(df["specialization"].value_counts().index)
    chosen = st.selectbox("Choose a Specialty", spec_list, label_visibility="collapsed")
    sdf = df[df["specialization"] == chosen].copy()

    exp_v = sdf["experience_years"].dropna()
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Doctors",       len(sdf))
    k2.metric("Avg Experience",f"{exp_v.mean():.1f} yrs" if len(exp_v) else "—")
    k3.metric("Max Experience",f"{int(exp_v.max())} yrs" if len(exp_v) else "—")
    k4.metric("Designations",  sdf["designation"].nunique())
    k5.metric("Open Slots",    f"{int(sdf['total_available_slots'].fillna(0).sum()):,}")

    sl, sr = st.columns(2)
    with sl:
        st.markdown('<div class="sh">Experience Profile</div>', unsafe_allow_html=True)
        if len(exp_v):
            fig_e = px.histogram(sdf[sdf["experience_years"].notna()], x="experience_years",
                                 color_discrete_sequence=[C_BLUE], nbins=10,
                                 labels={"experience_years": "Years"})
            fig_e.update_layout(**CHART_LAYOUT, height=240, bargap=0.1)
            st.plotly_chart(fig_e, use_container_width=True)
        else:
            st.info("No experience data.")

    with sr:
        st.markdown('<div class="sh">Designation Mix</div>', unsafe_allow_html=True)
        dm = sdf["designation"].replace("","Unknown").value_counts().reset_index()
        dm.columns = ["Designation","Count"]
        fig_dm = px.pie(dm, values="Count", names="Designation", hole=0.52,
                        color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_dm.update_traces(textposition="inside", textinfo="percent", textfont_size=11)
        fig_dm.update_layout(**CHART_LAYOUT, height=240, showlegend=True,
                             legend=dict(font=dict(size=10,color=C_MUTED), bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig_dm, use_container_width=True)

    # Availability by city
    city_avail = (sdf.groupby("city")
                  .agg(doctors=("id","count"), slots=("total_available_slots","sum"))
                  .reset_index().sort_values("slots", ascending=False))
    if not city_avail.empty:
        st.markdown('<div class="sh">Availability by City</div>', unsafe_allow_html=True)
        fig_ca = go.Figure()
        for _, ca in city_avail.iterrows():
            cc2 = city_color(ca["city"])
            fig_ca.add_trace(go.Bar(
                name=ca["city"],
                x=[ca["city"]],
                y=[ca["slots"]],
                marker_color=cc2,
                text=[f"{int(ca['slots'])} slots<br>{int(ca['doctors'])} drs"],
                textposition="outside",
            ))
        fig_ca.update_layout(**CHART_LAYOUT, height=260, showlegend=False)
        st.plotly_chart(fig_ca, use_container_width=True)

    # Language availability
    lang_s = sdf["languages"].str.split(",").explode().str.strip()
    lang_c = lang_s[lang_s != ""].value_counts().reset_index()
    lang_c.columns = ["Language","Doctors"]
    if not lang_c.empty:
        st.markdown('<div class="sh">Languages Spoken</div>', unsafe_allow_html=True)
        fig_l = px.bar(lang_c, x="Language", y="Doctors",
                       color="Doctors", color_continuous_scale="Blues", text="Doctors")
        fig_l.update_traces(textposition="outside")
        fig_l.update_coloraxes(showscale=False)
        fig_l.update_layout(**CHART_LAYOUT, height=230)
        st.plotly_chart(fig_l, use_container_width=True)

    # Doctor cards — CSS grid, no Streamlit columns
    st.markdown('<div class="sh">Doctors in this Specialty</div>', unsafe_allow_html=True)
    spec_cards_html = ""
    for _, row in sdf.sort_values("total_available_slots", ascending=False, na_position="last").iterrows():
        ini     = initials(row["name"])
        cc2     = city_color(row["city"])
        exp     = f"{int(row['experience_years'])} yrs" if pd.notna(row.get("experience_years")) else ""
        city_v  = row["city"] or "—"
        qual_b  = "".join(f'<span class="badge badge-default">{q.strip()}</span>'
                          for q in (row["qualifications"] or "").split(",")[:3] if q.strip())
        lang_b  = "".join(f'<span class="badge badge-blue">{l.strip()}</span>'
                          for l in (row["languages"] or "").split(",") if l.strip())
        booking = row.get("booking_url") or row.get("profile_url") or ""
        meta = slot_badge(row.get("total_available_slots"))
        if exp:
            meta += f'<span class="badge badge-amber">🕐 {exp}</span>'
        meta += f'<span class="badge badge-default">📍 {city_v}</span>'

        spec_cards_html += f"""
<div class="dcard">
  <div class="dcard-top">
    <div class="avatar" style="border-color:{cc2};color:{cc2}">{ini}</div>
    <div class="dcard-info">
      <div class="dname" title="{row['name']}">{row['name']}</div>
      <div class="ddesig">{row.get('designation') or ''}</div>
    </div>
  </div>
  <div style="line-height:1.8">{meta}</div>
  {'<div style="line-height:1.8">'+qual_b+'</div>' if qual_b else ''}
  {'<div style="line-height:1.8">'+lang_b+'</div>' if lang_b else ''}
  {'<a class="book-btn" href="'+booking+'" target="_blank">📅 Book</a>' if booking else ''}
</div>"""

    st.markdown(f'<div class="card-grid-3">{spec_cards_html}</div>', unsafe_allow_html=True)
