"""MCP security manager with RBAC, rate limiting, and audit integration."""

from __future__ import annotations

import os
import stat
import sys
import time
from collections import defaultdict, deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .audit import AuditTrail, get_audit_trail
from .backend_manager import load_backend_config
from .identity import os_identity
from .security_config import (
    IDENTITY_DECLARED,
    IDENTITY_INVALID,
    SecuritySettings,
    load_security_settings,
)

DEFAULT_ROLE_POLICY: dict[str, set[str] | str] = {
    "admin": "*",
    "builder": {
        "neuralmind_wakeup",
        "neuralmind_query",
        "neuralmind_search",
        "neuralmind_build",
        "neuralmind_stats",
        "neuralmind_health",
        "neuralmind_benchmark",
        "neuralmind_skeleton",
        "neuralmind_ingest_document",
        # Analytics tools — local installs should measure ROI
        "neuralmind_savings",
        "neuralmind_compliance_report",
        "neuralmind_structural_gaps",
        "neuralmind_synapse_stats",
        "neuralmind_synapse_decay",
        "neuralmind_export_synapse_memory",
        "neuralmind_feedback",
        # Read-only structure and recall lookups. They were listed in
        # tools/list but refused to every default role, so `neuralmind_review`
        # (documented as callable by Claude Code) returned security_denied.
        "neuralmind_review",
        "neuralmind_impact",
        "neuralmind_structural_neighbors",
        "neuralmind_synaptic_neighbors",
        "neuralmind_next_likely",
        # Decision memory (v1.0) — read + write for builders
        "neuralmind_query_decisions",
        "neuralmind_audit_decisions",
        "neuralmind_record_decision",
        "neuralmind_invalidate_decision",
        "neuralmind_memory_search",
        "neuralmind_memory_timeline",
        "neuralmind_memory_get",
    },
    "reader": {
        "neuralmind_wakeup",
        "neuralmind_query",
        "neuralmind_search",
        "neuralmind_stats",
        "neuralmind_health",
        "neuralmind_benchmark",
        "neuralmind_skeleton",
        "neuralmind_savings",
        "neuralmind_compliance_report",
        "neuralmind_structural_gaps",
        "neuralmind_synapse_stats",
        "neuralmind_synapse_decay",
        "neuralmind_export_synapse_memory",
        "neuralmind_feedback",
        # Read-only structure and recall lookups (see builder).
        "neuralmind_review",
        "neuralmind_impact",
        "neuralmind_structural_neighbors",
        "neuralmind_synaptic_neighbors",
        "neuralmind_next_likely",
        # Decision memory (v1.0) — read-only for readers
        "neuralmind_query_decisions",
        "neuralmind_audit_decisions",
        "neuralmind_memory_search",
        "neuralmind_memory_timeline",
        "neuralmind_memory_get",
    },
}

_SECURITY_MANAGERS: dict[str, MCPSecurityManager] = {}

# The transport the server is actually serving, set by mcp_server.main().
# NEURALMIND_MCP_TRANSPORT only says what was requested: main() falls back to
# stdio when the HTTP dependencies are missing, and identity checks must follow
# what is running, not what was asked for.
_active_transport: str | None = None


def set_active_transport(name: str) -> None:
    global _active_transport
    _active_transport = name


def active_transport() -> str:
    """The running transport, or the requested one when no server set it."""
    return _active_transport or os.environ.get("NEURALMIND_MCP_TRANSPORT") or "stdio"


class RBACPolicy:
    def __init__(self, role_permissions: dict[str, set[str] | str] | None = None):
        # None means no policy was configured. An empty mapping is a policy
        # that grants nothing, and must not turn back into the defaults.
        self.role_permissions = (
            DEFAULT_ROLE_POLICY if role_permissions is None else role_permissions
        )

    def is_allowed(self, role: str, tool_name: str) -> bool:
        permissions = self.role_permissions.get(role, set())
        if permissions == "*":
            return True
        if isinstance(permissions, set):
            return tool_name in permissions
        return False


class AccessDeniedError(PermissionError):
    """RBAC refused the call.

    A ``PermissionError`` subclass so existing ``except PermissionError``
    callers keep working, but distinct from the ``PermissionError`` the OS
    raises on an unreadable file — only this one is a security denial.
    """


class IdentityDeniedError(AccessDeniedError):
    """``security.identity: os`` could not establish who is calling.

    Raised before the role check, so a caller the server can't identify never
    reaches the policy at all.
    """


class PolicyConfigError(AccessDeniedError):
    """The ``security`` section is malformed, so every call is refused.

    Guessing what a broken policy meant would mean guessing in the caller's
    favour; refusing makes the mistake visible instead.
    """


