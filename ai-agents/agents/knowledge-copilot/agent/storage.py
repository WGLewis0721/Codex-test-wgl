"""SQLite storage for Knowledge Copilot document metadata."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from shared.storage import get_db_path, execute, fetchall

DB_NAME = "knowledge_copilot"

CREATE_DOCS_TABLE = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    doc_id TEXT NOT NULL UNIQUE,
    chunk_count INTEGER NOT NULL,
    created_at TEXT NOT NULL
)
"""

CREATE_QUERIES_TABLE = """
CREATE TABLE IF NOT EXISTS queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    answer TEXT NOT NULL,
    sources TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""


def init_db() -> str:
    db_path = get_db_path(DB_NAME)
    execute(db_path, CREATE_DOCS_TABLE)
    execute(db_path, CREATE_QUERIES_TABLE)
    return db_path


def save_document(filename: str, doc_id: str, chunk_count: int) -> None:
    db_path = get_db_path(DB_NAME)
    execute(
        db_path,
        "INSERT OR REPLACE INTO documents (filename, doc_id, chunk_count, created_at) VALUES (?,?,?,?)",
        (filename, doc_id, chunk_count, datetime.now(timezone.utc).isoformat()),
    )


def get_documents() -> list[dict[str, Any]]:
    db_path = get_db_path(DB_NAME)
    return fetchall(db_path, "SELECT * FROM documents ORDER BY created_at DESC")


def save_query(query: str, answer: str, sources: str) -> None:
    db_path = get_db_path(DB_NAME)
    execute(
        db_path,
        "INSERT INTO queries (query, answer, sources, created_at) VALUES (?,?,?,?)",
        (query, answer, sources, datetime.now(timezone.utc).isoformat()),
    )
