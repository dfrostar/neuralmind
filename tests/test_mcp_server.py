"""Tests for neuralmind.mcp_server — MCP server tool handlers."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
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

    def test_include_relevance_attaches_sidecar(self, tmp_path):
        from neuralmind.mcp_server import tool_query

        # An absolute path on every OS: "/proj" is drive-relative on Windows,
        # where it passed only because another test's hook left C:\proj\.neuralmind.
        with patch("neuralmind.mcp_server.get_mind", return_value=self._mock_mind()):
            out = tool_query(str(tmp_path), "q", include_relevance=True)
        assert "relevance" in out
        assert out["relevance"]["version"] == 1
        node = out["relevance"]["files"]["a.py"]["nodes"][0]
        assert node["label"] == "f"
        assert node["score"] == 0.8

    def test_default_omits_sidecar(self, tmp_path):
        """Backward-compatible: no relevance key unless requested."""
        from neuralmind.mcp_server import tool_query

        with patch("neuralmind.mcp_server.get_mind", return_value=self._mock_mind()):
            out = tool_query(str(tmp_path), "q")
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


class TestErrorCodes:
    """Side finding 3: every RuntimeError, including a missing index, was
    reported as ``security_denied``. Only the security manager's own
    refusals are security denials now."""

    def test_missing_index_is_index_not_built(self, empty_project):
        """End to end, no mocks: a read-only query on a project with no index."""
        result = handle_tool_call(
            "neuralmind_query",
            {"project_path": str(empty_project), "question": "what is this?", "learn": False},
        )
        data = json.loads(result)
        assert data["code"] == "index_not_built"
        assert "neuralmind build" in data["error"]
        assert "neuralmind_build" in data["hint"]

    def test_graph_not_built_from_any_tool(self, temp_project):
        from neuralmind.core import GraphNotBuiltError

        with patch("neuralmind.mcp_server.get_mind", side_effect=GraphNotBuiltError("no graph")):
            data = json.loads(
                handle_tool_call("neuralmind_wakeup", {"project_path": str(temp_project)})
            )
        assert data["code"] == "index_not_built"
        assert data["error"] == "no graph"

    @pytest.mark.parametrize(
        "exc",
        [
            RuntimeError("tree-sitter grammar for 'go' is not installed"),
            PermissionError(13, "Permission denied", "/proj/secret.py"),
        ],
        ids=["tool-runtime-error", "os-permission-error"],
    )
    def test_tool_failure_is_not_a_security_denial(self, temp_project, exc):
        with patch("neuralmind.mcp_server.get_mind", side_effect=exc):
            data = json.loads(
                handle_tool_call("neuralmind_wakeup", {"project_path": str(temp_project)})
            )
        assert data.get("code") != "security_denied"
        assert str(exc) == data["error"]

    def test_rbac_denial_reason(self, temp_project):
        data = json.loads(
            handle_tool_call(
                "neuralmind_build", {"project_path": str(temp_project), "role": "reader"}
            )
        )
        assert data["code"] == "security_denied"
        assert data["reason"] == "rbac"

    def test_rate_limit_reason(self, temp_project):
        from neuralmind.mcp_security import MCPSecurityManager, RateLimiter

        _security_cache[str(Path(temp_project).resolve())] = MCPSecurityManager(
            str(temp_project), rate_limiter=RateLimiter(max_calls=1, window_seconds=60)
        )
        args = {"project_path": str(temp_project), "actor": "bob"}
        first = json.loads(handle_tool_call("neuralmind_stats", args))
        second = json.loads(handle_tool_call("neuralmind_stats", args))
        assert "code" not in first
        assert second["code"] == "security_denied"
        assert second["reason"] == "rate_limit"

    def test_security_roles_from_config_replace_the_default_policy(self, temp_project):
        """The Security Guide tells operators to cap what a caller can claim by
        leaving admin out of security.roles. The server used to build its
        security manager without reading the config, so a declared admin still
        got every tool."""
        (Path(temp_project) / "neuralmind-backend.yaml").write_text(
            "security:\n  roles:\n    builder: [neuralmind_stats]\n", encoding="utf-8"
        )
        base = {"project_path": str(temp_project)}
        as_admin = json.loads(handle_tool_call("neuralmind_stats", {**base, "role": "admin"}))
        assert as_admin["code"] == "security_denied"
        assert as_admin["reason"] == "rbac"
        as_default = json.loads(handle_tool_call("neuralmind_stats", base))
        assert as_default.get("code") != "security_denied", as_default

    def test_rate_limit_from_config_applies(self, temp_project):
        (Path(temp_project) / "neuralmind-backend.yaml").write_text(
            "security:\n  rate_limit:\n    max_calls: 1\n    window_seconds: 60\n",
            encoding="utf-8",
        )
        args = {"project_path": str(temp_project), "actor": "bob"}
        json.loads(handle_tool_call("neuralmind_stats", args))
        second = json.loads(handle_tool_call("neuralmind_stats", args))
        assert second["code"] == "security_denied"
        assert second["reason"] == "rate_limit"

    def _config(self, temp_project, text):
        (Path(temp_project) / "neuralmind-backend.yaml").write_text(text, encoding="utf-8")

    def test_an_empty_role_policy_grants_nothing(self, temp_project):
        """`roles: {}` used to read as "no policy" and restore the defaults,
        admin included. An explicit empty policy is a policy."""
        self._config(temp_project, "security:\n  roles: {}\n")
        base = {"project_path": str(temp_project)}
        for args in ({**base, "role": "admin"}, base):
            data = json.loads(handle_tool_call("neuralmind_stats", args))
            assert data["code"] == "security_denied", args
            assert data["reason"] == "rbac"

    @pytest.mark.parametrize(
        "body",
        [
            "security:\n  roles: [admin]\n",
            "security:\n  rate_limit: 60\n",
            "security:\n  rate_limit:\n    window_seconds: 0\n",
            "security:\n  rate_limit:\n    window_seconds: -5\n",
            "security:\n  rate_limit:\n    max_calls: lots\n",
            "security:\n  rate_limit:\n    max_calls: true\n",
            "security: open\n",
        ],
    )
    def test_a_malformed_policy_refuses_every_call(self, temp_project, body):
        """These used to crash every call (`rate_limit: 60`, a non-number),
        switch the limit off (a window of 0 or less), or fall back to the
        defaults (`roles` not a mapping)."""
        self._config(temp_project, body)
        data = json.loads(handle_tool_call("neuralmind_stats", {"project_path": str(temp_project)}))
        assert data["code"] == "security_denied", body
        assert data["reason"] == "config"
        assert "Refusing MCP calls" in data["error"]

    @pytest.mark.parametrize(
        "body",
        [
            # Doesn't parse: an unclosed flow list.
            "security:\n  roles:\n    builder: [neuralmind_stats\n",
            # Parses, but not to a mapping.
            "- security\n",
            # Empty keys, as when every entry under them is commented out.
            "security:\n",
            "security:\n  roles:\n  #  builder: [neuralmind_stats]\n",
        ],
    )
    def test_a_policy_that_does_not_parse_or_is_empty_refuses_every_call(self, temp_project, body):
        """Each of these used to restore the default policy, under which a
        caller declaring admin reaches every tool."""
        self._config(temp_project, body)
        args = {"project_path": str(temp_project), "role": "admin"}
        data = json.loads(handle_tool_call("neuralmind_stats", args))
        assert data["code"] == "security_denied", body
        assert data["reason"] == "config"
        assert "Refusing MCP calls" in data["error"]

    @pytest.mark.parametrize(
        "body",
        [
            "backend: [turbovec\n",
            # A comment that mentions a setting doesn't make it a policy.
            "backend: [turbovec\n# security is configured elsewhere\n",
            "backend: [turbovec  # roles live in another file\n",
        ],
    )
    def test_an_unparseable_file_that_names_no_policy_is_still_ignored(self, temp_project, body):
        """Only a file that names a security setting fails closed; a typo in
        backend tuning keeps the general loader's leniency."""
        self._config(temp_project, body)
        data = json.loads(handle_tool_call("neuralmind_stats", {"project_path": str(temp_project)}))
        assert "error" not in data, data

    def test_a_null_rate_limit_means_the_defaults(self, temp_project):
        self._config(temp_project, "security:\n  rate_limit: null\n")
        data = json.loads(handle_tool_call("neuralmind_stats", {"project_path": str(temp_project)}))
        # It used to raise AttributeError inside the dispatcher, which came
        # back as a bare {"error": ...} on every call.
        assert "error" not in data, data

    def test_unknown_decision_status_is_invalid_request(self, temp_project):
        """The status filter is case-insensitive, so its schema has no enum; an
        unknown value used to run inside the security manager and come back
        without a code, audited as a successful call. It is rejected up front
        now, like any other disallowed argument value."""
        args = {"project_path": str(temp_project), "query": "queue", "role": "admin"}
        with patch("neuralmind.mcp_server.get_security_manager") as security:
            data = json.loads(
                handle_tool_call("neuralmind_memory_search", {**args, "status": "archived"})
            )
        security.assert_not_called()
        assert data["code"] == "invalid_request"
        assert "'status'" in data["error"]
        assert "ALL" in data["error"]
        for word in ("all", "Stale"):
            data = json.loads(
                handle_tool_call("neuralmind_memory_search", {**args, "status": word})
            )
            assert "code" not in data, word
            assert data["count"] == 0, word


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

    def test_dispatcher_allows_builder_role_by_default(self, temp_project):
        """The default 'builder' role reaches neuralmind_next_likely. It was
        advertised but refused to every default role until v4.8.1."""
        with patch("neuralmind.mcp_server.tool_next_likely") as mock_tool:
            mock_tool.return_value = {"enabled": True, "from_node": "x", "next": []}
            result = handle_tool_call(
                "neuralmind_next_likely",
                {"project_path": str(temp_project), "from_node": "x"},
            )
        data = json.loads(result)
        assert data.get("code") != "security_denied"
        mock_tool.assert_called_once()


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

    def test_dispatcher_allows_builder_role_by_default(self, temp_project):
        """The default 'builder' role reaches neuralmind_impact (refused until v4.8.1)."""
        with patch("neuralmind.mcp_server.tool_impact") as mock_tool:
            mock_tool.return_value = {"symbol": "x", "resolution": "none", "dependents": []}
            result = handle_tool_call(
                "neuralmind_impact",
                {"project_path": str(temp_project), "symbol": "x"},
            )
        data = json.loads(result)
        assert data.get("code") != "security_denied"
        mock_tool.assert_called_once()


