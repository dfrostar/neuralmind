"""Tests for NeuralMind MCP server helpers and dispatch."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import neuralmind.mcp_server as mcp_server


class TestGetMind:
    """Tests for cached mind retrieval."""

    def test_get_mind_caches_by_resolved_path(self, tmp_path, monkeypatch):
        created = []

        class FakeMind:
            def __init__(self, project_path):
                self.project_path = project_path
                self.build_calls = 0
                created.append(self)

            def build(self):
                self.build_calls += 1

        monkeypatch.setattr(mcp_server, "NeuralMind", FakeMind)
        mcp_server._mind_cache.clear()

        rel_path = tmp_path / "project"
        rel_path.mkdir()

        first = mcp_server.get_mind(str(rel_path), auto_build=True)
        second = mcp_server.get_mind(str(rel_path), auto_build=True)

        assert first is second
        assert len(created) == 1
        assert created[0].build_calls == 1

    def test_get_mind_skips_build_when_auto_build_false(self, tmp_path, monkeypatch):
        class FakeMind:
            def __init__(self, project_path):
                self.project_path = project_path
                self.build_calls = 0

            def build(self):
                self.build_calls += 1

        monkeypatch.setattr(mcp_server, "NeuralMind", FakeMind)
        mcp_server._mind_cache.clear()

        project = tmp_path / "project"
        project.mkdir()
        mind = mcp_server.get_mind(str(project), auto_build=False)

        assert isinstance(mind, FakeMind)
        assert mind.build_calls == 0


class TestToolFunctions:
    """Tests for MCP tool handlers."""

    def test_tool_wakeup_formats_response(self, monkeypatch):
        result = SimpleNamespace(
            context="ctx",
            budget=SimpleNamespace(total=321),
            reduction_ratio=12.34,
            layers_used=["L0:Identity", "L1:Summary"],
        )
        fake_mind = SimpleNamespace(wakeup=MagicMock(return_value=result))
        monkeypatch.setattr(mcp_server, "get_mind", lambda *_args, **_kwargs: fake_mind)

        out = mcp_server.tool_wakeup("/tmp/project")

        assert out["context"] == "ctx"
        assert out["tokens"] == 321
        assert out["reduction_ratio"] == 12.3
        assert out["layers"] == ["L0:Identity", "L1:Summary"]

    def test_tool_query_includes_search_fields(self, monkeypatch):
        result = SimpleNamespace(
            context="query ctx",
            budget=SimpleNamespace(total=111),
            reduction_ratio=7.88,
            layers_used=["L0:Identity", "L3:Search(2 results)"],
            communities_loaded=[1, 2],
            search_hits=2,
        )
        fake_mind = SimpleNamespace(query=MagicMock(return_value=result))
        monkeypatch.setattr(mcp_server, "get_mind", lambda *_args, **_kwargs: fake_mind)

        out = mcp_server.tool_query("/tmp/project", "auth?")

        assert out["context"] == "query ctx"
        assert out["tokens"] == 111
        assert out["reduction_ratio"] == 7.9
        assert out["communities_loaded"] == [1, 2]
        assert out["search_hits"] == 2

    def test_tool_search_formats_results(self, monkeypatch):
        fake_mind = SimpleNamespace(
            search=MagicMock(
                return_value=[
                    {
                        "id": "n1",
                        "metadata": {
                            "label": "auth",
                            "file_type": "function",
                            "source_file": "auth/handlers.py",
                        },
                        "score": 0.98765,
                    }
                ]
            )
        )
        monkeypatch.setattr(mcp_server, "get_mind", lambda *_args, **_kwargs: fake_mind)

        out = mcp_server.tool_search("/tmp/project", "auth", n=5)

        assert out == [
            {
                "id": "n1",
                "label": "auth",
                "file_type": "function",
                "source_file": "auth/handlers.py",
                "score": 0.988,
            }
        ]

    def test_tool_build_replaces_cache_entry(self, tmp_path, monkeypatch):
        build_result = {"success": True, "nodes_total": 2}

        class FakeMind:
            def __init__(self, project_path):
                self.project_path = project_path

            def build(self, force=False):
                assert force is True
                return build_result

        monkeypatch.setattr(mcp_server, "NeuralMind", FakeMind)
        mcp_server._mind_cache.clear()
        abs_path = str((tmp_path / "project").resolve())
        mcp_server._mind_cache[abs_path] = object()

        out = mcp_server.tool_build(abs_path, force=True)

        assert out == build_result
        assert isinstance(mcp_server._mind_cache[abs_path], FakeMind)

    def test_tool_stats_success(self, monkeypatch):
        fake_embedder = SimpleNamespace(get_stats=MagicMock(return_value={"total_nodes": 5}))
        fake_mind = SimpleNamespace(embedder=fake_embedder)
        monkeypatch.setattr(mcp_server, "get_mind", lambda *_args, **_kwargs: fake_mind)

        out = mcp_server.tool_stats("/tmp/myproj")

        assert out["project"] == "myproj"
        assert out["built"] is True
        assert out["total_nodes"] == 5

    def test_tool_stats_error(self, monkeypatch):
        fake_embedder = SimpleNamespace(get_stats=MagicMock(side_effect=RuntimeError("boom")))
        fake_mind = SimpleNamespace(embedder=fake_embedder)
        monkeypatch.setattr(mcp_server, "get_mind", lambda *_args, **_kwargs: fake_mind)

        out = mcp_server.tool_stats("/tmp/myproj")

        assert out["project"] == "myproj"
        assert out["built"] is False
        assert "boom" in out["error"]

    def test_tool_benchmark_passthrough(self, monkeypatch):
        fake_mind = SimpleNamespace(benchmark=MagicMock(return_value={"summary": "ok"}))
        monkeypatch.setattr(mcp_server, "get_mind", lambda *_args, **_kwargs: fake_mind)

        out = mcp_server.tool_benchmark("/tmp/project")

        assert out == {"summary": "ok"}


class TestHandleToolCall:
    """Tests for tool-call dispatch."""

    def test_handle_tool_call_unknown(self):
        payload = mcp_server.handle_tool_call("does_not_exist", {})
        assert "Unknown tool" in payload

    def test_handle_tool_call_returns_json(self, monkeypatch):
        monkeypatch.setattr(mcp_server, "tool_wakeup", lambda _project_path: {"ok": True})
        payload = mcp_server.handle_tool_call("neuralmind_wakeup", {"project_path": "/tmp/p"})
        assert '"ok": true' in payload.lower()

    def test_handle_tool_call_wraps_exceptions(self, monkeypatch):
        monkeypatch.setattr(
            mcp_server,
            "tool_wakeup",
            lambda _project_path: (_ for _ in ()).throw(RuntimeError("dispatch fail")),
        )
        payload = mcp_server.handle_tool_call("neuralmind_wakeup", {"project_path": "/tmp/p"})
        assert "dispatch fail" in payload


@pytest.mark.asyncio
async def test_run_mcp_server_exits_when_mcp_missing(monkeypatch):
    monkeypatch.setattr(mcp_server, "MCP_AVAILABLE", False)
    with pytest.raises(SystemExit):
        await mcp_server.run_mcp_server()


@pytest.mark.asyncio
async def test_run_mcp_server_runs_with_fake_sdk(monkeypatch):
    class FakeServer:
        instance = None

        def __init__(self, name):
            self.name = name
            self.tools_fn = None
            self.call_fn = None
            self.run_called = False
            self.run_args = None
            FakeServer.instance = self

        def list_tools(self):
            def decorator(fn):
                self.tools_fn = fn
                return fn

            return decorator

        def call_tool(self):
            def decorator(fn):
                self.call_fn = fn
                return fn

            return decorator

        def create_initialization_options(self):
            return {"opts": True}

        async def run(self, read_stream, write_stream, opts):
            self.run_called = True
            self.run_args = (read_stream, write_stream, opts)

    class FakeStdioContext:
        async def __aenter__(self):
            return ("read", "write")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(mcp_server, "MCP_AVAILABLE", True)
    monkeypatch.setattr(mcp_server, "Server", FakeServer)
    monkeypatch.setattr(mcp_server, "Tool", lambda **kwargs: kwargs)
    monkeypatch.setattr(mcp_server, "TextContent", lambda **kwargs: kwargs)
    monkeypatch.setattr(mcp_server, "stdio_server", lambda: FakeStdioContext())

    await mcp_server.run_mcp_server()

    assert FakeServer.instance is not None
    assert FakeServer.instance.run_called is True
    assert FakeServer.instance.run_args == ("read", "write", {"opts": True})


def test_main_uses_asyncio_run(monkeypatch):
    run_spy = MagicMock()
    monkeypatch.setattr("asyncio.run", run_spy)
    mcp_server.main()
    run_spy.assert_called_once()
