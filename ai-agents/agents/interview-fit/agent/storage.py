"""SQLite storage + file exports for Interview Fit."""
from __future__ import annotations
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from shared.storage import get_db_path, execute, fetchall
from shared.config import get_settings
from shared.utils import sanitize_filename, write_export

_settings = get_settings()
DB_NAME = "interview_fit"
EXPORT_DIR = Path(_settings.sqlite_dir) / "exports"

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fit_grade TEXT NOT NULL,
    jd_summary TEXT NOT NULL,
    export_path TEXT,
    created_at TEXT NOT NULL
)
"""


def init_db() -> str:
    db_path = get_db_path(DB_NAME)
    execute(db_path, CREATE_TABLE)
    return db_path


def save_analysis(fit_grade: str, jd_summary: str, export_path: str | None = None) -> None:
    db_path = get_db_path(DB_NAME)
    execute(
        db_path,
        "INSERT INTO analyses (fit_grade, jd_summary, export_path, created_at) VALUES (?,?,?,?)",
        (fit_grade, jd_summary, export_path, datetime.now(timezone.utc).isoformat()),
    )


def save_export(content: str, filename: str) -> str:
    """Write analysis markdown to exports directory."""
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_filename(filename)
    path = write_export(content, EXPORT_DIR / safe_name)
    return str(path)


def list_exports() -> list[dict[str, Any]]:
    db_path = get_db_path(DB_NAME)
    return fetchall(db_path, "SELECT * FROM analyses ORDER BY created_at DESC")