class RateLimitExceededError(RuntimeError):
    """The actor made more calls than the rate limit allows.

    A ``RuntimeError`` subclass for backward compatibility; callers that
    need to tell a rate limit from a tool failure catch this class.
    """


class RateLimiter:
    def __init__(self, max_calls: int = 60, window_seconds: int = 60):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._actor_request_history: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, actor: str) -> bool:
        now = time.time()
        history = self._actor_request_history[actor]
        cutoff = now - self.window_seconds
        while history and history[0] < cutoff:
            history.popleft()
        if len(history) >= self.max_calls:
            return False
        history.append(now)
        return True


class MCPSecurityManager:
    def __init__(
        self,
        project_path: str,
        policy: RBACPolicy | None = None,
        rate_limiter: RateLimiter | None = None,
        audit_trail: AuditTrail | None = None,
        settings: SecuritySettings | None = None,
        config_problem: str | None = None,
    ):
        self.project_path = str(Path(project_path).resolve())
        self.policy = policy or RBACPolicy()
        self.rate_limiter = rate_limiter or RateLimiter()
        self.audit = audit_trail or get_audit_trail(self.project_path)
        self.settings = settings or SecuritySettings()
        self.config_problem = config_problem

    def resolve_caller(self, actor: str | None, role: str | None) -> tuple[str, str, dict]:
        """Decide who is calling and with which role.

        ``security.identity: declared`` (the default) believes the call's own
        ``actor`` and ``role``. ``os`` ignores them: the actor is the OS
        account this server runs as — over stdio, the agent that launched it —
        and the role comes from ``security.users``. What the call claimed is
        returned in the details so the audit log shows any mismatch.
        """
        if self.settings.identity == IDENTITY_DECLARED:
            return actor or "anonymous", role or "builder", {}
        if self.settings.identity == IDENTITY_INVALID:
            raise IdentityDeniedError(f"Refusing MCP calls: {self.settings.problem}")

        if active_transport() == "streamable_http":
            raise IdentityDeniedError(
                "security.identity: os needs the stdio transport; over HTTP the "
                "server's OS account is not the caller's"
            )
        problem = _policy_file_problem(self.settings.config_path)
        if problem:
            raise IdentityDeniedError(problem)
        name = os_identity()
        if not name:
            raise IdentityDeniedError(
                "security.identity: os, but the OS account this server runs as "
                "could not be determined"
            )
        resolved = self.settings.users.get(name, self.settings.default_role)
        if resolved is None:
            raise IdentityDeniedError(
                f"OS account '{name}' has no role in security.users and "
                "security.default_role is not set"
            )
        details: dict[str, Any] = {"identity": "os"}
        if actor and actor != name:
            details["claimed_actor"] = actor
        if role and role != resolved:
            details["claimed_role"] = role
        return name, resolved, details

    def refuse_if_misconfigured(self, actor: str | None, tool_name: str) -> None:
        """Raise ``PolicyConfigError`` when the ``security`` section is malformed.

        Called first, by ``secure_call`` and by the MCP dispatcher before its
        storage check, so a broken policy is reported as the cause rather than
        whichever refusal it also triggers.
        """
        if not self.config_problem:
            return
        self.audit.append_event(
            category="security",
            action="mcp_call_denied",
            actor=actor,
            status="denied",
            target=tool_name,
            details={"reason": "config", "error": self.config_problem},
        )
        raise PolicyConfigError(f"Refusing MCP calls: {self.config_problem}")

    def secure_call(
        self,
        actor: str | None,
        role: str | None,
        tool_name: str,
        call: Callable[[], Any],
    ) -> Any:
        self.refuse_if_misconfigured(actor, tool_name)

        try:
            actor, role, identity = self.resolve_caller(actor, role)
        except IdentityDeniedError as exc:
            claimed = {
                key: value
                for key, value in (("claimed_actor", actor), ("claimed_role", role))
                if value
            }
            self.audit.append_event(
                category="security",
                action="mcp_call_denied",
                status="denied",
                target=tool_name,
                details={"reason": "identity", "error": str(exc), **claimed},
            )
            raise

        if not self.policy.is_allowed(role, tool_name):
            self.audit.append_event(
                category="security",
                action="mcp_call_denied",
                actor=actor,
                status="denied",
                target=tool_name,
                details={"reason": "rbac", "role": role, **identity},
            )
            raise AccessDeniedError(f"Access denied for role '{role}' on tool '{tool_name}'")

        if not self.rate_limiter.allow(actor):
            self.audit.append_event(
                category="security",
                action="mcp_call_denied",
                actor=actor,
                status="denied",
                target=tool_name,
                details={"reason": "rate_limit", "role": role, **identity},
            )
            raise RateLimitExceededError(f"Rate limit exceeded for actor '{actor}'")

        try:
            result = call()
            self.audit.append_event(
                category="security",
                action="mcp_call",
                actor=actor,
                status="success",
                target=tool_name,
                details={"role": role, **identity},
            )
            return result
        except Exception as exc:
            self.audit.append_event(
                category="security",
                action="mcp_call",
                actor=actor,
                status="failure",
                target=tool_name,
                details={"role": role, "error": str(exc), **identity},
            )
            raise


