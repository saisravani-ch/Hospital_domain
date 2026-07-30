from __future__ import annotations

import json
from typing import Annotated, Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from src.tools import graphrag_tool


def _filter_by_location(doctors: list[dict], location: str) -> list[dict]:
    if not location or not doctors:
        return doctors
    loc_lower = location.strip().lower()
    filtered = []
    seen = set()
    for d in doctors:
        cities = d.get("cities") or []
        match = any(loc_lower in c.lower() for c in cities)
        key = d.get("doctor_id") or d.get("id") or d.get("name", "")
        if match and key not in seen:
            seen.add(key)
            filtered.append(d)
    return filtered or doctors


@tool
async def search_doctors(
    query: str,
    location: str | None = None,
    specialization: str | None = None,
    doctor_name: str | None = None,
    language: str | None = None,
    min_experience: int | None = None,
    _state: Annotated[dict, InjectedState] = None,
    runtime: ToolRuntime = None,
) -> Command:
    """Search for doctors by specialty, symptoms, condition, doctor name, or natural language query."""
    tenant_id = (_state or {}).get("tenant_id")
    result = await graphrag_tool.search_doctors(
        query, tenant_id=tenant_id, specialization=specialization,
        doctor_name=doctor_name, language=language, min_experience=min_experience,
    )
    try:
        content = json.dumps(result, ensure_ascii=False)
    except Exception:
        content = str(result)
    updates: dict[str, Any] = {
        "messages": [ToolMessage(content=content, tool_call_id=runtime.tool_call_id if runtime else "")]
    }
    docs = result.get("doctors", [])
    if location:
        docs = _filter_by_location(docs, location)
        updates["user_location"] = location
    if docs:
        updates["search_results"] = docs
        updates["current_phase"] = "searching"
    return Command(update=updates)


@tool
async def get_doctor_info(
    doctor_id: str,
    _state: Annotated[dict, InjectedState] = None,
    runtime: ToolRuntime = None,
) -> Command:
    """Get detailed information about a specific doctor by their ID."""
    tenant_id = (_state or {}).get("tenant_id")
    result = await graphrag_tool.get_doctor_info(doctor_id, tenant_id=tenant_id)
    try:
        content = json.dumps(result, ensure_ascii=False)
    except Exception:
        content = str(result)
    updates: dict[str, Any] = {
        "messages": [ToolMessage(content=content, tool_call_id=runtime.tool_call_id if runtime else "")]
    }
    if "error" not in result:
        updates["selected_doctor_id"] = doctor_id
        updates["current_phase"] = "selecting"
    return Command(update=updates)
