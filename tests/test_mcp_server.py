"""Tests for neuralmind.mcp_server — MCP server tool handlers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from neuralmind.mcp_server import (
    _mind_cache,
    get_mind,
    handle_tool_call,
    tool_build,
    tool_stats,
)


@pytest.fixture(autouse=True)
def clear_mind_cache():
    """Clear the module-level mind cache between tests."""
    _mind_cache.clear()
    yield
    _mind_cache.clear()


class TestGetMind:
    """Tests for get_mind() caching factory."""

    def test_creates_neuralmind_instance(self, temp_project):
        """get_mind returns a NeuralMind instance."""
        from neuralmind.core import NeuralMind

        mind = get_mind(str(temp_project), auto_build=False)
        assert isinstance(mind, NeuralMind)

    def test_caches_instance(self, temp_project):
        """Second call with same path returns cached instance."""
        mind1 = get_mind(str(temp_project), auto_build=False)
        mind2 = get_mind(str(temp_project), auto_build=False)
        assert mind1 is mind2

    def test_different_paths_different_instances(self, temp_project, empty_project):
        """Different project paths produce different instances."""
        mind1 = get_mind(str(temp_project), auto_build=False)
        mind2 = get_mind(str(empty_project), auto_build=False)
        assert mind1 is not mind2


class TestHandleToolCall:
    """Tests for handle_tool_call() dispatcher."""

    def test_unknown_tool_returns_error(self):
        """Unknown tool name returns JSON error."""
        result = handle_tool_call("neuralmind_nonexistent", {})
        data = json.loads(result)
        assert "error" in data
        assert "Unknown tool" in data["error"]

    def test_stats_tool_returns_json(self, temp_project):
        """neuralmind_stats returns valid JSON with expected keys."""
        result = handle_tool_call(
            "neuralmind_stats",
            {"project_path": str(temp_project), "role": "reader"},
        )
        data = json.loads(result)
        assert "project" in data

    def test_build_tool_returns_success(self, temp_project):
        """neuralmind_build returns build result."""
        with patch("neuralmind.mcp_server.NeuralMind") as mock_mind_cls:
            mock_instance = MagicMock()
            mock_instance.build.return_value = {"success": True, "nodes_total": 6}
            mock_mind_cls.return_value = mock_instance

            result = handle_tool_call(
                "neuralmind_build",
                {"project_path": str(temp_project), "role": "builder"},
            )
            data = json.loads(result)
            assert data.get("success") is True

    def test_project_path_is_required(self):
        """project_path is mandatory for all MCP tool calls."""
        result = handle_tool_call("neuralmind_query", {"question": "q"})
        data = json.loads(result)
        assert "error" in data
        assert "Missing required argument: project_path" in data["error"]

    def test_default_role_enforces_least_privilege(self, temp_project):
        """Default role is reader, so mutating tools are denied unless role is provided."""
        result = handle_tool_call(
            "neuralmind_build",
            {"project_path": str(temp_project)},
        )
        data = json.loads(result)
        assert "error" in data
        assert "Access denied" in data["error"]

    def test_tool_exception_returns_error(self):
        """Exceptions in tool handlers are caught and returned as error."""
        with patch("neuralmind.mcp_server.get_mind", side_effect=RuntimeError("test error")):
            result = handle_tool_call(
                "neuralmind_wakeup",
                {"project_path": "/nonexistent"},
            )
            data = json.loads(result)
            assert "error" in data

    def test_skeleton_tool_dispatches(self, temp_project):
        """neuralmind_skeleton calls tool_skeleton."""
        with patch("neuralmind.mcp_server.get_mind") as mock_get:
            mock_mind = MagicMock()
            mock_mind.skeleton.return_value = "# skeleton output"
            mock_get.return_value = mock_mind

            result = handle_tool_call(
                "neuralmind_skeleton",
                {"project_path": str(temp_project), "file_path": "foo.py"},
            )
            data = json.loads(result)
            assert data["file"] == "foo.py"
            assert data["indexed"] is True


class TestToolBuild:
    """Tests for tool_build()."""

    def test_clears_cache_on_build(self, temp_project):
        """tool_build clears the cache for the project path."""
        # Pre-populate cache
        abs_path = str(Path(temp_project).resolve())
        _mind_cache[abs_path] = MagicMock()

        with patch("neuralmind.mcp_server.NeuralMind") as mock_mind_cls:
            mock_instance = MagicMock()
            mock_instance.build.return_value = {"success": True}
            mock_mind_cls.return_value = mock_instance

            tool_build(str(temp_project), force=True)

        # After build, cache should have a fresh instance
        assert abs_path in _mind_cache


class TestToolStats:
    """Tests for tool_stats()."""

    def test_returns_project_name(self, temp_project):
        """tool_stats includes the project name."""
        result = tool_stats(str(temp_project))
        assert "project" in result

    def test_handles_exception(self, temp_project):
        """tool_stats returns error dict on failure."""
        with patch("neuralmind.mcp_server.get_mind") as mock_get:
            mock_mind = MagicMock()
            mock_mind.embedder.get_stats.side_effect = RuntimeError("db error")
            mock_get.return_value = mock_mind

            result = tool_stats(str(temp_project))
            assert result["built"] is False
            assert "error" in result


class TestToolDefinitions:
    """Tests for the TOOLS constant."""

    def test_tools_list_has_expected_count(self):
        """TOOLS should define 7 tools."""
        from neuralmind.mcp_server import TOOLS

        assert len(TOOLS) == 7

    def test_each_tool_has_required_fields(self):
        """Every tool definition has name, description, and inputSchema."""
        from neuralmind.mcp_server import TOOLS

        for tool in TOOLS:
            assert "name" in tool, f"Tool missing name: {tool}"
            assert "description" in tool, f"Tool {tool['name']} missing description"
            assert "inputSchema" in tool, f"Tool {tool['name']} missing inputSchema"
            assert "properties" in tool["inputSchema"]
            assert "required" in tool["inputSchema"]

    def test_tool_names_match_handlers(self):
        """All TOOLS names correspond to handlers in handle_tool_call."""
        from neuralmind.mcp_server import TOOLS

        tool_names = {t["name"] for t in TOOLS}
        expected = {
            "neuralmind_wakeup",
            "neuralmind_query",
            "neuralmind_search",
            "neuralmind_build",
            "neuralmind_stats",
            "neuralmind_benchmark",
            "neuralmind_skeleton",
        }
        assert tool_names == expected
