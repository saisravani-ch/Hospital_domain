"""
/search routes — semantic + graph search for doctors.
"""

from __future__ import annotations

from typing import Any, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text

from src.knowledge_base.api.dependencies import get_graphrag_engine, get_vector_store, get_graph_engine
from src.knowledge_base.db.database import get_session
from src.knowledge_base.query.graphrag_engine import GraphRAGEngine
from src.knowledge_base.rag.vector_store import VectorStore
from src.knowledge_base.graph.neo4j_loader import Neo4jQueryEngine

router = APIRouter(prefix="/search", tags=["search"])


class RetrieveRequest(BaseModel):
    query: str
    tenant_id: Optional[str] = None
    specialization: Optional[str] = None
    doctor_name: Optional[str] = None
    language: Optional[str] = None
    min_experience: Optional[int] = None
    location: Optional[str] = None


@router.post("/retrieve")
async def retrieve_doctors(
    req: RetrieveRequest,
    engine: GraphRAGEngine = Depends(get_graphrag_engine),
) -> dict[str, Any]:
    """
    Retrieval-only search: vector + graph search, no LLM calls.
    Returns fused doctor results for the orchestrator to synthesize.
    """
    fused, context_text, booking_links = await engine.retrieve_context(
        req.query, req.tenant_id,
        specialization=req.specialization,
        doctor_name=req.doctor_name,
        language=req.language,
        min_experience=req.min_experience,
        location=req.location,
    )

    # Supplement consultation_fee from SQLite (transactional data, not in Neo4j)
    ids_missing = [d.get("sql_id") or d.get("id") or d.get("doctor_id") for d in fused if not d.get("consultation_fee")]
    if ids_missing:
        session = get_session()
        try:
            placeholders = ",".join(f":id_{i}" for i in range(len(ids_missing)))
            params = {f"id_{i}": did for i, did in enumerate(ids_missing)}
            rows = session.execute(
                text(f"SELECT id, consultation_fee FROM doctors WHERE id IN ({placeholders})"),
                params,
            ).fetchall()
            fee_map = {row[0]: row[1] for row in rows if row[1] is not None}
            for d in fused:
                did = d.get("sql_id") or d.get("id") or d.get("doctor_id")
                if did in fee_map:
                    d["consultation_fee"] = fee_map[did]
        finally:
            session.close()

    return {
        "doctors": [
            {
                "doctor_id": d.get("doctor_id") or d.get("id") or d.get("sql_id", ""),
                "name": d.get("name") or d.get("doctor_name", ""),
                "specializations": d.get("specializations", ""),
                "experience_years": d.get("experience_years"),
                "consultation_fee": d.get("consultation_fee"),
                "languages": d.get("languages", ""),
                "hospital": d.get("hospitals") or d.get("hospital_ids", ""),
                "designation": d.get("designation", ""),
                "hospitals": d.get("hospitals") or [],
                "cities": d.get("cities") or [],
                "tenant_id": d.get("tenant_id") or "",
            }
            for d in fused
        ],
        "booking_links": booking_links,
        "total_doctors": len(fused),
    }


@router.get("/doctors")
async def search_doctors(
    q: str = Query(..., description="Natural language query, e.g. 'heart specialist Tamil speaking'"),
    n: int = Query(6, ge=1, le=20, description="Number of results"),
    tenant_id: Optional[str] = Query(None, description="Tenant filter (e.g. 'gleneagles', 'inventaa')"),
    engine: GraphRAGEngine = Depends(get_graphrag_engine),
):
    """
    GraphRAG search: combines semantic vector search with Neo4j graph traversal.
    Returns ranked list of matching doctors with booking links.
    """
    result = await engine.query(q, tenant_id=tenant_id)
    return {
        "query": q,
        "intent": result.intent,
        "doctors": result.doctors[:n],
        "booking_links": result.booking_links[:n],
        "ai_response": result.response,
    }


@router.get("/doctors/semantic")
async def semantic_search(
    q: str = Query(..., description="Natural language query"),
    n: int = Query(5, ge=1, le=20),
    store: VectorStore = Depends(get_vector_store),
):
    """Pure semantic vector search (no graph traversal)."""
    results = await __import__("asyncio").to_thread(store.semantic_search, q, n)
    return {"query": q, "results": results}


@router.get("/doctors/by-specialization")
async def search_by_specialization(
    specialization: str = Query(..., description="e.g. 'Cardiology', 'Orthopaedics'"),
    n: int = Query(10, ge=1, le=50),
    graph: Neo4jQueryEngine = Depends(get_graph_engine),
):
    """Graph-based search: match doctors by specialization node in Neo4j."""
    results = await graph.find_doctors_by_specialization(specialization, n)
    return {"specialization": specialization, "doctors": results}
