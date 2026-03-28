"""
Persistent response cache for repeated chat/analyze requests.
"""

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


CACHE_ENABLED = os.getenv("PERSISTENT_CACHE_ENABLED", "true").strip().lower() not in {"0", "false", "no"}
CACHE_PATH = Path(os.getenv("PERSISTENT_CACHE_PATH", Path(__file__).with_name("runtime_cache.sqlite3")))
CACHE_MAX_ROWS = int(os.getenv("PERSISTENT_CACHE_MAX_ROWS", "2000"))

_lock = threading.Lock()
_initialized = False


def init() -> None:
    global _initialized
    if not CACHE_ENABLED or _initialized:
        return

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        if _initialized:
            return
        with sqlite3.connect(CACHE_PATH) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    namespace TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    meta_json TEXT,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    PRIMARY KEY (namespace, cache_key)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_entries_expires_at ON cache_entries (expires_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_entries_created_at ON cache_entries (created_at)"
            )
            _prune_locked(conn)
        _initialized = True


def get(namespace: str, cache_key: str) -> dict[str, Any] | None:
    if not CACHE_ENABLED:
        return None
    init()
    now = time.time()
    with _lock:
        with sqlite3.connect(CACHE_PATH) as conn:
            row = conn.execute(
                """
                SELECT value_json, meta_json, expires_at
                FROM cache_entries
                WHERE namespace = ? AND cache_key = ?
                """,
                (namespace, cache_key),
            ).fetchone()
            if not row:
                return None
            if float(row[2]) <= now:
                conn.execute(
                    "DELETE FROM cache_entries WHERE namespace = ? AND cache_key = ?",
                    (namespace, cache_key),
                )
                conn.commit()
                return None
            value = json.loads(row[0])
            meta = json.loads(row[1]) if row[1] else {}
            return {"value": value, "meta": meta}


def set(namespace: str, cache_key: str, value: Any, ttl_seconds: int, meta: dict[str, Any] | None = None) -> None:
    if not CACHE_ENABLED or ttl_seconds <= 0:
        return
    init()
    now = time.time()
    expires_at = now + ttl_seconds
    with _lock:
        with sqlite3.connect(CACHE_PATH) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache_entries (
                    namespace, cache_key, value_json, meta_json, created_at, expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    namespace,
                    cache_key,
                    json.dumps(value, ensure_ascii=False),
                    json.dumps(meta or {}, ensure_ascii=False),
                    now,
                    expires_at,
                ),
            )
            _prune_locked(conn)
            conn.commit()


def _prune_locked(conn: sqlite3.Connection) -> None:
    now = time.time()
    conn.execute("DELETE FROM cache_entries WHERE expires_at <= ?", (now,))
    if CACHE_MAX_ROWS <= 0:
        return
    row = conn.execute("SELECT count(*) FROM cache_entries").fetchone()
    total = int(row[0] or 0) if row else 0
    overflow = total - CACHE_MAX_ROWS
    if overflow > 0:
        conn.execute(
            """
            DELETE FROM cache_entries
            WHERE rowid IN (
                SELECT rowid
                FROM cache_entries
                ORDER BY created_at ASC
                LIMIT ?
            )
            """,
            (overflow,),
        )
