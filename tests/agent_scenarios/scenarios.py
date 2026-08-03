from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Turn:
    user_message: str
    expect_pending_confirmation: bool = False
    confirm_on_pending: bool = True
    expected_in_response: list[str] = field(default_factory=list)
    expected_not_in_response: list[str] = field(default_factory=list)
    expect_error: bool = False


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    persona: str
    tenant_id: str = ""
    client_id: str = "gleneagles_001"
    turns: list[Turn] = field(default_factory=list)
    auto_confirm: bool = True

    @property
    def persona_obj(self) -> Any:
        from .personas import ALL_PERSONAS
        return ALL_PERSONAS.get(self.persona, ALL_PERSONAS["patient"])


def _t(
    user: str,
    expect_pending_confirmation: bool = False,
    confirm_on_pending: bool = True,
    expected_contains: list[str] | None = None,
    expected_absent: list[str] | None = None,
    expect_error: bool = False,
) -> Turn:
    return Turn(
        user_message=user,
        expect_pending_confirmation=expect_pending_confirmation,
        confirm_on_pending=confirm_on_pending,
        expected_in_response=expected_contains or [],
        expected_not_in_response=expected_absent or [],
        expect_error=expect_error,
    )


def search_and_book_scenario() -> Scenario:
    return Scenario(
        name="search_and_book",
        description="Patient searches for a heart doctor in Chennai, checks availability, and books an appointment through full multi-turn flow.",
        persona="patient",
        turns=[
            _t(
                "I need a heart doctor in chennai",
                expected_contains=["cardiolog", "heart", "Susan George", "Gobu"],
            ),
            _t(
                "Show me the available slots for Dr Susan George on 2026-07-29",
                expected_contains=["10:30", "11:00", "14:00", "slot", "available"],
                expect_pending_confirmation=False,
            ),
            _t(
                "Book the 10:30 slot for me. My phone is +919999999999",
                expect_pending_confirmation=True,
                confirm_on_pending=True,
            ),
        ],
    )


def check_availability_scenario() -> Scenario:
    return Scenario(
        name="check_availability",
        description="Attender checks available slots for a known doctor without booking.",
        persona="attender",
        turns=[
            _t(
                "I am calling on behalf of my mother. She needs to see Dr Gobu P for cardiology. What slots are available for 2026-07-30?",
                expected_contains=["10:30", "11:00", "14:00", "Gobu"],
            ),
        ],
    )


def cancel_appointment_scenario() -> Scenario:
    return Scenario(
        name="cancel_appointment",
        description="Existing patient cancels a booked appointment after providing phone.",
        persona="existing_patient",
        turns=[
            _t(
                "I want to cancel my appointment",
                expected_contains=["phone", "cancel", "appointment"],
            ),
            _t(
                "My phone number is +919999999999",
                expected_contains=["appointment", "cancel", "apt_"],
            ),
        ],
    )


def reschedule_appointment_scenario() -> Scenario:
    return Scenario(
        name="reschedule_appointment",
        description="Existing patient reschedules a booked appointment to a new date and time after providing phone.",
        persona="existing_patient",
        turns=[
            _t(
                "I need to reschedule my appointment",
                expected_contains=["phone", "reschedule", "appointment"],
            ),
            _t(
                "My phone is +919999999999. Reschedule to 2026-08-05 at 14:00",
                expected_contains=["reschedule", "2026-08-05", "14:00"],
            ),
        ],
    )


def check_status_scenario() -> Scenario:
    return Scenario(
        name="check_appointment_status",
        description="Patient checks the status of their existing appointments by phone number.",
        persona="patient",
        turns=[
            _t(
                "Can you check my appointment status? My number is +919999999999",
                expected_contains=["appointment"],
            ),
        ],
    )


def edge_case_no_results_scenario() -> Scenario:
    return Scenario(
        name="edge_case_no_results",
        description="Patient searches for a specialty that has no matching doctors.",
        persona="patient",
        turns=[
            _t(
                "Find me a dermatologist in chennai",
                expected_contains=["not found", "no doctor", "dermatolog", "sorry"],
            ),
        ],
    )


def booking_cancelled_at_confirmation_scenario() -> Scenario:
    return Scenario(
        name="booking_cancelled_at_confirmation",
        description="Patient initiates a booking but says 'no' when asked to confirm.",
        persona="patient",
        turns=[
            _t(
                "I want to book an appointment with Dr Susan George on 2026-07-29 at 10:30. My phone is +919999999999",
                expect_pending_confirmation=True,
                confirm_on_pending=False,
            ),
        ],
    )


def confused_user_scenario() -> Scenario:
    return Scenario(
        name="confused_user",
        description="Confused user asks vague questions and needs follow-up guidance from the agent.",
        persona="confused",
        turns=[
            _t(
                "I dont feel well, can you help me see a doctor",
                expected_contains=["doctor", "specialist", "heart", "cardiolog", "help"],
            ),
        ],
    )


ALL_SCENARIOS: list[Scenario] = [
    search_and_book_scenario(),
    check_availability_scenario(),
    cancel_appointment_scenario(),
    reschedule_appointment_scenario(),
    check_status_scenario(),
    edge_case_no_results_scenario(),
    booking_cancelled_at_confirmation_scenario(),
    confused_user_scenario(),
]