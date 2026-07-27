from __future__ import annotations

from typing import Any

from src.knowledge_base.graph.neo4j_loader import Neo4jQueryEngine
from src.knowledge_base.query.graphrag_engine import GraphRAGEngine


async def search_doctors(
    query: str,
    graphrag: GraphRAGEngine | None,
    tenant_id: str | None = None,
    specialization: str | None = None,
    doctor_name: str | None = None,
    language: str | None = None,
    min_experience: int | None = None,
) -> dict[str, Any]:
    """Search for doctors using structured params extracted by the LLM."""
    if graphrag is None:
        return {"error": "Knowledge base unavailable", "context": "", "doctors": [], "booking_links": []}
    fused, context_text, booking_links = await graphrag.retrieve_context(
        query, tenant_id,
        specialization=specialization,
        doctor_name=doctor_name,
        language=language,
        min_experience=min_experience,
    )
    return {
        "context": context_text,
        "doctors": [
            {
                "doctor_id": d.get("doctor_id") or d.get("id", ""),
                "name": d.get("name") or d.get("doctor_name", ""),
                "specializations": d.get("specializations", ""),
                "experience_years": d.get("experience_years"),
                "consultation_fee": d.get("consultation_fee"),
                "languages": d.get("languages", ""),
                "hospital": d.get("hospitals") or d.get("hospital_ids", ""),
                "designation": d.get("designation", ""),
            }
            for d in fused
        ],
        "booking_links": booking_links,
    }


async def get_doctor_info(
    doctor_id: str,
    graph: Neo4jQueryEngine,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Get detailed information about a specific doctor by ID."""
    doc = await graph.get_doctor_context(doctor_id)
    if not doc:
        return {"error": f"Doctor '{doctor_id}' not found"}
    return dict(doc)
