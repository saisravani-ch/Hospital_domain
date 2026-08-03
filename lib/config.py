"""Shared settings loaded from environment / .env file.

Cross-cutting config used by orchestrator, tools, and KB service.
KB-specific fields (Neo4j, Chroma, SQLite path) live in `knowledge_base.config`.

# Domain glossary — two distinct IDs, never interchangeable

- **tenant_id** — hospital BRANCH (e.g. "glh-chn"). Scopes knowledge-base
  search (Chroma/Neo4j filtering) and branding. Defined in `tenants.json`.
- **client_id** — hospital GROUP that owns branches (e.g. "gleneagles_001").
  Scopes booking/workflow endpoints (`CLIENTS` in apps/workflows/config.py).
  Defined in `clients.json`.

One client owns many tenants. A booking always happens under the *client*
(hospital group); the *tenant* (branch) merely identifies which location the
patient is talking about. Use `resolve_booking_client_id()` to map a tenant
(branch) to its client before calling workflow endpoints.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# ── Tenant branding ──────────────────────────────────────────────────────────


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


# ── Tenant registry — loaded from tenants.json with fallback ────────────────


def _load_tenant_meta() -> dict[str, int]:
    """Load tenant_id → location_id mapping from tenants.json, or fall back to hardcoded dict."""
    path = Path(os.getcwd()) / "tenants.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return {tid: v["location_id"] for tid, v in data.items()}
    return {
        "glh-chn":     80,
        "glh-adyar":   81,
        "glh-kengeri": 82,
        "glh-richmond": 83,
        "glh-parel":   84,
        "glh-lkp":     85,
        "glh-lbn":     86,
    }


def _load_tenant_data() -> dict[str, dict]:
    """Load full tenant data from tenants.json, or fall back to derived data."""
    path = Path(os.getcwd()) / "tenants.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


TENANT_META: dict[str, int] = _load_tenant_meta()
_TENANT_DATA: dict[str, dict] = _load_tenant_data()


# ── Client registry — tenant (branch) → client (hospital group) ─────────────
# Multiple tenant branches belong to one client (hospital group). Booking
# endpoints are keyed by client_id (hospital group), so a branch tenant must
# resolve to its client before any workflow call.
#
# Loaded from `tenants.json` (`client_id` per tenant) when present; the dict
# below is only a fallback for deployments without the file.


def _load_tenant_clients() -> dict[str, str]:
    path = Path(os.getcwd()) / "tenants.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return {tid: v["client_id"] for tid, v in data.items() if v.get("client_id")}
    return {
        "glh-chn": "gleneagles_001",
        "glh-adyar": "gleneagles_001",
        "glh-kengeri": "gleneagles_001",
        "glh-richmond": "gleneagles_001",
        "glh-parel": "gleneagles_001",
        "glh-lkp": "gleneagles_001",
        "glh-lbn": "gleneagles_001",
    }


TENANT_CLIENTS: dict[str, str] = _load_tenant_clients()


def resolve_booking_client_id(tenant_id: str | None, client_id: str | None) -> str | None:
    """Resolve the booking client (hospital group) id for a session.

    Priority: explicit client_id → tenant's client → configured default → None.
    If the client_id is actually a branch/tenant id, map it to its client
    (hospital group) so workflow endpoints never receive a tenant id.
    """
    cid = client_id or (TENANT_CLIENTS.get(tenant_id) if tenant_id else None)
    if cid and cid in TENANT_CLIENTS:
        return TENANT_CLIENTS[cid]
    return cid or get_settings().booking_client_id or None


# ── Shared Settings ──────────────────────────────────────────────────────────


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    tenant_id: str

    # Azure OpenAI
    azure_openai_api_key: str
    azure_openai_endpoint: str
    azure_openai_api_version: str
    azure_openai_deployment_name: str
    azure_openai_deployment2_name: str = ""

    # Tenant branding defaults (overridable per tenant via DB / env)
    currency_symbol: str = "₹"
    item_noun: str = "doctor"
    item_noun_plural: str = "doctors"
    booking_base_url: str = "https://www.gleneagleshospitals.co.in/book-an-appointment"
    # Default booking client (hospital group) used when neither client_id nor a
    # tenant mapping resolves (env: BOOKING_CLIENT_ID). Empty = no fallback.
    booking_client_id: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


# ── Tenant helpers ───────────────────────────────────────────────────────────


def get_tenant_config(tenant_id: str | None = None) -> TenantConfig:
    """Resolve a TenantConfig from tenant data file or build-time fallback."""
    s = get_settings()
    tid = tenant_id or s.tenant_id
    loc_id = TENANT_META.get(tid, 0)

    td = _TENANT_DATA.get(tid, {})
    if td:
        return TenantConfig(
            tenant_id=tid,
            brand_name=td.get("brand_name", ""),
            brand_description=td.get("brand_description", ""),
            currency_symbol=s.currency_symbol,
            item_noun=s.item_noun,
            item_noun_plural=s.item_noun_plural,
            contact_phone=td.get("contact_phone", ""),
            booking_base_url=s.booking_base_url,
            location_id=loc_id,
            loc_short=td.get("loc_short", ""),
            city=td.get("city", ""),
            state=td.get("state", ""),
            hospital_id=tid,
        )

    return TenantConfig(
        tenant_id=tid,
        brand_name=tid.replace("-", " ").title() if tid else "",
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
