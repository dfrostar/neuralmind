"""security.profile: cui — the CUI-enclave settings as one enforced unit.

The profile forces ``identity: os`` and ``require_encrypted_storage: true``,
refuses to serve a project beyond loopback or without its access token, and
refuses LLM documentation seeding. A broken profile setting fails closed: it is
held to the strictest profile, never read as none.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

from neuralmind import daemon as daemon_mod
from neuralmind import doctor
from neuralmind import security_profile as sp
from neuralmind.audit import get_audit_trail
from neuralmind.security_config import (
    IDENTITY_INVALID,
    IDENTITY_OS,
    PROFILE_CUI,
    load_security_settings,
)
from neuralmind.storage_guard import StorageStatus
from neuralmind.synapses import SynapseStore, default_db_path

CUI = "security:\n  profile: cui\n  users:\n    alice: reader\n"


def _config(project: Path, text: str) -> Path:
    path = Path(project) / "neuralmind-backend.yaml"
    path.write_text(text, encoding="utf-8")
    if sys.platform != "win32":
        path.chmod(0o644)
    return path


def _refusals(project: Path) -> list[dict]:
    events = get_audit_trail(project).events_file
    if not events.exists():
        return []
    rows = [json.loads(line) for line in events.read_text().splitlines() if line.strip()]
    return [r for r in rows if r["action"] == "profile_refused"]


# --- parsing ----------------------------------------------------------------


def test_cui_forces_os_identity_and_encrypted_storage(tmp_path):
    _config(tmp_path, CUI)
    s = load_security_settings(tmp_path)
    assert (s.profile, s.identity, s.require_encrypted_storage, s.problem) == (
        PROFILE_CUI,
        IDENTITY_OS,
        True,
        None,
    )


def test_profile_name_is_case_insensitive(tmp_path):
    _config(tmp_path, "security:\n  profile: CUI\n")
    assert load_security_settings(tmp_path).profile == PROFILE_CUI


def test_no_profile_leaves_settings_alone(tmp_path):
    _config(tmp_path, "security:\n  identity: os\n")
    s = load_security_settings(tmp_path)
    assert (s.profile, s.require_encrypted_storage) == (None, False)


@pytest.mark.parametrize(
    "extra, needle",
    [
        ("  identity: declared\n", "requires identity: os"),
        ("  require_encrypted_storage: false\n", "requires encrypted storage"),
    ],
)
def test_profile_cannot_be_loosened(tmp_path, extra, needle):
    _config(tmp_path, CUI + extra)
    s = load_security_settings(tmp_path)
    assert s.identity == IDENTITY_INVALID  # every MCP call refused
    assert s.require_encrypted_storage is True
    assert s.profile == PROFILE_CUI
    assert needle in s.problem


@pytest.mark.parametrize("value", ["cuii", "", "none"])
def test_broken_profile_is_held_to_the_strictest(tmp_path, value):
    _config(tmp_path, f"security:\n  profile: {value}\n")
    s = load_security_settings(tmp_path)
    assert (s.profile, s.identity, s.require_encrypted_storage) == (
        PROFILE_CUI,
        IDENTITY_INVALID,
        True,
    )
    assert "security.profile must be 'cui'" in s.problem


def test_unparseable_file_naming_a_profile_is_held_to_it(tmp_path):
    _config(tmp_path, "security: [\n  profile: cui\n")
    s = load_security_settings(tmp_path)
    assert (s.profile, s.identity, s.require_encrypted_storage) == (
        PROFILE_CUI,
        IDENTITY_INVALID,
        True,
    )


# --- listeners --------------------------------------------------------------


@pytest.mark.parametrize(
    "host", ["127.0.0.1", "127.8.9.10", "::1", "[::1]", "localhost", "LocalHost"]
)
def test_loopback_hosts(host):
    assert sp.is_loopback(host)


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.5", "10.0.0.1", "example.com", ""])
def test_non_loopback_hosts(host):
    assert not sp.is_loopback(host)


@pytest.mark.parametrize(
    "host, auth, needle",
    [("0.0.0.0", True, "beyond loopback"), ("127.0.0.1", False, "--no-auth")],
)
def test_serve_refuses_an_exposed_listener_before_building(
    tmp_path, monkeypatch, host, auth, needle
):
    from neuralmind import server

    _config(tmp_path, CUI)

    def must_not_run(*_a, **_k):
        raise AssertionError("refusal must come before any build or bind")

    monkeypatch.setattr(server, "_ensure_graph_or_explain", must_not_run)
    monkeypatch.setattr(server, "ThreadingHTTPServer", must_not_run)
    with pytest.raises(sp.ProfileRefusedError, match=needle):
        server.serve(str(tmp_path), host=host, port=0, auth=auth)
    refused = _refusals(tmp_path)
    assert refused and refused[-1]["target"] == "serve"
    assert refused[-1]["status"] == "denied"


def test_loopback_with_token_is_allowed(tmp_path):
    _config(tmp_path, CUI)
    assert sp.refuse_exposed_listener(tmp_path, "127.0.0.1", True, "serve") is None
    assert _refusals(tmp_path) == []


def test_a_project_without_the_profile_may_still_listen_widely(tmp_path):
    assert sp.refuse_exposed_listener(tmp_path, "0.0.0.0", False, "serve") is None


def test_cli_serve_reports_a_refusal_not_a_bind_failure(tmp_path, monkeypatch, capsys):
    from neuralmind import cli

    _config(tmp_path, CUI)
    args = argparse.Namespace(
        project_path=str(tmp_path),
        host="0.0.0.0",
        port=0,
        no_browser=True,
        no_auth=False,
        editor=None,
    )
    with pytest.raises(SystemExit) as exc:
        cli.cmd_serve(args)
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "serve refused: security.profile: cui" in out
    assert "could not bind" not in out


class _FakeMind:
    def __init__(self, project_path: str) -> None:
        self.project_path = project_path

    def build(self, force: bool = False) -> dict:
        return {"success": True}

    def get_stats(self) -> dict:
        return {"built": True}


def _ctx(exposure: str | None) -> daemon_mod.DaemonContext:
    return daemon_mod.DaemonContext(
        registry=daemon_mod.ProjectRegistry(mind_factory=_FakeMind),
        jobs=daemon_mod.JobManager(),
        exposure=exposure,
    )


@pytest.mark.parametrize(
    "method, route, body",
    [
        ("POST", "/query", {"question": "q"}),
        ("POST", "/search", {"query": "q"}),
        ("GET", "/stats", {}),
        ("GET", "/savings", {}),
        ("POST", "/build", {"sync": True}),
        ("POST", "/validate", {}),
    ],
)
def test_an_exposed_daemon_refuses_a_cui_project_on_every_route(tmp_path, method, route, body):
    _config(tmp_path, CUI)
    ctx = _ctx(sp.listener_problem("0.0.0.0", True))
    status, payload = daemon_mod.dispatch(ctx, method, route, {**body, "project": str(tmp_path)})
    assert status == 403
    assert (payload["code"], payload["reason"]) == ("security_denied", "profile")
    assert ctx.registry.projects() == []  # never opened
    assert _refusals(tmp_path)[-1]["target"] == "daemon"


def test_an_exposed_daemon_still_serves_projects_without_the_profile(tmp_path):
    ctx = _ctx(sp.listener_problem("0.0.0.0", True))
    status, _ = daemon_mod.dispatch(ctx, "GET", "/stats", {"project": str(tmp_path)})
    assert status == 200


def test_a_loopback_daemon_with_its_token_serves_a_cui_project(tmp_path):
    _config(tmp_path, CUI)
    status, _ = daemon_mod.dispatch(_ctx(None), "GET", "/stats", {"project": str(tmp_path)})
    assert status == 200


def test_create_server_records_its_own_exposure():
    httpd, _ = daemon_mod.create_server("127.0.0.1", 0, auth=False, write_disco=False)
    try:
        assert "--no-auth" in httpd.nm_context.exposure
    finally:
        httpd.server_close()
    httpd, _ = daemon_mod.create_server("127.0.0.1", 0, auth=True, write_disco=False)
    try:
        assert httpd.nm_context.exposure is None
    finally:
        httpd.server_close()


# --- LLM seeding ------------------------------------------------------------


def test_llm_seeding_is_refused_even_when_switched_on(tmp_path, monkeypatch):
    _config(tmp_path, CUI)
    monkeypatch.setenv("NEURALMIND_LLM_SEED", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    (tmp_path / "README.md").write_text("# App\nAuth delegates to hashing.")
    store = SynapseStore(default_db_path(tmp_path))

    def must_not_call(*_a, **_k):
        raise AssertionError("no prose may reach the model provider")

    monkeypatch.setattr(store, "_llm_extract_relations", must_not_call)
    assert store.seed_from_documentation(tmp_path) == 0
    assert _refusals(tmp_path)[-1]["target"] == "llm_seed"


# --- doctor -----------------------------------------------------------------


@pytest.fixture
def host(monkeypatch):
    """A host with FIPS mode on, the model pre-seeded and no daemon running."""
    state = {"fips": True, "model": True, "daemon": None}
    monkeypatch.setattr(
        "neuralmind.storage_guard.check_storage",
        lambda _p: StorageStatus(True, "LUKS", state["fips"], "encrypted"),
    )
    from neuralmind.onnx_embedder import OnnxMiniLMEmbedder

    monkeypatch.setattr(
        OnnxMiniLMEmbedder,
        "local_model_dir",
        lambda self: Path("/models") if state["model"] else None,
    )
    monkeypatch.setattr(doctor, "_running_daemon_exposure", lambda: state["daemon"])
    monkeypatch.delenv("NEURALMIND_LLM_SEED", raising=False)
    return state


def test_doctor_without_a_profile(tmp_path, host):
    check = doctor._check_security_profile(tmp_path)
    assert check.status == doctor.OK and check.detail.startswith("none")


def test_doctor_profile_holds(tmp_path, host):
    _config(tmp_path, CUI)
    check = doctor._check_security_profile(tmp_path)
    assert check.status == doctor.OK
    assert "profile: cui" in check.detail and "FIPS mode on" in check.detail


def test_doctor_fails_without_fips_mode(tmp_path, host):
    _config(tmp_path, CUI)
    host["fips"] = False
    check = doctor._check_security_profile(tmp_path)
    assert check.status == doctor.FAIL and "FIPS mode is off" in check.detail


def test_doctor_fails_on_a_contradiction(tmp_path, host):
    _config(tmp_path, CUI + "  identity: declared\n")
    assert doctor._check_security_profile(tmp_path).status == doctor.FAIL


@pytest.mark.parametrize(
    "change, needle",
    [
        (lambda h, mp: mp.setenv("NEURALMIND_LLM_SEED", "1"), "NEURALMIND_LLM_SEED=1"),
        (lambda h, mp: h.update(model=False), "first build downloads it"),
        (lambda h, mp: h.update(fips=None), "could not be determined"),
        (lambda h, mp: h.update(daemon="it listens on '0.0.0.0'"), "running daemon refuses"),
    ],
)
def test_doctor_warns(tmp_path, host, monkeypatch, change, needle):
    _config(tmp_path, CUI)
    change(host, monkeypatch)
    check = doctor._check_security_profile(tmp_path)
    assert check.status == doctor.WARN and needle in check.detail


def test_doctor_ignores_a_dead_daemon(tmp_path, monkeypatch):
    monkeypatch.setattr(daemon_mod, "read_discovery", lambda: {"pid": 0, "host": "0.0.0.0"})
    assert doctor._running_daemon_exposure() is None
