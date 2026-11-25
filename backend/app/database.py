"""SQLite database setup using raw sqlite3 (no ORM overhead)."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator, List, Optional

from app.config import get_settings


def _get_db_path() -> str:
    return get_settings().db_path


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    db_path = _get_db_path()
    conn = _connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables and indexes on startup."""
    import os
    db_path = _get_db_path()
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)

    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT    NOT NULL,
                role        TEXT    NOT NULL,
                content     TEXT    NOT NULL,
                metadata    TEXT,
                created_at  TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session
            ON messages (session_id, id)
        """)


def session_exists(session_id: str) -> bool:
    with get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM messages WHERE session_id = ? LIMIT 1",
            (session_id,),
        ).fetchone()
        return row is not None


def get_session_messages(session_id: str) -> List[dict]:
    """Return all non-system messages for a session, oldest first."""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT role, content, metadata
            FROM messages
            WHERE session_id = ? AND role != 'system'
            ORDER BY id ASC
            """,
            (session_id,),
        ).fetchall()
    result = []
    for row in rows:
        msg: dict = {"role": row["role"], "content": row["content"]}
        if row["role"] == "assistant" and row["metadata"]:
            try:
                msg["metadata"] = json.loads(row["metadata"])
            except json.JSONDecodeError:
                pass
        result.append(msg)
    return result


def get_history_for_llm(session_id: str) -> List[dict]:
    """Return raw role/content pairs for LLM context (excludes system)."""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT role, content
            FROM messages
            WHERE session_id = ? AND role != 'system'
            ORDER BY id ASC
            """,
            (session_id,),
        ).fetchall()
    return [{"role": row["role"], "content": row["content"]} for row in rows]


def save_message(
    session_id: str,
    role: str,
    content: str,
    metadata: Optional[dict] = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    meta_str = json.dumps(metadata) if metadata else None
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO messages (session_id, role, content, metadata, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, role, content, meta_str, now),
        )


def check_db_health() -> bool:
    try:
        with get_db() as conn:
            conn.execute("SELECT 1").fetchone()
        return True
    except Exception:
        return False
