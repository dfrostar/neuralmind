"""security.identity: os — MCP callers identified by their OS account.

By default an MCP tool call declares its own ``actor`` and ``role``, and any
caller can declare ``admin``. With ``identity: os`` the server ignores both:
the actor is the OS account it runs as (over stdio, the agent that launched
it) and the role comes from ``security.users``.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from neuralmind import identity as identity_module
from neuralmind.audit import AuditTrail
from neuralmind.mcp_security import (
    AccessDeniedError,
    IdentityDeniedError,
    MCPSecurityManager,
    RateLimiter,
    RateLimitExceededError,
    RBACPolicy,
    build_security_manager,
)
from neuralmind.security_config import (
    IDENTITY_DECLARED,
    IDENTITY_INVALID,
    IDENTITY_OS,
    load_security_settings,
)

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")

OS_POLICY = """\
security:
  identity: os
  users:
    alice: reader
    root: admin
  roles:
    admin: "*"
    builder: [neuralmind_stats, neuralmind_build]
    reader: [neuralmind_stats]
"""


def _config(project: Path, text: str) -> Path:
    path = Path(project) / "neuralmind-backend.yaml"
    path.write_text(text, encoding="utf-8")
    if sys.platform != "win32":
        path.chmod(0o644)
    return path


@pytest.fixture(autouse=True)
def no_running_transport(monkeypatch):
    """No server has started in tests; fall back to the requested transport."""
    from neuralmind import mcp_security

    monkeypatch.setattr(mcp_security, "_active_transport", None)


@pytest.fixture
def as_alice(monkeypatch):
    """Make the OS report the server's account as 'alice'."""
    monkeypatch.setattr(identity_module, "os_identity", lambda: "alice")
    monkeypatch.setattr("neuralmind.mcp_security.os_identity", lambda: "alice")
    monkeypatch.delenv("NEURALMIND_MCP_TRANSPORT", raising=False)
    return "alice"


def _manager(project: Path) -> MCPSecurityManager:
    return build_security_manager(str(project))


# --- the OS account itself ----------------------------------------------------


@posix_only
def test_os_identity_comes_from_the_os_not_the_environment(monkeypatch):
    import pwd

    real = pwd.getpwuid(os.geteuid()).pw_name
    for var in ("LOGNAME", "USER", "USERNAME"):
        monkeypatch.setenv(var, "mallory-spoofed")
    assert identity_module.os_identity() == real


# --- settings -----------------------------------------------------------------


def test_settings_default_to_declared_identity(temp_project):
    settings = load_security_settings(temp_project)
    assert settings.identity == IDENTITY_DECLARED
    assert settings.require_encrypted_storage is False


def test_settings_read_identity_users_and_default_role(temp_project):
    _config(temp_project, OS_POLICY + "  default_role: reader\n")
    settings = load_security_settings(temp_project)
    assert settings.identity == IDENTITY_OS
    assert settings.users == {"alice": "reader", "root": "admin"}
    assert settings.default_role == "reader"


@pytest.mark.parametrize(
    "body, fragment",
    [
        ("security:\n  identity: kerberos\n", "'declared' or 'os'"),
        ("security:\n  identity: os\n  users: [alice]\n", "security.users"),
        ("security:\n  identity: os\n  default_role: [reader]\n", "default_role"),
        ("security: just-a-string\n", "mapping"),
    ],
)
def test_bad_identity_settings_fail_closed(temp_project, body, fragment):
    _config(temp_project, body)
    settings = load_security_settings(temp_project)
    assert settings.identity == IDENTITY_INVALID
    assert fragment in settings.problem


def test_an_unparseable_policy_that_names_enforcement_fails_closed(temp_project):
    _config(temp_project, "security:\n  identity: os\n  users: {alice: reader\n")
    settings = load_security_settings(temp_project)
    assert settings.identity == IDENTITY_INVALID
    assert settings.require_encrypted_storage is True
    assert "does not parse" in settings.problem


def test_an_unparseable_config_without_enforcement_keeps_defaults(temp_project):
    _config(temp_project, "backend: [turbovec\n")
    settings = load_security_settings(temp_project)
    assert settings.identity == IDENTITY_DECLARED
    assert settings.require_encrypted_storage is False


@pytest.mark.parametrize(
    "value, expected",
    [("true", True), ("yes", True), ("false", False), ("off", False), ("maybe", True)],
)
def test_require_encrypted_storage_errs_toward_on(temp_project, value, expected):
    _config(temp_project, f"security:\n  require_encrypted_storage: '{value}'\n")
    assert load_security_settings(temp_project).require_encrypted_storage is expected


