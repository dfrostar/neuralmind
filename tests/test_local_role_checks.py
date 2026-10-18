"""Role checks off the MCP path: the daemon's routes and the CLI's writes.

Under ``security.identity: os`` the role policy used to stop at the MCP server:
an OS account mapped to ``reader`` couldn't call ``neuralmind_build`` through
MCP, but could build through the daemon's ``/build`` route or ``neuralmind
build``. Each daemon route and CLI write now needs the role the MCP tool that
does the same thing needs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from neuralmind import cli
from neuralmind import daemon as daemon_mod
from neuralmind import identity as identity_module
from neuralmind.audit import get_audit_trail

POLICY = "security:\n  identity: os\n  users:\n    alice: builder\n    bob: reader\n"


def _config(project: Path, text: str = POLICY) -> Path:
    path = project / "neuralmind-backend.yaml"
    path.write_text(text, encoding="utf-8")
    if sys.platform != "win32":
        path.chmod(0o644)
    return path


@pytest.fixture
def account(monkeypatch):
    """Make the OS report this process's account as the name given."""

    def be(name: str | None) -> None:
        monkeypatch.setattr(identity_module, "os_identity", lambda: name)
        monkeypatch.setattr("neuralmind.mcp_security.os_identity", lambda: name)

    return be


class _FakeMind:
    def __init__(self, project_path: str) -> None:
        self.project_path = project_path
        self.built = False

    def build(self, force: bool = False) -> dict:
        self.built = True
        return {"success": True}

    def get_stats(self) -> dict:
        return {"built": True}


def _ctx() -> daemon_mod.DaemonContext:
    return daemon_mod.DaemonContext(
        registry=daemon_mod.ProjectRegistry(mind_factory=_FakeMind),
        jobs=daemon_mod.JobManager(),
        exposure=None,
    )


def _denials(project: Path) -> list[dict]:
    events = get_audit_trail(project).events_file
    if not events.exists():
        return []
    rows = [json.loads(line) for line in events.read_text().splitlines() if line.strip()]
    return [r for r in rows if r["action"] == "call_denied"]


# --- the daemon -------------------------------------------------------------


def test_a_reader_cannot_build_through_the_daemon(tmp_path, account):
    _config(tmp_path)
    account("bob")
    ctx = _ctx()
    status, payload = daemon_mod.dispatch(
        ctx, "POST", "/build", {"project": str(tmp_path), "sync": True}
    )
    assert status == 403
    assert (payload["code"], payload["reason"]) == ("security_denied", "rbac")
    assert "role 'reader'" in payload["error"]
    assert ctx.registry.projects() == []  # never opened
    denial = _denials(tmp_path)[-1]
    assert (denial["target"], denial["actor"], denial["actor_role"]) == (
        "neuralmind_build",
        "bob",
        "reader",
    )
    assert denial["details"]["surface"] == "daemon"


@pytest.mark.parametrize(
    "method, route, body",
    [
        ("GET", "/stats", {}),
        ("GET", "/savings", {}),
        ("POST", "/validate", {}),
    ],
)
def test_a_reader_can_still_read_through_the_daemon(tmp_path, account, method, route, body):
    _config(tmp_path)
    account("bob")
    status, payload = daemon_mod.dispatch(_ctx(), method, route, {**body, "project": str(tmp_path)})
    assert status != 403, payload


def test_a_reader_cannot_write_the_ir_through_the_daemon(tmp_path, account):
    _config(tmp_path)
    account("bob")
    status, payload = daemon_mod.dispatch(
        _ctx(), "POST", "/validate", {"project": str(tmp_path), "write": True}
    )
    assert status == 403 and payload["reason"] == "rbac"


def test_a_builder_builds_through_the_daemon(tmp_path, account):
    _config(tmp_path)
    account("alice")
    status, payload = daemon_mod.dispatch(
        _ctx(), "POST", "/build", {"project": str(tmp_path), "sync": True}
    )
    assert status == 200, payload


def test_an_account_without_a_role_is_refused_by_the_daemon(tmp_path, account):
    _config(tmp_path)
    account("mallory")
    status, payload = daemon_mod.dispatch(_ctx(), "GET", "/stats", {"project": str(tmp_path)})
    assert status == 403 and payload["reason"] == "identity"
    assert _denials(tmp_path)[-1]["details"]["reason"] == "identity"


def test_a_custom_role_policy_applies_to_the_daemon(tmp_path, account):
    _config(tmp_path, POLICY + "  roles:\n    builder: [neuralmind_query]\n")
    account("alice")
    status, payload = daemon_mod.dispatch(
        _ctx(), "POST", "/build", {"project": str(tmp_path), "sync": True}
    )
    assert status == 403 and payload["reason"] == "rbac"


def test_a_broken_role_policy_refuses_the_daemon(tmp_path, account):
    _config(tmp_path, POLICY + "  roles: [builder]\n")
    account("alice")
    status, payload = daemon_mod.dispatch(_ctx(), "GET", "/stats", {"project": str(tmp_path)})
    assert status == 403 and payload["reason"] == "config"


def test_declared_identity_leaves_the_daemon_unchecked(tmp_path, account):
    # Off the MCP path nothing names a role, so nothing is checked, as before.
    _config(tmp_path, "security:\n  users:\n    bob: reader\n")
    account("bob")
    status, _ = daemon_mod.dispatch(
        _ctx(), "POST", "/build", {"project": str(tmp_path), "sync": True}
    )
    assert status == 200
    assert _denials(tmp_path) == []


# --- the CLI ----------------------------------------------------------------


def _run_cli(monkeypatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["neuralmind", *argv])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    return exc.value.code


def test_a_reader_cannot_build_from_the_cli(temp_project, account, monkeypatch, capsys):
    _config(temp_project)
    account("bob")
    assert _run_cli(monkeypatch, "build", str(temp_project)) == 1
    err = capsys.readouterr().err
    assert "refused" in err and "role 'reader'" in err and "neuralmind_build" in err
    assert not (temp_project / ".neuralmind" / "graph.json").exists()
    assert _denials(temp_project)[-1]["details"]["surface"] == "cli"


def test_a_reader_cannot_write_the_ir_from_the_cli(temp_project, account, monkeypatch, capsys):
    _config(temp_project)
    account("bob")
    assert _run_cli(monkeypatch, "validate", str(temp_project), "--write") == 1
    assert "role 'reader'" in capsys.readouterr().err
