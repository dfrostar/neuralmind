"""MCP security manager with RBAC, rate limiting, and audit integration."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .audit import AuditTrail, get_audit_trail
from .backend_manager import load_backend_config

DEFAULT_ROLE_POLICY: dict[str, set[str] | str] = {
    "admin": "*",
    "builder": {
        "neuralmind_wakeup",
        "neuralmind_query",
        "neuralmind_search",
        "neuralmind_build",
        "neuralmind_stats",
        "neuralmind_benchmark",
        "neuralmind_skeleton",
    },
    "reader": {
        "neuralmind_wakeup",
        "neuralmind_query",
        "neuralmind_search",
        "neuralmind_stats",
        "neuralmind_benchmark",
        "neuralmind_skeleton",
    },
}

_SECURITY_MANAGERS: dict[str, MCPSecurityManager] = {}


class RBACPolicy:
    def __init__(self, role_permissions: dict[str, set[str] | str] | None = None):
        self.role_permissions = role_permissions or DEFAULT_ROLE_POLICY

    def is_allowed(self, role: str, tool_name: str) -> bool:
        permissions = self.role_permissions.get(role, set())
        if permissions == "*":
            return True
        if isinstance(permissions, set):
            return tool_name in permissions
        return False


class RateLimiter:
    def __init__(self, max_calls: int = 60, window_seconds: int = 60):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._history: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, actor: str) -> bool:
        now = time.time()
        history = self._history[actor]
        cutoff = now - self.window_seconds
        while history and history[0] <= cutoff:
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
    ):
        self.project_path = str(Path(project_path).resolve())
        self.policy = policy or RBACPolicy()
        self.rate_limiter = rate_limiter or RateLimiter()
        self.audit = audit_trail or get_audit_trail(self.project_path)

    def secure_call(
        self,
        actor: str,
        role: str,
        tool_name: str,
        call: Callable[[], Any],
    ) -> Any:
        if not self.policy.is_allowed(role, tool_name):
            self.audit.append_event(
                category="security",
                action="mcp_call_denied",
                actor=actor,
                status="denied",
                target=tool_name,
                details={"reason": "rbac", "role": role},
            )
            raise PermissionError(f"Access denied for role '{role}' on tool '{tool_name}'")

        if not self.rate_limiter.allow(actor):
            self.audit.append_event(
                category="security",
                action="mcp_call_denied",
                actor=actor,
                status="denied",
                target=tool_name,
                details={"reason": "rate_limit", "role": role},
            )
            raise RuntimeError(f"Rate limit exceeded for actor '{actor}'")

        try:
            result = call()
            self.audit.append_event(
                category="security",
                action="mcp_call",
                actor=actor,
                status="success",
                target=tool_name,
                details={"role": role},
            )
            return result
        except Exception as exc:
            self.audit.append_event(
                category="security",
                action="mcp_call",
                actor=actor,
                status="failure",
                target=tool_name,
                details={"role": role, "error": str(exc)},
            )
            raise


def get_security_manager(project_path: str) -> MCPSecurityManager:
    key = str(Path(project_path).resolve())
    if key not in _SECURITY_MANAGERS:
        config = load_backend_config(key)
        security = config.get("security", {}) if isinstance(config, dict) else {}
        role_permissions = security.get("roles") if isinstance(security, dict) else None
        parsed_roles: dict[str, set[str] | str] | None = None
        if isinstance(role_permissions, dict):
            parsed_roles = {}
            for role, permissions in role_permissions.items():
                if permissions == "*":
                    parsed_roles[str(role)] = "*"
                elif isinstance(permissions, list):
                    parsed_roles[str(role)] = {str(name) for name in permissions}
        rate_cfg = security.get("rate_limit", {}) if isinstance(security, dict) else {}
        max_calls = int(rate_cfg.get("max_calls", 60))
        window_seconds = int(rate_cfg.get("window_seconds", 60))
        _SECURITY_MANAGERS[key] = MCPSecurityManager(
            project_path=key,
            policy=RBACPolicy(parsed_roles) if parsed_roles else RBACPolicy(),
            rate_limiter=RateLimiter(max_calls=max_calls, window_seconds=window_seconds),
        )
    return _SECURITY_MANAGERS[key]