@pytest.mark.parametrize(
    "line, expected",
    [
        ("  require_encrypted_storage:\n", True),
        ("  require_encrypted_storage: []\n", True),
        ("  require_encrypted_storage: {}\n", True),
        ("  require_encrypted_storage: ''\n", True),
        ("  require_encrypted_storage: false\n", False),
        ("  require_encrypted_storage: 0\n", False),
        ("  identity: declared\n", False),
    ],
)
def test_only_an_explicit_off_disables_encrypted_storage(temp_project, line, expected):
    """A blank value parses as None and used to read as off."""
    _config(temp_project, "security:\n" + line)
    assert load_security_settings(temp_project).require_encrypted_storage is expected


# --- the security manager -----------------------------------------------------


def test_declared_identity_is_unchanged(temp_project):
    manager = MCPSecurityManager(str(temp_project), policy=RBACPolicy({"admin": "*"}))
    assert manager.resolve_caller("bob", "admin") == ("bob", "admin", {})
    assert manager.resolve_caller(None, None) == ("anonymous", "builder", {})


def test_os_identity_ignores_the_declared_actor_and_role(temp_project, as_alice):
    _config(temp_project, OS_POLICY)
    manager = _manager(temp_project)
    actor, role, details = manager.resolve_caller("root", "admin")
    assert (actor, role) == ("alice", "reader")
    assert details == {"identity": "os", "claimed_actor": "root", "claimed_role": "admin"}

    assert manager.secure_call("root", "admin", "neuralmind_stats", lambda: "ok") == "ok"
    with pytest.raises(AccessDeniedError):
        manager.secure_call("root", "admin", "neuralmind_build", lambda: "ok")

    events = AuditTrail(temp_project).read_events()
    allowed = next(e for e in events if e["action"] == "mcp_call")
    assert allowed["actor"] == "alice"
    assert allowed["details"]["role"] == "reader"
    assert allowed["details"]["claimed_role"] == "admin"
    denied = next(e for e in events if e["action"] == "mcp_call_denied")
    assert denied["details"]["reason"] == "rbac"


def test_unmapped_account_is_refused_without_a_default_role(temp_project, monkeypatch):
    _config(temp_project, OS_POLICY)
    monkeypatch.setattr("neuralmind.mcp_security.os_identity", lambda: "mallory")
    monkeypatch.delenv("NEURALMIND_MCP_TRANSPORT", raising=False)
    with pytest.raises(IdentityDeniedError, match="'mallory' has no role"):
        _manager(temp_project).secure_call(None, "admin", "neuralmind_stats", lambda: "ok")
    denied = AuditTrail(temp_project).read_events()[-1]
    assert denied["action"] == "mcp_call_denied"
    assert denied["details"]["reason"] == "identity"
    assert denied["details"]["claimed_role"] == "admin"


def test_unmapped_account_gets_the_default_role(temp_project, monkeypatch):
    _config(temp_project, OS_POLICY + "  default_role: reader\n")
    monkeypatch.setattr("neuralmind.mcp_security.os_identity", lambda: "mallory")
    monkeypatch.delenv("NEURALMIND_MCP_TRANSPORT", raising=False)
    assert _manager(temp_project).resolve_caller(None, None)[:2] == ("mallory", "reader")


def test_os_identity_refuses_the_http_transport(temp_project, as_alice, monkeypatch):
    _config(temp_project, OS_POLICY)
    monkeypatch.setenv("NEURALMIND_MCP_TRANSPORT", "streamable_http")
    with pytest.raises(IdentityDeniedError, match="stdio"):
        _manager(temp_project).resolve_caller(None, None)


def test_os_identity_follows_the_transport_actually_running(temp_project, as_alice, monkeypatch):
    """mcp_server.main() falls back to stdio when the HTTP dependencies are
    missing, leaving NEURALMIND_MCP_TRANSPORT set. Refusing then would block
    every call on a server that is in fact running stdio."""
    from neuralmind import mcp_security

    _config(temp_project, OS_POLICY)
    monkeypatch.setenv("NEURALMIND_MCP_TRANSPORT", "streamable_http")
    monkeypatch.setattr(mcp_security, "_active_transport", "stdio")
    assert _manager(temp_project).resolve_caller(None, None)[:2] == ("alice", "reader")

    monkeypatch.delenv("NEURALMIND_MCP_TRANSPORT")
    monkeypatch.setattr(mcp_security, "_active_transport", "streamable_http")
    with pytest.raises(IdentityDeniedError, match="stdio"):
        _manager(temp_project).resolve_caller(None, None)


def test_os_identity_refuses_when_the_account_is_unknown(temp_project, monkeypatch):
    _config(temp_project, OS_POLICY)
    monkeypatch.setattr("neuralmind.mcp_security.os_identity", lambda: None)
    monkeypatch.delenv("NEURALMIND_MCP_TRANSPORT", raising=False)
    with pytest.raises(IdentityDeniedError, match="could not be determined"):
        _manager(temp_project).resolve_caller(None, None)


@posix_only
def test_os_identity_refuses_a_world_writable_policy(temp_project, as_alice):
    path = _config(temp_project, OS_POLICY)
    path.chmod(0o666)
    with pytest.raises(IdentityDeniedError, match="writable by every user"):
        _manager(temp_project).resolve_caller(None, None)


