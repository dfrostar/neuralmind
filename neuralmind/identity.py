"""identity.py — the OS account this process runs as, asked of the OS.

``security.identity: os`` in ``neuralmind-backend.yaml`` makes the MCP server
take a caller's identity from here instead of from the ``actor`` and ``role``
arguments a tool call declares. Over the default stdio transport the caller is
the agent that launched the server, so the server's own OS account *is* the
caller's, and the OS authenticated it at login.

Environment variables are deliberately not consulted. ``LOGNAME``, ``USER``
and ``USERNAME`` are inherited from whoever spawned the process, so an agent
could set them to anything; ``getpass.getuser()`` reads them first for the
same reason and is not used here.
"""

from __future__ import annotations

import os
import sys


def os_identity() -> str | None:
    """Return the account name of this process's effective user, or None.

    POSIX: the passwd entry for ``os.geteuid()``. Windows: ``GetUserNameW``,
    which reports the token's account. None when the OS can't answer (a uid
    with no passwd entry, a sandbox without advapi32) — callers enforcing
    identity must treat that as "unknown" and refuse, never fall back to an
    environment variable.
    """
    if sys.platform == "win32":
        return _windows_user()
    try:
        import pwd

        return pwd.getpwuid(os.geteuid()).pw_name or None
    except (ImportError, KeyError, OSError):
        return None


def _windows_user() -> str | None:
    try:
        import ctypes
        from ctypes import wintypes

        size = wintypes.DWORD(257)  # UNLEN + 1
        buffer = ctypes.create_unicode_buffer(size.value)
        if not ctypes.windll.advapi32.GetUserNameW(buffer, ctypes.byref(size)):
            return None
        return buffer.value or None
    except (AttributeError, OSError, ValueError):
        return None
