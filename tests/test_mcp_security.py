"""Tests for MCP security manager components."""

import pytest

from neuralmind.audit import AuditTrail
from neuralmind.mcp_security import MCPSecurityManager, RateLimiter, RBACPolicy


def test_rbac_policy_allows_expected_tools():
    policy = RBACPolicy({"reader": {"neuralmind_query"}})
    assert policy.is_allowed("reader", "neuralmind_query") is True
    assert policy.is_allowed("reader", "neuralmind_build") is False


def test_rate_limiter_enforces_sliding_window():
    limiter = RateLimiter(max_calls=2, window_seconds=60)
    assert limiter.allow("alice") is True
    assert limiter.allow("alice") is True
    assert limiter.allow("alice") is False


def test_security_manager_audits_success_and_failure(temp_project):
    manager = MCPSecurityManager(
        project_path=str(temp_project),
        policy=RBACPolicy({"reader": {"neuralmind_query"}}),
        rate_limiter=RateLimiter(max_calls=10, window_seconds=60),
        audit_trail=AuditTrail(temp_project),
    )

    result = manager.secure_call("alice", "reader", "neuralmind_query", lambda: {"ok": True})
    assert result == {"ok": True}

    with pytest.raises(PermissionError):
        manager.secure_call("alice", "reader", "neuralmind_build", lambda: {"ok": True})

    with pytest.raises(RuntimeError):
        limiter = RateLimiter(max_calls=1, window_seconds=60)
        limited = MCPSecurityManager(
            project_path=str(temp_project),
            policy=RBACPolicy({"reader": {"neuralmind_query"}}),
            rate_limiter=limiter,
            audit_trail=AuditTrail(temp_project),
        )
        limited.secure_call("bob", "reader", "neuralmind_query", lambda: {"ok": True})
        limited.secure_call("bob", "reader", "neuralmind_query", lambda: {"ok": True})

    events = AuditTrail(temp_project).read_events()
    statuses = {event["status"] for event in events}
    assert "success" in statuses
    assert "denied" in statuses
