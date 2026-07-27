"""
/search routes — semantic + graph search for doctors.
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, Query

from src.knowledge_base.api.dependencies import get_graphrag_engine, get_vector_store, get_graph_engine
from src.knowledge_base.query.graphrag_engine import GraphRAGEngine
from src.knowledge_base.rag.vector_store import VectorStore
from src.knowledge_base.graph.neo4j_loader import Neo4jQueryEngine

router = APIRouter(prefix="/search", tags=["search"])


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
