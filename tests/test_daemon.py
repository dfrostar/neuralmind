"""Tests for the local daemon (PRD 5).

Stdlib-only: a fake NeuralMind is injected into the registry so the daemon,
job manager, dispatch contract, discovery, client, and a real end-to-end HTTP
round-trip are all exercised without the embedding backend.
"""

from __future__ import annotations

import http.client
import json
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

    def query(self, question: str, trace: bool = False, trace_verbose: bool = False) -> _FakeResult:
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


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
def test_write_discovery_is_owner_only(daemon_home):
    """The discovery file holds the bearer token — it must be owner-only (0600)."""
    import stat

    path = daemon_mod.write_discovery(
        {"host": "127.0.0.1", "port": 9, "token": "secret", "pid": os.getpid()}
    )
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600, f"token file mode {oct(mode)} is not 0600"


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


def test_build_marks_built_under_lock(registry, tmp_path):
    """A sync build records built-state (inside the lock) so a later
    ensure_built is a no-op rather than a redundant rebuild."""
    ctx = _ctx(registry)
    daemon_mod.dispatch(ctx, "POST", "/build", {"project": str(tmp_path), "sync": True})
    assert registry.is_built(str(tmp_path))
    mind = registry.get(str(tmp_path))
    registry.ensure_built(str(tmp_path))  # must NOT rebuild
    assert mind.build_count == 1


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
    """Start a real daemon on an ephemeral port and yield a connected client.

    Uses create_server so the socket is bound + listening (and discovery is
    written) *before* the serving thread starts — no startup race — and so the
    test owns shutdown deterministically (no leaked daemon threads clobbering
    later tests).
    """
    httpd, info = daemon_mod.create_server(host="127.0.0.1", port=0, auth=True, registry=registry)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        client = None
        for _ in range(100):  # socket is already listening; this is near-instant
            client = daemon_client.connect()
            if client is not None:
                break
            time.sleep(0.05)
        assert client is not None, "daemon did not come up"
        yield client
    finally:
        httpd.shutdown()
        httpd.server_close()
        daemon_mod.clear_discovery()
        t.join(timeout=5)


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


# --------------------------------------------------------------------------- #
# Malformed requests over real HTTP
# --------------------------------------------------------------------------- #


def _raw_request(method, path, *, headers=None, body=None, auth=True):
    """Send a hand-built request to the running daemon.

    ``http.client.putrequest`` lets a test send headers no well-behaved client
    would (a non-numeric Content-Length, a non-ASCII token). Returns
    ``(status, payload)``; a daemon that drops the connection without a
    response raises ``http.client.RemoteDisconnected`` here.
    """
    info = daemon_mod.read_discovery()
    conn = http.client.HTTPConnection(info["host"], info["port"], timeout=5)
    try:
        conn.putrequest(method, path, skip_accept_encoding=True)
        if auth:
            conn.putheader("Authorization", f"Bearer {info['token']}")
        for key, value in (headers or {}).items():
            conn.putheader(key, value)
        conn.endheaders(body)
        resp = conn.getresponse()
        return resp.status, json.loads(resp.read() or b"null")
    finally:
        conn.close()


@pytest.mark.parametrize("length", ["abc", "-5", "1.5", "+3", "1_0"])
def test_e2e_malformed_content_length_gets_400(running_daemon, length):
    # No body follows: the daemon must answer from the header alone instead of
    # raising inside the handler (which dropped the connection unanswered).
    status, payload = _raw_request("POST", "/query", headers={"Content-Length": length})
    assert status == 400
    assert "Content-Length" in payload["error"]
    assert running_daemon.health()["ok"] is True  # still serving


@pytest.mark.parametrize(
    "length",
    # 5,000 digits is over int()'s 4,300-digit limit but within a header line.
    [str(daemon_mod.MAX_BODY_BYTES + 1), "99999999999999999999", "9" * 5000],
    ids=["limit-plus-one", "20-digits", "5000-digits"],
)
def test_e2e_oversized_content_length_gets_413(running_daemon, length):
    # Answered from the header alone: the daemon neither waits for a body that
    # never arrives nor tries to allocate one this size.
    status, payload = _raw_request("POST", "/query", headers={"Content-Length": length})
    assert status == 413
    assert "too large" in payload["error"]
    assert running_daemon.health()["ok"] is True


