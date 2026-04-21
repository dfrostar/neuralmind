"""User model + CRUD operations."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ..db.connection import get_connection


@dataclass
class User:
    """Canonical user record."""

    id: int
    email: str
    password_hash: str
    created_at: datetime
    last_login: datetime | None = None
    is_active: bool = True


def create_user(email: str, password_hash: str) -> User:
    """Insert a new user and return the created record."""
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO users (email, password_hash, created_at, is_active) "
        "VALUES (?, ?, ?, ?) RETURNING id",
        (email, password_hash, datetime.now(timezone.utc), True),
    )
    new_id = cursor.fetchone()[0]
    return User(
        id=new_id,
        email=email,
        password_hash=password_hash,
        created_at=datetime.now(timezone.utc),
    )


def get_user_by_email(email: str) -> dict | None:
    """Fetch a user by email, returning a raw dict (for auth hot path speed)."""
    conn = get_connection()
    row = conn.execute(
        "SELECT id, email, password_hash, created_at, last_login, is_active "
        "FROM users WHERE email = ? AND is_active = 1",
        (email,),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "email": row[1],
        "password_hash": row[2],
        "created_at": row[3],
        "last_login": row[4],
        "is_active": bool(row[5]),
    }


def get_user(user_id: int) -> User | None:
    """Fetch a user by primary key."""
    conn = get_connection()
    row = conn.execute(
        "SELECT id, email, password_hash, created_at, last_login, is_active "
        "FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        return None
    return User(
        id=row[0],
        email=row[1],
        password_hash=row[2],
        created_at=row[3],
        last_login=row[4],
        is_active=bool(row[5]),
    )


def update_last_login(user_id: int) -> None:
    """Stamp the user's last_login timestamp."""
    conn = get_connection()
    conn.execute(
        "UPDATE users SET last_login = ? WHERE id = ?",
        (datetime.now(timezone.utc), user_id),
    )


def deactivate_user(user_id: int) -> None:
    """Soft-delete a user by flipping is_active off."""
    conn = get_connection()
    conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
