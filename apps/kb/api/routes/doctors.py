"""
/doctors routes — individual doctor profiles and chunks.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

# pyrefly: ignore [missing-import]
from apps.kb.api.dependencies import get_graph_engine, get_vector_store
from apps.kb.graph.neo4j_engine import Neo4jQueryEngine
from apps.kb.rag.vector_store import VectorStore
from apps.kb.db.database import get_session

router = APIRouter(prefix="/doctors", tags=["doctors"])


@router.get("/{doctor_id}")
async def get_doctor(
    doctor_id: str,
    graph: Neo4jQueryEngine = Depends(get_graph_engine),
):
    """Full semantic context for a doctor (specializations, hospitals, languages).
    Falls back to the SQLite record if the Neo4j lookup fails, so a graph hiccup
    never surfaces as a 500 to the agent/UI."""
    try:
        doc = await graph.get_doctor_context(doctor_id)
    except Exception:
        doc = None

    # Transactional data from SQLite (fees are not stored in Neo4j; also the fallback profile)
    session = get_session()
    try:
        row = session.execute(
            text("SELECT name, speciality, consultation_fee FROM doctors WHERE id = :did"),
            {"did": doctor_id},
        ).fetchone()
    finally:
        session.close()

    if not doc and not row:
        raise HTTPException(status_code=404, detail=f"Doctor '{doctor_id}' not found")

    if doc is None:
        doc = {
            "sql_id": doctor_id,
            "name": row[0],
            "specializations": [row[1]] if row[1] else [],
            "hospitals": [],
            "languages": [],
            "source": "sqlite-fallback",
        }
    if row and row[2] is not None:
        doc["consultation_fee"] = row[2]

    return doc


@router.get("/{doctor_id}/chunks")
async def get_doctor_chunks(
    doctor_id: str,
    store: VectorStore = Depends(get_vector_store),
):
    """Raw text chunks stored in the vector store for this doctor."""
    import asyncio
    chunks = await asyncio.to_thread(store.search_by_doctor_id, doctor_id)
    return {"doctor_id": doctor_id, "chunks": chunks}
