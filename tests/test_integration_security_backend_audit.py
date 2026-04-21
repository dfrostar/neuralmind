"""Integration tests for backend switching, audit trail, and MCP security."""

from __future__ import annotations

import json

from neuralmind.core import NeuralMind
from neuralmind.mcp_server import _mind_cache, _security_cache, handle_tool_call


def test_end_to_end_backend_switching(temp_project, mock_chromadb):
    mind = NeuralMind(str(temp_project), backend_name="in_memory")
    stats = mind.build()
    assert stats["success"] is True
    assert mind.backend_name == "in_memory"

    switched = mind.switch_backend("graph", auto_build=True)
    assert switched == "graph"
    assert mind.backend_name == "graph"
    assert mind.get_stats()["built"] is True


def test_end_to_end_audit_trail_validation(temp_project):
    mind = NeuralMind(str(temp_project), backend_name="in_memory")
    mind.build()
    mind.wakeup()
    mind.query("authentication")
    mind.search("auth", n=2)

    events = mind.audit.list_events()
    actions = {e["action"] for e in events}
    assert "build" in actions
    assert "wakeup" in actions
    assert "query" in actions
    assert "search" in actions

    report = mind.audit.generate_nist_rmf_report()
    assert report["total_events"] >= 4
    assert "AU-2" in report["controls"]


def test_end_to_end_mcp_security(temp_project, mock_chromadb):
    _mind_cache.clear()
    _security_cache.clear()

    denied_raw = handle_tool_call(
        "neuralmind_build",
        {"project_path": str(temp_project), "actor": "bob", "role": "viewer"},
    )
    denied = json.loads(denied_raw)
    assert denied["code"] == "security_denied"

    allowed_raw = handle_tool_call(
        "neuralmind_stats",
        {"project_path": str(temp_project), "actor": "bob", "role": "viewer"},
    )
    allowed = json.loads(allowed_raw)
    assert "error" not in allowed or allowed.get("code") != "security_denied"
