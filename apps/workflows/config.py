"""Configuration loaded from clients.json with hardcoded fallback.

NOTE: keys here are **client_id** values — hospital GROUPS (e.g.
"gleneagles_001"), never branch tenant ids (e.g. "glh-chn"). The agent
resolves tenant → client before calling these endpoints.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def _load_clients() -> dict:
    path = Path(os.getcwd()) / "clients.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for cid, cfg in data.items():
            cfg.setdefault("db_path", os.getenv("DB_PATH", "data/db/knowledge_base.db"))
            cfg.setdefault("whatsapp_account", os.getenv("WHATSAPP_ID", ""))
        return data
    return {
        "gleneagles_001": {
            "name": "Gleneagles Hospitals",
            "db_path": os.getenv("DB_PATH", "data/db/knowledge_base.db"),
            "whatsapp_account": os.getenv("WHATSAPP_ID", "wabp_gleneagles"),
        }
    }


CLIENTS: dict = _load_clients()


def get_client_config(client_id: str):
    if client_id not in CLIENTS:
        raise ValueError(f"Client not configured: {client_id}")
    return CLIENTS[client_id]


def get_database_url(client_id: str):
    return f"sqlite:///{get_client_config(client_id)['db_path']}"