class TestToolDefinitions:
    """Tests for the TOOLS constant."""

    def test_tools_list_has_expected_count(self):
        """TOOLS should define 28 tools: 21 core + 4 memory-layer + 3 progressive-retrieval."""
        from neuralmind.mcp_server import TOOLS

        assert len(TOOLS) == 28

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
            # v4.0.0 decision memory layer
            "neuralmind_query_decisions",
            "neuralmind_audit_decisions",
            "neuralmind_record_decision",
            "neuralmind_invalidate_decision",
            # v4.3.0 progressive decision retrieval (3-layer)
            "neuralmind_memory_search",
            "neuralmind_memory_timeline",
            "neuralmind_memory_get",
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


class TestRunMcpServer:
    """Regression tests for MCP SDK compatibility."""

    def test_uses_constructor_handlers_when_decorator_api_is_absent(self):
        """Modern MCP SDKs register tool handlers via Server constructor callbacks."""
        from neuralmind import mcp_server

        created: dict[str, object] = {}

        class FakeServer:
            def __init__(self, name, on_list_tools=None, on_call_tool=None, **kwargs):
                created["name"] = name
                created["kwargs"] = {
                    "on_list_tools": on_list_tools,
                    "on_call_tool": on_call_tool,
                    **kwargs,
                }

            def create_initialization_options(self):
                return {"init": True}

            async def run(self, read_stream, write_stream, options):
                created["run"] = (read_stream, write_stream, options)

        class FakeStdioServer:
            async def __aenter__(self):
                return ("read-stream", "write-stream")

            async def __aexit__(self, exc_type, exc, tb):
                return False

        with (
            patch.object(mcp_server, "MCP_AVAILABLE", True),
            patch.object(mcp_server, "Server", FakeServer),
            patch.object(mcp_server, "stdio_server", lambda: FakeStdioServer()),
            patch.object(
                mcp_server, "handle_tool_call", return_value='{"ok": true}'
            ) as mock_handle,
        ):
            asyncio.run(mcp_server.run_mcp_server())
            kwargs = created["kwargs"]
            tools_result = asyncio.run(kwargs["on_list_tools"](None, None))
            params = SimpleNamespace(
                name="neuralmind_stats", arguments={"project_path": "/tmp/project"}
            )
            call_result = asyncio.run(kwargs["on_call_tool"](None, params))
            assert call_result.content[0].text == '{"ok": true}'
            mock_handle.assert_called_once_with(
                "neuralmind_stats", {"project_path": "/tmp/project"}
            )

        kwargs = created["kwargs"]
        assert created["name"] == "neuralmind"
        assert "on_list_tools" in kwargs
        assert "on_call_tool" in kwargs
        assert created["run"] == ("read-stream", "write-stream", {"init": True})
        assert [tool.name for tool in tools_result.tools] == [
            tool["name"] for tool in mcp_server.TOOLS
        ]

    def test_falls_back_to_legacy_decorators_when_server_signature_is_unavailable(self):
        """Uninspectable Server implementations should still take the legacy path."""
        from neuralmind import mcp_server

        created: dict[str, object] = {}

        class FakeLegacyServer:
            def __init__(self, name):
                created["name"] = name

            def list_tools(self):
                def decorator(fn):
                    created["list_tools_handler"] = fn
                    return fn

                return decorator

            def call_tool(self):
                def decorator(fn):
                    created["call_tool_handler"] = fn
                    return fn

                return decorator

            def create_initialization_options(self):
                return {"init": True}

            async def run(self, read_stream, write_stream, options):
                created["run"] = (read_stream, write_stream, options)

        class FakeStdioServer:
            async def __aenter__(self):
                return ("read-stream", "write-stream")

            async def __aexit__(self, exc_type, exc, tb):
                return False

        with (
            patch.object(mcp_server, "MCP_AVAILABLE", True),
            patch.object(mcp_server, "Server", FakeLegacyServer),
            patch.object(mcp_server, "stdio_server", lambda: FakeStdioServer()),
            patch(
                "neuralmind.mcp_server.inspect.signature", side_effect=ValueError("no signature")
            ),
        ):
            asyncio.run(mcp_server.run_mcp_server())

        assert created["name"] == "neuralmind"
        assert "list_tools_handler" in created
        assert "call_tool_handler" in created
        assert created["run"] == ("read-stream", "write-stream", {"init": True})


