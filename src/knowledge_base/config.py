"""Centralised settings loaded from environment / .env file."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.orm import Session


# ── Tenant Configuration ────────────────────────────────────────────────────────
# Each tenant = one hospital branch.
# Tenant ID matches the hospital ID (e.g. "glh-chn" for Gleneagles Chennai).
# Define tenants in tenants.json at the project root (see tenants.json for format).
# The hardcoded dict below serves as a build-time registry before the DB is populated.
# At runtime all display/branding data is loaded from the `hospitals` SQLite table.


@dataclass
class TenantConfig:
    """Identity and branding for a hospital branch tenant."""

    tenant_id: str = ""
    brand_name: str = ""
    brand_description: str = ""
    currency_symbol: str = "₹"
    item_noun: str = "doctor"
    item_noun_plural: str = "doctors"
    contact_phone: str = ""
    booking_base_url: str = ""
    location_id: int = 0
    loc_short: str = ""
    city: str = ""
    state: str = ""
    hospital_id: str = ""

    def format(self, template: str) -> str:
        return (
            template
            .replace("{brand_name}", self.brand_name)
            .replace("{brand_description}", self.brand_description)
            .replace("{brand}", self.brand_name)
            .replace("{currency}", self.currency_symbol)
            .replace("{item_noun}", self.item_noun)
            .replace("{item_noun_plural}", self.item_noun_plural)
            .replace("{contact_phone}", self.contact_phone)
            .replace("{tenant_id}", self.tenant_id)
        )


# ── Tenant topology (build-time registry) ──────────────────────────────────────
# Minimal tenant_id → location_id mapping used by the data pipeline before
# the SQLite DB is populated. All display/branding fields come from the DB.

TENANT_META: dict[str, int] = {
    "glh-chn":     80,
    "glh-adyar":   81,
    "glh-kengeri": 82,
    "glh-richmond": 83,
    "glh-parel":   84,
    "glh-lkp":     85,
    "glh-lbn":     86,
}

LOCATION_TO_TENANT: dict[int, str] = {loc: tid for tid, loc in TENANT_META.items()}

TENANTS: tuple[str, ...] = tuple(TENANT_META.keys())


def tenant_id_for_location(location_id: int) -> str:
    """Map a location_id to the tenant_id that owns it."""
    return LOCATION_TO_TENANT.get(location_id, "")


def get_tenant_config(tenant_id: str | None = None) -> TenantConfig:
    """Resolve a TenantConfig without a DB session (uses slim build-time fallback)."""
    s = get_settings()
    tid = tenant_id or s.tenant_id
    loc_id = TENANT_META.get(tid, 0)

    return TenantConfig(
        tenant_id=tid,
        brand_name=tid.replace("-", " ").title().replace("Glh", "Gleneagles") if tid else "",
        brand_description=f"a hospital (tenant {tid})" if tid else "",
        currency_symbol=s.currency_symbol,
        item_noun=s.item_noun,
        item_noun_plural=s.item_noun_plural,
        contact_phone="",
        booking_base_url=s.booking_base_url,
        location_id=loc_id,
        loc_short=tid.split("-")[-1] if "-" in tid else "",
        city="",
        state="",
        hospital_id=tid,
    )


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


# ── Application Settings ────────────────────────────────────────────────────────


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Default tenant (used when no tenant_id is explicitly provided)
    tenant_id: str

    # Neo4j AuraDB  (env vars: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE)
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str
    neo4j_database: str

    # ChromaDB
    chroma_persist_dir: str

    # Azure OpenAI
    azure_openai_api_key: str
    azure_openai_endpoint: str
    azure_openai_api_version: str
    azure_openai_deployment_name: str

    # Embeddings
    embedding_model: str
    embedding_device: str

    # API
    api_host: str
    api_port: int

    # SQL — SQLite (structured facts: doctors, hospitals, schedules, slots)
    sqlite_path: str

    # Tenant branding defaults (overridable per tenant via DB / env)
    currency_symbol: str = "₹"
    item_noun: str = "doctor"
    item_noun_plural: str = "doctors"
    booking_base_url: str = "https://www.gleneagleshospitals.co.in/book-an-appointment"

    # Scraper / build (optional — only needed when running data import)
    gleneagles_base_url: str | None = None
    scrape_hospital_id: int | None = None
    scrape_delay_seconds: float | None = None
    scrape_max_pages: int | None = None
    raw_data_dir: str | None = None
    processed_data_dir: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
