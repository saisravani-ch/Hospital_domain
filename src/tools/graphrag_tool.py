from __future__ import annotations

import os
from typing import Any

import httpx

KB_BASE = os.getenv("KB_URL", "http://localhost:8000")


async def search_doctors(
    query: str,
    graphrag: Any = None,
    tenant_id: str | None = None,
    specialization: str | None = None,
    doctor_name: str | None = None,
    language: str | None = None,
    min_experience: int | None = None,
) -> dict[str, Any]:
    """Search for doctors via knowledge_base retrieval API (no LLM on KB side)."""
    body = {"query": query}
    if tenant_id:
        body["tenant_id"] = tenant_id
    if specialization:
        body["specialization"] = specialization
    if doctor_name:
        body["doctor_name"] = doctor_name
    if language:
        body["language"] = language
    if min_experience is not None:
        body["min_experience"] = min_experience
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{KB_BASE}/search/retrieve", json=body)
            resp.raise_for_status()
            data = resp.json()
            return {
                "context": "",
                "doctors": data.get("doctors", []),
                "booking_links": data.get("booking_links", []),
            }
    except httpx.HTTPError as e:
        return {"error": f"Knowledge base unavailable: {e}", "context": "", "doctors": [], "booking_links": []}


async def get_doctor_info(
    doctor_id: str,
    graph: Any = None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Get detailed doctor info via knowledge_base HTTP API."""
    try:
        params = {}
        if tenant_id:
            params["tenant_id"] = tenant_id
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{KB_BASE}/doctors/{doctor_id}", params=params)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        return {"error": f"Doctor info unavailable: {e}"}
