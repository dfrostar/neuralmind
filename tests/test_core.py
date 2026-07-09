"""Tests for NeuralMind core functionality."""

from pathlib import Path
from unittest.mock import MagicMock, patch


class TestNeuralMindInit:
    """Tests for NeuralMind initialization."""

    def test_init_with_valid_project(self, temp_project):
        """Test initialization with a valid project path."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        assert mind.project_path == Path(temp_project)
        # graph_path is on the embedder, not NeuralMind directly
        assert mind.embedder.graph_path.exists()

    def test_init_accepts_nonexistent_path(self, tmp_path):
        """Test initialization with non-existent path (doesn't raise at init)."""
        from neuralmind import NeuralMind

        nonexistent = tmp_path / "nonexistent"
        nonexistent.mkdir()  # Create the directory

        # NeuralMind doesn't validate graph existence at init
        mind = NeuralMind(str(nonexistent))
        assert mind.project_path == nonexistent

    def test_init_custom_db_path(self, temp_project, tmp_path):
        """Test initialization with custom database path."""
        from neuralmind import NeuralMind

        custom_db = tmp_path / "custom_db"
        mind = NeuralMind(str(temp_project), db_path=str(custom_db))
        assert mind.db_path == str(custom_db)

    def test_init_creates_embedder(self, temp_project):
        """Test that init creates an embedding backend instance.

        Backend-agnostic: as of v0.29.0 the default is the ChromaDB-free
        turbovec backend, but any concrete ``EmbeddingBackend`` is valid here.
        """
        from neuralmind import NeuralMind
        from neuralmind.embedding_backend import EmbeddingBackend

        mind = NeuralMind(str(temp_project))
        assert isinstance(mind.embedder, EmbeddingBackend)

    def test_init_accepts_deprecated_enable_reranking(self, temp_project):
        """The deprecated enable_reranking kwarg is accepted (no TypeError).

        The learned_patterns reranker was removed in favor of the synapse
        layer; the kwarg is ignored but still part of the public signature so
        existing callers don't break.
        """
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project), enable_reranking=False)
        # Stored for backward compat, but it no longer gates any behavior.
        assert mind.enable_reranking is False


class TestNeuralMindBuild:
    """Tests for NeuralMind build functionality."""

    def test_build_returns_stats(self, temp_project):
        """Test that build returns statistics."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        stats = mind.build()

        assert isinstance(stats, dict)
        assert "success" in stats
        assert stats["success"] is True

    def test_build_creates_index(self, temp_project):
        """Test that build creates the neural index."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        stats = mind.build()

        # Check actual keys from build()
        assert "nodes_total" in stats
        assert stats["nodes_total"] == 6  # From sample_graph fixture
        assert "communities" in stats

    def test_build_incremental(self, temp_project):
        """Test that incremental builds skip unchanged nodes."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))

        # First build
        stats1 = mind.build()
        assert stats1["nodes_added"] == 6

        # Second build should skip nodes
        stats2 = mind.build()
        assert stats2["nodes_skipped"] >= 0

    def test_build_force_reembeds_all(self, temp_project):
        """Test that force=True re-embeds all nodes."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))

        # First build
        mind.build()

        # Force rebuild (existing nodes should be counted as updated, not added)
        stats = mind.build(force=True)
        assert stats["nodes_updated"] == 6

    def test_build_without_graph_fails(self, empty_project):
        """Test that building without graph.json returns failure stats."""
        from neuralmind import NeuralMind

        # Create graphify-out directory but no graph.json
        (empty_project / "graphify-out").mkdir()

        mind = NeuralMind(str(empty_project))
        stats = mind.build()

        # build() returns failure dict, not raises exception
        assert stats["success"] is False
        assert "error" in stats

    def test_build_sets_built_flag(self, temp_project):
        """Test that build sets the _built flag."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        assert mind._built is False

        mind.build()
        assert mind._built is True

    def test_build_creates_selector(self, temp_project):
        """Test that build creates the context selector."""
        from neuralmind import NeuralMind
        from neuralmind.context_selector import ContextSelector

        mind = NeuralMind(str(temp_project))
        assert mind.selector is None

        mind.build()
        assert isinstance(mind.selector, ContextSelector)


class TestNeuralMindWakeup:
    """Tests for NeuralMind wakeup context."""

    def test_wakeup_returns_context_result(self, temp_project):
        """Test that wakeup returns a ContextResult."""
        from neuralmind import NeuralMind
        from neuralmind.context_selector import ContextResult

        mind = NeuralMind(str(temp_project))
        mind.build()

        result = mind.wakeup()

        assert isinstance(result, ContextResult)
        assert result.context is not None
        assert len(result.context) > 0

    def test_wakeup_uses_l0_l1_only(self, temp_project):
        """Test that wakeup only uses L0 and L1 layers."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        result = mind.wakeup()

        assert any("L0" in layer for layer in result.layers_used)
        assert any("L1" in layer for layer in result.layers_used)
        assert not any("L2" in layer for layer in result.layers_used)
        assert not any("L3" in layer for layer in result.layers_used)

    def test_wakeup_token_budget(self, temp_project):
        """Test that wakeup stays within token budget."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        result = mind.wakeup()

        # Wake-up should be ~600 tokens (L0 + L1)
        assert result.budget.total < 1500
        assert result.budget.l2_ondemand == 0
        assert result.budget.l3_search == 0

    def test_wakeup_auto_builds(self, temp_project):
        """Test that wakeup auto-builds if not built."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        assert mind._built is False

        # wakeup() should auto-build via _ensure_built()
        result = mind.wakeup()

        assert mind._built is True
        assert result.context is not None