def _post_json(path, raw: bytes):
    return _raw_request(
        "POST",
        path,
        headers={"Content-Type": "application/json", "Content-Length": str(len(raw))},
        body=raw,
    )


@pytest.mark.parametrize(
    "raw, kind", [(b"[]", "array"), (b'"x"', "string"), (b"3", "number"), (b"null", "null")]
)
def test_e2e_non_object_json_body_gets_400(running_daemon, raw, kind):
    status, payload = _post_json("/search", raw)
    assert status == 400
    assert "JSON object" in payload["error"] and kind in payload["error"]


def test_e2e_invalid_json_body_gets_400(running_daemon):
    status, payload = _post_json("/search", b"{not json")
    assert status == 400 and "invalid JSON" in payload["error"]


def test_e2e_non_integer_search_n_gets_400(running_daemon, tmp_path):
    raw = json.dumps({"project": str(tmp_path), "query": "q", "n": "abc"}).encode()
    status, payload = _post_json("/search", raw)
    assert status == 400 and "'n'" in payload["error"]


def test_e2e_non_integer_queries_per_day_gets_400(running_daemon, tmp_path):
    status, payload = _raw_request("GET", f"/savings?project={tmp_path}&queries_per_day=abc")
    assert status == 400 and "queries_per_day" in payload["error"]


def test_dispatch_rejects_non_object_body(registry):
    status, payload = daemon_mod.dispatch(_ctx(registry), "POST", "/query", ["x"])
    assert status == 400 and "JSON object" in payload["error"]


@pytest.mark.parametrize("n", ["abc", "1.5", True, [3], {"n": 1}, 0, -2])
def test_dispatch_search_rejects_bad_n(registry, tmp_path, n):
    status, payload = daemon_mod.dispatch(
        _ctx(registry), "POST", "/search", {"project": str(tmp_path), "query": "q", "n": n}
    )
    assert status == 400 and "'n'" in payload["error"]


@pytest.mark.parametrize("n", [3, "3", 3.0])
def test_dispatch_search_accepts_integer_n(registry, tmp_path, n):
    status, payload = daemon_mod.dispatch(
        _ctx(registry), "POST", "/search", {"project": str(tmp_path), "query": "q", "n": n}
    )
    assert status == 200 and isinstance(payload["results"], list)


@pytest.mark.parametrize(
    "path, headers",
    [
        # parse_qs decodes %C3%A9 to "é"; compare_digest raised TypeError on a
        # non-ASCII str and the connection dropped with no response.
        ("/health?token=%C3%A9", {}),
        ("/health?token=%FF", {}),  # invalid UTF-8 -> U+FFFD
        # Header values are decoded as latin-1, so raw high bytes arrive as
        # non-ASCII str too.
        ("/health", {"Authorization": b"Bearer \xc3\xa9"}),
    ],
)
def test_e2e_non_ascii_token_gets_401(running_daemon, path, headers):
    status, payload = _raw_request("GET", path, headers=headers, auth=False)
    assert status == 401 and "token" in payload["error"]
    assert running_daemon.health()["ok"] is True  # the real token still works


def test_e2e_query_string_token_still_accepted(running_daemon):
    info = daemon_mod.read_discovery()
    status, payload = _raw_request("GET", f"/health?token={info['token']}", auth=False)
    assert status == 200 and payload["ok"] is True


@pytest.mark.parametrize("field", ["project", "question"])
def test_dispatch_rejects_non_string_required_field(registry, tmp_path, field):
    body = {"project": str(tmp_path), "question": "how?"}
    body[field] = ["not", "a", "string"]
    status, payload = daemon_mod.dispatch(_ctx(registry), "POST", "/query", body)
    assert status == 400 and field in payload["error"]


# --------------------------------------------------------------------------- #
# Flags and stalled clients
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "value, expected",
    [(None, False), (True, True), (False, False), (1, True), (0, False)]
    + [("true", True), ("FALSE", False), (" yes ", True), ("off", False), ("0", False)],
)
def test_bool_param_reads_flags(value, expected):
    assert daemon_mod._bool_param(value, "force", False) is expected


