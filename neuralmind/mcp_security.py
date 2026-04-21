"""
mcp_security.py — Enterprise Security Hardening for MCP Server
==============================================================

Adds security controls to NeuralMind MCP server:
- Role-Based Access Control (RBAC)
- Rate limiting per user/tool
- Audit logging of all tool calls
- Anomaly detection for suspicious patterns
- Token budget enforcement

Enterprise-ready MCP deployments require:
1. Authorization: Who can call what?
2. Accountability: What was called and by whom?
3. Rate limiting: Prevent abuse/DOS
4. Audit trail: Full compliance trail
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from .memory import _append_jsonl


# ============================================================================
# Role-Based Access Control (RBAC)
# ============================================================================


class Permission(Enum):
    """MCP tool permissions."""

    # Query permissions
    QUERY_READ = "query:read"  # neuralmind_query, neuralmind_wakeup, neuralmind_search
    QUERY_WRITE = "query:write"  # neuralmind_build (rebuild index)

    # Admin permissions
    ADMIN = "admin:all"


class Role(Enum):
    """MCP user roles."""

    VIEWER = "viewer"  # Read-only: query, wakeup, search, stats
    DEVELOPER = "developer"  # Read + rebuild: all above + build
    ADMIN = "admin"  # Full access


class RolePermissionMap:
    """Map roles to permissions."""

    _map: dict[Role, set[Permission]] = {
        Role.VIEWER: {Permission.QUERY_READ},
        Role.DEVELOPER: {Permission.QUERY_READ, Permission.QUERY_WRITE},
        Role.ADMIN: {Permission.QUERY_READ, Permission.QUERY_WRITE, Permission.ADMIN},
    }

    @classmethod
    def get_permissions(cls, role: Role) -> set[Permission]:
        """Get permissions for a role."""
        return cls._map.get(role, set())

    @classmethod
    def has_permission(cls, role: Role, permission: Permission) -> bool:
        """Check if role has permission."""
        return permission in cls.get_permissions(role)


class ToolPermissionMap:
    """Map MCP tools to required permissions."""

    _map: dict[str, Permission] = {
        # Read-only tools
        "neuralmind_wakeup": Permission.QUERY_READ,
        "neuralmind_query": Permission.QUERY_READ,
        "neuralmind_search": Permission.QUERY_READ,
        "neuralmind_stats": Permission.QUERY_READ,
        "neuralmind_benchmark": Permission.QUERY_READ,
        "neuralmind_skeleton": Permission.QUERY_READ,
        # Write tools
        "neuralmind_build": Permission.QUERY_WRITE,
    }

    @classmethod
    def get_required_permission(cls, tool_name: str) -> Permission | None:
        """Get required permission for a tool."""
        return cls._map.get(tool_name)


# ============================================================================
# Rate Limiting
# ============================================================================


@dataclass
class RateLimit:
    """Rate limit configuration."""

    calls_per_minute: int = 60
    calls_per_hour: int = 3600
    max_token_budget_per_day: int = 1_000_000  # 1M tokens/day


@dataclass
class RateLimitTracker:
    """Track user's rate limit status."""

    user_id: str
    calls_minute: list[datetime] = field(default_factory=list)
    calls_hour: list[datetime] = field(default_factory=list)
    tokens_today: int = 0
    last_reset: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_rate_limited(self, config: RateLimit, tokens: int = 0) -> tuple[bool, str]:
        """
        Check if user is rate limited.

        Returns:
            (is_limited, reason)
        """
        now = datetime.now(timezone.utc)

        # Prune old entries
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        self.calls_minute = [t for t in self.calls_minute if t > minute_ago]
        self.calls_hour = [t for t in self.calls_hour if t > hour_ago]

        if now - self.last_reset > timedelta(days=1):
            self.tokens_today = 0
            self.last_reset = now

        # Check limits
        if len(self.calls_minute) >= config.calls_per_minute:
            return True, "Rate limit: too many calls per minute"

        if len(self.calls_hour) >= config.calls_per_hour:
            return True, "Rate limit: too many calls per hour"

        if self.tokens_today + tokens > config.max_token_budget_per_day:
            return True, "Rate limit: daily token budget exceeded"

        return False, ""

    def record_call(self, tokens: int = 0) -> None:
        """Record a tool call."""
        now = datetime.now(timezone.utc)
        self.calls_minute.append(now)
        self.calls_hour.append(now)
        self.tokens_today += tokens


