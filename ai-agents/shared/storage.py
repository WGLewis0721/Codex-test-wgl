"""SQLite connection pool and CRUD helpers."""
from __future__ import annotations
import sqlite3
import os
from contextlib import contextmanager
from typing import Any, Generator
from .config import get_settings
from .logging import get_logger

logger = get_logger(__name__)
_settings = get_settings()


def get_db_path(db_name: str) -> str:
    os.makedirs(_settings.sqlite_dir, exist_ok=True)
    return os.path.join(_settings.sqlite_dir, f"{db_name}.db")


@contextmanager
def get_connection(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute(db_path: str, sql: str, params: tuple[Any, ...] = ()) -> None:
    with get_connection(db_path) as conn:
        conn.execute(sql, params)


def fetchall(
    db_path: str,
    sql: str,
    params: tuple[Any, ...] = (),
) -> list[dict[str, Any]]:
    with get_connection(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]


def fetchone(
    db_path: str,
    sql: str,
    params: tuple[Any, ...] = (),
) -> dict[str, Any] | None:
    with get_connection(db_path) as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


def paginate(
    db_path: str,
    sql: str,
    params: tuple[Any, ...] = (),
    limit: int = 20,
    offset: int = 0,
) -> list[dict[str, Any]]:
    paged_sql = f"{sql} LIMIT ? OFFSET ?"
    return fetchall(db_path, paged_sql, params + (limit, offset))
