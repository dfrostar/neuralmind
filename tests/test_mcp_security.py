"""Tests for NeuralMind MCP security (RBAC, rate limiting, audit, anomaly detection)."""

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from neuralmind.mcp_security import (
    AnomalyDetector,
    MCPAuditEntry,
    MCPSecurityMiddleware,
    Permission,
    RateLimit,
    RateLimitTracker,
    RateLimiter,
    Role,
    RolePermissionMap,
    ToolPermissionMap,
    log_mcp_call,
    mcp_audit_log_dir,
    mcp_audit_log_file,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project directory."""
    project_path = tmp_path / "test_project"
    project_path.mkdir()
    (project_path / ".neuralmind" / "audit" / "mcp").mkdir(parents=True)
    return project_path


# ============================================================================
# Test Role-Based Access Control
# ============================================================================


class TestPermissionEnum:
    """Test Permission enum."""

    def test_permission_values(self):
        """Test permission enum values."""
        assert Permission.QUERY_READ.value == "query:read"
        assert Permission.QUERY_WRITE.value == "query:write"
        assert Permission.ADMIN.value == "admin:all"


class TestRoleEnum:
    """Test Role enum."""

    def test_role_values(self):
        """Test role enum values."""
        assert Role.VIEWER.value == "viewer"
        assert Role.DEVELOPER.value == "developer"
        assert Role.ADMIN.value == "admin"


class TestRolePermissionMap:
    """Test role-to-permission mapping."""

    def test_viewer_permissions(self):
        """Test viewer role permissions."""
        perms = RolePermissionMap.get_permissions(Role.VIEWER)

        assert Permission.QUERY_READ in perms
        assert Permission.QUERY_WRITE not in perms
        assert Permission.ADMIN not in perms

    def test_developer_permissions(self):
        """Test developer role permissions."""
        perms = RolePermissionMap.get_permissions(Role.DEVELOPER)

        assert Permission.QUERY_READ in perms
        assert Permission.QUERY_WRITE in perms
        assert Permission.ADMIN not in perms

    def test_admin_permissions(self):
        """Test admin role permissions."""
        perms = RolePermissionMap.get_permissions(Role.ADMIN)

        assert Permission.QUERY_READ in perms
        assert Permission.QUERY_WRITE in perms
        assert Permission.ADMIN in perms

    def test_has_permission(self):
        """Test has_permission check."""
        assert RolePermissionMap.has_permission(Role.VIEWER, Permission.QUERY_READ)
        assert not RolePermissionMap.has_permission(Role.VIEWER, Permission.QUERY_WRITE)
        assert RolePermissionMap.has_permission(Role.ADMIN, Permission.ADMIN)


class TestToolPermissionMap:
    """Test tool-to-permission mapping."""

    def test_query_tools_require_read(self):
        """Test that query tools require read permission."""
        assert ToolPermissionMap.get_required_permission("neuralmind_query") == Permission.QUERY_READ
        assert ToolPermissionMap.get_required_permission("neuralmind_wakeup") == Permission.QUERY_READ
        assert ToolPermissionMap.get_required_permission("neuralmind_search") == Permission.QUERY_READ

    def test_build_tool_requires_write(self):
        """Test that build tool requires write permission."""
        assert ToolPermissionMap.get_required_permission("neuralmind_build") == Permission.QUERY_WRITE

    def test_nonexistent_tool(self):
        """Test permission for unknown tool."""
        result = ToolPermissionMap.get_required_permission("unknown_tool")
        assert result is None


# ============================================================================
# Test Rate Limiting
# ============================================================================


class TestRateLimitTracker:
    """Test rate limit tracker."""

    def test_tracker_initialization(self):
        """Test tracker starts with no calls."""
        tracker = RateLimitTracker(user_id="alice")

        assert tracker.user_id == "alice"
        assert len(tracker.calls_minute) == 0
        assert len(tracker.calls_hour) == 0
        assert tracker.tokens_today == 0

    def test_record_call(self):
        """Test recording a call."""
        tracker = RateLimitTracker(user_id="alice")

        tracker.record_call(tokens=100)

        assert len(tracker.calls_minute) == 1
        assert len(tracker.calls_hour) == 1
        assert tracker.tokens_today == 100

    def test_record_multiple_calls(self):
        """Test recording multiple calls."""
        tracker = RateLimitTracker(user_id="alice")

        for i in range(5):
            tracker.record_call(tokens=50)

        assert len(tracker.calls_minute) == 5
        assert len(tracker.calls_hour) == 5
        assert tracker.tokens_today == 250

    def test_not_rate_limited_initially(self):
        """Test no rate limit initially."""
        tracker = RateLimitTracker(user_id="alice")
        config = RateLimit(calls_per_minute=10)

        is_limited, reason = tracker.is_rate_limited(config)

        assert is_limited is False

    def test_minute_rate_limit_exceeded(self):
        """Test minute rate limit enforcement."""
        tracker = RateLimitTracker(user_id="alice")
        config = RateLimit(calls_per_minute=3)

        # Record calls up to limit
        for _ in range(3):
            tracker.record_call()

        # Next call should be limited
        is_limited, reason = tracker.is_rate_limited(config)

        assert is_limited is True
        assert "minute" in reason.lower()

    def test_hour_rate_limit_exceeded(self):
        """Test hour rate limit enforcement."""
        tracker = RateLimitTracker(user_id="alice")
        config = RateLimit(calls_per_minute=1000, calls_per_hour=5)

        # Record calls up to limit
        for _ in range(5):
            tracker.record_call()

        # Next call should be limited
        is_limited, reason = tracker.is_rate_limited(config)

        assert is_limited is True
        assert "hour" in reason.lower()

    def test_token_budget_exceeded(self):
        """Test token budget limit."""
        tracker = RateLimitTracker(user_id="alice")
        config = RateLimit(max_token_budget_per_day=1000)

        # Use half the budget
        tracker.record_call(tokens=500)
        is_limited, _ = tracker.is_rate_limited(config, tokens=400)
        assert is_limited is False

        # Try to exceed budget
        is_limited, reason = tracker.is_rate_limited(config, tokens=600)
        assert is_limited is True
        assert "token" in reason.lower()

    def test_daily_reset(self):
        """Test that token budget resets daily."""
        tracker = RateLimitTracker(user_id="alice")
        config = RateLimit(max_token_budget_per_day=1000)

        # Use some tokens
        tracker.record_call(tokens=800)
        tracker.tokens_today = 800

        # Simulate day passing
        tracker.last_reset = datetime.now(timezone.utc) - timedelta(days=1, seconds=1)

        # Should reset and allow more calls
        is_limited, _ = tracker.is_rate_limited(config, tokens=500)
        assert is_limited is False


class TestRateLimiter:
    """Test rate limiter (multi-user)."""

    def test_get_tracker_creates_new(self):
        """Test that get_tracker creates new tracker for unknown user."""
        limiter = RateLimiter()

        tracker = limiter.get_tracker("alice")

        assert tracker is not None
        assert tracker.user_id == "alice"

    def test_get_tracker_returns_same(self):
        """Test that get_tracker returns same tracker."""
        limiter = RateLimiter()

        tracker1 = limiter.get_tracker("alice")
        tracker2 = limiter.get_tracker("alice")

        assert tracker1 is tracker2

    def test_is_allowed(self):
        """Test is_allowed check."""
        limiter = RateLimiter(RateLimit(calls_per_minute=2))

        # First two calls allowed
        assert limiter.is_allowed("alice")[0] is False  # 0 calls, not limited
        assert limiter.is_allowed("bob")[0] is False  # Different user

        # Record calls
        limiter.record("alice")
        limiter.record("alice")

        # Third call should be limited
        assert limiter.is_allowed("alice")[0] is True

    def test_record_call(self):
        """Test recording call in limiter."""
        limiter = RateLimiter()

        limiter.record("alice", tokens=100)
        tracker = limiter.get_tracker("alice")

        assert tracker.tokens_today == 100


# ============================================================================
# Test Audit Logging
# ============================================================================


def test_mcp_audit_log_dir(temp_project):
    """Test audit log directory path."""
    log_dir = mcp_audit_log_dir(temp_project)

    assert log_dir == temp_project / ".neuralmind" / "audit" / "mcp"


def test_mcp_audit_log_file(temp_project):
    """Test audit log file path."""
    log_file = mcp_audit_log_file(temp_project)

    assert log_file == temp_project / ".neuralmind" / "audit" / "mcp" / "tool_calls.jsonl"


def test_log_mcp_call(temp_project):
    """Test logging MCP call."""
    success = log_mcp_call(
        temp_project,
        user_id="alice",
        role="developer",
        tool_name="neuralmind_query",
        parameters={"question": "How does auth work?"},
        result_tokens=847,
        status="success",
    )

    assert success is True

    # Verify log file was created and has content
    log_file = mcp_audit_log_file(temp_project)
    assert log_file.exists()

    lines = log_file.read_text().strip().split("\n")
    assert len(lines) == 1

    entry = json.loads(lines[0])
    assert entry["user_id"] == "alice"
    assert entry["tool_name"] == "neuralmind_query"
    assert entry["result_tokens"] == 847


def test_log_mcp_call_denial(temp_project):
    """Test logging denied MCP call."""
    log_mcp_call(
        temp_project,
        user_id="alice",
        role="viewer",
        tool_name="neuralmind_build",
        parameters={},
        status="denied",
        reason="Role 'viewer' cannot access 'neuralmind_build'",
    )

    log_file = mcp_audit_log_file(temp_project)
    entry = json.loads(log_file.read_text().strip())

    assert entry["result_status"] == "denied"
    assert "cannot access" in entry["denial_reason"]


def test_log_mcp_call_error(temp_project):
    """Test logging MCP call with error."""
    log_mcp_call(
        temp_project,
        user_id="alice",
        role="developer",
        tool_name="neuralmind_query",
        parameters={},
        status="error",
        error="Database connection failed",
    )

    log_file = mcp_audit_log_file(temp_project)
    entry = json.loads(log_file.read_text().strip())

    assert entry["result_status"] == "error"
    assert "connection failed" in entry["error_message"]


# ============================================================================
# Test Anomaly Detection
# ============================================================================


class TestAnomalyDetector:
    """Test anomaly detection."""

    def test_no_anomalies_initially(self):
        """Test no anomalies for new user."""
        detector = AnomalyDetector()

        anomalies = detector.detect_anomalies("alice")

        assert anomalies == []

    def test_high_call_volume_detection(self):
        """Test detection of high call volume."""
        detector = AnomalyDetector(window_minutes=60)

        # Record 101 calls (threshold is 100)
        for i in range(101):
            detector.record_call("alice", "neuralmind_query")

        anomalies = detector.detect_anomalies("alice")

        assert len(anomalies) > 0
        assert "High call volume" in anomalies[0]

    def test_repeated_tool_detection(self):
        """Test detection of repeated same tool."""
        detector = AnomalyDetector()

        # Record same tool 10 times in succession
        for _ in range(10):
            detector.record_call("alice", "neuralmind_query")

        anomalies = detector.detect_anomalies("alice")

        assert len(anomalies) > 0
        assert "Repeated tool pattern" in anomalies[0]

    def test_many_queries_detection(self):
        """Test detection of many queries."""
        detector = AnomalyDetector()

        # Record 21 query calls (threshold is 20)
        for i in range(21):
            detector.record_call("alice", "neuralmind_query")

        anomalies = detector.detect_anomalies("alice")

        assert len(anomalies) > 0
        # Should have at least one anomaly about high volume or repeated queries
        has_query_anomaly = any("query" in a.lower() or "repeated" in a.lower() for a in anomalies)
        assert has_query_anomaly

    def test_no_anomaly_within_normal_usage(self):
        """Test normal usage doesn't trigger anomalies."""
        detector = AnomalyDetector()

        # Normal usage: 5 different tools, spread out
        for i in range(5):
            detector.record_call("alice", f"neuralmind_tool_{i}")

        anomalies = detector.detect_anomalies("alice")

        assert anomalies == []

    def test_window_pruning(self):
        """Test that old calls are pruned from window."""
        detector = AnomalyDetector(window_minutes=1)

        # Record a call
        detector.record_call("alice", "neuralmind_query")

        # Manually age the first call to be outside window
        if detector.call_history.get("alice"):
            first_call_time, first_tool = detector.call_history["alice"][0]
            new_time = first_call_time - timedelta(minutes=2)
            detector.call_history["alice"][0] = (new_time, first_tool)

        # Record a new call (this one is current)
        detector.record_call("alice", "neuralmind_query")

        # Calling detect_anomalies should prune old entries
        anomalies = detector.detect_anomalies("alice")
        # After pruning, should only have 1 call left in window
        # (the old one should be removed)
        assert len(detector.call_history["alice"]) == 1


# ============================================================================
# Test MCP Security Middleware
# ============================================================================


class TestMCPSecurityMiddleware:
    """Test MCP security middleware."""

    def test_middleware_initialization(self, temp_project):
        """Test middleware initialization."""
        middleware = MCPSecurityMiddleware(
            project_path=temp_project,
            user_id="alice",
            role=Role.DEVELOPER
        )

        assert middleware.user_id == "alice"
        assert middleware.role == Role.DEVELOPER

    def test_authorize_tool_success(self, temp_project):
        """Test successful tool authorization."""
        middleware = MCPSecurityMiddleware(
            temp_project,
            user_id="alice",
            role=Role.DEVELOPER
        )

        authorized, reason = middleware.authorize_tool("neuralmind_query")

        assert authorized is True
        assert reason == ""

    def test_authorize_tool_denied_insufficient_role(self, temp_project):
        """Test tool authorization denied due to insufficient role."""
        middleware = MCPSecurityMiddleware(
            temp_project,
            user_id="alice",
            role=Role.VIEWER
        )

        authorized, reason = middleware.authorize_tool("neuralmind_build")

        assert authorized is False
        assert "cannot access" in reason.lower()

    def test_authorize_tool_allowed_by_admin(self, temp_project):
        """Test admin can access all tools."""
        middleware = MCPSecurityMiddleware(
            temp_project,
            user_id="admin",
            role=Role.ADMIN
        )

        authorized, reason = middleware.authorize_tool("neuralmind_build")

        assert authorized is True

    def test_check_rate_limit(self, temp_project):
        """Test rate limit checking."""
        rate_config = RateLimit(calls_per_minute=2)
        middleware = MCPSecurityMiddleware(
            temp_project,
            user_id="alice",
            role=Role.DEVELOPER,
            rate_limit_config=rate_config
        )

        # Record calls
        middleware.rate_limiter.record("alice")
        middleware.rate_limiter.record("alice")

        # Next call should be limited
        is_limited, reason = middleware.check_rate_limit()

        assert is_limited is True

    def test_check_anomalies(self, temp_project):
        """Test anomaly detection."""
        middleware = MCPSecurityMiddleware(
            temp_project,
            user_id="alice",
            role=Role.DEVELOPER
        )

        # Record many calls
        for _ in range(101):
            middleware.anomaly_detector.record_call("alice", "neuralmind_query")

        anomalies = middleware.check_anomalies()

        assert len(anomalies) > 0


class TestMCPSecurityMiddlewareWrapping:
    """Test tool wrapping with security checks."""

    def test_wrap_tool_success(self, temp_project):
        """Test successful tool execution."""
        middleware = MCPSecurityMiddleware(
            temp_project,
            user_id="alice",
            role=Role.DEVELOPER
        )

        # Define a simple tool function
        def tool_query(question: str):
            return {"answer": "test", "tokens": 100}

        wrapped = middleware.wrap_tool("neuralmind_query", tool_query)

        result = wrapped(question="What is X?")

        assert result["answer"] == "test"
        assert result["tokens"] == 100

    def test_wrap_tool_authorization_denied(self, temp_project):
        """Test tool execution denied due to authorization."""
        middleware = MCPSecurityMiddleware(
            temp_project,
            user_id="alice",
            role=Role.VIEWER
        )

        def tool_build():
            return {"status": "built"}

        wrapped = middleware.wrap_tool("neuralmind_build", tool_build)

        with pytest.raises(PermissionError, match="Not authorized"):
            wrapped()

    def test_wrap_tool_rate_limited(self, temp_project):
        """Test tool execution rate limited."""
        rate_config = RateLimit(calls_per_minute=1)
        middleware = MCPSecurityMiddleware(
            temp_project,
            user_id="alice",
            role=Role.DEVELOPER,
            rate_limit_config=rate_config
        )

        # Pre-record a call to trigger rate limit
        middleware.rate_limiter.record("alice")

        def tool_query(question: str):
            return {"answer": "test"}

        wrapped = middleware.wrap_tool("neuralmind_query", tool_query)

        with pytest.raises(RuntimeError, match="Rate limited"):
            wrapped(question="What is X?")

    def test_wrap_tool_exception_handling(self, temp_project):
        """Test exception handling in wrapped tool."""
        middleware = MCPSecurityMiddleware(
            temp_project,
            user_id="alice",
            role=Role.DEVELOPER
        )

        def failing_tool():
            raise ValueError("Tool failed")

        wrapped = middleware.wrap_tool("neuralmind_query", failing_tool)

        with pytest.raises(ValueError, match="Tool failed"):
            wrapped()

        # Verify error was logged
        log_file = mcp_audit_log_file(temp_project)
        entry = json.loads(log_file.read_text().strip())
        assert entry["result_status"] == "error"

    def test_wrap_tool_records_tokens(self, temp_project):
        """Test that wrapped tool records token usage."""
        middleware = MCPSecurityMiddleware(
            temp_project,
            user_id="alice",
            role=Role.DEVELOPER
        )

        def tool_query():
            return {"answer": "test", "tokens": 847}

        wrapped = middleware.wrap_tool("neuralmind_query", tool_query)
        result = wrapped()

        # Verify audit log has tokens
        log_file = mcp_audit_log_file(temp_project)
        entry = json.loads(log_file.read_text().strip())
        assert entry["result_tokens"] == 847

    def test_wrap_tool_audit_logging(self, temp_project):
        """Test that tool calls are audit logged."""
        middleware = MCPSecurityMiddleware(
            temp_project,
            user_id="alice",
            role=Role.DEVELOPER
        )

        def tool_query(question: str):
            return {"answer": "test"}

        wrapped = middleware.wrap_tool("neuralmind_query", tool_query)
        wrapped(question="How does X work?")

        # Verify audit log
        log_file = mcp_audit_log_file(temp_project)
        assert log_file.exists()

        entry = json.loads(log_file.read_text().strip())
        assert entry["user_id"] == "alice"
        assert entry["tool_name"] == "neuralmind_query"
        assert entry["parameters"]["question"] == "How does X work?"
        assert entry["result_status"] == "success"

    def test_wrap_tool_anomaly_recording(self, temp_project):
        """Test that wrapped tool records anomaly data."""
        # Use high rate limit to avoid triggering rate limit during test
        rate_config = RateLimit(
            calls_per_minute=500,
            calls_per_hour=10000,
            max_token_budget_per_day=10_000_000
        )
        middleware = MCPSecurityMiddleware(
            temp_project,
            user_id="alice",
            role=Role.DEVELOPER,
            rate_limit_config=rate_config
        )

        def tool_query():
            return {"answer": "test"}

        wrapped = middleware.wrap_tool("neuralmind_query", tool_query)

        # Record many calls
        for _ in range(101):
            wrapped()

        # Check anomalies detected
        anomalies = middleware.check_anomalies()
        assert len(anomalies) > 0
