"""Database connection pool.

Uses SQLite for the fixture (zero external dependencies). Production
versions would swap in a PostgreSQL pool — the public API stays the same.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path


_DB_PATH = Path(__file__).parent / "fixture.db"
_local = threading.local()


def get_connection() -> sqlite3.Connection:
    """Return a thread-local connection to the fixture database.

    The schema is created lazily on first access so the fixture is
    self-contained — callers don't need to run migrations first.
    """
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        conn.row_factory = None  # tuples, not Row objects
        _local.conn = conn
        _ensure_schema(conn)
    return conn


def close_all() -> None:
    """Close the thread-local connection, if any."""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create fixture tables if they don't exist yet."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            email        TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at   TIMESTAMP NOT NULL,
            last_login   TIMESTAMP,
            is_active    INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS revoked_tokens (
            token       TEXT PRIMARY KEY,
            revoked_at  TIMESTAMP NOT NULL
        );

        CREATE TABLE IF NOT EXISTS charges (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            stripe_id   TEXT NOT NULL UNIQUE,
            amount_cents INTEGER NOT NULL,
            status      TEXT NOT NULL,
            created_at  INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS refunds (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            charge_id   TEXT NOT NULL REFERENCES charges(stripe_id),
            refund_id   TEXT NOT NULL UNIQUE,
            reason      TEXT,
            created_at  INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS invoices (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL REFERENCES users(id),
            amount_cents  INTEGER NOT NULL,
            charge_id     TEXT REFERENCES charges(stripe_id),
            description   TEXT,
            created_at    INTEGER NOT NULL,
            sent_at       INTEGER
        );
        """
    )
    conn.commit()
