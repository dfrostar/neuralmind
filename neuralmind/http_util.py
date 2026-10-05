"""http_util.py — request-hygiene helpers shared by NeuralMind's local HTTP servers.

The daemon (``daemon.py``) and the graph view (``server.py``) are both stdlib
``http.server`` handlers that read client-supplied headers and bodies. A
malformed value there must become a 4xx JSON answer, never an exception inside
the handler: ``http.server`` logs those and drops the connection without
sending any response, so the client sees only a reset socket.

Stdlib-only.
"""

from __future__ import annotations

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
