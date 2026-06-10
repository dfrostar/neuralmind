"""Tests for the local daemon (PRD 5).

Stdlib-only: a fake NeuralMind is injected into the registry so the daemon,
job manager, dispatch contract, discovery, client, and a real end-to-end HTTP
round-trip are all exercised without the embedding backend.
"""

from __future__ import annotations

import os
import threading
import time

import pytest

from neuralmind import daemon as daemon_mod
from neuralmind import daemon_client

# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #


class _FakeBudget:
    total = 123


class _FakeResult:
    budget = _FakeBudget()
    reduction_ratio = 6.5
    layers_used = ["L0", "L1"]
    context = "fake context"


class FakeMind:
    """Minimal NeuralMind stand-in; counts builds to prove warm reuse."""

    def __init__(self, project_path: str) -> None:
        self.project_path = project_path
        self.build_count = 0
        self.query_count = 0

    def build(self, force: bool = False) -> dict:
        self.build_count += 1
        return {"success": True, "project": self.project_path, "force": force}

    def query(self, question: str) -> _FakeResult:
        self.query_count += 1
        return _FakeResult()

    def search(self, query: str, n: int = 10) -> list[dict]:
        return [{"id": "n1", "metadata": {"source_file": "a.py"}, "score": 0.9}][:n]

    def get_stats(self) -> dict:
        return {"built": True, "project": self.project_path, "nodes": 42}


