"""security_profile.py — what ``security.profile: cui`` refuses at run time.

The profile is parsed in ``security_config``, which also makes it force
``identity: os`` and ``require_encrypted_storage: true``; everything already
keyed off those settings (the MCP identity check, the storage guard, the audit
actor) follows from that. This module holds the refusals that are new with the
profile:

* a listener that a CUI project's data could leave through: the graph-view
  server on a non-loopback address or without its access token, and a shared
  daemon started that way;
* LLM documentation seeding, which sends README and architecture prose to a
  model provider, even when ``NEURALMIND_LLM_SEED=1`` is set.

Each refusal raises ``ProfileRefusedError`` (a ``PermissionError``) or returns a
reason, and is written to the project's audit log, so an assessor can see it
was enforced, not just configured.
"""

from __future__ import annotations

import ipaddress
from pathlib import Path

from .security_config import PROFILE_CUI, load_security_settings


class ProfileRefusedError(PermissionError):
    """An action the project's ``security.profile`` forbids."""


def project_profile(project_path: str | Path) -> str | None:
    """The project's ``security.profile``, or None. Never raises."""
    try:
        return load_security_settings(project_path).profile
    except Exception:
        return None


def is_loopback(host: str) -> bool:
    """Whether ``host`` names only this machine.

    ``localhost`` and loopback addresses (127.0.0.0/8, ::1) count. Anything
    else, including the wildcard ``0.0.0.0``/``::``, a LAN address or another
    hostname, does not.
    """
    value = (host or "").strip().strip("[]").lower()
    if value == "localhost":
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def listener_problem(host: str, auth: bool) -> str | None:
    """Why a listener on ``host`` would expose a CUI project, or None."""
    if not is_loopback(host):
        return f"it listens on {host!r}, beyond loopback"
    if not auth:
        return "it runs without its access token (--no-auth)"
    return None


def refuse_exposed_listener(project_path: str | Path, host: str, auth: bool, surface: str) -> None:
    """Raise ``ProfileRefusedError`` if a CUI project would be served this way."""
    if project_profile(project_path) != PROFILE_CUI:
        return
    problem = listener_problem(host, auth)
    if problem is None:
        return
    record_refusal(project_path, surface, problem)
    raise ProfileRefusedError(
        f"security.profile: cui refuses to serve this project because {problem}. "
        "Serve it on 127.0.0.1 with its access token, and reach it from another "
        "machine through an SSH tunnel."
    )


def llm_seeding_refusal(project_path: str | Path) -> str | None:
    """The reason LLM seeding is refused for this project, or None if it isn't."""
    if project_profile(project_path) != PROFILE_CUI:
        return None
    return "security.profile: cui keeps documentation out of LLM seeding"


def record_refusal(project_path: str | Path, surface: str, reason: str) -> None:
    """Write a ``security``/``profile_refused`` record to the project's audit log."""
    try:
        from .audit import get_audit_trail

        get_audit_trail(project_path).append_event(
            category="security",
            action="profile_refused",
            status="denied",
            target=surface,
            details={"profile": PROFILE_CUI, "reason": reason},
        )
    except Exception:
        pass  # the refusal itself must not depend on the audit log being writable
