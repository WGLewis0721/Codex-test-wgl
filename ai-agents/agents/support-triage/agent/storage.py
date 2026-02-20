"""SQLite schema and queries for Support Triage."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))
from shared.storage import get_db_path, execute, paginate, fetchall

DB_NAME = "support_triage"

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_text TEXT NOT NULL,
    urgency TEXT NOT NULL,
    sentiment TEXT NOT NULL,
    domain TEXT NOT NULL,
    routing TEXT NOT NULL,
    draft_response TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""


def init_db() -> str:
    db_path = get_db_path(DB_NAME)
    execute(db_path, CREATE_TABLE)
    return db_path


def save_analysis(
    ticket_text: str,
    urgency: str,
    sentiment: str,
    domain: str,
    routing: str,
    draft_response: str,
) -> None:
    db_path = get_db_path(DB_NAME)
    execute(
        db_path,
        "INSERT INTO analyses (ticket_text, urgency, sentiment, domain, routing, draft_response, created_at) VALUES (?,?,?,?,?,?,?)",
        (ticket_text, urgency, sentiment, domain, routing, draft_response, datetime.now(timezone.utc).isoformat()),
    )


def get_history(limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
    db_path = get_db_path(DB_NAME)
    return paginate(
        db_path,
        "SELECT * FROM analyses ORDER BY created_at DESC",
        limit=limit,
        offset=offset,
    )


def count_all() -> int:
    db_path = get_db_path(DB_NAME)
    rows = fetchall(db_path, "SELECT COUNT(*) as cnt FROM analyses")
    return rows[0]["cnt"] if rows else 0