@pytest.fixture
def daemon_home(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_DAEMON_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def registry():
    minds: dict[str, FakeMind] = {}

    def factory(path: str) -> FakeMind:
        minds[path] = FakeMind(path)
        return minds[path]

    reg = daemon_mod.ProjectRegistry(mind_factory=factory)
    reg._created = minds  # type: ignore[attr-defined]
    return reg


def _ctx(registry):
    return daemon_mod.DaemonContext(registry=registry, jobs=daemon_mod.JobManager(), version="test")


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #


def test_discovery_round_trip(daemon_home):
    assert daemon_mod.read_discovery() is None
    daemon_mod.write_discovery({"host": "127.0.0.1", "port": 9, "pid": os.getpid()})
    got = daemon_mod.read_discovery()
    assert got["port"] == 9
    daemon_mod.clear_discovery()
    assert daemon_mod.read_discovery() is None


def test_connect_clears_stale_discovery_for_dead_pid(daemon_home):
    # A pid that is essentially never alive.
    daemon_mod.write_discovery({"host": "127.0.0.1", "port": 9, "pid": 2_000_000_000})
    assert daemon_client.connect() is None
    assert daemon_mod.read_discovery() is None  # cleaned up


def test_connect_none_when_no_discovery(daemon_home):
    assert daemon_client.connect() is None
    assert daemon_client.is_running() is False


# --------------------------------------------------------------------------- #
# Registry: warm cache + locks
# --------------------------------------------------------------------------- #


def test_registry_warm_reuse(registry, tmp_path):
    m1 = registry.get(str(tmp_path))
    m2 = registry.get(str(tmp_path))
    assert m1 is m2  # same instance reused


def test_registry_ensure_built_builds_once(registry, tmp_path):
    m = registry.ensure_built(str(tmp_path))
    registry.ensure_built(str(tmp_path))
    registry.ensure_built(str(tmp_path))
    assert m.build_count == 1  # built once, then warm
    assert registry.is_built(str(tmp_path))


def test_registry_lock_is_stable_and_reentrant(registry, tmp_path):
    lock = registry.lock_for(str(tmp_path))
    assert registry.lock_for(str(tmp_path)) is lock
    with lock:
        with lock:  # RLock — reentrant
            assert True


# --------------------------------------------------------------------------- #
# Job manager
# --------------------------------------------------------------------------- #


def test_job_runs_and_completes():
    jm = daemon_mod.JobManager()
    job = jm.submit("build", "/p", lambda: {"ok": True})
    for _ in range(50):
        if jm.get(job.id).status == daemon_mod.JOB_DONE:
            break
        time.sleep(0.02)
    done = jm.get(job.id)
    assert done.status == daemon_mod.JOB_DONE
    assert done.result == {"ok": True}


def test_job_captures_error():
    jm = daemon_mod.JobManager()

    def boom():
        raise ValueError("nope")

    job = jm.submit("build", "/p", boom)
    for _ in range(50):
        if jm.get(job.id).status in (daemon_mod.JOB_DONE, daemon_mod.JOB_ERROR):
            break
        time.sleep(0.02)
    failed = jm.get(job.id)
    assert failed.status == daemon_mod.JOB_ERROR
    assert "nope" in failed.error


# --------------------------------------------------------------------------- #
# Dispatch contract
# --------------------------------------------------------------------------- #


def test_dispatch_health(registry):
    status, payload = daemon_mod.dispatch(_ctx(registry), "GET", "/health", None)
    assert status == 200 and payload["ok"] is True and payload["version"] == "test"


def test_dispatch_query(registry, tmp_path):
    status, payload = daemon_mod.dispatch(
        _ctx(registry), "POST", "/query", {"project": str(tmp_path), "question": "how?"}
    )
    assert status == 200
    assert payload["tokens"] == 123
    assert payload["reduction_ratio"] == 6.5
    assert payload["context"] == "fake context"


def test_dispatch_query_missing_field(registry):
    status, payload = daemon_mod.dispatch(_ctx(registry), "POST", "/query", {"project": "/p"})
    assert status == 400 and "question" in payload["error"]


def test_dispatch_stats_via_query_string(registry, tmp_path):
    status, payload = daemon_mod.dispatch(_ctx(registry), "GET", f"/stats?project={tmp_path}", None)
    assert status == 200 and payload["nodes"] == 42


def test_dispatch_build_async_then_poll(registry, tmp_path):
    ctx = _ctx(registry)
    status, payload = daemon_mod.dispatch(ctx, "POST", "/build", {"project": str(tmp_path)})
    assert status == 202 and "job_id" in payload
    job_id = payload["job_id"]
    for _ in range(50):
        s, p = daemon_mod.dispatch(ctx, "GET", f"/jobs/{job_id}", None)
        if p["status"] == daemon_mod.JOB_DONE:
            break
        time.sleep(0.02)
    assert p["status"] == daemon_mod.JOB_DONE
    assert p["result"]["success"] is True


def test_dispatch_build_sync(registry, tmp_path):
    status, payload = daemon_mod.dispatch(
        _ctx(registry), "POST", "/build", {"project": str(tmp_path), "sync": True}
    )
    assert status == 200 and payload["success"] is True


def test_dispatch_unknown_route(registry):
    status, payload = daemon_mod.dispatch(_ctx(registry), "GET", "/nope", None)
    assert status == 404


def test_dispatch_validate_is_backend_free(registry, tmp_path):
    # No graph/index -> validate_project returns an actionable error, not a crash.
    status, payload = daemon_mod.dispatch(
        _ctx(registry), "POST", "/validate", {"project": str(tmp_path)}
    )
    assert status == 200
    assert payload.get("ok") is False  # no index yet
    assert "error" in payload


# --------------------------------------------------------------------------- #
# End-to-end over real HTTP (server thread + client)
# --------------------------------------------------------------------------- #


@pytest.fixture
def running_daemon(daemon_home, registry):
    """Start a real daemon on an ephemeral port in a thread; yield the client."""
    t = threading.Thread(
        target=daemon_mod.serve,
        kwargs={"host": "127.0.0.1", "port": 0, "auth": True, "registry": registry},
        daemon=True,
    )
    t.start()
    client = None
    for _ in range(200):  # up to ~20s — CI runners (esp. macOS) can be slow to bind
        client = daemon_client.connect()
        if client is not None:
            break
        time.sleep(0.1)
    assert client is not None, "daemon did not come up"
    yield client
    try:
        client.shutdown()
    except Exception:
        pass


def test_e2e_health_query_stats(running_daemon, tmp_path):
    health = running_daemon.health()
    assert health["ok"] is True

    out = running_daemon.query(str(tmp_path), "how does X work?")
    assert out["tokens"] == 123 and out["context"] == "fake context"

    stats = running_daemon.stats(str(tmp_path))
    assert stats["nodes"] == 42


def test_e2e_auth_rejected_without_token(running_daemon, daemon_home):
    info = daemon_mod.read_discovery()
    bad = daemon_client.DaemonClient({**info, "token": "wrong"})
    with pytest.raises(daemon_client.DaemonUnavailableError):
        bad.status()


def test_e2e_shutdown_clears_discovery(running_daemon, daemon_home):
    running_daemon.shutdown()
    for _ in range(50):
        if daemon_client.connect(ping=True) is None:
            break
        time.sleep(0.05)
    assert daemon_client.connect(ping=True) is None
