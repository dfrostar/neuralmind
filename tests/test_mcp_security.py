"""Tests for MCP security controls: RBAC, rate limiting, and auditing."""

import pytest

from neuralmind.mcp_security import (
    AccessDeniedError,
    MCPSecurityManager,
    RateLimitExceededError,
    RateLimiter,
)


def test_rbac_denies_unauthorized_role(tmp_path):
    security = MCPSecurityManager(tmp_path)
    with pytest.raises(AccessDeniedError):
        security.enforce(actor="alice", role="viewer", tool_name="neuralmind_build")


def test_rbac_allows_authorized_role(tmp_path):
    security = MCPSecurityManager(tmp_path)
    security.enforce(actor="alice", role="admin", tool_name="neuralmind_build")


def test_rate_limiter_blocks_excess_calls():
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    limiter.check("alice", "neuralmind_query")
    limiter.check("alice", "neuralmind_query")
    with pytest.raises(RateLimitExceededError):
        limiter.check("alice", "neuralmind_query")


def test_secure_call_logs_audit_on_success(tmp_path):
    security = MCPSecurityManager(tmp_path)
    value = security.secure_call("alice", "admin", "neuralmind_stats", lambda: {"ok": True})
    assert value == {"ok": True}
    events = security.audit.list_events(category="security")
    assert any(e["action"] == "tool_call" and e["status"] == "success" for e in events)


def test_secure_call_logs_audit_on_denied(tmp_path):
    security = MCPSecurityManager(tmp_path)
    with pytest.raises(AccessDeniedError):
        security.secure_call("alice", "viewer", "neuralmind_build", lambda: {"ok": True})
    events = security.audit.list_events(category="security", status="denied")
    assert events
