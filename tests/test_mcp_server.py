"""Tests for NeuralMind MCP server helpers."""

import json
from types import SimpleNamespace


class TestGetMindCache:
    """Tests for get_mind caching behavior."""

    def test_get_mind_caches_instances(self, temp_project, monkeypatch):
        """get_mind should reuse cached instance and build only once."""
        from neuralmind import mcp_server

        mcp_server._mind_cache.clear()

        class DummyMind:
            def __init__(self, _project_path):
                self.build_calls = 0

            def build(self):
                self.build_calls += 1

        monkeypatch.setattr(mcp_server, "NeuralMind", DummyMind)

        first = mcp_server.get_mind(str(temp_project), auto_build=True)
        second = mcp_server.get_mind(str(temp_project), auto_build=True)

        assert first is second
        assert first.build_calls == 1

    def test_get_mind_auto_build_false_does_not_build(self, temp_project, monkeypatch):
        """get_mind should skip build when auto_build=False."""
        from neuralmind import mcp_server

        mcp_server._mind_cache.clear()

        class DummyMind:
            def __init__(self, _project_path):
                self.build_calls = 0

            def build(self):
                self.build_calls += 1

        monkeypatch.setattr(mcp_server, "NeuralMind", DummyMind)
        mind = mcp_server.get_mind(str(temp_project), auto_build=False)
        assert mind.build_calls == 0


class TestMcpTools:
    """Tests for MCP tool helper functions."""

    def test_tool_wakeup_formats_payload(self, monkeypatch):
        """tool_wakeup should include expected response fields."""
        from neuralmind import mcp_server

        fake_result = SimpleNamespace(
            context="Wakeup context",
            budget=SimpleNamespace(total=555),
            reduction_ratio=23.48,
            layers_used=["L0:Identity", "L1:Summary"],
        )
        monkeypatch.setattr(
            mcp_server,
            "get_mind",
            lambda *_args, **_kwargs: SimpleNamespace(wakeup=lambda: fake_result),
        )

        payload = mcp_server.tool_wakeup("/tmp/project")
        assert payload["tokens"] == 555
        assert payload["reduction_ratio"] == 23.5
        assert "layers" in payload

    def test_tool_query_formats_payload(self, monkeypatch):
        """tool_query should include communities and hit metadata."""
        from neuralmind import mcp_server

        fake_result = SimpleNamespace(
            context="Query context",
            budget=SimpleNamespace(total=777),
            reduction_ratio=40.11,
            layers_used=["L0", "L1", "L2", "L3"],
            communities_loaded=[1, 2],
            search_hits=3,
        )
        monkeypatch.setattr(
            mcp_server,
            "get_mind",
            lambda *_args, **_kwargs: SimpleNamespace(query=lambda _q: fake_result),
        )

        payload = mcp_server.tool_query("/tmp/project", "auth")
        assert payload["tokens"] == 777
        assert payload["communities_loaded"] == [1, 2]
        assert payload["search_hits"] == 3

    def test_tool_search_rounds_scores(self, monkeypatch):
        """tool_search should round score values."""
        from neuralmind import mcp_server

        fake_results = [
            {
                "id": "node_1",
                "metadata": {
                    "label": "authenticate_user",
                    "file_type": "function",
                    "source_file": "a.py",
                },
                "score": 0.98765,
            }
        ]
        monkeypatch.setattr(
            mcp_server,
            "get_mind",
            lambda *_args, **_kwargs: SimpleNamespace(search=lambda _q, n=10: fake_results),
        )

        payload = mcp_server.tool_search("/tmp/project", "auth", n=1)
        assert payload[0]["score"] == 0.988

    def test_tool_build_replaces_cached_instance(self, temp_project, monkeypatch):
        """tool_build should clear stale cache and store rebuilt instance."""
        from neuralmind import mcp_server

        mcp_server._mind_cache.clear()
        abs_path = str(temp_project.resolve())
        mcp_server._mind_cache[abs_path] = object()

        class DummyMind:
            def __init__(self, _project_path):
                self.force_received = None

            def build(self, force=False):
                self.force_received = force
                return {"success": True, "force": force}

        monkeypatch.setattr(mcp_server, "NeuralMind", DummyMind)
        payload = mcp_server.tool_build(str(temp_project), force=True)

        assert payload["success"] is True
        assert isinstance(mcp_server._mind_cache[abs_path], DummyMind)
        assert mcp_server._mind_cache[abs_path].force_received is True

    def test_tool_stats_success_and_error(self, monkeypatch):
        """tool_stats should support both success and exception branches."""
        from neuralmind import mcp_server

        good_mind = SimpleNamespace(
            embedder=SimpleNamespace(get_stats=lambda: {"total_nodes": 5, "communities": 2})
        )
        monkeypatch.setattr(mcp_server, "get_mind", lambda *_args, **_kwargs: good_mind)
        ok = mcp_server.tool_stats("/tmp/project")
        assert ok["built"] is True

        bad_mind = SimpleNamespace(
            embedder=SimpleNamespace(
                get_stats=lambda: (_ for _ in ()).throw(RuntimeError("stats failed"))
            )
        )
        monkeypatch.setattr(mcp_server, "get_mind", lambda *_args, **_kwargs: bad_mind)
        err = mcp_server.tool_stats("/tmp/project")
        assert err["built"] is False
        assert err["error"] == "stats failed"


class TestHandleToolCall:
    """Tests for handle_tool_call dispatch and error handling."""

    def test_handle_tool_call_unknown_tool(self):
        """Unknown tools should return JSON error payload."""
        from neuralmind import mcp_server

        payload = json.loads(mcp_server.handle_tool_call("unknown_tool", {}))
        assert payload["error"].startswith("Unknown tool")

    def test_handle_tool_call_catches_handler_errors(self, monkeypatch):
        """Handler exceptions should be caught and returned as JSON errors."""
        from neuralmind import mcp_server

        monkeypatch.setattr(
            mcp_server,
            "tool_wakeup",
            lambda _project_path: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        payload = json.loads(
            mcp_server.handle_tool_call("neuralmind_wakeup", {"project_path": "/tmp/project"})
        )
        assert payload["error"] == "boom"
