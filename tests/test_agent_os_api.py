"""Tests for Agent OS HTTP route handlers (api.py).

Covers all 10 endpoints with happy path, auth, RBAC, and validation.
Route handlers are tested directly (no HTTP layer) for speed and isolation.
"""

from __future__ import annotations

import pytest

from neuralmind.agent_os import (
    ExperimentRunner,
    SignalDetector,
    TenantRegistry,
    create_agent_os_routes,
)


@pytest.fixture
def tmp_tenants(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_TENANTS_DIR", str(tmp_path))
    registry = TenantRegistry(tmp_path)
    return registry, tmp_path


@pytest.fixture
def routes(tmp_tenants):
    registry, _ = tmp_tenants
    signal_detector = SignalDetector()
    experiment_runner = ExperimentRunner()
    return create_agent_os_routes(registry, signal_detector, experiment_runner)


def _post(routes, path, body, **params):
    handler = routes.get(("POST", path))
    assert handler is not None
    return handler(body, **params)


def _get(routes, path, body=None, **params):
    handler = routes.get(("GET", path))
    assert handler is not None
    return handler(body, **params)


class TestCreateTenant:
    def test_happy_path(self, routes):
        status, payload = _post(routes, "/api/agent-os/tenants",
            {"tenant_id": "acme", "name": "Acme Corp", "admin_email": "alice"})
        assert status == 201
        assert payload["tenant_id"] == "acme"
        assert payload["name"] == "Acme Corp"
        # Email is lowercased by design in RoleAssignment.from_dict
        emails = [r["email"] for r in payload["rbac"]]
        assert "alice" in emails
        assert "admin" in [r["role"] for r in payload["rbac"]]

    def test_missing_admin_email(self, routes):
        status, payload = _post(routes, "/api/agent-os/tenants", {"tenant_id": "acme", "name": "Acme"})
        assert status == 400
        assert "admin_email" in payload["error"]

    def test_missing_tenant_id(self, routes):
        status, payload = _post(routes, "/api/agent-os/tenants", {"name": "Acme", "admin_email": "alice"})
        assert status == 400
        assert "tenant_id" in payload["error"]

    def test_invalid_tenant_id(self, routes):
        status, payload = _post(routes, "/api/agent-os/tenants",
            {"tenant_id": "Acme_Corp", "name": "Acme", "admin_email": "alice"})
        assert status == 500

    def test_duplicate_tenant(self, routes):
        _post(routes, "/api/agent-os/tenants", {"tenant_id": "acme", "name": "Acme", "admin_email": "alice"})
        status, payload = _post(routes, "/api/agent-os/tenants",
            {"tenant_id": "acme", "name": "Acme 2", "admin_email": "alice"})
        assert status == 500

    def test_with_projects(self, routes, tmp_path):
        proj = tmp_path / "project"
        proj.mkdir()
        status, payload = _post(routes, "/api/agent-os/tenants",
            {"tenant_id": "acme", "name": "Acme", "admin_email": "alice", "projects": [str(proj)]})
        assert status == 201
        assert len(payload["projects"]) == 1

    def test_default_tier(self, routes):
        status, payload = _post(routes, "/api/agent-os/tenants",
            {"tenant_id": "acme", "name": "Acme", "admin_email": "alice"})
        assert payload["tier"] == "free"


class TestListTenants:
    def test_empty(self, routes):
        status, payload = _get(routes, "/api/agent-os/tenants", {"email": "alice"})
        assert status == 200
        assert payload["tenants"] == []
        assert payload["count"] == 0

    def test_lists_accessible(self, routes):
        _post(routes, "/api/agent-os/tenants", {"tenant_id": "acme", "name": "Acme", "admin_email": "alice"})
        _post(routes, "/api/agent-os/tenants", {"tenant_id": "other", "name": "Other", "admin_email": "bob"})
        status, payload = _get(routes, "/api/agent-os/tenants", {"email": "alice"})
        assert status == 200
        assert payload["count"] == 1
        assert payload["tenants"][0]["tenant_id"] == "acme"

    def test_missing_email(self, routes):
        status, payload = _get(routes, "/api/agent-os/tenants", {})
        assert status == 401


class TestGetTenant:
    def test_happy_path(self, routes):
        _post(routes, "/api/agent-os/tenants", {"tenant_id": "acme", "name": "Acme", "admin_email": "alice"})
        status, payload = routes[("GET", "/api/agent-os/tenants/{tenant_id}")](
            {"email": "alice"}, tenant_id="acme")
        assert status == 200
        assert payload["tenant_id"] == "acme"

    def test_access_denied(self, routes):
        _post(routes, "/api/agent-os/tenants", {"tenant_id": "acme", "name": "Acme", "admin_email": "alice"})
        status, payload = routes[("GET", "/api/agent-os/tenants/{tenant_id}")](
            {"email": "bob"}, tenant_id="acme")
        assert status == 403

    def test_tenant_not_found(self, routes):
        status, payload = routes[("GET", "/api/agent-os/tenants/{tenant_id}")](
            {"email": "alice"}, tenant_id="ghost")
        assert status == 404

    def test_missing_email(self, routes):
        status, payload = routes[("GET", "/api/agent-os/tenants/{tenant_id}")]({}, tenant_id="acme")
        assert status == 401


class TestAddProject:
    def test_happy_path(self, routes, tmp_path):
        _post(routes, "/api/agent-os/tenants", {"tenant_id": "acme", "name": "Acme", "admin_email": "alice"})
        proj = tmp_path / "newproj"
        proj.mkdir()
        status, payload = routes[("POST", "/api/agent-os/tenants/{tenant_id}/projects")](
            {"email": "alice", "project_path": str(proj)}, tenant_id="acme")
        assert status == 200
        assert len(payload["projects"]) == 1

    def test_viewer_cannot_add(self, routes, tmp_path):
        _post(routes, "/api/agent-os/tenants", {"tenant_id": "acme", "name": "Acme", "admin_email": "alice"})
        routes[("POST", "/api/agent-os/tenants/{tenant_id}/rbac")](
            {"email": "alice", "target_email": "alice", "role": "viewer"}, tenant_id="acme")
        proj = tmp_path / "failproj"
        proj.mkdir()
        status, payload = routes[("POST", "/api/agent-os/tenants/{tenant_id}/projects")](
            {"email": "alice", "project_path": str(proj)}, tenant_id="acme")
        assert status == 403

    def test_missing_project_path(self, routes):
        _post(routes, "/api/agent-os/tenants", {"tenant_id": "acme", "name": "Acme", "admin_email": "alice"})
        status, payload = routes[("POST", "/api/agent-os/tenants/{tenant_id}/projects")](
            {"email": "alice"}, tenant_id="acme")
        assert status == 400


class TestDeleteTenant:
    def test_happy_path(self, routes):
        _post(routes, "/api/agent-os/tenants", {"tenant_id": "acme", "name": "Acme", "admin_email": "alice"})
        status, payload = routes[("DELETE", "/api/agent-os/tenants/{tenant_id}")](
            {"email": "alice"}, tenant_id="acme")
        assert status == 200
        assert payload["deleted"] == "acme"

    def test_viewer_cannot_delete(self, routes):
        _post(routes, "/api/agent-os/tenants", {"tenant_id": "acme", "name": "Acme", "admin_email": "alice"})
        routes[("POST", "/api/agent-os/tenants/{tenant_id}/rbac")](
            {"email": "alice", "target_email": "alice", "role": "viewer"}, tenant_id="acme")
        status, payload = routes[("DELETE", "/api/agent-os/tenants/{tenant_id}")](
            {"email": "alice"}, tenant_id="acme")
        assert status == 403

    def test_missing_email(self, routes):
        status, payload = routes[("DELETE", "/api/agent-os/tenants/{tenant_id}")]({}, tenant_id="acme")
        assert status == 401


class TestAssignRole:
    def test_happy_path(self, routes):
        _post(routes, "/api/agent-os/tenants", {"tenant_id": "acme", "name": "Acme", "admin_email": "alice"})
        status, payload = routes[("POST", "/api/agent-os/tenants/{tenant_id}/rbac")](
            {"email": "alice", "target_email": "alice", "role": "operator"}, tenant_id="acme")
        assert status == 200
        emails = [r["email"] for r in payload["rbac"]]
        assert "alice" in emails

    def test_viewer_cannot_assign(self, routes):
        _post(routes, "/api/agent-os/tenants", {"tenant_id": "acme", "name": "Acme", "admin_email": "alice"})
        routes[("POST", "/api/agent-os/tenants/{tenant_id}/rbac")](
            {"email": "alice", "target_email": "alice", "role": "viewer"}, tenant_id="acme")
        status, payload = routes[("POST", "/api/agent-os/tenants/{tenant_id}/rbac")](
            {"email": "alice", "target_email": "alice", "role": "admin"}, tenant_id="acme")
        assert status == 403

    def test_missing_target_email(self, routes):
        _post(routes, "/api/agent-os/tenants", {"tenant_id": "acme", "name": "Acme", "admin_email": "alice"})
        status, payload = routes[("POST", "/api/agent-os/tenants/{tenant_id}/rbac")](
            {"email": "alice", "role": "operator"}, tenant_id="acme")
        assert status == 400


class TestGetSignals:
    def test_happy_path(self, routes):
        _post(routes, "/api/agent-os/tenants", {"tenant_id": "acme", "name": "Acme", "admin_email": "alice"})
        routes[("POST", "/api/agent-os/signals")](
            {"tenant_id": "acme", "email": "alice", "metric_name": "latency", "value": 100.0})
        status, payload = _get(routes, "/api/agent-os/signals", {"tenant_id": "acme", "email": "alice"})
        assert status == 200
        assert payload["tracked_count"] == 1

    def test_viewer_can_view(self, routes):
        _post(routes, "/api/agent-os/tenants", {"tenant_id": "acme", "name": "Acme", "admin_email": "alice"})
        routes[("POST", "/api/agent-os/tenants/{tenant_id}/rbac")](
            {"email": "alice", "target_email": "alice", "role": "viewer"}, tenant_id="acme")
        status, payload = _get(routes, "/api/agent-os/signals", {"tenant_id": "acme", "email": "alice"})
        assert status == 200

    def test_missing_tenant_id(self, routes):
        status, payload = _get(routes, "/api/agent-os/signals", {"email": "alice"})
        assert status == 400


class TestPushSignal:
    def test_happy_path(self, routes):
        _post(routes, "/api/agent-os/tenants", {"tenant_id": "acme", "name": "Acme", "admin_email": "alice"})
        status, payload = _post(routes, "/api/agent-os/signals",
            {"tenant_id": "acme", "email": "alice", "metric_name": "latency", "value": 100.0})
        assert status == 200
        assert payload["metric"] == "latency"
        assert payload["value"] == 100.0

    def test_viewer_cannot_push(self, routes):
        _post(routes, "/api/agent-os/tenants", {"tenant_id": "acme", "name": "Acme", "admin_email": "alice"})
        routes[("POST", "/api/agent-os/tenants/{tenant_id}/rbac")](
            {"email": "alice", "target_email": "alice", "role": "viewer"}, tenant_id="acme")
        status, payload = _post(routes, "/api/agent-os/signals",
            {"tenant_id": "acme", "email": "alice", "metric_name": "latency", "value": 100.0})
        assert status == 403

    def test_missing_metric_name(self, routes):
        _post(routes, "/api/agent-os/tenants", {"tenant_id": "acme", "name": "Acme", "admin_email": "alice"})
        status, payload = _post(routes, "/api/agent-os/signals",
            {"tenant_id": "acme", "email": "alice", "value": 100.0})
        assert status == 400

    def test_invalid_value(self, routes):
        _post(routes, "/api/agent-os/tenants", {"tenant_id": "acme", "name": "Acme", "admin_email": "alice"})
        status, payload = _post(routes, "/api/agent-os/signals",
            {"tenant_id": "acme", "email": "alice", "metric_name": "latency", "value": "abc"})
        assert status == 400


class TestRunExperiment:
    def test_happy_path(self, routes):
        _post(routes, "/api/agent-os/tenants", {"tenant_id": "acme", "name": "Acme", "admin_email": "alice"})
        status, payload = _post(routes, "/api/agent-os/experiments",
            {"tenant_id": "acme", "email": "alice", "proposal_id": "p1",
             "metric_name": "latency_ms", "baseline_value": 100.0, "candidate_value": 90.0})
        assert status == 200
        assert payload["verdict"] in ("promoted", "rolled_back", "rejected")
        assert payload["delta"] != 0

    def test_viewer_cannot_run(self, routes):
        _post(routes, "/api/agent-os/tenants", {"tenant_id": "acme", "name": "Acme", "admin_email": "alice"})
        routes[("POST", "/api/agent-os/tenants/{tenant_id}/rbac")](
            {"email": "alice", "target_email": "alice", "role": "viewer"}, tenant_id="acme")
        status, payload = _post(routes, "/api/agent-os/experiments",
            {"tenant_id": "acme", "email": "alice", "proposal_id": "p1",
             "metric_name": "latency_ms", "baseline_value": 100.0, "candidate_value": 90.0})
        assert status == 403

    def test_missing_baseline(self, routes):
        _post(routes, "/api/agent-os/tenants", {"tenant_id": "acme", "name": "Acme", "admin_email": "alice"})
        status, payload = _post(routes, "/api/agent-os/experiments",
            {"tenant_id": "acme", "email": "alice", "proposal_id": "p1", "metric_name": "latency_ms"})
        assert status == 400


class TestListExperiments:
    def test_happy_path(self, routes):
        _post(routes, "/api/agent-os/tenants", {"tenant_id": "acme", "name": "Acme", "admin_email": "alice"})
        _post(routes, "/api/agent-os/experiments",
            {"tenant_id": "acme", "email": "alice", "proposal_id": "p1",
             "metric_name": "latency_ms", "baseline_value": 100.0, "candidate_value": 90.0})
        status, payload = _get(routes, "/api/agent-os/experiments", {"tenant_id": "acme", "email": "alice"})
        assert status == 200
        assert payload["count"] == 1

    def test_viewer_can_view(self, routes):
        _post(routes, "/api/agent-os/tenants", {"tenant_id": "acme", "name": "Acme", "admin_email": "alice"})
        routes[("POST", "/api/agent-os/tenants/{tenant_id}/rbac")](
            {"email": "alice", "target_email": "alice", "role": "viewer"}, tenant_id="acme")
        status, payload = _get(routes, "/api/agent-os/experiments", {"tenant_id": "acme", "email": "alice"})
        assert status == 200
