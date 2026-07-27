"""Configuration for Gleneagles"""
import os

CLIENTS = {
    "gleneagles_001": {
        "name": "Gleneagles Hospitals",
        "db_path": os.getenv("DB_PATH", "data/db/knowledge_base.db"),
        "whatsapp_account": os.getenv("WHATSAPP_ID", "wabp_gleneagles"),
    }
}

def get_client_config(client_id: str):
    if client_id not in CLIENTS:
        raise ValueError(f"Client not configured: {client_id}")
    return CLIENTS[client_id]

def get_database_url(client_id: str):
    return f"sqlite:///{get_client_config(client_id)['db_path']}"