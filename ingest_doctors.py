"""
Ingestion script: load doctors_data_enriched.xlsx into all three data stores.
Uses ONLY the 'Perumbakam' sheet (glh-chn / Perumbakkam branch).
Clears all existing data first.

Usage:
    python ingest_doctors.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from apps.kb.config import get_settings
from apps.kb.db.database import get_session, get_async_engine, init_db
from apps.kb.db.models import Base, Doctor, Hospital, ScheduleDay, TimeSlot
from apps.kb.graph.neo4j_engine import Neo4jQueryEngine
from apps.kb.rag.vector_store import VectorStore, COLLECTION_PROFILES
from lib.config import TENANT_META

import chromadb
from neo4j import AsyncGraphDatabase
from sentence_transformers import SentenceTransformer

settings = get_settings()

PERUMBAKKAM_TENANT = "glh-chn"
PERUMBAKKAM_SHEET = "Perumbakam"
EXCEL_FILE = "doctors_data_enriched.xlsx"


def _parse_csv(value) -> list[str]:
    if not value or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if v and str(v).strip()]
    items = str(value).split(",")
    return [s.strip() for s in items if s.strip()]


def _parse_experience(value) -> int | None:
    if pd.isna(value) or value is None or value == "":
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def _safe(val):
    if pd.isna(val) or val is None:
        return None
    return str(val).strip() if str(val).strip() != "" else None


# ── SQLite: clear + reload ────────────────────────────────────────────────────

def clean_sqlite(session):
    """Delete all rows from schedule/time_slots, doctors, hospitals (clear and reload)."""
    session.query(TimeSlot).delete()
    session.query(ScheduleDay).delete()
    session.query(Doctor).delete()
    session.query(Hospital).delete()
    session.commit()


def ingest_sqlite(df: pd.DataFrame):
    session = get_session()
    try:
        # Clear existing data
        clean_sqlite(session)
        print("  Cleared existing SQLite data")

        # ── Hospitals ──
        tid = PERUMBAKKAM_TENANT
        loc_id = TENANT_META.get(tid, 80)

        from lib.config import get_tenant_config
        tc = get_tenant_config(tid)
        tenant_rows = df[df["tenant_id"] == tid]
        hospital_name = str(tenant_rows.iloc[0].get("hospital_name", "")).strip()

        h = Hospital(
            id=tid,
            name=tc.brand_name or hospital_name,
            branch=hospital_name,
            brand_description=tc.brand_description,
            city=tc.city,
            state=tc.state,
            location_id=loc_id,
            loc_short=tc.loc_short,
            address=f"{hospital_name}, {tc.city}, {tc.state}",
            phone=tc.contact_phone,
            emergency_phone=tc.contact_phone,
            booking_base_url=getattr(settings, "booking_base_url", "https://www.gleneagleshospitals.co.in/book-an-appointment"),
            url_slug=tc.loc_short,
            tenant_id=tid,
        )
        session.merge(h)
        session.commit()
        print(f"  [SQLite] Hospital: {tid} — {hospital_name}")

        # ── Doctors ──
        doc_count = 0
        for _, row in df.iterrows():
            if str(row.get("tenant_id", "")) != tid:
                continue

            designation = _safe(row.get("Unnamed: 5", ""))
            speciality = _safe(row.get("speciality", ""))
            fee = row.get("consultation_fee")
            fee_str = _safe(fee) if not pd.isna(fee) else None

            doctor = Doctor(
                id=str(row["id"]),
                name=str(row.get("name", "")),
                first_name=_safe(row.get("first_name", "")),
                last_name=_safe(row.get("last_name", "")),
                gender=_safe(row.get("gender", "")),
                location_id=loc_id,
                designation=designation,
                speciality=speciality,
                experience_years=_parse_experience(row.get("experience_years")),
                consultation_fee=fee_str,
                bio=_safe(row.get("bio", "")),
                profile_url=_safe(row.get("profile_url", "")),
                booking_url=_safe(row.get("booking_url", "")),
                specializations=", ".join(_parse_csv(row.get("specializations", ""))),
                qualifications=", ".join(_parse_csv(row.get("qualifications", ""))),
                languages=", ".join(_parse_csv(row.get("languages", ""))),
                consultation_types=None,
                working_days=None,
                next_available=None,
                total_available_slots=0,
                tenant_id=tid,
            )
            session.merge(doctor)
            doc_count += 1

        session.commit()
        print(f"[SQLite] Loaded {doc_count} doctors (Perumbakkam only)")
    finally:
        session.close()


# ── Neo4j: clear + reload ─────────────────────────────────────────────────────

async def ingest_neo4j(df: pd.DataFrame, graph_engine: Neo4jQueryEngine):
    async with graph_engine._driver.session(database=graph_engine._db) as session:
        # Clear everything
        await session.run("MATCH (n) DETACH DELETE n")
        print("  Cleared existing Neo4j data")

        # Schema
        for stmt in [
            "CREATE CONSTRAINT doctor_id_unique IF NOT EXISTS FOR (d:Doctor) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT hospital_id_unique IF NOT EXISTS FOR (h:Hospital) REQUIRE h.id IS UNIQUE",
            "CREATE CONSTRAINT spec_name_unique IF NOT EXISTS FOR (s:Specialization) REQUIRE s.name IS UNIQUE",
            "CREATE CONSTRAINT lang_name_unique IF NOT EXISTS FOR (l:Language) REQUIRE l.name IS UNIQUE",
            "CREATE FULLTEXT INDEX doctor_ft IF NOT EXISTS FOR (d:Doctor) ON EACH [d.name, d.designation]",
            "CREATE FULLTEXT INDEX spec_ft IF NOT EXISTS FOR (s:Specialization) ON EACH [s.name]",
            "CREATE INDEX doctor_name_idx IF NOT EXISTS FOR (d:Doctor) ON (d.name)",
        ]:
            try:
                await session.run(stmt)
            except Exception as e:
                print(f"  [Neo4j] Schema skip: {e}")

        # Hospital
        from lib.config import get_tenant_config
        tc = get_tenant_config(PERUMBAKKAM_TENANT)
        loc_id = TENANT_META.get(PERUMBAKKAM_TENANT, 80)

        await session.run(
            """
            MERGE (h:Hospital {id: $id})
            SET h.name = $name, h.city = $city, h.state = $state,
                h.location_id = $loc_id, h.tenant_id = $tid, h.sql_id = $id
            """,
            id=PERUMBAKKAM_TENANT, name=tc.brand_name, city=tc.city, state=tc.state,
            loc_id=loc_id, tid=PERUMBAKKAM_TENANT,
        )
        print(f"  [Neo4j] Hospital: {PERUMBAKKAM_TENANT}")

        # Doctors
        doc_count = 0
        for _, row in df.iterrows():
            if str(row.get("tenant_id", "")) != PERUMBAKKAM_TENANT:
                continue

            doc_id = str(row["id"])
            designation = _safe(row.get("Unnamed: 5", ""))
            experience = _parse_experience(row.get("experience_years"))

            await session.run(
                """
                MERGE (d:Doctor {id: $id})
                SET d.name = $name, d.designation = $designation, d.gender = $gender,
                    d.experience_years = $exp, d.tenant_id = $tid, d.sql_id = $id
                """,
                id=doc_id, name=str(row.get("name", "")),
                designation=designation,
                gender=_safe(row.get("gender", "")),
                exp=experience, tid=PERUMBAKKAM_TENANT,
            )

            # PRACTICES_AT
            await session.run(
                "MATCH (d:Doctor {id: $did}), (h:Hospital {id: $hid}) MERGE (d)-[:PRACTICES_AT]->(h)",
                did=doc_id, hid=PERUMBAKKAM_TENANT,
            )

            # SPECIALIZES_IN
            specs = _parse_csv(row.get("specializations", ""))
            spec = _safe(row.get("speciality", ""))
            if spec:
                specs.append(spec)
            for spec_name in set(specs):
                spec_name = spec_name.strip()
                if not spec_name:
                    continue
                await session.run(
                    "MERGE (s:Specialization {name: $name}) WITH s MATCH (d:Doctor {id: $did}) MERGE (d)-[:SPECIALIZES_IN]->(s)",
                    name=spec_name, did=doc_id,
                )

            # SPEAKS
            langs = _parse_csv(row.get("languages", ""))
            for lang in set(langs):
                lang = lang.strip()
                if not lang:
                    continue
                await session.run(
                    "MERGE (l:Language {name: $name}) WITH l MATCH (d:Doctor {id: $did}) MERGE (d)-[:SPEAKS]->(l)",
                    name=lang, did=doc_id,
                )

            doc_count += 1

        print(f"[Neo4j] Loaded {doc_count} doctors (Perumbakkam only)")


# ── ChromaDB: clear + reload ───────────────────────────────────────────────────

def ingest_chroma(df: pd.DataFrame, embedder: SentenceTransformer):
    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    profiles = client.get_or_create_collection(COLLECTION_PROFILES, metadata={"hnsw:space": "cosine"})

    # Clear existing
    try:
        result = profiles.get(include=["metadatas", "documents"])
        existing_ids = result.get("ids", [])
        if existing_ids:
            profiles.delete(ids=existing_ids)
        print("  Cleared existing ChromaDB data")
    except Exception as e:
        print(f"  [ChromaDB] Clear note: {e}")

    chunks = []
    for _, row in df.iterrows():
        if str(row.get("tenant_id", "")) != PERUMBAKKAM_TENANT:
            continue

        name = str(row.get("name", ""))
        designation = _safe(row.get("Unnamed: 5", "")) or ""
        speciality = _safe(row.get("speciality", "")) or ""
        experience = row.get("experience_years")
        fee = row.get("consultation_fee")
        languages = _safe(row.get("languages", "")) or ""
        specializations = _safe(row.get("specializations", "")) or ""
        hospital = _safe(row.get("hospital_name", "")) or ""
        bio = _safe(row.get("bio", "")) or ""

        text = f"Dr. {name}"
        if designation:
            text += f", {designation}"
        if speciality:
            text += f" — {speciality}"
        if not pd.isna(experience):
            text += f" ({int(float(experience))} years experience)"
        if not pd.isna(fee):
            text += f" | Fee: ₹{fee}"
        if languages:
            text += f" | Languages: {languages}"
        if specializations:
            text += f" | Specializations: {specializations}"
        if hospital:
            text += f" | Hospital: {hospital}"
        if bio:
            text += f"\n\n{bio}"

        chunks.append({
            "id": f"doc_{row['id']}",
            "text": text,
            "metadata": {
                "doctor_id": str(row["id"]),
                "doctor_name": name,
                "tenant_id": PERUMBAKKAM_TENANT,
                "designation": designation,
                "speciality": speciality,
                "specializations": specializations,
                "experience_years": int(float(experience)) if not pd.isna(experience) else 0,
                "consultation_fee": str(fee) if not pd.isna(fee) else "",
                "languages": languages,
                "hospital_name": hospital,
                "chunk_type": "profile",
            },
        })

    batch_size = 32
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        ids = [c["id"] for c in batch]
        texts = [c["text"] for c in batch]
        metadatas = []
        for c in batch:
            meta = {}
            for k, v in c["metadata"].items():
                meta[k] = v if isinstance(v, (str, int, float, bool)) else str(v)
            metadatas.append(meta)

        embeddings = embedder.encode(texts, normalize_embeddings=True).tolist()
        profiles.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
        print(f"  [ChromaDB] Batch {i // batch_size + 1}: {len(batch)} chunks")

    print(f"[ChromaDB] Loaded {len(chunks)} doctor profile chunks (Perumbakkam only)")


# ── Main ─────────────────────────────────────────────────────────────────────

async def main():
    xlsx_path = Path(EXCEL_FILE)
    if not xlsx_path.exists():
        print(f"ERROR: {xlsx_path} not found")
        sys.exit(1)

    print("Reading Excel (Perumbakam sheet only)...")
    xls = pd.ExcelFile(xlsx_path)
    print(f"  Sheets available: {xls.sheet_names}")

    df = pd.read_excel(xlsx_path, sheet_name=PERUMBAKKAM_SHEET)
    print(f"  Loaded {len(df)} rows from '{PERUMBAKKAM_SHEET}' sheet")
    print(f"  Tenants in sheet: {df['tenant_id'].unique()}")

    # 1. SQLite
    print("\n=== SQLite ===")
    init_db()
    ingest_sqlite(df)

    # 2. Neo4j
    print("\n=== Neo4j ===")
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )
    graph_engine = Neo4jQueryEngine(driver, database=settings.neo4j_database)
    await ingest_neo4j(df, graph_engine)
    await driver.close()

    # 3. ChromaDB
    print("\n=== ChromaDB ===")
    embedder = SentenceTransformer(settings.embedding_model, device=settings.embedding_device)
    ingest_chroma(df, embedder)

    print("\n=== Done! All databases updated with Perumbakkam data only. ===")


if __name__ == "__main__":
    asyncio.run(main())
