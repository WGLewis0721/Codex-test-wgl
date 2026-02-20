"""SQLite storage for Lead Qualification."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from shared.storage import get_db_path, execute, paginate, fetchall

DB_NAME = "lead_qualification"

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    contact TEXT NOT NULL,
    industry TEXT NOT NULL,
    budget TEXT NOT NULL,
    timeline TEXT NOT NULL,
    use_case TEXT NOT NULL,
    score INTEGER NOT NULL,
    breakdown TEXT NOT NULL,
    explanation TEXT NOT NULL,
    email_draft TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""


def init_db() -> str:
    db_path = get_db_path(DB_NAME)
    execute(db_path, CREATE_TABLE)
    return db_path


def save_lead(form_data: dict[str, Any], result: dict[str, Any]) -> None:
    db_path = get_db_path(DB_NAME)
    execute(
        db_path,
        """INSERT INTO leads (company, contact, industry, budget, timeline, use_case,
           score, breakdown, explanation, email_draft, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            form_data.get("company", ""),
            form_data.get("contact", ""),
            form_data.get("industry", ""),
            form_data.get("budget", ""),
            form_data.get("timeline", ""),
            form_data.get("use_case", ""),
            result["score"],
            json.dumps(result["breakdown"]),
            result["explanation"],
            result["email_draft"],
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def get_history(limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
    db_path = get_db_path(DB_NAME)
    return paginate(db_path, "SELECT * FROM leads ORDER BY created_at DESC", limit=limit, offset=offset)


def count_all() -> int:
    db_path = get_db_path(DB_NAME)
    rows = fetchall(db_path, "SELECT COUNT(*) as cnt FROM leads")
    return rows[0]["cnt"] if rows else 0
