"""MCP security: RBAC, rate limiting, and audit hooks."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .audit import AuditTrail


class AccessDeniedError(PermissionError):
    """Raised when RBAC authorization fails."""


class RateLimitExceededError(RuntimeError):
    """Raised when a caller exceeds configured request limits."""


class RBACPolicy:
    """Role-based access control policy for MCP tools."""

    def __init__(self, allowed_roles: dict[str, set[str]] | None = None):
        self.allowed_roles = allowed_roles or {
            "neuralmind_wakeup": {"viewer", "analyst", "admin"},
            "neuralmind_query": {"viewer", "analyst", "admin"},
            "neuralmind_search": {"viewer", "analyst", "admin"},
            "neuralmind_stats": {"viewer", "analyst", "admin"},
            "neuralmind_benchmark": {"analyst", "admin"},
            "neuralmind_skeleton": {"viewer", "analyst", "admin"},
            "neuralmind_build": {"admin"},
        }

    def authorize(self, role: str, tool_name: str) -> None:
        allowed = self.allowed_roles.get(tool_name, {"admin"})
        if role not in allowed:
            raise AccessDeniedError(f"Role '{role}' is not allowed to call {tool_name}")


class RateLimiter:
    """Sliding-window rate limiter keyed by actor + tool."""

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = timedelta(seconds=window_seconds)
        self._events: dict[str, deque[datetime]] = defaultdict(deque)

    def check(self, actor: str, tool_name: str) -> None:
        key = f"{actor}:{tool_name}"
        now = datetime.now(UTC)
        cutoff = now - self.window
        entries = self._events[key]
        while entries and entries[0] < cutoff:
            entries.popleft()
        if len(entries) >= self.max_requests:
            raise RateLimitExceededError(f"Rate limit exceeded for {actor} on {tool_name}")
        entries.append(now)


class MCPSecurityManager:
    """Central MCP security manager with audit logging."""

    def __init__(
        self,
        project_path: str | Path,
        policy: RBACPolicy | None = None,
        rate_limiter: RateLimiter | None = None,
        audit_trail: AuditTrail | None = None,
    ):
        self.project_path = Path(project_path)
        self.policy = policy or RBACPolicy()
        self.rate_limiter = rate_limiter or RateLimiter()
        self.audit = audit_trail or AuditTrail(self.project_path)

    def enforce(self, actor: str, role: str, tool_name: str) -> None:
        self.policy.authorize(role, tool_name)
        self.audit.log_event(
            category="security",
            action="rbac_check",
            actor=actor,
            target=tool_name,
            details={"role": role},
        )
        self.rate_limiter.check(actor, tool_name)
        self.audit.log_event(
            category="security",
            action="rate_limit_check",
            actor=actor,
            target=tool_name,
            details={"window_seconds": self.rate_limiter.window.total_seconds()},
        )

    def secure_call(
        self,
        actor: str,
        role: str,
        tool_name: str,
        action: Callable[..., Any],
        *args,
        **kwargs,
    ) -> Any:
        try:
            self.enforce(actor, role, tool_name)
            result = action(*args, **kwargs)
            self.audit.log_event(
                category="security",
                action="tool_call",
                actor=actor,
                target=tool_name,
                status="success",
            )
            return result
        except (AccessDeniedError, RateLimitExceededError) as exc:
            self.audit.log_event(
                category="security",
                action="tool_call",
                actor=actor,
                target=tool_name,
                status="denied",
                details={"error": str(exc)},
            )
            raise
        except Exception as exc:
            self.audit.log_event(
                category="security",
                action="tool_call",
                actor=actor,
                target=tool_name,
                status="failed",
                details={"error": str(exc)},
            )
            raise