def test_invalid_identity_refuses_every_call(temp_project):
    _config(temp_project, "security:\n  identity: kerberos\n")
    with pytest.raises(IdentityDeniedError, match="Refusing MCP calls"):
        _manager(temp_project).secure_call("bob", "admin", "neuralmind_stats", lambda: "ok")


def test_rate_limit_keys_on_the_os_account(temp_project, as_alice):
    _config(temp_project, OS_POLICY)
    manager = MCPSecurityManager(
        str(temp_project),
        policy=RBACPolicy({"reader": {"neuralmind_stats"}}),
        rate_limiter=RateLimiter(max_calls=1, window_seconds=60),
        settings=load_security_settings(temp_project),
    )
    manager.secure_call("first-name", None, "neuralmind_stats", lambda: "ok")
    with pytest.raises(RateLimitExceededError):
        manager.secure_call("a-different-name", None, "neuralmind_stats", lambda: "ok")


# --- end to end through the MCP dispatcher ------------------------------------


def test_dispatcher_applies_os_identity(temp_project, as_alice):
    from neuralmind.mcp_server import _security_cache, handle_tool_call

    _security_cache.clear()
    _config(temp_project, OS_POLICY)
    base = {"project_path": str(temp_project)}
    stats = json.loads(handle_tool_call("neuralmind_stats", {**base, "role": "admin"}))
    assert stats.get("code") != "security_denied", stats
    build = json.loads(handle_tool_call("neuralmind_build", {**base, "role": "admin"}))
    assert build["code"] == "security_denied"
    assert build["reason"] == "rbac"


def test_dispatcher_reports_identity_refusals(temp_project, monkeypatch):
    from neuralmind.mcp_server import _security_cache, handle_tool_call

    _security_cache.clear()
    _config(temp_project, OS_POLICY)
    monkeypatch.setattr("neuralmind.mcp_security.os_identity", lambda: "mallory")
    monkeypatch.delenv("NEURALMIND_MCP_TRANSPORT", raising=False)
    data = json.loads(handle_tool_call("neuralmind_stats", {"project_path": str(temp_project)}))
    assert data["code"] == "security_denied"
    assert data["reason"] == "identity"


# --- the audit log's actor outside MCP ----------------------------------------


def test_audit_actor_is_the_os_account_under_os_identity(temp_project, as_alice, monkeypatch):
    _config(temp_project, OS_POLICY)
    monkeypatch.setenv("NEURALMIND_ACTOR", "mallory")
    event = AuditTrail(temp_project).append_event(category="audit", action="query")
    assert event["actor"] == "alice"
    assert event["details"]["claimed_actor"] == "mallory"


def test_audit_actor_still_honours_neuralmind_actor_by_default(temp_project, monkeypatch):
    monkeypatch.setenv("NEURALMIND_ACTOR", "hashed-token")
    event = AuditTrail(temp_project).append_event(category="audit", action="query")
    assert event["actor"] == "hashed-token"
    assert "claimed_actor" not in event["details"]


# --- doctor -------------------------------------------------------------------


def _policy_check(project):
    from neuralmind.doctor import _check_security_policy

    return _check_security_policy(Path(project).resolve())


def test_doctor_reports_declared_identity(temp_project):
    check = _policy_check(temp_project)
    assert check.status == "ok"
    assert "declared" in check.detail


def test_doctor_warns_about_an_account_without_a_role(temp_project, monkeypatch):
    _config(temp_project, OS_POLICY)
    monkeypatch.setattr(identity_module, "os_identity", lambda: "mallory")
    check = _policy_check(temp_project)
    assert check.status == "warn"
    assert "'mallory' has no role" in check.detail


@posix_only
@pytest.mark.parametrize("mode, status", [(0o664, "warn"), (0o666, "fail"), (0o644, "ok")])
def test_doctor_checks_policy_file_permissions(temp_project, as_alice, mode, status):
    _config(temp_project, OS_POLICY).chmod(mode)
    assert _policy_check(temp_project).status == status


@pytest.mark.parametrize(
    "body, fragment",
    [
        ("security:\n  roles:\n", "security.roles is empty"),
        ("security:\n  roles: [admin]\n", "security.roles must map"),
        ("security:\n  roles:\n    builder: [neuralmind_stats\n", "does not parse"),
    ],
)
def test_doctor_reports_a_role_policy_the_server_refuses(temp_project, body, fragment):
    _config(temp_project, body)
    check = _policy_check(temp_project)
    assert check.status == "fail"
    assert fragment in check.detail


def test_doctor_fails_on_an_unparseable_config(temp_project):
    _config(temp_project, "security:\n  identity: os\n  users: {alice: reader\n")
    check = _policy_check(temp_project)
    assert check.status == "fail"
    assert "does not parse" in check.detail
