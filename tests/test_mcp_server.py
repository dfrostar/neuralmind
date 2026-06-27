"""Tests for neuralmind.mcp_server — MCP server tool handlers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from neuralmind.mcp_server import (
    _mind_cache,
    _security_cache,
    get_mind,
    handle_tool_call,
    tool_build,
    tool_stats,
)


@pytest.fixture(autouse=True)
def clear_mind_cache():
    """Clear the module-level mind cache between tests."""
    _mind_cache.clear()
    _security_cache.clear()
    yield
    _mind_cache.clear()
    _security_cache.clear()


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
            {"project_path": str(temp_project)},
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
                {"project_path": str(temp_project)},
            )
            data = json.loads(result)
            assert data.get("success") is True

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


class TestToolNextLikely:
    """Tests for tool_next_likely() — the v0.11.0 directional-transition handler."""

    def test_handler_returns_predicted_successors(self, temp_project):
        """tool_next_likely surfaces probabilities from SynapseStore.next_likely."""
        from neuralmind.mcp_server import tool_next_likely

        with patch("neuralmind.mcp_server.get_mind") as mock_get:
            mock_store = MagicMock()
            mock_store.next_likely.return_value = [
                ("tests/test_auth.py", 0.6),
                ("src/auth/middleware.py", 0.4),
            ]
            mock_mind = MagicMock()
            mock_mind.synapses = mock_store
            mock_get.return_value = mock_mind

            result = tool_next_likely(str(temp_project), "src/auth/handlers.py", top_k=2)

        assert result["enabled"] is True
        assert result["from_node"] == "src/auth/handlers.py"
        assert result["next"] == [
            {"to_node": "tests/test_auth.py", "probability": 0.6},
            {"to_node": "src/auth/middleware.py", "probability": 0.4},
        ]
        mock_store.next_likely.assert_called_once_with("src/auth/handlers.py", top_k=2)

    def test_handler_disabled_when_synapses_off(self, temp_project):
        """tool_next_likely returns enabled:False when the store is disabled."""
        from neuralmind.mcp_server import tool_next_likely

        with patch("neuralmind.mcp_server.get_mind") as mock_get:
            mock_mind = MagicMock()
            mock_mind.synapses = None
            mock_get.return_value = mock_mind

            result = tool_next_likely(str(temp_project), "anything.py")

        assert result == {"enabled": False, "from_node": "anything.py", "next": []}

    def test_handler_unknown_node_returns_empty_next(self, temp_project):
        """tool_next_likely with no recorded transitions returns enabled:True and empty next."""
        from neuralmind.mcp_server import tool_next_likely

        with patch("neuralmind.mcp_server.get_mind") as mock_get:
            mock_store = MagicMock()
            mock_store.next_likely.return_value = []
            mock_mind = MagicMock()
            mock_mind.synapses = mock_store
            mock_get.return_value = mock_mind

            result = tool_next_likely(str(temp_project), "unknown.py")

        assert result == {"enabled": True, "from_node": "unknown.py", "next": []}

    def test_dispatcher_routes_to_handler(self, temp_project):
        """handle_tool_call routes neuralmind_next_likely to tool_next_likely.

        The synapse-family tools default to admin-only per the RBAC policy
        (same as neuralmind_synapse_stats/decay/etc.), so this dispatcher
        test sets role='admin' explicitly. The default 'builder' role is
        denied by design.
        """
        with patch("neuralmind.mcp_server.tool_next_likely") as mock_tool:
            mock_tool.return_value = {"enabled": True, "from_node": "x", "next": []}
            result = handle_tool_call(
                "neuralmind_next_likely",
                {
                    "project_path": str(temp_project),
                    "from_node": "x",
                    "top_k": 3,
                    "role": "admin",
                },
            )
            data = json.loads(result)
            assert data == {"enabled": True, "from_node": "x", "next": []}
            mock_tool.assert_called_once_with(str(temp_project), "x", 3)

    def test_dispatcher_denies_builder_role_by_default(self, temp_project):
        """Confirm the synapse-family default: 'builder' role can't call
        neuralmind_next_likely. Matches the pre-existing behavior for
        neuralmind_synapse_stats/decay/synaptic_neighbors. If you want
        builders to call this tool, extend the role policy explicitly."""
        result = handle_tool_call(
            "neuralmind_next_likely",
            {"project_path": str(temp_project), "from_node": "x"},
        )
        data = json.loads(result)
        assert data.get("code") == "security_denied"


class TestToolDefinitions:
    """Tests for the TOOLS constant."""

    def test_tools_list_has_expected_count(self):
        """TOOLS should define 12 tools (7 retrieval + 4 v0.4 synapse +
        1 v0.11 directional-transition tool)."""
        from neuralmind.mcp_server import TOOLS

        assert len(TOOLS) == 13

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
            # v0.4.0 synapse layer
            "neuralmind_synaptic_neighbors",
            "neuralmind_synapse_stats",
            "neuralmind_synapse_decay",
            "neuralmind_export_synapse_memory",
            # v0.11.0 directional transitions
            "neuralmind_next_likely",
            # v0.38.0 explicit feedback loop
            "neuralmind_feedback",
        }
        assert tool_names == expected
