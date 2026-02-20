"""Metadata logging for Workbench Gateway (no raw prompt storage by default)."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from shared.storage import get_db_path, execute, fetchall

DB_NAME = "workbench_gateway"

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    model TEXT NOT NULL,
    client_id TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""


def init_db() -> str:
    db_path = get_db_path(DB_NAME)
    execute(db_path, CREATE_TABLE)
    return db_path


def log_request(
    request_id: str,
    model: str,
    client_id: str | None,
    prompt_tokens: int,
    completion_tokens: int,
    status: str,
) -> None:
    db_path = get_db_path(DB_NAME)
    execute(
        db_path,
        "INSERT INTO requests (request_id, model, client_id, prompt_tokens, completion_tokens, status, created_at) VALUES (?,?,?,?,?,?,?)",
        (
            request_id,
            model,
            client_id,
            prompt_tokens,
            completion_tokens,
            status,
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def get_recent_requests(limit: int = 50) -> list[dict[str, Any]]:
    db_path = get_db_path(DB_NAME)
    return fetchall(db_path, "SELECT * FROM requests ORDER BY created_at DESC LIMIT ?", (limit,))


def get_stats() -> dict[str, Any]:
    db_path = get_db_path(DB_NAME)
    rows = fetchall(db_path, "SELECT COUNT(*) as total, model, status FROM requests GROUP BY model, status")
    return {"request_counts": rows}
