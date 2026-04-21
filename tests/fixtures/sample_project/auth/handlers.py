"""Authentication handlers — login, logout, token refresh."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..db.connection import get_connection
from ..users.crud import get_user_by_email, update_last_login
from .jwt_utils import decode_token, encode_token

SESSION_TTL = timedelta(hours=1)
REFRESH_TTL = timedelta(days=30)


def authenticate_user(email: str, password: str) -> dict:
    """Validate credentials and issue an access + refresh token pair.

    Looks the user up by email, verifies the password hash, stamps a login
    event, and returns JWT access and refresh tokens.
    """
    user = get_user_by_email(email)
    if user is None:
        raise InvalidCredentialsError("unknown email")

    if not verify_password(password, user["password_hash"]):
        raise InvalidCredentialsError("bad password")

    update_last_login(user["id"])

    now = datetime.now(timezone.utc)
    access = encode_token({"sub": user["id"], "exp": now + SESSION_TTL})
    refresh = encode_token({"sub": user["id"], "exp": now + REFRESH_TTL, "kind": "refresh"})

    return {"access_token": access, "refresh_token": refresh, "user_id": user["id"]}


def verify_session(access_token: str) -> int:
    """Return the user id if the access token is valid; raise if not."""
    payload = decode_token(access_token)
    if payload.get("kind") == "refresh":
        raise InvalidTokenError("refresh token used as access")
    return int(payload["sub"])


def refresh_session(refresh_token: str) -> dict:
    """Exchange a refresh token for a new access token."""
    payload = decode_token(refresh_token)
    if payload.get("kind") != "refresh":
        raise InvalidTokenError("not a refresh token")

    now = datetime.now(timezone.utc)
    new_access = encode_token({"sub": payload["sub"], "exp": now + SESSION_TTL})
    return {"access_token": new_access}


def logout(refresh_token: str) -> None:
    """Revoke a refresh token by writing it to the revocation list."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO revoked_tokens (token, revoked_at) VALUES (?, ?)",
        (refresh_token, datetime.now(timezone.utc)),
    )


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time password verification against stored hash."""
    import hmac

    return hmac.compare_digest(plain.encode(), hashed.encode())


class InvalidCredentialsError(Exception):
    """Raised when email or password does not match any user."""


class InvalidTokenError(Exception):
    """Raised when a token is malformed, expired, or misused."""
