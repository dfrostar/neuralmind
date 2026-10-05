"""http_util.py — request-hygiene helpers shared by NeuralMind's local HTTP servers.

The daemon (``daemon.py``) and the graph view (``server.py``) are both stdlib
``http.server`` handlers that read client-supplied headers and bodies. A
malformed value there must become a 4xx JSON answer, never an exception inside
the handler: ``http.server`` logs those and drops the connection without
sending any response, so the client sees only a reset socket.

Stdlib-only.
"""

from __future__ import annotations

import hmac
import json
from typing import Any

# Request bodies on these servers are small JSON objects (a project path and a
# question, a node id). Anything larger is refused before a byte is read.
MAX_BODY_BYTES = 1 << 20  # 1 MiB


class RequestError(Exception):
    """A client error that the handler answers with ``status`` and ``message``."""

    def __init__(self, status: int, message: str) -> None:
        """Create a request error.

        Args:
            status: HTTP status code to answer with (4xx).
            message: Human-readable reason, sent back as the JSON ``error``.
        """
        super().__init__(message)
        self.status = status
        self.message = message


def content_length(headers: Any, max_bytes: int = MAX_BODY_BYTES) -> int:
    """Return the request's validated ``Content-Length`` (0 when absent).

    Raises :class:`RequestError` 400 for a value that is not a plain decimal
    integer (RFC 9110 §8.6 allows digits only, so no sign, decimal point or
    underscore — all of which ``int()`` would accept), and 413 for one above
    ``max_bytes``. Both are decided from the header alone, before any body
    byte is read, so a bogus length can neither stall the handler waiting for
    bytes that never arrive nor make it allocate an absurd buffer.
    """
    raw = headers.get("Content-Length")
    if raw is None:
        return 0
    value = raw.strip()
    if not (value.isascii() and value.isdigit()):
        raise RequestError(400, "invalid Content-Length header (expected a non-negative integer)")
    length = int(value)
    if length > max_bytes:
        raise RequestError(413, f"request body too large (limit {max_bytes} bytes)")
    return length


def read_body(handler: Any, max_bytes: int = MAX_BODY_BYTES) -> bytes:
    """Read a request body of validated length from a ``BaseHTTPRequestHandler``.

    Raises :class:`RequestError` (see :func:`content_length`) without reading
    anything when the declared length is malformed or too large.
    """
    length = content_length(handler.headers, max_bytes)
    return handler.rfile.read(length) if length else b""


def json_type_name(value: Any) -> str:
    """Name a decoded JSON value by its JSON type ("array", "string", ...)."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object" if isinstance(value, dict) else type(value).__name__


def parse_json_object(raw: bytes) -> dict:
    """Decode a request body that must be a JSON object (an empty body is ``{}``).

    Raises :class:`RequestError` 400 for invalid JSON or for valid JSON of any
    other type — handlers call ``body.get(...)``, which on a list, string or
    number raised ``AttributeError`` and surfaced as a 500 (or no response).
    """
    if not raw:
        return {}
    try:
        body = json.loads(raw.decode("utf-8"))
    except ValueError:  # includes UnicodeDecodeError
        raise RequestError(400, "invalid JSON body") from None
    if not isinstance(body, dict):
        raise RequestError(400, f"request body must be a JSON object, got {json_type_name(body)}")
    return body


def read_json_object(handler: Any, max_bytes: int = MAX_BODY_BYTES) -> dict:
    """:func:`read_body` then :func:`parse_json_object`; raises :class:`RequestError`."""
    return parse_json_object(read_body(handler, max_bytes))


def token_matches(candidate: str | None, expected: str | None) -> bool:
    """Constant-time check of a client-supplied token; never raises.

    ``hmac.compare_digest`` raises ``TypeError`` when handed a ``str`` with
    non-ASCII characters — and a ``?token=%C3%A9`` query value or a header
    carrying high bytes (``http.server`` decodes headers as latin-1) is exactly
    that — so both sides are compared as UTF-8 bytes. ``surrogatepass`` keeps
    even a lone surrogate encodable. An empty or missing value never matches.
    """
    if not candidate or not expected:
        return False
    return hmac.compare_digest(
        candidate.encode("utf-8", "surrogatepass"), expected.encode("utf-8", "surrogatepass")
    )