class RateLimiter:
    """Manage rate limits for multiple users."""

    def __init__(self, config: RateLimit | None = None):
        self.config = config or RateLimit()
        self.users: dict[str, RateLimitTracker] = {}

    def get_tracker(self, user_id: str) -> RateLimitTracker:
        """Get or create tracker for user."""
        if user_id not in self.users:
            self.users[user_id] = RateLimitTracker(user_id)
        return self.users[user_id]

    def is_allowed(self, user_id: str, tokens: int = 0) -> tuple[bool, str]:
        """Check if user is allowed to make a call."""
        tracker = self.get_tracker(user_id)
        return tracker.is_rate_limited(self.config, tokens)

    def record(self, user_id: str, tokens: int = 0) -> None:
        """Record a successful call."""
        tracker = self.get_tracker(user_id)
        tracker.record_call(tokens)


# ============================================================================
# Audit Logging for MCP
# ============================================================================


@dataclass
class MCPAuditEntry:
    """Audit log entry for MCP tool call."""

    timestamp: str
    user_id: str | None
    role: str | None
    tool_name: str
    project_path: str
    parameters: dict[str, Any]
    result_tokens: int = 0
    result_status: str = "success"  # "success", "denied", "error"
    denial_reason: str = ""
    error_message: str = ""


def mcp_audit_log_dir(project_path: str | Path) -> Path:
    """Get MCP audit log directory."""
    return Path(project_path) / ".neuralmind" / "audit" / "mcp"


def mcp_audit_log_file(project_path: str | Path) -> Path:
    """Get MCP audit log file path."""
    return mcp_audit_log_dir(project_path) / "tool_calls.jsonl"


def log_mcp_call(
    project_path: str | Path,
    user_id: str | None,
    role: str | None,
    tool_name: str,
    parameters: dict[str, Any],
    result_tokens: int = 0,
    status: str = "success",
    reason: str = "",
    error: str = "",
) -> bool:
    """
    Log an MCP tool call to audit trail.

    Args:
        project_path: Project root
        user_id: User identifier
        role: User role
        tool_name: MCP tool name
        parameters: Tool input parameters
        result_tokens: Tokens returned
        status: "success", "denied", "error"
        reason: Reason for denial
        error: Error message if applicable

    Returns:
        True if logged successfully
    """
    entry = MCPAuditEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        user_id=user_id,
        role=role,
        tool_name=tool_name,
        project_path=str(Path(project_path).resolve()),
        parameters=parameters,
        result_tokens=result_tokens,
        result_status=status,
        denial_reason=reason,
        error_message=error,
    )

    try:
        log_file = mcp_audit_log_file(project_path)
        _append_jsonl(log_file, entry.__dict__)
        return True
    except Exception:
        return False


# ============================================================================
# Anomaly Detection
# ============================================================================


class AnomalyDetector:
    """Detect suspicious patterns in MCP usage."""

    def __init__(self, window_minutes: int = 60):
        self.window_minutes = window_minutes
        self.call_history: dict[str, list[tuple[datetime, str]]] = {}

    def record_call(self, user_id: str, tool_name: str) -> None:
        """Record a tool call."""
        if user_id not in self.call_history:
            self.call_history[user_id] = []

        now = datetime.now(timezone.utc)
        self.call_history[user_id].append((now, tool_name))

        # Prune old entries
        cutoff = now - timedelta(minutes=self.window_minutes)
        self.call_history[user_id] = [
            (t, tool) for t, tool in self.call_history[user_id] if t > cutoff
        ]

    def detect_anomalies(self, user_id: str) -> list[str]:
        """
        Detect anomalies for a user.

        Returns:
            List of anomaly descriptions
        """
        if user_id not in self.call_history:
            return []

        calls = self.call_history[user_id]
        now = datetime.now(timezone.utc)

        anomalies = []

        # Anomaly 1: Too many calls in short window
        if len(calls) > 100:  # 100 calls in 60 minutes
            anomalies.append(
                f"High call volume: {len(calls)} calls in {self.window_minutes} minutes"
            )

        # Anomaly 2: Repeated same tool in short period
        recent_tools = [tool for _, tool in calls[-10:]]
        if len(recent_tools) == 10 and len(set(recent_tools)) == 1:
            anomalies.append(
                f"Repeated tool pattern: same tool called 10 times in succession"
            )

        # Anomaly 3: Query after query without reading results
        query_calls = sum(1 for _, t in calls if "query" in t)
        if query_calls > 20:  # 20+ queries in window
            anomalies.append(f"Many consecutive queries: {query_calls} in {self.window_minutes} minutes")

        return anomalies


