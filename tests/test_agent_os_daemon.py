"""Integration tests for Agent OS routes through the actual daemon HTTP layer."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

import pytest

import neuralmind.daemon as daemon_mod
import neuralmind.daemon_client as daemon_client_mod


@pytest.fixture
def daemon_home(tmp_path, monkeypatch):
    """Point all daemon state at a temp dir."""
    monkeypatch.setenv("NEURALMIND_DAEMON_HOME", str(tmp_path / "daemon"))
    monkeypatch.setenv("NEURALMIND_TENANTS_DIR", str(tmp_path / "tenants"))
    return tmp_path


@pytest.fixture
def fake_registry(tmp_path):
    """Create a registry with a pre-built fake mind."""
    minds = {}

    class FakeBudget:
        total = 100

    class FakeResult:
        budget = FakeBudget()
        reduction_ratio = 5.0
        layers_used = ["L0", "L1"]
        context = "fake context"

    class FakeMind:
        def __init__(self, project_path: str):
            self.project_path = project_path
            self.build_count = 0

        def build(self, force=False):
            self.build_count += 1
            return {"success": True, "project": self.project_path}

        def query(self, question, trace=False, trace_verbose=False):
            return FakeResult()

        def search(self, query, n=10):
            return [{"id": "n1", "score": 0.9}]

        def get_stats(self):
            return {"built": True, "project": self.project_path, "nodes": 10}

    def factory(path):
        minds[path] = FakeMind(path)
        return minds[path]

    reg = daemon_mod.ProjectRegistry(mind_factory=factory)
    reg._created = minds
    return reg


@pytest.fixture
def running_daemon(daemon_home, fake_registry):
    """Start a real daemon with Agent OS routes on an ephemeral port."""
    # Force fresh Agent OS routes so TenantRegistry reads the temp tenants dir
    if hasattr(daemon_mod._match_agent_os_route, "_routes"):
        delattr(daemon_mod._match_agent_os_route, "_routes")

    httpd, info = daemon_mod.create_server(
        host="127.0.0.1",
        port=0,
        auth=True,
        registry=fake_registry,
    )
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()

    client = None
    for _ in range(100):
        client = daemon_client_mod.connect()
        if client is not None:
            break
        time.sleep(0.05)

    assert client is not None, "Daemon failed to start"
    yield client, info

    httpd.shutdown()
    httpd.server_close()
    daemon_mod.clear_discovery()
    t.join(timeout=5)


def _create_tenant(host, port, token, tenant_id, name, admin_email):
    """Helper to create a tenant via HTTP."""
    req = urllib.request.Request(
        f"http://{host}:{port}/api/agent-os/tenants?token={token}",
        data=json.dumps({
            "tenant_id": tenant_id,
            "name": name,
            "admin_email": admin_email,
        }).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 201
        return json.loads(resp.read())


class TestAgentOSEndpoints:
    """Test Agent OS routes through actual HTTP requests."""

    def test_create_tenant(self, running_daemon):
        _, info = running_daemon
        token = info["token"]

        req = urllib.request.Request(
            f"http://{info['host']}:{info['port']}/api/agent-os/tenants?token={token}",
            data=json.dumps({
                "tenant_id": "testcorp",
                "name": "Test Corp",
                "admin_email": "alice",
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 201
            body = json.loads(resp.read())
            assert body["tenant_id"] == "testcorp"
            assert body["name"] == "Test Corp"

    def test_create_tenant_missing_auth(self, running_daemon):
        _, info = running_daemon
        req = urllib.request.Request(
            f"http://{info['host']}:{info['port']}/api/agent-os/tenants",
            data=json.dumps({
                "tenant_id": "testcorp",
                "name": "Test Corp",
                "admin_email": "alice",
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            raise AssertionError("Should have raised HTTPError")
        except urllib.error.HTTPError as e:
            assert e.code == 401

    def test_create_tenant_wrong_token(self, running_daemon):
        _, info = running_daemon
        req = urllib.request.Request(
            f"http://{info['host']}:{info['port']}/api/agent-os/tenants?token=wrong",
            data=json.dumps({
                "tenant_id": "testcorp",
                "name": "Test Corp",
                "admin_email": "alice",
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            raise AssertionError("Should have raised HTTPError")
        except urllib.error.HTTPError as e:
            assert e.code == 401

    def test_create_tenant_via_bearer_token(self, running_daemon):
        _, info = running_daemon
        token = info["token"]
        req = urllib.request.Request(
            f"http://{info['host']}:{info['port']}/api/agent-os/tenants",
            data=json.dumps({
                "tenant_id": "bearercorp",
                "name": "Bearer Corp",
                "admin_email": "alice",
            }).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 201
            body = json.loads(resp.read())
            assert body["tenant_id"] == "bearercorp"

    def test_list_tenants(self, running_daemon):
        _, info = running_daemon
        token = info["token"]

        req = urllib.request.Request(
            f"http://{info['host']}:{info['port']}/api/agent-os/tenants?token={token}",
            data=json.dumps({"email": "alice"}).encode(),
            headers={"Content-Type": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())
            assert isinstance(body["tenants"], list)
            assert body["count"] == 0

    def test_get_tenant_by_id(self, running_daemon):
        _, info = running_daemon
        token = info["token"]

        # Create tenant first
        _create_tenant(info['host'], info['port'], token, "getcorp", "Get Corp", "alice")

        # Get by ID using path parameter
        req = urllib.request.Request(
            f"http://{info['host']}:{info['port']}/api/agent-os/tenants/getcorp?token={token}",
            data=json.dumps({"email": "alice"}).encode(),
            headers={"Content-Type": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())
            assert body["tenant_id"] == "getcorp"

    def test_get_tenant_access_denied(self, running_daemon):
        _, info = running_daemon
        token = info["token"]

        # Create tenant with alice
        _create_tenant(info['host'], info['port'], token, "deniedcorp", "Denied Corp", "alice")

        # Try to access with bob (non-member) - should get 403
        req = urllib.request.Request(
            f"http://{info['host']}:{info['port']}/api/agent-os/tenants/deniedcorp?token={token}",
            data=json.dumps({"email": "bob"}).encode(),
            headers={"Content-Type": "application/json"},
            method="GET",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            # If we get here, the daemon returned 200, which means access was granted
            # This is a bug - but let's check the response to understand why
            raise AssertionError("Should have raised HTTPError")
        except urllib.error.HTTPError as e:
            assert e.code == 403

    def test_delete_tenant(self, running_daemon):
        _, info = running_daemon
        token = info["token"]

        # Create
        _create_tenant(info['host'], info['port'], token, "delcorp", "Delete Corp", "alice")

        # Delete
        req = urllib.request.Request(
            f"http://{info['host']}:{info['port']}/api/agent-os/tenants/delcorp?token={token}",
            data=json.dumps({"email": "alice"}).encode(),
            headers={"Content-Type": "application/json"},
            method="DELETE",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())
            assert body["deleted"] == "delcorp"

    def test_push_signal(self, running_daemon):
        _, info = running_daemon
        token = info["token"]

        # Create tenant first
        _create_tenant(info['host'], info['port'], token, "acme", "ACME Corp", "alice")

        req = urllib.request.Request(
            f"http://{info['host']}:{info['port']}/api/agent-os/signals?token={token}",
            data=json.dumps({
                "tenant_id": "acme",
                "email": "alice",
                "metric_name": "latency_ms",
                "value": 500.0,
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())
            assert body["metric"] == "latency_ms"
            assert body["value"] == 500.0

    def test_run_experiment(self, running_daemon):
        _, info = running_daemon
        token = info["token"]

        # Create tenant first
        _create_tenant(info['host'], info['port'], token, "acme", "ACME Corp", "alice")

        req = urllib.request.Request(
            f"http://{info['host']}:{info['port']}/api/agent-os/experiments?token={token}",
            data=json.dumps({
                "tenant_id": "acme",
                "email": "alice",
                "proposal_id": "p1",
                "metric_name": "latency_ms",
                "baseline_value": 100.0,
                "candidate_value": 85.0,
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())
            assert "verdict" in body
            assert body["delta"] != 0

    def test_assign_role(self, running_daemon):
        _, info = running_daemon
        token = info["token"]

        # Create tenant
        _create_tenant(info['host'], info['port'], token, "rbaccorp", "RBAC Corp", "alice")

        # Assign role
        req = urllib.request.Request(
            f"http://{info['host']}:{info['port']}/api/agent-os/tenants/rbaccorp/rbac?token={token}",
            data=json.dumps({
                "email": "alice",
                "target_email": "alice",
                "role": "viewer",
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())
            emails = [r["email"] for r in body["rbac"]]
            assert "alice" in emails

    def test_assign_role_viewer_forbidden(self, running_daemon):
        _, info = running_daemon
        token = info["token"]

        # Create tenant
        _create_tenant(info['host'], info['port'], token, "rbac2corp", "RBAC2 Corp", "alice")

        # Assign viewer role
        req = urllib.request.Request(
            f"http://{info['host']}:{info['port']}/api/agent-os/tenants/rbac2corp/rbac?token={token}",
            data=json.dumps({
                "email": "alice",
                "target_email": "alice",
                "role": "viewer",
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)

        # Try to assign another role as viewer
        req = urllib.request.Request(
            f"http://{info['host']}:{info['port']}/api/agent-os/tenants/rbac2corp/rbac?token={token}",
            data=json.dumps({
                "email": "alice",
                "target_email": "alice",
                "role": "admin",
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            raise AssertionError("Should have raised HTTPError")
        except urllib.error.HTTPError as e:
            assert e.code == 403

    def test_unknown_route(self, running_daemon):
        _, info = running_daemon
        req = urllib.request.Request(
            f"http://{info['host']}:{info['port']}/api/agent-os/unknown?token={info['token']}",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            raise AssertionError("Should have raised HTTPError")
        except urllib.error.HTTPError as e:
            assert e.code == 404

    def test_experiment_list(self, running_daemon):
        _, info = running_daemon
        token = info["token"]

        # Create tenant first
        _create_tenant(info['host'], info['port'], token, "acme", "ACME Corp", "alice")

        req = urllib.request.Request(
            f"http://{info['host']}:{info['port']}/api/agent-os/experiments?token={token}",
            data=json.dumps({
                "tenant_id": "acme",
                "email": "alice",
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())
            assert "experiments" in body

    def test_signals_list(self, running_daemon):
        _, info = running_daemon
        token = info["token"]

        # Create tenant first
        _create_tenant(info['host'], info['port'], token, "acme", "ACME Corp", "alice")

        req = urllib.request.Request(
            f"http://{info['host']}:{info['port']}/api/agent-os/signals?token={token}",
            data=json.dumps({
                "tenant_id": "acme",
                "email": "alice",
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())
            assert "metrics" in body
