from __future__ import annotations

from typing import Any

import openai

from src.knowledge_base.config import get_tenant_config
from src.knowledge_base.graph.neo4j_loader import Neo4jQueryEngine
from src.knowledge_base.query.graphrag_engine import GraphRAGEngine
from src.memory.conversation_memory import ConversationMemory
from src.tools import graphrag_tool, workflow_tool

TOOL_DEFS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_doctors",
            "description": "Search for doctors by specialty, symptoms, condition, doctor name, or any query. Extracts structured fields from the user's request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The user's full natural language query"},
                    "specialization": {"type": "string", "description": "Medical specialty or condition the user asked about (e.g. 'Cardiology', 'Orthopaedics', 'Diabetes')", "nullable": True},
                    "doctor_name": {"type": "string", "description": "Specific doctor name if mentioned by the user", "nullable": True},
                    "language": {"type": "string", "description": "Preferred language for the doctor (e.g. 'Tamil', 'Hindi', 'English')", "nullable": True},
                    "min_experience": {"type": "integer", "description": "Minimum years of experience requested", "nullable": True},
                    "tenant_id": {"type": "string", "description": "Hospital tenant filter (e.g. 'glh-chn' for Chennai, 'glh-kengeri' for Bengaluru)", "nullable": True},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_doctor_info",
            "description": "Get detailed information about a specific doctor by their ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {"type": "string", "description": "Doctor's unique ID (e.g. 'dr-j-ajith-kumar-chn')"},
                    "tenant_id": {"type": "string", "description": "Hospital tenant filter", "nullable": True},
                },
                "required": ["doctor_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check available appointment slots for a doctor on a specific date",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {"type": "string", "description": "Doctor's ID"},
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                    "client_id": {"type": "string", "description": "Client/hospital identifier", "nullable": True},
                },
                "required": ["doctor_id", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book an appointment with a doctor at a specific date and time",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {"type": "string", "description": "Doctor's ID"},
                    "patient_phone": {"type": "string", "description": "Patient's phone number"},
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                    "time": {"type": "string", "description": "Time slot in HH:MM format (e.g. '10:30', '14:00')"},
                    "client_id": {"type": "string", "description": "Client/hospital identifier", "nullable": True},
                    "notes": {"type": "string", "description": "Optional notes or reason for visit", "nullable": True},
                },
                "required": ["doctor_id", "patient_phone", "date", "time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_appointment",
            "description": "Reschedule an existing appointment to a new date and time",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "string", "description": "Appointment ID to reschedule"},
                    "new_date": {"type": "string", "description": "New date in YYYY-MM-DD format"},
                    "new_time": {"type": "string", "description": "New time in HH:MM format"},
                    "client_id": {"type": "string", "description": "Client/hospital identifier", "nullable": True},
                },
                "required": ["appointment_id", "new_date", "new_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel an existing appointment",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "string", "description": "Appointment ID to cancel"},
                    "client_id": {"type": "string", "description": "Client/hospital identifier", "nullable": True},
                },
                "required": ["appointment_id"],
            },
        },
    },
]


def build_tool_map(
    graphrag: GraphRAGEngine | None,
    graph: Neo4jQueryEngine | None,
    memory: ConversationMemory,
) -> dict[str, callable]:
    """Bind engine dependencies to tool functions and return a name->callable map."""

    async def search_doctors(query: str, tenant_id: str | None = None, specialization: str | None = None, doctor_name: str | None = None, language: str | None = None, min_experience: int | None = None) -> dict[str, Any]:
        if graphrag is None:
            return {"error": "Knowledge base is not available (Neo4j/chroma not connected)."}
        return await graphrag_tool.search_doctors(query, graphrag, tenant_id, specialization, doctor_name, language, min_experience)

    async def get_doctor_info(doctor_id: str, tenant_id: str | None = None) -> dict[str, Any]:
        if graph is None:
            return {"error": "Knowledge base is not available (Neo4j not connected)."}
        return await graphrag_tool.get_doctor_info(doctor_id, graph, tenant_id)

    async def check_availability(doctor_id: str, date: str, client_id: str = "gleneagles_001") -> dict[str, Any]:
        return await workflow_tool.check_availability(doctor_id, date, client_id)

    async def book_appointment(doctor_id: str, patient_phone: str, date: str, time: str, client_id: str = "gleneagles_001", notes: str | None = None) -> dict[str, Any]:
        return await workflow_tool.book_appointment(doctor_id, patient_phone, date, time, client_id, notes)

    async def reschedule_appointment(appointment_id: str, new_date: str, new_time: str, client_id: str = "gleneagles_001") -> dict[str, Any]:
        return await workflow_tool.reschedule_appointment(appointment_id, new_date, new_time, client_id)

    async def cancel_appointment(appointment_id: str, client_id: str = "gleneagles_001") -> dict[str, Any]:
        return await workflow_tool.cancel_appointment(appointment_id, client_id)

    return {
        "search_doctors": search_doctors,
        "get_doctor_info": get_doctor_info,
        "check_availability": check_availability,
        "book_appointment": book_appointment,
        "reschedule_appointment": reschedule_appointment,
        "cancel_appointment": cancel_appointment,
    }