class TestRelativePathGuard:
    """The detached-host footgun guard on the four first-contact tools.

    Hosts that spawn the MCP server detached (Hermes-Agent, OpenClaw, Agent
    Zero, Claude Desktop) give it a working directory unrelated to any
    project, so ``project_path="."`` used to silently read — or worse,
    auto-build — whatever that directory was. Smoke-tested for real: stats
    returned a well-formed empty payload (0 nodes) for a built project.
    """

    def test_stats_dot_in_unindexed_cwd_hints(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        out = tool_stats(".")
        assert out["built"] is False
        assert "hint" in out
        assert str(tmp_path.resolve()) in out["hint"]
        assert "absolute project path" in out["hint"]

    def test_query_dot_in_unindexed_cwd_refuses_to_autobuild(self, tmp_path, monkeypatch):
        from neuralmind.mcp_server import tool_query

        monkeypatch.chdir(tmp_path)
        with pytest.raises(ValueError, match="absolute project path"):
            tool_query(".", "how does auth work?")
        # The refusal must have prevented the wrong-directory auto-build.
        assert not (tmp_path / ".neuralmind").exists()
        assert not (tmp_path / "graphify-out").exists()

    def test_wakeup_and_search_refuse_too(self, tmp_path, monkeypatch):
        from neuralmind.mcp_server import tool_search, tool_wakeup

        monkeypatch.chdir(tmp_path)
        with pytest.raises(ValueError, match="working directory"):
            tool_wakeup(".")
        with pytest.raises(ValueError, match="working directory"):
            tool_search(".", "AuthService")

    def test_relative_path_to_indexed_project_passes_through(self, tmp_path, monkeypatch):
        """Claude Code / Cursor style hosts, where cwd IS the project."""
        (tmp_path / ".neuralmind").mkdir()
        monkeypatch.chdir(tmp_path)
        out = tool_stats(".")
        assert "hint" not in out  # proceeded to the normal stats path

    def test_absolute_path_never_hints(self, tmp_path):
        out = tool_stats(str(tmp_path))
        assert "hint" not in out