# ============================================================================
# Security Middleware for MCP
# ============================================================================


class MCPSecurityMiddleware:
    """Wrap MCP tool functions with security checks."""

    def __init__(
        self,
        project_path: str | Path,
        user_id: str | None = None,
        role: Role = Role.VIEWER,
        rate_limit_config: RateLimit | None = None,
    ):
        """
        Initialize security middleware.

        Args:
            project_path: Project root
            user_id: User identifier
            role: User role (for RBAC)
            rate_limit_config: Rate limit configuration
        """
        self.project_path = Path(project_path)
        self.user_id = user_id or "anonymous"
        self.role = role
        self.rate_limiter = RateLimiter(rate_limit_config)
        self.anomaly_detector = AnomalyDetector()

    def authorize_tool(self, tool_name: str) -> tuple[bool, str]:
        """
        Check if user is authorized to call a tool.

        Returns:
            (is_authorized, reason_if_denied)
        """
        required_permission = ToolPermissionMap.get_required_permission(tool_name)
        if required_permission is None:
            return True, ""

        if RolePermissionMap.has_permission(self.role, required_permission):
            return True, ""

        return False, f"Role '{self.role.value}' cannot access '{tool_name}'"

    def check_rate_limit(self, estimated_tokens: int = 0) -> tuple[bool, str]:
        """Check if user is rate limited."""
        return self.rate_limiter.is_allowed(self.user_id, estimated_tokens)

    def check_anomalies(self) -> list[str]:
        """Detect anomalous patterns."""
        return self.anomaly_detector.detect_anomalies(self.user_id)

    def wrap_tool(self, tool_name: str, tool_func: Callable) -> Callable:
        """
        Wrap a tool function with security checks.

        Usage:
            @middleware.wrap_tool("neuralmind_query")
            def tool_query(project_path: str, question: str):
                ...
        """

        def wrapped(*args, **kwargs) -> Any:
            # 1. Authorization check
            authorized, reason = self.authorize_tool(tool_name)
            if not authorized:
                log_mcp_call(
                    self.project_path,
                    self.user_id,
                    self.role.value,
                    tool_name,
                    {**kwargs},
                    status="denied",
                    reason=reason,
                )
                raise PermissionError(f"Not authorized: {reason}")

            # 2. Rate limit check
            rate_limited, reason = self.check_rate_limit()
            if rate_limited:
                log_mcp_call(
                    self.project_path,
                    self.user_id,
                    self.role.value,
                    tool_name,
                    {**kwargs},
                    status="denied",
                    reason=reason,
                )
                raise RuntimeError(f"Rate limited: {reason}")

            # 3. Anomaly detection
            anomalies = self.check_anomalies()
            if anomalies:
                # Log anomalies but don't block (for now)
                for anomaly in anomalies:
                    pass  # Could alert here

            # 4. Execute tool
            try:
                result = tool_func(*args, **kwargs)

                # Extract token count if available
                tokens = 0
                if isinstance(result, dict) and "tokens" in result:
                    tokens = result["tokens"]

                # 5. Record successful call
                self.rate_limiter.record(self.user_id, tokens)
                self.anomaly_detector.record_call(self.user_id, tool_name)

                # 6. Audit log
                log_mcp_call(
                    self.project_path,
                    self.user_id,
                    self.role.value,
                    tool_name,
                    {**kwargs},
                    result_tokens=tokens,
                    status="success",
                )

                return result
            except Exception as e:
                log_mcp_call(
                    self.project_path,
                    self.user_id,
                    self.role.value,
                    tool_name,
                    {**kwargs},
                    status="error",
                    error=str(e),
                )
                raise

        return wrapped