def build_security_manager(project_path: str) -> MCPSecurityManager:
    """A manager configured from the project's ``neuralmind-backend.yaml``.

    ``security.roles`` replaces the default role policy and
    ``security.rate_limit`` sets the limiter. Uncached: callers keep their own.
    """
    key = str(Path(project_path).resolve())
    config = load_backend_config(key)
    security = config.get("security") if isinstance(config, dict) else None
    roles, max_calls, window_seconds, problem = _parse_policy(security)
    return MCPSecurityManager(
        project_path=key,
        policy=RBACPolicy(roles),
        rate_limiter=RateLimiter(max_calls=max_calls, window_seconds=window_seconds),
        settings=load_security_settings(key),
        config_problem=problem,
    )


def _parse_policy(
    security: Any,
) -> tuple[dict[str, set[str] | str] | None, int, int, str | None]:
    """Read ``security.roles`` and ``security.rate_limit``.

    Returns ``(roles, max_calls, window_seconds, problem)``. ``roles`` is None
    when no policy is configured; an empty mapping is kept, and grants
    nothing. A role whose value is neither a list nor ``"*"`` gets no tools.
    ``problem`` names a malformed setting, which makes the manager refuse
    every call rather than fall back to defaults that may be looser.
    """
    max_calls, window_seconds = 60, 60
    if security is None:
        return None, max_calls, window_seconds, None
    if not isinstance(security, dict):
        return None, max_calls, window_seconds, "`security` must be a mapping"

    roles: dict[str, set[str] | str] | None = None
    raw_roles = security.get("roles")
    if raw_roles is not None:
        if not isinstance(raw_roles, dict):
            return (
                None,
                max_calls,
                window_seconds,
                "security.roles must map role names to tool lists",
            )
        roles = {}
        for role, permissions in raw_roles.items():
            if permissions == "*":
                roles[str(role)] = "*"
            elif isinstance(permissions, list):
                roles[str(role)] = {str(name) for name in permissions}

    raw_rate = security.get("rate_limit")
    if raw_rate is not None:
        if not isinstance(raw_rate, dict):
            return roles, max_calls, window_seconds, "security.rate_limit must be a mapping"
        try:
            max_calls = _whole_number(raw_rate.get("max_calls", max_calls), "max_calls", minimum=0)
            window_seconds = _whole_number(
                raw_rate.get("window_seconds", window_seconds), "window_seconds", minimum=1
            )
        except ValueError as exc:
            return roles, 60, 60, f"security.rate_limit.{exc}"
    return roles, max_calls, window_seconds, None


def _whole_number(value: Any, name: str, minimum: int) -> int:
    # A window of 0 or less would drop every timestamp at once and switch the
    # limit off, so the floor is part of the check, not a nicety.
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"{name} must be a whole number, not {value!r}")
    try:
        number = int(value)
    except ValueError:
        raise ValueError(f"{name} must be a whole number, not {value!r}") from None
    if number < minimum:
        raise ValueError(f"{name} must be at least {minimum}, not {number}")
    return number


def get_security_manager(project_path: str) -> MCPSecurityManager:
    key = str(Path(project_path).resolve())
    if key not in _SECURITY_MANAGERS:
        _SECURITY_MANAGERS[key] = build_security_manager(key)
    return _SECURITY_MANAGERS[key]


def _policy_file_problem(path: Path | None) -> str | None:
    """A role mapping any local user can edit is not a policy.

    POSIX only: refuse when the config file is world-writable. Group-writable
    is common in shared checkouts and is reported by ``neuralmind doctor``
    instead. Windows ACLs aren't mode bits, so nothing is checked there.
    """
    if path is None or sys.platform == "win32":
        return None
    try:
        mode = path.stat().st_mode
    except OSError:
        return f"cannot read the permissions of {path.name}"
    if mode & stat.S_IWOTH:
        return f"{path.name} is writable by every user, so its role mapping can't be trusted (chmod o-w)"
    return None
