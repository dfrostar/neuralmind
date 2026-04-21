"""JWT encode/decode helpers."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time


JWT_SECRET = "change-me-in-prod"
ALGORITHM = "HS256"


def encode_token(claims: dict) -> str:
    """Produce a signed JWT string from a claims dict.

    Expiry should be passed as a datetime in ``claims['exp']``.
    """
    exp = claims.get("exp")
    if exp is not None and hasattr(exp, "timestamp"):
        claims = {**claims, "exp": int(exp.timestamp())}

    header = {"alg": ALGORITHM, "typ": "JWT"}
    header_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url(json.dumps(claims, separators=(",", ":")).encode())

    signing_input = f"{header_b64}.{payload_b64}".encode()
    signature = _sign(signing_input)
    return f"{header_b64}.{payload_b64}.{_b64url(signature)}"


def decode_token(token: str) -> dict:
    """Verify signature + expiry and return the claims dict."""
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
    except ValueError as exc:
        raise MalformedTokenError("token must have 3 segments") from exc

    signing_input = f"{header_b64}.{payload_b64}".encode()
    expected = _sign(signing_input)
    if not hmac.compare_digest(expected, _b64url_decode(sig_b64)):
        raise InvalidSignatureError("signature mismatch")

    payload = json.loads(_b64url_decode(payload_b64))
    exp = payload.get("exp")
    if exp is not None and int(time.time()) > int(exp):
        raise TokenExpiredError("token expired")

    return payload


def _sign(data: bytes) -> bytes:
    return hmac.new(JWT_SECRET.encode(), data, hashlib.sha256).digest()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


class TokenExpiredError(Exception):
    """Raised when the exp claim is in the past."""


class InvalidSignatureError(Exception):
    """Raised when the HMAC signature does not match."""


class MalformedTokenError(Exception):
    """Raised when the token cannot be parsed."""