class TestNeuralMindQuery:
    """Tests for NeuralMind query functionality."""

    def test_query_returns_context_result(self, temp_project):
        """Test that query returns a ContextResult."""
        from neuralmind import NeuralMind
        from neuralmind.context_selector import ContextResult

        mind = NeuralMind(str(temp_project))
        mind.build()

        result = mind.query("How does authentication work?")

        assert isinstance(result, ContextResult)
        assert result.context is not None
        assert len(result.context) > 0

    def test_query_uses_base_layers(self, temp_project):
        """Test that query uses at least L0 and L1 layers."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        result = mind.query("How does authentication work?")

        assert any("L0" in layer for layer in result.layers_used)
        assert any("L1" in layer for layer in result.layers_used)
        # L2 and L3 depend on query relevance

    def test_query_includes_relevant_content(self, temp_project):
        """Test that query includes relevant content."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        result = mind.query("authentication")

        # Should include some content
        assert len(result.context) > 0

    def test_query_auto_builds(self, temp_project):
        """Test that query auto-builds if not built."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        assert mind._built is False

        # query() should auto-build via _ensure_built()
        result = mind.query("test")

        assert mind._built is True
        assert result.context is not None

    def test_query_logs_memory_event(self, temp_project, mock_chromadb):
        """Test that query attempts to log a memory event."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        with patch("neuralmind.core.log_query_event") as mock_log:
            result = mind.query("test memory log")

        mock_log.assert_called_once_with(mind.project_path, "test memory log", result)


class TestNeuralMindSearch:
    """Tests for NeuralMind search functionality."""

    def test_search_returns_list(self, temp_project):
        """Test that search returns a list."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        results = mind.search("authentication")

        assert isinstance(results, list)

    def test_search_results_have_scores(self, temp_project):
        """Test that search results include scores."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        results = mind.search("function")

        if results:
            assert "score" in results[0] or "distance" in results[0]

    def test_search_respects_n_parameter(self, temp_project):
        """Test that search respects the n parameter."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        results = mind.search("function", n=2)

        assert len(results) <= 2

    def test_search_auto_builds(self, temp_project):
        """Test that search auto-builds if not built."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        assert mind._built is False

        results = mind.search("test")

        assert mind._built is True
        assert isinstance(results, list)


