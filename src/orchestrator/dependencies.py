from __future__ import annotations

import openai
from neo4j import AsyncGraphDatabase

from src.knowledge_base.config import get_settings
from src.knowledge_base.graph.neo4j_loader import Neo4jQueryEngine
from src.knowledge_base.query.graphrag_engine import GraphRAGEngine
from src.knowledge_base.rag.vector_store import VectorStore
from src.memory.conversation_memory import ConversationMemory

settings = get_settings()

_vector_store: VectorStore | None = None
_graph_engine: Neo4jQueryEngine | None = None
_graphrag_engine: GraphRAGEngine | None = None
_llm_client: openai.AsyncAzureOpenAI | None = None
_memory: ConversationMemory | None = None


async def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


async def get_graph_engine() -> Neo4jQueryEngine | None:
    global _graph_engine
    if _graph_engine is None:
        try:
            driver = AsyncGraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_username, settings.neo4j_password),
                connection_timeout=5,
            )
            _graph_engine = Neo4jQueryEngine(driver, database=settings.neo4j_database)
        except Exception:
            from loguru import logger
            logger.warning("Neo4j unavailable — graph engine disabled")
            _graph_engine = None
    return _graph_engine


async def get_graphrag_engine() -> GraphRAGEngine | None:
    global _graphrag_engine
    if _graphrag_engine is None:
        vs = await get_vector_store()
        ge = await get_graph_engine()
        _graphrag_engine = GraphRAGEngine(vector_store=vs, graph_engine=ge)
    return _graphrag_engine


def get_llm_client() -> openai.AsyncAzureOpenAI | None:
    global _llm_client
    if _llm_client is None:
        try:
            _llm_client = openai.AsyncAzureOpenAI(
                api_key=settings.azure_openai_api_key,
                azure_endpoint=settings.azure_openai_endpoint,
                api_version=settings.azure_openai_api_version,
                timeout=10,
                max_retries=0,
            )
        except Exception:
            from loguru import logger
            logger.warning("Azure OpenAI unavailable — LLM disabled")
            _llm_client = None
    return _llm_client


def get_memory() -> ConversationMemory:
    global _memory
    if _memory is None:
        _memory = ConversationMemory()
    return _memory
