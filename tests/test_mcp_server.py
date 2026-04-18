"""Tests for neuralmind.mcp_server."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock


def test_get_mind_caches_instance_and_builds_once(tmp_path, monkeypatch):
    from neuralmind import mcp_server

    project = tmp_path / "project"
    project.mkdir()
    fake_mind = MagicMock()
    neuralmind_ctor = MagicMock(return_value=fake_mind)
    monkeypatch.setattr(mcp_server, "NeuralMind", neuralmind_ctor)
    mcp_server._mind_cache.clear()

    first = mcp_server.get_mind(str(project), auto_build=True)
    second = mcp_server.get_mind(str(project), auto_build=True)

    assert first is second
    assert neuralmind_ctor.call_count == 1
    fake_mind.build.assert_called_once_with()


def test_get_mind_respects_auto_build_false(tmp_path, monkeypatch):
    from neuralmind import mcp_server

    project = tmp_path / "project"
    project.mkdir()
    fake_mind = MagicMock()
    monkeypatch.setattr(mcp_server, "NeuralMind", MagicMock(return_value=fake_mind))
    mcp_server._mind_cache.clear()

    _ = mcp_server.get_mind(str(project), auto_build=False)

    fake_mind.build.assert_not_called()


def test_tool_search_maps_and_rounds_fields(monkeypatch):
    from neuralmind import mcp_server

    fake_mind = MagicMock()
    fake_mind.search.return_value = [
        {
            "id": "node_1",
            "metadata": {
                "label": "authenticate_user",
                "file_type": "function",
                "source_file": "auth/handlers.py",
            },
            "score": 0.98765,
        }
    ]
    monkeypatch.setattr(mcp_server, "get_mind", lambda _project_path: fake_mind)

    result = mcp_server.tool_search("/tmp/project", "auth", n=5)

    assert result == [
        {
            "id": "node_1",
            "label": "authenticate_user",
            "file_type": "function",
            "source_file": "auth/handlers.py",
            "score": 0.988,
        }
    ]
    fake_mind.search.assert_called_once_with("auth", n=5)


def test_tool_build_clears_cache_and_replaces_instance(tmp_path, monkeypatch):
    from neuralmind import mcp_server

    project = tmp_path / "project"
    project.mkdir()
    abs_path = str(project.resolve())

    stale_mind = MagicMock()
    mcp_server._mind_cache.clear()
    mcp_server._mind_cache[abs_path] = stale_mind

    fresh_mind = MagicMock()
    fresh_mind.build.return_value = {"success": True}
    monkeypatch.setattr(mcp_server, "NeuralMind", MagicMock(return_value=fresh_mind))

    result = mcp_server.tool_build(str(project), force=True)

    assert result == {"success": True}
    fresh_mind.build.assert_called_once_with(force=True)
    assert mcp_server._mind_cache[abs_path] is fresh_mind


def test_tool_stats_success(monkeypatch):
    from neuralmind import mcp_server

    fake_mind = MagicMock()
    fake_mind.embedder.get_stats.return_value = {"total_nodes": 3, "communities": 2}
    monkeypatch.setattr(mcp_server, "get_mind", lambda _project_path, auto_build=False: fake_mind)

    stats = mcp_server.tool_stats("/tmp/my-project")

    assert stats["project"] == "my-project"
    assert stats["built"] is True
    assert stats["total_nodes"] == 3


def test_tool_stats_handles_errors(monkeypatch):
    from neuralmind import mcp_server

    fake_mind = MagicMock()
    fake_mind.embedder.get_stats.side_effect = RuntimeError("stats unavailable")
    monkeypatch.setattr(mcp_server, "get_mind", lambda _project_path, auto_build=False: fake_mind)

    stats = mcp_server.tool_stats("/tmp/my-project")

    assert stats["project"] == "my-project"
    assert stats["built"] is False
    assert stats["error"] == "stats unavailable"


def test_handle_tool_call_unknown_tool_returns_error_json():
    from neuralmind import mcp_server

    response = mcp_server.handle_tool_call("not_a_real_tool", {})

    assert json.loads(response) == {"error": "Unknown tool: not_a_real_tool"}


def test_handle_tool_call_dispatches_and_serializes(monkeypatch):
    from neuralmind import mcp_server

    monkeypatch.setattr(
        mcp_server,
        "tool_wakeup",
        lambda _project_path: {
            "context": "hi",
            "tokens": 123,
            "reduction_ratio": 5.5,
            "layers": ["L0", "L1"],
        },
    )

    response = mcp_server.handle_tool_call("neuralmind_wakeup", {"project_path": "/tmp/project"})
    data = json.loads(response)

    assert data["context"] == "hi"
    assert data["tokens"] == 123


def test_handle_tool_call_catches_handler_exceptions(monkeypatch):
    from neuralmind import mcp_server

    def _boom(_project_path, _question):
        raise RuntimeError("query failed")

    monkeypatch.setattr(mcp_server, "tool_query", _boom)

    response = mcp_server.handle_tool_call(
        "neuralmind_query",
        {"project_path": "/tmp/project", "question": "test"},
    )

    assert json.loads(response) == {"error": "query failed"}


def test_tool_wakeup_and_query_return_expected_projection(monkeypatch):
    from neuralmind import mcp_server

    wakeup_result = SimpleNamespace(
        context="wakeup context",
        budget=SimpleNamespace(total=100),
        reduction_ratio=6.66,
        layers_used=["L0", "L1"],
    )
    query_result = SimpleNamespace(
        context="query context",
        budget=SimpleNamespace(total=300),
        reduction_ratio=9.99,
        layers_used=["L0", "L1", "L2"],
        communities_loaded=[1, 2],
        search_hits=4,
    )

    fake_mind = MagicMock()
    fake_mind.wakeup.return_value = wakeup_result
    fake_mind.query.return_value = query_result
    monkeypatch.setattr(mcp_server, "get_mind", lambda _project_path: fake_mind)

    wakeup = mcp_server.tool_wakeup("/tmp/project")
    query = mcp_server.tool_query("/tmp/project", "How does auth work?")

    assert wakeup == {
        "context": "wakeup context",
        "tokens": 100,
        "reduction_ratio": 6.7,
        "layers": ["L0", "L1"],
    }
    assert query == {
        "context": "query context",
        "tokens": 300,
        "reduction_ratio": 10.0,
        "layers": ["L0", "L1", "L2"],
        "communities_loaded": [1, 2],
        "search_hits": 4,
    }
