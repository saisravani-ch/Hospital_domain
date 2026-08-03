from __future__ import annotations

import os
from typing import Any

import httpx

KB_BASE = os.getenv("KB_URL", "http://localhost:8000")

_client: httpx.AsyncClient | None = None


def _get_client(timeout: float = 30) -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(timeout))
    return _client


async def search_doctors(
    query: str,
    tenant_id: str | None = None,
    specialization: str | None = None,
    doctor_name: str | None = None,
    language: str | None = None,
    min_experience: int | None = None,
    location: str | None = None,
) -> dict[str, Any]:
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
    if location:
        body["location"] = location
    try:
        client = _get_client(30)
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
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Get detailed doctor info via knowledge_base HTTP API."""
    try:
        params = {}
        if tenant_id:
            params["tenant_id"] = tenant_id
        client = _get_client(15)
        resp = await client.get(f"{KB_BASE}/doctors/{doctor_id}", params=params)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as e:
        return {"error": f"Doctor info unavailable: {e}"}
