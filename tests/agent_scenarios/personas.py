from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Persona:
    name: str
    role: str
    style: str
    system_note: str

    def format_message(self, msg: str) -> str:
        return msg


@dataclass(frozen=True)
class PatientPersona(Persona):
    name: str = "Patient"
    role: str = "patient"
    style: str = "first-person, direct, uses casual language"
    system_note: str = "User is the patient themselves, speaking in first person."

    def format_message(self, msg: str) -> str:
        return msg


@dataclass(frozen=True)
class AttenderPersona(Persona):
    name: str = "Attender"
    role: str = "attender"
    style: str = "third-person, formal, speaks on behalf of patient"
    system_note: str = "User is a family member or caregiver speaking on behalf of the patient."

    def format_message(self, msg: str) -> str:
        return msg


@dataclass(frozen=True)
class ConfusedUserPersona(Persona):
    name: str = "Confused User"
    role: str = "confused_user"
    style: str = "vague, needs clarification, asks follow-up questions"
    system_note: str = "User is unsure of what they need, provides vague queries."

    def format_message(self, msg: str) -> str:
        return msg


@dataclass(frozen=True)
class ExistingPatientPersona(Persona):
    name: str = "Existing Patient"
    role: str = "existing_patient"
    style: str = "first-person, references past appointments"
    system_note: str = "User has an existing booking and wants to check or modify it."
    phone: str = "+919999999999"
    appointment_id: str = "apt_a1b2c3d4"

    def format_message(self, msg: str) -> str:
        return msg


ALL_PERSONAS: dict[str, Persona] = {
    "patient": PatientPersona(),
    "attender": AttenderPersona(),
    "confused": ConfusedUserPersona(),
    "existing_patient": ExistingPatientPersona(),
}