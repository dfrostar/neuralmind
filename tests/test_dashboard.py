"""Tests for the NeuralMind dashboard data layer and HTTP routes."""

from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from neuralmind.dashboard import (
    communities,
    full_dashboard,
    ingestion_status,
    performance_summary,
    project_status,
    recent_queries,
    savings_summary,
    synapse_summary,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def empty_project(tmp_path):
    """A project directory with no .neuralmind state."""
    return tmp_path / "empty_project"


@pytest.fixture
def project_with_audit(tmp_path):
    """A project with audit_events.jsonl containing query events."""
    proj = tmp_path / "audited"
    proj.mkdir()
    nm_dir = proj / ".neuralmind"
    nm_dir.mkdir()

    events = [
        {
            "action": "query",
            "category": "audit",
            "status": "success",
            "target": "audited",
            "timestamp": "2026-08-01T10:00:00Z",
            "details": {
                "question": "How does auth work?",
                "tokens": 1200,
                "search_hits": 5,
            },
        },
        {
            "action": "query",
            "category": "audit",
            "status": "success",
            "target": "audited",
            "timestamp": "2026-08-01T11:00:00Z",
            "details": {
                "question": "Show me the database schema",
                "tokens": 800,
                "search_hits": 3,
            },
        },
        {
            "action": "ingest_cmmc",
            "category": "ingestion",
            "status": "success",
            "target": "audited",
            "timestamp": "2026-08-01T09:00:00Z",
            "details": {
                "source": "CMMC_2.0_Level2.md",
                "framework": "CMMC",
                "node_count": 1486,
            },
        },
        {
            "action": "ingest_document",
            "category": "ingestion",
            "status": "success",
            "target": "audited",
            "timestamp": "2026-08-01T09:30:00Z",
            "details": {
                "source": "SOX_requirements.pdf",
                "framework": "SOX",
                "node_count": 42,
            },
        },
    ]
    audit_file = nm_dir / "audit_events.jsonl"
    audit_file.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    return proj


@pytest.fixture
def project_with_recent_queries(tmp_path):
    """A project with recent_queries.jsonl replay log."""
    proj = tmp_path / "with_queries"
    proj.mkdir()
    nm_dir = proj / ".neuralmind"
    nm_dir.mkdir()

    queries = [
        {
            "query": "How does auth work?",
            "timestamp": "2026-08-01T10:00:00Z",
            "tokens": 1200,
            "reduction_ratio": 41.7,
        },
        {
            "query": "Show me the database schema",
            "timestamp": "2026-08-01T11:00:00Z",
            "tokens": 800,
            "reduction_ratio": 62.5,
        },
    ]
    rq_file = nm_dir / "recent_queries.jsonl"
    rq_file.write_text("\n".join(json.dumps(q) for q in queries), encoding="utf-8")
    return proj


@pytest.fixture
def project_with_synapses(tmp_path):
    """A project with a populated synapse store."""
    proj = tmp_path / "synapsed"
    proj.mkdir()
    nm_dir = proj / ".neuralmind"
    nm_dir.mkdir()

    from neuralmind.synapses import SynapseStore, default_db_path

    store = SynapseStore(default_db_path(proj), namespace="personal")
    store.reinforce(["node_a", "node_b", "node_c"], strength=1.0)
    store.reinforce(["node_a", "node_b"], strength=1.0)
    store.reinforce(["node_b", "node_c"], strength=1.0)
    return proj


@pytest.fixture
def project_with_metrics(tmp_path):
    """A project with query metrics JSONL files."""
    proj = tmp_path / "metrics"
    proj.mkdir()
    nm_dir = proj / ".neuralmind"
    nm_dir.mkdir()
    metrics_dir = nm_dir / "metrics"
    metrics_dir.mkdir()

    from neuralmind.metrics_pipeline import _day_key

    day = _day_key()
    records = [
        {
            "event": "query",
            "ts": time.time(),
            "session_id": "test-session",
            "query": "auth flow",
            "latency_ms": 8400.0,
            "retrieval_reuse_rate": 0.3,
            "tool_calls": 2,
            "tool_successes": 2,
            "tokens_used": 740,
            "synapses_activated": 5,
        },
        {
            "event": "query",
            "ts": time.time() - 3600,
            "session_id": "test-session",
            "query": "database schema",
            "latency_ms": 6200.0,
            "retrieval_reuse_rate": 0.5,
            "tool_calls": 1,
            "tool_successes": 1,
            "tokens_used": 520,
            "synapses_activated": 3,
        },
    ]
    metrics_file = metrics_dir / f"metrics_{day}.jsonl"
    metrics_file.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    return proj


# ---------------------------------------------------------------------------
# project_status
# ---------------------------------------------------------------------------


def test_project_status_empty(empty_project):
    result = project_status(project_path=empty_project)
    assert result["project"] == "empty_project"
    assert result["built"] is False
    assert result["nodes"] == 0
    assert result["backend"] == "unknown"


def test_project_status_with_mind():
    """project_status with a real NeuralMind instance (unbuilt)."""
    import tempfile

    from neuralmind.core import NeuralMind

    with tempfile.TemporaryDirectory() as tmp:
        mind = NeuralMind(tmp)
        try:
            result = project_status(mind=mind)
            assert result["built"] is False
            assert result["project"] == Path(tmp).name
        finally:
            mind.close()


# ---------------------------------------------------------------------------
# synapse_summary
# ---------------------------------------------------------------------------


def test_synapse_summary_empty(empty_project):
    result = synapse_summary(project_path=empty_project)
    assert result["total_edges"] == 0
    assert result["has_data"] is False
    assert result["namespace"] == "personal"


def test_synapse_summary_with_data(project_with_synapses):
    result = synapse_summary(project_path=project_with_synapses)
    assert result["total_edges"] == 3
    assert result["has_data"] is True
    assert len(result["top_edges"]) > 0


# ---------------------------------------------------------------------------
# ingestion_status
# ---------------------------------------------------------------------------


def test_ingestion_status_empty(empty_project):
    result = ingestion_status(project_path=empty_project)
    assert result["total_doc_nodes"] == 0
    assert result["frameworks"] == {}
    assert result["has_data"] is False


def test_ingestion_status_with_data(project_with_audit):
    result = ingestion_status(project_path=project_with_audit)
    assert result["total_doc_nodes"] == 1528  # 1486 + 42
    assert "CMMC" in result["frameworks"]
    assert "SOX" in result["frameworks"]
    assert result["frameworks"]["CMMC"] == 1486
    assert result["has_data"] is True
    assert len(result["ingested_files"]) == 2


# ---------------------------------------------------------------------------
# savings_summary
# ---------------------------------------------------------------------------


def test_savings_summary_empty(empty_project):
    result = savings_summary(project_path=empty_project)
    # No audit_events.jsonl → returns error
    assert "error" in result


def test_savings_summary_with_data(project_with_audit):
    result = savings_summary(project_path=project_with_audit)
    # compute_savings counts all non-wakeup events (queries + ingestions) as "queries"
    assert result["total_queries"] == 4  # 2 queries + 2 ingestions
    assert result["total_tokens_used"] == 2000  # 1200 + 800 (ingestions have 0 tokens)
    assert result["est_total_full_cost"] == 200_000  # 4 * 50K
    assert result["total_tokens_saved"] == 198_000


# ---------------------------------------------------------------------------
# performance_summary
# ---------------------------------------------------------------------------


def test_performance_summary_empty(empty_project):
    result = performance_summary(project_path=empty_project)
    assert result == {}  # no metrics dir


def test_performance_summary_with_data(project_with_metrics):
    result = performance_summary(project_path=project_with_metrics)
    assert result.get("n_events") == 2
    queries = result.get("queries", {})
    assert queries["n_queries"] == 2
    assert "mean_latency_ms" in queries
    assert "mean_tokens_used" in queries


# ---------------------------------------------------------------------------
# recent_queries
# ---------------------------------------------------------------------------


def test_recent_queries_empty(empty_project):
    result = recent_queries(project_path=empty_project)
    assert result == []


def test_recent_queries_with_data(project_with_recent_queries):
    result = recent_queries(project_path=project_with_recent_queries)
    assert len(result) == 2
    # newest first
    assert result[0]["query"] == "Show me the database schema"
    assert result[1]["query"] == "How does auth work?"


# ---------------------------------------------------------------------------
# communities
# ---------------------------------------------------------------------------


def test_communities_empty(empty_project):
    result = communities(project_path=empty_project)
    assert result == []


# ---------------------------------------------------------------------------
# full_dashboard
# ---------------------------------------------------------------------------


def test_full_dashboard_empty(empty_project):
    result = full_dashboard(project_path=empty_project)
    assert "generated_at" in result
    assert result["status"]["built"] is False
    assert result["synapses"]["total_edges"] == 0
    assert result["ingestion"]["has_data"] is False


def test_full_dashboard_populated(project_with_audit, project_with_metrics):
    """Merge audit + metrics data into one dashboard."""
    # Use the metrics project as base, add audit data
    proj = project_with_metrics
    nm_dir = proj / ".neuralmind"

    # Copy audit events into the metrics project
    events = [
        {
            "action": "query",
            "category": "audit",
            "status": "success",
            "target": "metrics",
            "timestamp": "2026-08-01T10:00:00Z",
            "details": {"question": "test", "tokens": 1000, "search_hits": 3},
        },
    ]
    audit_file = nm_dir / "audit_events.jsonl"
    audit_file.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")

    result = full_dashboard(project_path=proj)
    assert result["savings"]["total_queries"] == 1
    # performance_summary reads metrics JSONL (query events), not audit log
    assert result["performance"]["n_events"] == 2


# ---------------------------------------------------------------------------
# HTTP route tests (integration)
# ---------------------------------------------------------------------------


def test_dashboard_html_served(tmp_path):
    """Dashboard static files are served correctly."""
    import urllib.request
    from http.server import ThreadingHTTPServer

    from neuralmind.server import _Handler

    _Handler.mind = SimpleNamespace(
        project_path=tmp_path,
        _built=False,
        enable_synapses=False,
        _synapses=None,
        project_name=tmp_path.name,
        get_stats=lambda: {"built": False, "project": tmp_path.name},
    )
    _Handler.auth_token = None
    _Handler.editor = None
    _Handler.allowed_open_paths = set()
    _Handler._graph_cache = None

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    import threading

    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    try:
        port = httpd.server_address[1]
        base = f"http://127.0.0.1:{port}"

        # dashboard.html
        with urllib.request.urlopen(f"{base}/dashboard", timeout=5) as resp:
            assert resp.status == 200
            body = resp.read().decode("utf-8")
            assert "<title>NeuralMind" in body

        # dashboard.css
        with urllib.request.urlopen(f"{base}/dashboard.css", timeout=5) as resp:
            assert resp.status == 200

        # dashboard.js
        with urllib.request.urlopen(f"{base}/dashboard.js", timeout=5) as resp:
            assert resp.status == 200

        # /api/dashboard/full
        with urllib.request.urlopen(f"{base}/api/dashboard/full", timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read())
            assert "status" in data
            assert "synapses" in data
            assert "ingestion" in data
    finally:
        httpd.shutdown()
        thread.join(timeout=2.0)
        httpd.server_close()


def test_dashboard_api_requires_auth(tmp_path):
    """Dashboard endpoints require auth token when set."""
    import urllib.request
    from http.server import ThreadingHTTPServer

    from neuralmind.server import _Handler

    _Handler.mind = SimpleNamespace(
        project_path=tmp_path,
        _built=False,
        enable_synapses=False,
        _synapses=None,
        project_name=tmp_path.name,
        get_stats=lambda: {"built": False, "project": tmp_path.name},
    )
    _Handler.auth_token = "test-token"
    _Handler.editor = None
    _Handler.allowed_open_paths = set()
    _Handler._graph_cache = None

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    import threading

    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    try:
        port = httpd.server_address[1]
        base = f"http://127.0.0.1:{port}"

        # Without token → 401
        try:
            urllib.request.urlopen(f"{base}/api/dashboard/full", timeout=5)
            raise AssertionError("Should have raised")
        except urllib.error.HTTPError as e:
            assert e.code == 401

        # With token → 200
        with urllib.request.urlopen(
            f"{base}/api/dashboard/full?token=test-token", timeout=5
        ) as resp:
            assert resp.status == 200
    finally:
        httpd.shutdown()
        thread.join(timeout=2.0)
        httpd.server_close()
