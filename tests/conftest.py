from __future__ import annotations

import json
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

MOCK_DOCTORS = [
    {
        "doctor_id": "dr-susan-george",
        "name": "Susan George",
        "specializations": "Cardiology",
        "experience_years": 30,
        "consultation_fee": 500,
        "languages": "English, Tamil",
    },
    {
        "doctor_id": "dr-gobu-p",
        "name": "Gobu P",
        "specializations": "Cardiology",
        "experience_years": 20,
        "consultation_fee": 400,
        "languages": "English, Malayalam",
    },
    {
        "doctor_id": "dr-madhusudhan-m",
        "name": "Madhusudhan M",
        "specializations": "Cardio Thoracic Surgery",
        "experience_years": 12,
        "consultation_fee": 600,
        "languages": "English, Tamil",
    },
]

MOCK_SLOTS = [
    {"time": "10:30", "slot_id": "slot_001", "period": "Morning"},
    {"time": "11:00", "slot_id": "slot_002", "period": "Morning"},
    {"time": "14:00", "slot_id": "slot_003", "period": "Afternoon"},
]

MOCK_BOOKING = {
    "appointment_id": "apt_a1b2c3d4",
    "status": "confirmed",
    "doctor_id": "dr-susan-george",
    "date": "2026-07-29",
    "time": "10:30",
}

MOCK_DOCTOR_INFO = {
    "doctor_id": "dr-susan-george",
    "name": "Susan George",
    "specializations": "Cardiology",
    "experience_years": 30,
    "consultation_fee": 500,
    "languages": "English, Tamil",
    "hospital": "Gleneagles Chennai",
    "designation": "Senior Cardiologist",
    "qualifications": "MBBS, MD, DM Cardiology",
    "about": "Experienced cardiologist with 30 years of practice.",
}


@pytest.fixture
def base_state():
    return {
        "messages": [],
        "session_id": "test_session",
        "tenant_id": None,
        "client_id": "gleneagles_001",
        "search_results": [],
        "selected_doctor_id": None,
        "available_slots": [],
        "selected_slot": None,
        "patient_phone": None,
        "booking_result": None,
        "current_phase": "idle",
        "pending_skill": None,
        "user_location": None,
    }


@pytest.fixture
def mock_search_tool_result():
    return {"doctors": MOCK_DOCTORS, "booking_links": []}


@pytest.fixture
def mock_availability_result():
    return {"doctor_id": "dr-susan-george", "date": "2026-07-29", "slots_available": 3, "slots": MOCK_SLOTS}
