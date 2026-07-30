"""KB-specific settings extending the shared config in `src.config`.

Re-exports all shared types so existing KB-internal imports keep working.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import SettingsConfigDict
from sqlalchemy.orm import Session

# Re-export shared types so KB-internal imports from this module still work
from src.config import (
    TENANT_META,
    Settings as _BaseSettings,
    TenantConfig,
    get_settings as _get_base_settings,
    get_tenant_config,
)

__all__ = [
    "TENANT_META",
    "KBSettings",
    "Settings",
    "TenantConfig",
    "get_kb_settings",
    "get_settings",
    "get_tenant_config",
    "get_tenant_config_from_db",
]


class KBSettings(_BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Neo4j AuraDB
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str
    neo4j_database: str

    # ChromaDB
    chroma_persist_dir: str

    # Embeddings
    embedding_model: str
    embedding_device: str

    # API
    api_host: str
    api_port: int

    # SQL — SQLite (structured facts)
    sqlite_path: str

    # Scraper / build (optional — only needed when running data import)
    gleneagles_base_url: str | None = None
    scrape_hospital_id: int | None = None
    scrape_delay_seconds: float | None = None
    scrape_max_pages: int | None = None
    raw_data_dir: str | None = None
    processed_data_dir: str | None = None


# Keep `Settings` as alias so existing imports of `Settings` from this module still work
Settings = KBSettings


@lru_cache
def get_kb_settings() -> KBSettings:
    return KBSettings()


# Override the shared get_settings so KB-internal code gets KB-specific settings
@lru_cache
def get_settings() -> KBSettings:
    return KBSettings()


def get_tenant_config_from_db(tid: str, session: Session) -> TenantConfig | None:
    """Load a TenantConfig from the `hospitals` SQLite table."""
    from src.knowledge_base.db.models import Hospital

    s = get_settings()
    h = session.query(Hospital).filter(Hospital.id == tid).first()
    if not h:
        return None

    return TenantConfig(
        tenant_id=tid,
        brand_name=h.name or "",
        brand_description=h.brand_description or "",
        currency_symbol=s.currency_symbol,
        item_noun=s.item_noun,
        item_noun_plural=s.item_noun_plural,
        contact_phone=h.phone or "",
        booking_base_url=h.booking_base_url or s.booking_base_url,
        location_id=h.location_id or 0,
        loc_short=h.loc_short or "",
        city=h.city or "",
        state=h.state or "",
        hospital_id=tid,
    )
