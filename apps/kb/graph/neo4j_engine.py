"""
apps/kb/graph/neo4j_engine.py

Semantic-only graph queries in Neo4j AuraDB.

Nodes:   Doctor, Hospital, Specialization, Language
Edges:   PRACTICES_AT, SPECIALIZES_IN, SPEAKS

No schedule data here — availability lives entirely in SQLite (schedule_days / time_slots).
Every Doctor node carries sql_id = SQL doctors.id for cross-store retrieval.
"""

from __future__ import annotations

from neo4j import AsyncGraphDatabase, AsyncDriver

from apps.kb.config import get_settings

settings = get_settings()


class Neo4jQueryEngine:
    """
    Semantic graph queries. Results contain sql_id so callers can join to SQLite
    for schedule availability and transactional details.
    """

    def __init__(self, driver: AsyncDriver, database: str):
        self._driver = driver
        self._db = database

    def _session(self):
        return self._driver.session(database=self._db)

    async def find_doctors_by_specialization(self, specialization: str, limit: int = 20, tenant_id: str | None = None) -> list[dict]:
        """Find doctors by full-text search on specialization names (exact + prefix for related terms), optionally filtered by tenant."""
        root = specialization[:5].lower() if len(specialization) >= 5 else specialization.lower()
        lucene_query = f"{specialization} OR {root}*" if root != specialization.lower() else specialization
        async with self._session() as session:
            result = await session.run(
                """
                CALL db.index.fulltext.queryNodes('spec_ft', $spec) YIELD node AS s, score
                MATCH (d:Doctor)-[:SPECIALIZES_IN]->(s)
                """ + ("""
                WHERE d.tenant_id STARTS WITH $tenant_id
                """ if tenant_id else "") + """
                OPTIONAL MATCH (d)-[:PRACTICES_AT]->(h:Hospital)
                RETURN d.sql_id AS sql_id, d.name AS name, d.designation AS designation,
                       d.experience_years AS experience_years,
                       d.tenant_id AS tenant_id,
                       collect(DISTINCT s.name) AS specializations,
                       collect(DISTINCT h.name) AS hospitals,
                       collect(DISTINCT h.city)  AS cities
                ORDER BY d.experience_years DESC
                LIMIT $limit
                """,
                spec=lucene_query, limit=limit, tenant_id=tenant_id,
            )
            return await result.data()

    async def find_doctors_by_language(self, language: str, limit: int = 20, tenant_id: str | None = None) -> list[dict]:
        """Find doctors who SPEAKS the given language, optionally filtered by tenant."""
        async with self._session() as session:
            result = await session.run(
                """
                MATCH (d:Doctor)-[:SPEAKS]->(l:Language)
                WHERE toLower(l.name) CONTAINS toLower($lang)
                """ + ("""
                AND d.tenant_id STARTS WITH $tenant_id
                """ if tenant_id else "") + """
                OPTIONAL MATCH (d)-[:SPECIALIZES_IN]->(s:Specialization)
                OPTIONAL MATCH (d)-[:PRACTICES_AT]->(h:Hospital)
                RETURN d.sql_id AS sql_id, d.name AS name, d.designation AS designation,
                       d.tenant_id AS tenant_id,
                       collect(DISTINCT s.name) AS specializations,
                       collect(DISTINCT h.name) AS hospitals,
                       collect(DISTINCT h.city)  AS cities
                ORDER BY d.name
                LIMIT $limit
                """,
                lang=language, limit=limit, tenant_id=tenant_id,
            )
            return await result.data()

    async def find_by_fulltext(self, keyword: str, limit: int = 20, tenant_id: str | None = None) -> list[dict]:
        """Full-text search on doctor name and designation, optionally filtered by tenant."""
        async with self._session() as session:
            result = await session.run(
                """
                CALL db.index.fulltext.queryNodes('doctor_ft', $search_term) YIELD node AS d, score
                WHERE $tenant_id IS NULL OR d.tenant_id STARTS WITH $tenant_id
                OPTIONAL MATCH (d)-[:SPECIALIZES_IN]->(s:Specialization)
                OPTIONAL MATCH (d)-[:PRACTICES_AT]->(h:Hospital)
                RETURN d.sql_id AS sql_id, d.name AS name, d.designation AS designation,
                       d.tenant_id AS tenant_id,
                       score,
                       collect(DISTINCT s.name) AS specializations,
                       collect(DISTINCT h.name) AS hospitals
                ORDER BY score DESC
                LIMIT $limit
                """,
                search_term=keyword, limit=limit, tenant_id=tenant_id,
            )
            return await result.data()

    async def get_doctor_context(self, doctor_id: str) -> dict | None:
        """Full semantic context for one doctor (for RAG). Caller joins SQL for slots."""
        async with self._session() as session:
            result = await session.run(
                """
                MATCH (d:Doctor {id: $id})
                WITH d LIMIT 1
                OPTIONAL MATCH (d)-[:SPECIALIZES_IN]->(s:Specialization)
                OPTIONAL MATCH (d)-[:PRACTICES_AT]->(h:Hospital)
                OPTIONAL MATCH (d)-[:SPEAKS]->(l:Language)
                RETURN d.sql_id AS sql_id, d.name AS name,
                       d.designation AS designation,
                       d.experience_years AS experience_years,
                       d.gender AS gender,
                       collect(DISTINCT s.name)                          AS specializations,
                       collect(DISTINCT {name: h.name, city: h.city})   AS hospitals,
                       collect(DISTINCT l.name)                          AS languages
                """,
                id=doctor_id,
            )
            row = await result.single()
        return dict(row) if row else None

    async def colleagues_by_specialty(self, doctor_id: str, limit: int = 10) -> list[dict]:
        """Doctors sharing specialization and hospital with the given doctor."""
        async with self._session() as session:
            result = await session.run(
                """
                MATCH (d:Doctor {id: $did})-[:SPECIALIZES_IN]->(s:Specialization)
                MATCH (d)-[:PRACTICES_AT]->(h:Hospital)
                MATCH (c:Doctor)-[:SPECIALIZES_IN]->(s)
                MATCH (c)-[:PRACTICES_AT]->(h)
                WHERE c.id <> $did
                RETURN DISTINCT c.sql_id AS sql_id, c.name AS name,
                       c.designation AS designation,
                       s.name AS shared_specialty,
                       h.name AS hospital
                LIMIT $limit
                """,
                did=doctor_id, limit=limit,
            )
            return await result.data()

    async def get_doctors_at_hospital(self, hospital_id: str, limit: int = 100) -> list[dict]:
        async with self._session() as session:
            result = await session.run(
                """
                MATCH (d:Doctor)-[:PRACTICES_AT]->(h:Hospital {id: $hid})
                OPTIONAL MATCH (d)-[:SPECIALIZES_IN]->(s:Specialization)
                RETURN d.sql_id AS sql_id, d.name AS name, d.designation AS designation,
                       collect(DISTINCT s.name) AS specializations
                ORDER BY d.name
                LIMIT $limit
                """,
                hid=hospital_id, limit=limit,
            )
            return await result.data()
