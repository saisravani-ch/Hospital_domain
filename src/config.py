"""Shared settings loaded from environment / .env file.

Cross-cutting config used by orchestrator, tools, and KB service.
KB-specific fields (Neo4j, Chroma, SQLite path) live in `knowledge_base.config`.
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
