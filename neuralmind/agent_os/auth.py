"""auth.py — Authentication context for Agent OS.

Derives caller identity from the session token, never from request body.
This is the security boundary: the daemon's bearer token authenticates
the transport, and per-tenant sessions authenticate the actor.

Design:
    - Session tokens are random UUIDs stored in ~/.config/neuralmind/sessions/
    - Each session maps to an email + tenant_id + role
    - The Authorization header carries the session token (Bearer <token>)
    - Body email is NEVER trusted for authenticated operations
    - Bootstrap operations (create_tenant) are the only exception
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_SESSIONS_DIR = Path(
    os.environ.get("NEURALMIND_SESSIONS_DIR", Path.home() / ".config" / "neuralmind" / "sessions")
)


@dataclass
class AuthContext:
    """Authenticated caller identity."""
    email: str
    tenant_id: str | None  # None for bootstrap operations
    role: str | None = None
    session_token: str | None = None

    @property
    def is_authenticated(self) -> bool:
        return bool(self.email)


class SessionStore:
    """Persistent session storage. Thread-safe, atomic writes."""

    def __init__(self, sessions_dir: Path | None = None) -> None:
        self._sessions_dir = sessions_dir or DEFAULT_SESSIONS_DIR
        self._lock = threading.Lock()

    def create_session(self, email: str, tenant_id: str | None = None, role: str | None = None) -> str:
        """Create a new session and return the token."""
        token = uuid.uuid4().hex
        session = {
            "token": token,
            "email": email.lower().strip(),
            "tenant_id": tenant_id,
            "role": role,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_used": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._sessions_dir.mkdir(parents=True, exist_ok=True)
            path = self._sessions_dir / f"{token}.json"
            data = json.dumps(session, indent=2)
            fd, tmp_path = tempfile.mkstemp(dir=self._sessions_dir, prefix=f".{token}-", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(data)
                Path(tmp_path).replace(path)
            except OSError:
                Path(tmp_path).unlink(missing_ok=True)
                raise
        return token

    def get_session(self, token: str) -> AuthContext | None:
        """Look up a session by token. Returns None if not found."""
        if not token:
            return None
        path = self._sessions_dir / f"{token}.json"
        if not path.exists():
            return None
        try:
            session = json.loads(path.read_text(encoding="utf-8"))
            # Update last_used
            session["last_used"] = datetime.now(timezone.utc).isoformat()
            path.write_text(json.dumps(session, indent=2), encoding="utf-8")
            return AuthContext(
                email=session["email"],
                tenant_id=session.get("tenant_id"),
                role=session.get("role"),
                session_token=token,
            )
        except (OSError, KeyError, ValueError):
            return None

    def delete_session(self, token: str) -> None:
        """Delete a session."""
        path = self._sessions_dir / f"{token}.json"
        try:
            path.unlink()
        except OSError:
            pass


def extract_bearer_token(auth_header: str | None) -> str | None:
    """Extract bearer token from Authorization header."""
    if not auth_header:
        return None
    parts = auth_header.strip().split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None
