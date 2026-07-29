"""
/doctors routes — individual doctor profiles and chunks.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

# pyrefly: ignore [missing-import]
from src.knowledge_base.api.dependencies import get_graph_engine, get_vector_store
from src.knowledge_base.graph.neo4j_loader import Neo4jQueryEngine
from src.knowledge_base.rag.vector_store import VectorStore
from src.knowledge_base.db.database import get_session

router = APIRouter(prefix="/doctors", tags=["doctors"])


@router.get("/{doctor_id}")
async def get_doctor(
    doctor_id: str,
    graph: Neo4jQueryEngine = Depends(get_graph_engine),
):
    """Full semantic context for a doctor (specializations, hospitals, languages)."""
    doc = await graph.get_doctor_context(doctor_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Doctor '{doctor_id}' not found")

    # Supplement transactional data from SQLite (not stored in Neo4j)
    session = get_session()
    try:
        row = session.execute(
            text("SELECT consultation_fee FROM doctors WHERE id = :did"),
            {"did": doctor_id},
        ).fetchone()
        if row and row[0] is not None:
            doc["consultation_fee"] = row[0]
    finally:
        session.close()

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