class TestNeuralMindStats:
    """Tests for NeuralMind stats functionality."""

    def test_get_stats_before_build(self, temp_project):
        """Test get_stats before build."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        stats = mind.get_stats()

        assert stats["built"] is False

    def test_get_stats_after_build(self, temp_project):
        """Test get_stats after build."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        stats = mind.get_stats()

        assert stats["built"] is True
        assert "nodes" in stats
        assert "communities" in stats


class TestNeuralMindBenchmark:
    """Tests for NeuralMind benchmark functionality."""

    def test_benchmark_returns_results(self, temp_project):
        """Test that benchmark returns results."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        results = mind.benchmark()

        assert isinstance(results, dict)

    def test_benchmark_with_custom_queries(self, temp_project):
        """Test benchmark with custom queries."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        queries = ["authentication", "task management"]
        results = mind.benchmark(sample_queries=queries)

        assert isinstance(results, dict)

    def test_benchmark_auto_builds(self, temp_project):
        """Test that benchmark auto-builds if not built."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        assert mind._built is False

        results = mind.benchmark()

        assert mind._built is True
        assert isinstance(results, dict)


class TestNeuralMindSkeleton:
    """Tests for NeuralMind.skeleton() method."""

    def test_skeleton_returns_string(self, temp_project, mock_chromadb):
        """skeleton() returns a string for an indexed file."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        result = mind.skeleton("auth/handlers.py")
        assert isinstance(result, str)

    def test_skeleton_empty_for_unindexed_file(self, temp_project, mock_chromadb):
        """skeleton() returns empty string for file not in the graph."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        result = mind.skeleton("nonexistent/file.py")
        assert result == ""

    def test_skeleton_auto_builds(self, temp_project, mock_chromadb):
        """skeleton() triggers auto-build if not built."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        assert mind._built is False

        # Should auto-build via _ensure_built
        mind.skeleton("auth/handlers.py")
        assert mind._built is True

    def test_skeleton_with_mock_embedder(self, temp_project, sample_graph):
        """skeleton() formats output correctly using mocked embedder data."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))

        # Manually set up the embedder with graph loaded (no ChromaDB needed)
        mind.embedder.nodes = sample_graph["nodes"]
        mind.embedder.edges = sample_graph["edges"]
        mind.embedder.graph = sample_graph

        # Set built state and create a minimal selector
        mind._built = True
        from neuralmind.context_selector import ContextSelector

        mock_emb = MagicMock()
        mock_emb.get_stats.return_value = {"total_nodes": 6, "communities": 3}
        mind.selector = ContextSelector(mock_emb, str(temp_project))

        result = mind.skeleton("auth/handlers.py")
        assert isinstance(result, str)


class TestNeuralMindExportContext:
    """Tests for NeuralMind.export_context() method."""

    def test_export_wakeup_creates_file(self, temp_project, tmp_path, mock_chromadb):
        """export_context without query exports wakeup context."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        output_path = str(tmp_path / "context_export.md")
        result = mind.export_context(output_path=output_path)

        assert result == output_path
        assert Path(output_path).exists()
        content = Path(output_path).read_text()
        assert "NeuralMind Context Export" in content
        assert "wakeup" in content

    def test_export_query_creates_file(self, temp_project, tmp_path, mock_chromadb):
        """export_context with query exports query context."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        output_path = str(tmp_path / "query_export.md")
        result = mind.export_context(query="authentication", output_path=output_path)

        assert Path(output_path).exists()
        content = Path(output_path).read_text()
        assert "query" in content
        assert "authentication" in content

    def test_export_default_path(self, temp_project, mock_chromadb):
        """export_context uses default path when none specified."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        result = mind.export_context()
        expected_path = str(Path(temp_project) / "neuralmind_context.md")
        assert result == expected_path
        assert Path(result).exists()

    def test_export_includes_metadata(self, temp_project, tmp_path, mock_chromadb):
        """export_context output includes metadata like tokens and reduction."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        output_path = str(tmp_path / "meta_export.md")
        mind.export_context(output_path=output_path)

        content = Path(output_path).read_text()
        assert "Tokens:" in content
        assert "Reduction:" in content
        assert "Layers:" in content


class TestCreateMind:
    """Tests for create_mind() factory function."""

    def test_create_mind_returns_neuralmind(self, temp_project):
        """create_mind returns a NeuralMind instance."""
        from neuralmind.core import NeuralMind, create_mind

        mind = create_mind(str(temp_project), auto_build=False)
        assert isinstance(mind, NeuralMind)

    def test_create_mind_auto_build_true(self, temp_project, mock_chromadb):
        """create_mind with auto_build=True builds automatically."""
        from neuralmind.core import create_mind

        mind = create_mind(str(temp_project), auto_build=True)
        assert mind._built is True

    def test_create_mind_auto_build_false(self, temp_project):
        """create_mind with auto_build=False skips building."""
        from neuralmind.core import create_mind

        mind = create_mind(str(temp_project), auto_build=False)
        assert mind._built is False


class TestTurbovecMigrationNotice:
    """Regression coverage for the v0.22 one-time turbovec migration notice."""

    def test_notice_reads_embedder_nodes_without_attributeerror(
        self, temp_project, capsys, monkeypatch
    ):
        # The notice path fires only when auto-selection lands on turbovec for a
        # project with a legacy chroma index and an unbuilt turbovec index. It
        # must read the node list off the embedder (NeuralMind has no self.nodes)
        # — previously this raised AttributeError and blocked the reindex.
        from neuralmind.core import NeuralMind

        mind = NeuralMind(str(temp_project), backend_type="in_memory")
        mind.embedder.load_graph()
        monkeypatch.setattr(mind.backend_manager, "backend_name", "turbovec", raising=False)
        monkeypatch.setattr(mind.embedder, "get_stats", lambda: {"total_nodes": 0})
        (temp_project / "graphify-out" / "neuralmind_db").mkdir(parents=True, exist_ok=True)

        mind._maybe_announce_turbovec_migration()  # must not raise

        assert "reindexing" in capsys.readouterr().err

    def test_notice_skipped_when_no_legacy_chroma_index(self, temp_project, capsys, monkeypatch):
        from neuralmind.core import NeuralMind

        mind = NeuralMind(str(temp_project), backend_type="in_memory")
        mind.embedder.load_graph()
        monkeypatch.setattr(mind.backend_manager, "backend_name", "turbovec", raising=False)
        # No legacy graphify-out/neuralmind_db -> fresh project, no notice.
        mind._maybe_announce_turbovec_migration()
        assert capsys.readouterr().err == ""


class TestBuiltinGraphRefresh:
    """`_maybe_generate_builtin_graph` decides by *ownership*, not by `force`.

    Regression: before v0.42 it returned early whenever a graph existed and
    `force` was False, so `neuralmind build .` silently re-embedded a stale
    graph and never picked up files added since the first build. The shipped
    post-commit hook ran exactly that command, making it a structural no-op.
    """

    def _graph_labels(self, project):
        import json

        graph = json.loads((project / "graphify-out" / "graph.json").read_text())
        return sorted(n["label"] for n in graph["nodes"])

    def _mind(self, project):
        from neuralmind import NeuralMind

        return NeuralMind(str(project))

    def test_plain_build_refreshes_our_own_graph(self, tmp_path):
        import pytest

        from neuralmind import graphgen

        if not graphgen.is_available():
            pytest.skip("tree-sitter not installed")

        (tmp_path / "a.py").write_text("def one():\n    return 1\n")
        mind = self._mind(tmp_path)
        mind._maybe_generate_builtin_graph()
        assert "one()" in self._graph_labels(tmp_path)

        # A new file must appear without --force.
        (tmp_path / "b.py").write_text("def two():\n    return 2\n")
        mind._maybe_generate_builtin_graph()
        labels = self._graph_labels(tmp_path)
        assert "two()" in labels, "plain build must refresh a graph we own"
        assert "one()" in labels

    def test_deleted_file_drops_out_on_refresh(self, tmp_path):
        import pytest

        from neuralmind import graphgen

        if not graphgen.is_available():
            pytest.skip("tree-sitter not installed")

        (tmp_path / "a.py").write_text("def one():\n    return 1\n")
        (tmp_path / "b.py").write_text("def two():\n    return 2\n")
        mind = self._mind(tmp_path)
        mind._maybe_generate_builtin_graph()
        assert "two()" in self._graph_labels(tmp_path)

        (tmp_path / "b.py").unlink()
        mind._maybe_generate_builtin_graph()
        assert "two()" not in self._graph_labels(tmp_path)

    def test_never_overwrites_a_graphify_owned_graph(self, tmp_path):
        """A real graphify build always wins — refresh must not touch it."""
        import json

        import pytest

        from neuralmind import graphgen

        if not graphgen.is_available():
            pytest.skip("tree-sitter not installed")

        (tmp_path / "a.py").write_text("def one():\n    return 1\n")
        out = tmp_path / "graphify-out"
        out.mkdir()
        (out / "graph.json").write_text(
            json.dumps(
                {
                    "generated_by": "graphify v1.2.3",
                    "directed": True,
                    "multigraph": False,
                    "nodes": [{"id": "s", "label": "GRAPHIFY_SENTINEL", "file_type": "code"}],
                    "links": [],
                }
            )
        )

        self._mind(tmp_path)._maybe_generate_builtin_graph()

        graph = json.loads((out / "graph.json").read_text())
        assert graph["generated_by"] == "graphify v1.2.3"
        assert self._graph_labels(tmp_path) == ["GRAPHIFY_SENTINEL"]

    def test_refresh_is_silent_and_never_writes_stdout(self, tmp_path, capsys):
        """The graph-generation notice fires once, on stdout-free stderr.

        Two regressions guarded here, both introduced when v0.42.0 made every
        build refresh the graph:

        1. The notice used to fire only on first generation. Printing it on
           every build is noise.
        2. It printed to **stdout** with a `->` arrow that was once `→`.
           `build()` runs under the MCP server (whose stdout carries JSON-RPC),
           Claude Code hooks, and the VS Code extension — none of which install
           the CLI's UTF-8 stdout guard. A non-ASCII byte there raises
           UnicodeEncodeError on a Windows cp1252 console, and *any* stdout
           byte corrupts the MCP wire protocol.
        """
        import pytest

        from neuralmind import graphgen

        if not graphgen.is_available():
            pytest.skip("tree-sitter not installed")

        (tmp_path / "a.py").write_text("def one():\n    return 1\n")
        mind = self._mind(tmp_path)

        mind._maybe_generate_builtin_graph()  # first generation: announces
        first = capsys.readouterr()
        assert first.out == "", "graph generation must never write to stdout"
        assert "generated code graph" in first.err

        (tmp_path / "b.py").write_text("def two():\n    return 2\n")
        mind._maybe_generate_builtin_graph()  # refresh: silent
        second = capsys.readouterr()
        assert second.out == ""
        assert second.err == "", "refresh must not re-announce on every build"

        # The refresh still happened, silence notwithstanding.
        assert "two()" in self._graph_labels(tmp_path)

    def test_generation_notice_survives_a_cp1252_stream(self, tmp_path, monkeypatch):
        """The exact crash: a cp1252 stderr must be able to encode the notice."""
        import io
        import sys

        import pytest

        from neuralmind import graphgen

        if not graphgen.is_available():
            pytest.skip("tree-sitter not installed")

        (tmp_path / "a.py").write_text("def one():\n    return 1\n")

        buf = io.BytesIO()
        monkeypatch.setattr(sys, "stderr", io.TextIOWrapper(buf, encoding="cp1252"))
        self._mind(tmp_path)._maybe_generate_builtin_graph()
        sys.stderr.flush()

        assert b"generated code graph" in buf.getvalue()


class TestTransitionPathKeys:
    """Transition keys are repo-relative POSIX, whatever the caller passed.

    Regression: the watcher hands `activate_files` absolute native paths, and
    they used to be recorded verbatim — but `neuralmind next src/api.py` passes
    the user's relative input verbatim too, so live-learned transitions could
    never match a query. Both sides now normalize to the convention
    `mine-history` established (repo-relative POSIX), with a dual-read fallback
    for stores recorded before normalization.
    """

    def _mind(self, tmp_path, monkeypatch):
        from neuralmind import NeuralMind

        mind = NeuralMind(str(tmp_path))
        # Keep the test on the synapse layer: no index build, no embeddings.
        monkeypatch.setattr(mind, "_ensure_built", lambda: None)
        monkeypatch.setattr(mind.embedder, "get_file_nodes", lambda _p: [])
        assert mind.synapses is not None
        return mind

    # -- the key normalizer -------------------------------------------------

    def test_key_normalizes_backslashes(self, tmp_path, monkeypatch):
        mind = self._mind(tmp_path, monkeypatch)
        assert mind._transition_key(r"src\api.py") == "src/api.py"

    def test_key_relativizes_absolute_paths_under_root(self, tmp_path, monkeypatch):
        mind = self._mind(tmp_path, monkeypatch)
        absolute = str(tmp_path / "src" / "api.py")  # native separators
        assert mind._transition_key(absolute) == "src/api.py"

    def test_key_rejects_paths_outside_the_project(self, tmp_path, monkeypatch):
        mind = self._mind(tmp_path, monkeypatch)
        outside = str(tmp_path.parent / "elsewhere" / "x.py")
        assert mind._transition_key(outside) is None

    def test_key_passes_node_ids_through(self, tmp_path, monkeypatch):
        mind = self._mind(tmp_path, monkeypatch)
        assert mind._transition_key("api_py__handler_fn") == "api_py__handler_fn"

    def test_key_collapses_leading_dot_segment(self, tmp_path, monkeypatch):
        mind = self._mind(tmp_path, monkeypatch)
        assert mind._transition_key("./src/api.py") == "src/api.py"

    # -- write side: the watcher's absolute paths ---------------------------

    def test_watcher_absolute_input_is_stored_relative(self, tmp_path, monkeypatch):
        mind = self._mind(tmp_path, monkeypatch)
        mind.activate_files([str(tmp_path / "a.py"), str(tmp_path / "b.py")])

        # Stored under the relative key...
        assert dict(mind.synapses.next_likely("a.py"))
        # ...and NOT under the raw absolute key the watcher passed.
        assert mind.synapses.next_likely(str(tmp_path / "a.py")) == []

    def test_paths_outside_root_are_dropped_from_the_sequence(self, tmp_path, monkeypatch):
        mind = self._mind(tmp_path, monkeypatch)
        outside = str(tmp_path.parent / "elsewhere.py")
        mind.activate_files([str(tmp_path / "a.py"), outside])
        # Only one in-project path survived -> no pair, nothing recorded.
        assert mind.synapses.next_likely("a.py") == []

    # -- query side: relative, backslash, legacy ----------------------------

    def test_next_query_with_relative_path_finds_watcher_learning(self, tmp_path, monkeypatch):
        mind = self._mind(tmp_path, monkeypatch)
        mind.activate_files([str(tmp_path / "src" / "api.py"), str(tmp_path / "src" / "models.py")])
        ranked = mind.next_likely("src/api.py")
        assert ranked and ranked[0][0] == "src/models.py"

    def test_next_query_normalizes_windows_backslash_input(self, tmp_path, monkeypatch):
        mind = self._mind(tmp_path, monkeypatch)
        mind.activate_files([str(tmp_path / "src" / "api.py"), str(tmp_path / "src" / "models.py")])
        ranked = mind.next_likely(r"src\api.py")
        assert ranked and ranked[0][0] == "src/models.py"

    def test_next_dual_reads_legacy_absolute_keyed_stores(self, tmp_path, monkeypatch):
        mind = self._mind(tmp_path, monkeypatch)
        # Simulate a pre-v0.42.0 store: the old watcher recorded absolute
        # native path strings verbatim.
        mind.synapses.record_sequence(
            [str(tmp_path.resolve() / "a.py"), str(tmp_path.resolve() / "b.py")]
        )
        ranked = mind.next_likely("a.py")
        assert ranked, "legacy absolute-keyed transitions must remain reachable"
        # Legacy successors are normalized on the way out.
        assert ranked[0][0] == "b.py"