@pytest.mark.parametrize("value", ["maybe", 2, -1, 1.5, [True], {"x": 1}, ""])
def test_bool_param_rejects_non_flags(value):
    with pytest.raises(daemon_mod.DaemonError) as excinfo:
        daemon_mod._bool_param(value, "force", False)
    assert excinfo.value.status == 400 and "'force'" in excinfo.value.message


@pytest.mark.parametrize(
    "route, body",
    [
        ("/build", {"force": "maybe"}),
        ("/build", {"sync": [1]}),
        ("/validate", {"write": "sometimes"}),
        ("/query", {"question": "q", "trace": 7}),
    ],
)
def test_dispatch_rejects_a_flag_that_is_not_a_boolean(registry, tmp_path, route, body):
    status, payload = daemon_mod.dispatch(
        _ctx(registry), "POST", route, {"project": str(tmp_path), **body}
    )
    assert status == 400 and "must be a boolean" in payload["error"]


def test_dispatch_reads_a_false_string_as_false(registry, tmp_path, monkeypatch):
    # bool("false") is True, so {"write": "false"} used to write.
    seen = {}

    def fake_validate(ctx, project, write):
        seen["write"] = write
        return {"ok": True}

    monkeypatch.setattr(daemon_mod, "_validate", fake_validate)
    status, _ = daemon_mod.dispatch(
        _ctx(registry), "POST", "/validate", {"project": str(tmp_path), "write": "false"}
    )
    assert status == 200 and seen == {"write": False}


def test_e2e_stalled_body_times_out(running_daemon, monkeypatch):
    # A client that declares a body and never sends it no longer holds a
    # handler thread forever: the socket times out and the daemon closes it.
    import socket

    monkeypatch.setattr(daemon_mod._Handler, "timeout", 0.5)
    info = daemon_mod.read_discovery()
    with socket.create_connection((info["host"], info["port"]), timeout=10) as sock:
        sock.sendall(
            (
                "POST /query HTTP/1.1\r\nHost: x\r\n"
                f"Authorization: Bearer {info['token']}\r\n"
                "Content-Length: 10\r\n\r\n"
            ).encode()
        )
        started = time.monotonic()
        assert sock.recv(1024) == b""  # closed by the daemon, not by our 10s timeout
        assert time.monotonic() - started < 5
    assert running_daemon.health()["ok"] is True


def test_content_length_reads_a_long_zero_padded_value():
    # Leading zeros don't make a length large; only the digits after them count.
    from neuralmind.http_util import content_length

    assert content_length({"Content-Length": "0" * 5000 + "12"}) == 12
    assert content_length({"Content-Length": "0" * 5000}) == 0


def test_handler_has_a_request_timeout():
    # http.server's default is None: no timeout at all.
    assert daemon_mod._Handler.timeout == daemon_mod.REQUEST_TIMEOUT_SECONDS
    assert 0 < daemon_mod.REQUEST_TIMEOUT_SECONDS <= 120


def test_dispatch_answers_a_missing_project_with_404(tmp_path):
    # The real registry builds a real NeuralMind, which refuses a path that
    # doesn't exist; that's the client's mistake, not a daemon error (500).
    ctx = daemon_mod.DaemonContext(
        registry=daemon_mod.ProjectRegistry(), jobs=daemon_mod.JobManager(), version="test"
    )
    missing = tmp_path / "no-such-project"
    status, payload = daemon_mod.dispatch(
        ctx, "POST", "/query", {"project": str(missing), "question": "q"}
    )
    assert status == 404 and payload["code"] == "project_not_found"
    assert not missing.exists()


def test_async_build_of_a_missing_project_is_refused_before_queueing(tmp_path):
    # A sync build failed with 404, but an async one answered 202 with a job
    # id and only failed inside the job, so a client polling it saw an
    # accepted build of a project that doesn't exist.
    ctx = daemon_mod.DaemonContext(
        registry=daemon_mod.ProjectRegistry(), jobs=daemon_mod.JobManager(), version="test"
    )
    missing = tmp_path / "no-such-project"
    status, payload = daemon_mod.dispatch(ctx, "POST", "/build", {"project": str(missing)})
    assert status == 404 and payload["code"] == "project_not_found"
    assert ctx.jobs.list() == []
    assert not missing.exists()
