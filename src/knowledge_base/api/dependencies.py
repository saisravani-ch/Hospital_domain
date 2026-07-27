"""
FastAPI dependency injection: shared singletons for vector store, graph engine,
Neo4j driver, and the GraphRAG query engine.
"""

from __future__ import annotations

from functools import lru_cache

from neo4j import AsyncGraphDatabase

from src.config import get_settings
from src.graph.neo4j_loader import Neo4jQueryEngine
from src.query.graphrag_engine import GraphRAGEngine
from src.rag.vector_store import VectorStore

settings = get_settings()

_vector_store: VectorStore | None = None
_graph_engine: Neo4jQueryEngine | None = None
_graphrag_engine: GraphRAGEngine | None = None


async def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


async def get_graph_engine() -> Neo4jQueryEngine:
    global _graph_engine
    if _graph_engine is None:
        driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
        _graph_engine = Neo4jQueryEngine(driver, database=settings.neo4j_database)
    return _graph_engine


async def get_graphrag_engine() -> GraphRAGEngine:
    global _graphrag_engine
    if _graphrag_engine is None:
        vs = await get_vector_store()
        ge = await get_graph_engine()
        _graphrag_engine = GraphRAGEngine(vector_store=vs, graph_engine=ge)
    return _graphrag_engine
