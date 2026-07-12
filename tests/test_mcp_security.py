"""Tests for MCP security manager components."""

import json

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
        strict_limiter = RateLimiter(max_calls=1, window_seconds=60)
        limited = MCPSecurityManager(
            project_path=str(temp_project),
            policy=RBACPolicy({"reader": {"neuralmind_query"}}),
            rate_limiter=strict_limiter,
            audit_trail=AuditTrail(temp_project),
        )
        limited.secure_call("bob", "reader", "neuralmind_query", lambda: {"ok": True})
        limited.secure_call("bob", "reader", "neuralmind_query", lambda: {"ok": True})

    events = AuditTrail(temp_project).read_events()
    statuses = {event["status"] for event in events}
    assert "success" in statuses
    assert "denied" in statuses


def test_handle_tool_call_rejects_missing_project_path(temp_project):
    from neuralmind.mcp_server import handle_tool_call

    # Simulate a tool call where the request has NO project_path key
    result = handle_tool_call(
        "neuralmind_query",
        {"question": "What does this code do?"},
    )

    parsed = json.loads(result)
    assert "error" in parsed
    assert parsed["code"] == "invalid_request"

    # Also verify it did NOT attempt to create a security manager
    # (which would require a project_path) — error message should mention it
    assert "project_path" in parsed["error"].lower()


def test_handle_tool_call_rejects_empty_project_path(temp_project):
    from neuralmind.mcp_server import handle_tool_call

    # Empty string
    result_empty = handle_tool_call(
        "neuralmind_query",
        {"project_path": "", "question": "What does this code do?"},
    )
    parsed_empty = json.loads(result_empty)
    assert "error" in parsed_empty
    assert parsed_empty["code"] == "invalid_request"

    # None
    result_none = handle_tool_call(
        "neuralmind_query",
        {"project_path": None, "question": "What does this code do?"},
    )
    parsed_none = json.loads(result_none)
    assert "error" in parsed_none
    assert parsed_none["code"] == "invalid_request"
