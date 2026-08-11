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


class TestQueryRelevanceSidecar:
    """tool_query gains an opt-in structured relevance sidecar (v0.38.0)."""

    def _mock_mind(self):
        mind = MagicMock()
        result = MagicMock()
        result.context = "ctx"
        result.budget.total = 100
        result.reduction_ratio = 5.0
        result.layers_used = ["L0"]
        result.communities_loaded = [1]
        result.search_hits = 1
        result.top_search_hits = [
            {
                "id": "n1",
                "score": 0.8,
                "_synapse_boost": 0.0,
                "_synapse_recalled": False,
                "metadata": {"label": "f", "source_file": "a.py", "node_id": "n1"},
            }
        ]
        mind.query.return_value = result
        mind.embedder.get_file_nodes.return_value = []  # no line spans
        return mind

    def test_include_relevance_attaches_sidecar(self):
        from neuralmind.mcp_server import tool_query

        with patch("neuralmind.mcp_server.get_mind", return_value=self._mock_mind()):
            out = tool_query("/proj", "q", include_relevance=True)
        assert "relevance" in out
        assert out["relevance"]["version"] == 1
        node = out["relevance"]["files"]["a.py"]["nodes"][0]
        assert node["label"] == "f"
        assert node["score"] == 0.8

    def test_default_omits_sidecar(self):
        """Backward-compatible: no relevance key unless requested."""
        from neuralmind.mcp_server import tool_query

        with patch("neuralmind.mcp_server.get_mind", return_value=self._mock_mind()):
            out = tool_query("/proj", "q")
        assert "relevance" not in out

    def test_dispatch_threads_include_relevance(self, temp_project):
        """handle_tool_call forwards include_relevance from arguments.

        Uses a real project path (not a synthetic one) so the MCP security
        manager's filesystem check passes on a non-root CI runner — the
        dispatch, not security, is what's under test here.
        """
        with patch("neuralmind.mcp_server.get_mind", return_value=self._mock_mind()):
            raw = handle_tool_call(
                "neuralmind_query",
                {"project_path": str(temp_project), "question": "q", "include_relevance": True},
            )
        assert "relevance" in json.loads(raw)


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


class TestToolImpact:
    """Tests for tool_impact() — the friendlier-named blast-radius handler."""

    def test_handler_delegates_to_mind_impact(self, temp_project):
        """tool_impact is a thin pass-through to NeuralMind.impact()."""
        from neuralmind.mcp_server import tool_impact

        with patch("neuralmind.mcp_server.get_mind") as mock_get:
            mock_mind = MagicMock()
            mock_mind.impact.return_value = {
                "symbol": "hash_password",
                "depth": 1,
                "relations": ["calls", "implements", "imports_from", "inherits"],
                "resolution": "exact",
                "resolved_node": "node_2",
                "dependents": [
                    {"id": "node_1", "relation": "calls", "hop": 1, "depends_on": "node_2"}
                ],
                "count": 1,
            }
            mock_get.return_value = mock_mind

            result = tool_impact(str(temp_project), "hash_password", depth=1)

        assert result["resolution"] == "exact"
        assert result["count"] == 1
        mock_mind.impact.assert_called_once_with("hash_password", depth=1)

    def test_dispatcher_routes_to_handler(self, temp_project):
        """handle_tool_call routes neuralmind_impact to tool_impact.

        Admin-only by default (not in the 'builder'/'reader' RBAC sets),
        matching neuralmind_structural_neighbors/synapse_stats/next_likely.
        """
        with patch("neuralmind.mcp_server.tool_impact") as mock_tool:
            mock_tool.return_value = {"symbol": "x", "resolution": "none", "dependents": []}
            result = handle_tool_call(
                "neuralmind_impact",
                {
                    "project_path": str(temp_project),
                    "symbol": "x",
                    "depth": 2,
                    "role": "admin",
                },
            )
            data = json.loads(result)
            assert data == {"symbol": "x", "resolution": "none", "dependents": []}
            mock_tool.assert_called_once_with(str(temp_project), "x", 2)

    def test_dispatcher_denies_builder_role_by_default(self, temp_project):
        """'builder' role can't call neuralmind_impact without explicit policy extension."""
        result = handle_tool_call(
            "neuralmind_impact",
            {"project_path": str(temp_project), "symbol": "x"},
        )
        data = json.loads(result)
        assert data.get("code") == "security_denied"


class TestToolDefinitions:
    """Tests for the TOOLS constant."""

    def test_tools_list_has_expected_count(self):
        """TOOLS should define 21 tools: previous 20 + neuralmind_health."""
        from neuralmind.mcp_server import TOOLS

        assert len(TOOLS) == 21

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
            "neuralmind_savings",
            "neuralmind_skeleton",
            # v0.4.0 synapse layer
            "neuralmind_synaptic_neighbors",
            # v0.42.0 structural code-graph neighbors
            "neuralmind_structural_neighbors",
            # v0.51.0 structural gaps — bridge analysis + betweenness centrality
            "neuralmind_structural_gaps",
            # v0.47.0 friendlier-named, richer-output blast-radius lookup
            "neuralmind_impact",
            "neuralmind_synapse_stats",
            "neuralmind_synapse_decay",
            "neuralmind_export_synapse_memory",
            # v0.11.0 directional transitions
            "neuralmind_next_likely",
            # v0.38.0 explicit feedback loop
            "neuralmind_feedback",
            # co-break risk review
            "neuralmind_review",
            # v2.0 compliance saving report — live from daemon
            "neuralmind_compliance_report",
            # v1.12.0 document ingestion via MCP
            "neuralmind_ingest_document",
            # v3.1.3 health check endpoint
            "neuralmind_health",
        }
        assert tool_names == expected


class TestAsyncToolHandler:
    """Tests for async MCP tool handler — verifies fix for #363."""

    def test_sqlite_timeout_is_30s(self, tmp_path):
        """SynapseStore uses 30s SQLite busy timeout to prevent hangs under contention."""
        from neuralmind.synapses import SynapseStore

        store = SynapseStore(tmp_path / "test.db")
        with store._connect() as conn:
            # PRAGMA busy_timeout is in milliseconds
            row = conn.execute("PRAGMA busy_timeout").fetchone()
            assert row[0] == 30000, f"Expected 30000ms, got {row[0]}"
