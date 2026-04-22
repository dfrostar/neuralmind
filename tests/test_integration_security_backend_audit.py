"""End-to-end coverage for backend switching, audit trail, and MCP enforcement."""

import json

from neuralmind.audit import AuditTrail
from neuralmind.core import NeuralMind
from neuralmind.mcp_security import _SECURITY_MANAGERS
from neuralmind.mcp_server import handle_tool_call


def _project_with_graph(tmp_path):
    project = tmp_path / "project"
    graph_dir = project / "graphify-out"
    graph_dir.mkdir(parents=True)
    graph = {
        "nodes": [
            {
                "id": "auth_1",
                "label": "authenticate_user",
                "file_type": "function",
                "source_file": "auth/handlers.py",
                "community": 1,
            },
            {
                "id": "db_1",
                "label": "create_user",
                "file_type": "function",
                "source_file": "users/crud.py",
                "community": 2,
            },
        ],
        "edges": [{"source": "auth_1", "target": "db_1", "type": "calls"}],
    }
    (graph_dir / "graph.json").write_text(json.dumps(graph), encoding="utf-8")
    (project / "neuralmind-backend.yaml").write_text("backend: in_memory\n", encoding="utf-8")
    return project


def test_end_to_end_backend_switching(tmp_path):
    project = _project_with_graph(tmp_path)
    mind = NeuralMind(str(project), backend_type="in_memory")
    build = mind.build()
    assert build["success"] is True
    switched = mind.switch_backend("in_memory")
    assert switched["success"] is True
    assert switched["backend"] == "in_memory"


def test_end_to_end_audit_trail_validation(tmp_path):
    project = _project_with_graph(tmp_path)
    mind = NeuralMind(str(project), backend_type="in_memory", hybrid_context=True)
    mind.build()
    mind.wakeup()
    mind.query("authentication flow")
    mind.search("user create")

    events = AuditTrail(project).read_events()
    actions = [event["action"] for event in events]
    assert "build" in actions
    assert "wakeup" in actions
    assert "query" in actions
    assert "search" in actions


def test_end_to_end_mcp_security_enforcement(tmp_path):
    project = _project_with_graph(tmp_path)
    _SECURITY_MANAGERS.clear()

    denied = json.loads(
        handle_tool_call(
            "neuralmind_build",
            {"project_path": str(project), "actor": "eve", "role": "reader"},
        )
    )
    assert "error" in denied
    assert "Access denied" in denied["error"]

    allowed = json.loads(
        handle_tool_call(
            "neuralmind_query",
            {
                "project_path": str(project),
                "question": "authentication",
                "actor": "alice",
                "role": "reader",
            },
        )
    )
    assert "context" in allowed
