"""Versioned SQLite storage for Customer Profiles."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from shared.storage import get_db_path, execute, fetchall, fetchone

DB_NAME = "customer_profile"

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    company TEXT NOT NULL,
    industry TEXT NOT NULL,
    profile_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(customer_id, version)
)
"""


def init_db() -> str:
    db_path = get_db_path(DB_NAME)
    execute(db_path, CREATE_TABLE)
    return db_path


def get_next_version(customer_id: str) -> int:
    db_path = get_db_path(DB_NAME)
    rows = fetchall(
        db_path,
        "SELECT MAX(version) as max_ver FROM profiles WHERE customer_id = ?",
        (customer_id,),
    )
    max_ver = rows[0]["max_ver"] if rows else None
    return (max_ver or 0) + 1


def save_profile(customer_id: str, profile: dict[str, Any]) -> int:
    db_path = get_db_path(DB_NAME)
    version = get_next_version(customer_id)
    execute(
        db_path,
        "INSERT INTO profiles (customer_id, version, company, industry, profile_json, created_at) VALUES (?,?,?,?,?,?)",
        (
            customer_id,
            version,
            profile.get("company", ""),
            profile.get("industry", ""),
            json.dumps(profile),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    return version


def list_versions(customer_id: str) -> list[dict[str, Any]]:
    db_path = get_db_path(DB_NAME)
    return fetchall(
        db_path,
        "SELECT id, customer_id, version, company, industry, created_at FROM profiles WHERE customer_id = ? ORDER BY version DESC",
        (customer_id,),
    )


def get_profile_version(customer_id: str, version: int) -> dict[str, Any] | None:
    db_path = get_db_path(DB_NAME)
    row = fetchone(
        db_path,
        "SELECT * FROM profiles WHERE customer_id = ? AND version = ?",
        (customer_id, version),
    )
    if row:
        row["profile_json"] = json.loads(row["profile_json"])
    return row
