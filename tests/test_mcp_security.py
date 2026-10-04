"""Tests for MCP security manager components."""

import json

import pytest

from neuralmind.audit import AuditTrail
from neuralmind.mcp_security import (
    AccessDeniedError,
    MCPSecurityManager,
    RateLimiter,
    RateLimitExceededError,
    RBACPolicy,
)


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


def test_security_refusals_have_their_own_types(temp_project):
    """MCP tells a security refusal from a tool failure by these types; they
    subclass the old PermissionError / RuntimeError so existing callers keep
    working."""
    assert issubclass(AccessDeniedError, PermissionError)
    assert issubclass(RateLimitExceededError, RuntimeError)
    manager = MCPSecurityManager(
        project_path=str(temp_project),
        policy=RBACPolicy({"reader": {"neuralmind_query"}}),
        rate_limiter=RateLimiter(max_calls=1, window_seconds=60),
        audit_trail=AuditTrail(temp_project),
    )
    with pytest.raises(AccessDeniedError):
        manager.secure_call("alice", "reader", "neuralmind_build", lambda: None)
    manager.secure_call("bob", "reader", "neuralmind_query", lambda: None)
    with pytest.raises(RateLimitExceededError):
        manager.secure_call("bob", "reader", "neuralmind_query", lambda: None)


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


# The default policy grants every tool to a role, or leaves it out on purpose.
# Admin-only by default, as docs/SECURITY-GUIDE.md ("Default roles") lists.
ADMIN_ONLY_TOOLS = {
    "neuralmind_synaptic_neighbors",
    "neuralmind_structural_neighbors",
    "neuralmind_next_likely",
    "neuralmind_impact",
    "neuralmind_review",
}
# Tools that change project state: builder has them, reader does not.
BUILDER_ONLY_TOOLS = {
    "neuralmind_build",
    "neuralmind_ingest_document",
    "neuralmind_record_decision",
    "neuralmind_invalidate_decision",
}


def test_default_roles_decide_every_advertised_tool():
    """A tool added to the MCP server without a place in DEFAULT_ROLE_POLICY is
    denied to every default role. The three progressive-retrieval memory tools
    shipped that way, although the Memory Layer wiki grants them to builder and
    reader. A new tool has to be granted, or listed above as left out on purpose."""
    from neuralmind.mcp_security import DEFAULT_ROLE_POLICY
    from neuralmind.mcp_server import TOOLS

    names = {tool["name"] for tool in TOOLS}
    assert names - DEFAULT_ROLE_POLICY["builder"] == ADMIN_ONLY_TOOLS
    assert names - DEFAULT_ROLE_POLICY["reader"] == ADMIN_ONLY_TOOLS | BUILDER_ONLY_TOOLS


@pytest.mark.parametrize(
    "tool, arguments",
    [
        ("neuralmind_memory_search", {"query": "sqlite"}),
        ("neuralmind_memory_timeline", {"decision_id": "missing"}),
        ("neuralmind_memory_get", {"ids": ["missing"]}),
    ],
)
@pytest.mark.parametrize("role", [None, "builder", "reader"])
def test_default_roles_reach_the_memory_retrieval_tools(temp_project, tool, arguments, role):
    """Through the main dispatcher, with no role (which defaults to builder) or
    a declared builder or reader role, the read-only memory tools run instead of
    coming back security_denied."""
    from neuralmind.mcp_server import handle_tool_call

    args = {"project_path": str(temp_project), **arguments}
    if role:
        args["role"] = role
    parsed = json.loads(handle_tool_call(tool, args))
    assert parsed.get("code") != "security_denied", parsed


def test_reader_still_cannot_write_decisions(temp_project):
    from neuralmind.mcp_server import handle_tool_call

    parsed = json.loads(
        handle_tool_call(
            "neuralmind_record_decision",
            {
                "project_path": str(temp_project),
                "role": "reader",
                "title": "Use WAL",
                "rationale": "Concurrent readers",
            },
        )
    )
    assert parsed["code"] == "security_denied"
    assert "Access denied for role 'reader'" in parsed["error"]
