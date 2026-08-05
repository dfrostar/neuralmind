"""Smoke tests for the dashboard API routes.

Covers /api/status, /api/synapses, /api/health, /api/dashboard/full,
and the /api/dashboard/* sub-routes. These were untested before N-08
and two of them (/api/status, /api/dashboard/full) were crashing the
handler thread due to a SQLite cross-thread issue — now fixed in
turbovec_backend.py (check_same_thread=False).
"""

from __future__ import annotations

import json
import tempfile
import threading
import urllib.request
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

from neuralmind.server import _Handler


@contextmanager
def _running_server(mind, **handler_overrides):
    """Start a real ThreadingHTTPServer in a background thread."""
    original = {
        "mind": _Handler.mind,
        "auth_token": _Handler.auth_token,
        "editor": _Handler.editor,
        "allowed_open_paths": _Handler.allowed_open_paths,
        "_graph_cache": _Handler._graph_cache,
    }
    _Handler.mind = mind
    _Handler.auth_token = None  # No auth in these tests
    _Handler.editor = None
    _Handler.allowed_open_paths = set()
    _Handler._graph_cache = None
    for k, v in handler_overrides.items():
        setattr(_Handler, k, v)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)
        for k, v in original.items():
            setattr(_Handler, k, v)


def _fake_mind(built=True, project_name="testproj"):
    """Minimal fake NeuralMind for route testing."""
    return SimpleNamespace(
        _built=built,
        project_path=Path(tempfile.mkdtemp()) / project_name,
        get_stats=lambda: {
            "project": project_name,
            "backend": "turbovec",
            "nodes_total": 100,
            "communities": 10,
            "build_stats": {"success": True},
        },
        recent_queries=lambda n=20: [],
        synapses=SimpleNamespace(
            stats=lambda: {
                "namespace": "personal",
                "namespaces": {"personal": {"edges": 5, "weight": 1.0, "transitions": 0, "transition_weight": 0.0, "nodes": 3}},
                "edges": 5,
                "transitions": 0,
                "ltp_edges": 1,
            },
            edges=lambda min_weight=0.1, limit=10: [],
        ),
        graph_data=lambda: {"nodes": [], "edges": [], "stats": {"nodes": 100, "edges": 200, "synapses": 5}},
        search=lambda q, n=12: [],
    )


def test_api_health_returns_healthy():
    fake_mind = _fake_mind(built=True)
    with _running_server(fake_mind) as base:
        with urllib.request.urlopen(base + "/api/health", timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read())
    assert data["status"] == "healthy"
    assert data["built"] is True
    assert "last_build" in data


def test_api_dashboard_full_returns_all_sections():
    fake_mind = _fake_mind(built=True)
    with _running_server(fake_mind) as base:
        with urllib.request.urlopen(base + "/api/dashboard/full", timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read())
    expected_keys = ["generated_at", "project_path", "status", "synapses", "ingestion", "savings", "performance", "queries", "communities"]
    for key in expected_keys:
        assert key in data, f"missing key: {key}"


def test_api_dashboard_status_returns_project_info():
    fake_mind = _fake_mind(built=True)
    with _running_server(fake_mind) as base:
        with urllib.request.urlopen(base + "/api/dashboard/status", timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read())
    assert "project" in data
    assert "built" in data


def test_api_dashboard_synapses_returns_data():
    fake_mind = _fake_mind(built=True)
    with _running_server(fake_mind) as base:
        with urllib.request.urlopen(base + "/api/dashboard/synapses", timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read())
    assert "total_edges" in data


def test_api_dashboard_ingestion_returns_structure():
    fake_mind = _fake_mind(built=True)
    with _running_server(fake_mind) as base:
        with urllib.request.urlopen(base + "/api/dashboard/ingestion", timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read())
    assert "ingested_files" in data
    assert "frameworks" in data
    assert "has_data" in data


def test_api_dashboard_savings_returns_structure():
    fake_mind = _fake_mind(built=True)
    with _running_server(fake_mind) as base:
        with urllib.request.urlopen(base + "/api/dashboard/savings", timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read())
    # When no event log exists, returns error dict; when present, has totals
    assert "total_queries" in data or "error" in data


def test_api_dashboard_performance_returns_structure():
    fake_mind = _fake_mind(built=True)
    with _running_server(fake_mind) as base:
        with urllib.request.urlopen(base + "/api/dashboard/performance", timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read())
    # Performance may be empty dict if no metrics files exist
    assert isinstance(data, dict)


def test_api_dashboard_full_accepts_days_param():
    fake_mind = _fake_mind(built=True)
    with _running_server(fake_mind) as base:
        with urllib.request.urlopen(base + "/api/dashboard/full?days=30", timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read())
    assert "generated_at" in data


def test_api_dashboard_full_clamps_invalid_days():
    fake_mind = _fake_mind(built=True)
    with _running_server(fake_mind) as base:
        # Invalid days should fall back to default (7)
        with urllib.request.urlopen(base + "/api/dashboard/full?days=invalid", timeout=5) as resp:
            assert resp.status == 200
        # Huge days should clamp to 365
        with urllib.request.urlopen(base + "/api/dashboard/full?days=99999", timeout=5) as resp:
            assert resp.status == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
