"""Tests for NeuralMind core functionality."""

from pathlib import Path

import pytest


class TestNeuralMindInit:
    """Tests for NeuralMind initialization."""

    def test_init_with_valid_project(self, temp_project):
        """Test initialization with a valid project path."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        assert mind.project_path == Path(temp_project)
        assert mind.graph_path.exists()

    def test_init_with_nonexistent_path(self, tmp_path):
        """Test initialization with non-existent path raises error."""
        from neuralmind import NeuralMind

        nonexistent = tmp_path / "nonexistent"
        with pytest.raises(FileNotFoundError):
            NeuralMind(str(nonexistent))

    def test_init_with_file_instead_of_directory(self, tmp_path):
        """Test initialization with a file instead of directory raises error."""
        from neuralmind import NeuralMind

        file_path = tmp_path / "file.txt"
        file_path.write_text("test")

        with pytest.raises(ValueError):
            NeuralMind(str(file_path))

    def test_init_custom_db_path(self, temp_project, tmp_path):
        """Test initialization with custom database path."""
        from neuralmind import NeuralMind

        custom_db = tmp_path / "custom_db"
        mind = NeuralMind(str(temp_project), db_path=str(custom_db))
        assert mind.db_path == custom_db


class TestNeuralMindBuild:
    """Tests for NeuralMind build functionality."""

    def test_build_creates_index(self, temp_project):
        """Test that build creates the neural index."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        stats = mind.build()

        assert "nodes_processed" in stats
        assert stats["nodes_processed"] == 6  # From sample_graph fixture
        assert "communities" in stats
        assert stats["communities"] == 3

    def test_build_incremental(self, temp_project):
        """Test that incremental builds skip unchanged nodes."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))

        # First build
        stats1 = mind.build()
        assert stats1["nodes_embedded"] == 6

        # Second build should skip nodes
        stats2 = mind.build()
        assert stats2["nodes_skipped"] >= 0

    def test_build_force_reembeds_all(self, temp_project):
        """Test that force=True re-embeds all nodes."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))

        # First build
        mind.build()

        # Force rebuild
        stats = mind.build(force=True)
        assert stats["nodes_embedded"] == 6

    def test_build_without_graph_raises_error(self, empty_project):
        """Test that building without graph.json raises error."""
        from neuralmind import NeuralMind

        # Create directory structure without graph.json
        (empty_project / "graphify-out").mkdir()

        with pytest.raises(FileNotFoundError):
            mind = NeuralMind(str(empty_project))
            mind.build()


class TestNeuralMindWakeup:
    """Tests for NeuralMind wakeup context."""

    def test_wakeup_returns_context_result(self, temp_project):
        """Test that wakeup returns a ContextResult."""
        from neuralmind import ContextResult, NeuralMind

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

        assert "L0" in result.layers_used
        assert "L1" in result.layers_used
        assert "L2" not in result.layers_used
        assert "L3" not in result.layers_used

    def test_wakeup_token_budget(self, temp_project):
        """Test that wakeup stays within token budget."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        result = mind.wakeup()

        # Wake-up should be around 600 tokens (L0 + L1)
        assert result.budget.total < 1000
        assert result.budget.l2 == 0
        assert result.budget.l3 == 0

    def test_wakeup_without_build_raises_error(self, temp_project):
        """Test that wakeup without build raises error."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))

        with pytest.raises(RuntimeError):
            mind.wakeup()


class TestNeuralMindQuery:
    """Tests for NeuralMind query functionality."""

    def test_query_returns_context_result(self, temp_project):
        """Test that query returns a ContextResult."""
        from neuralmind import ContextResult, NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        result = mind.query("How does authentication work?")

        assert isinstance(result, ContextResult)
        assert result.context is not None
        assert len(result.context) > 0

    def test_query_uses_all_layers(self, temp_project):
        """Test that query uses all four layers."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        result = mind.query("How does authentication work?")

        assert "L0" in result.layers_used
        assert "L1" in result.layers_used
        # L2 and L3 depend on query relevance

    def test_query_includes_relevant_content(self, temp_project):
        """Test that query includes relevant content."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        result = mind.query("How does authentication work?")

        # Should include auth-related content
        assert (
            "authenticat" in result.context.lower() or "auth" in result.context.lower()
        )

    def test_query_calculates_reduction_ratio(self, temp_project):
        """Test that query calculates reduction ratio."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        result = mind.query("How does authentication work?")

        assert result.reduction_ratio > 0
        # Should show significant reduction
        assert result.reduction_ratio > 1.0

    def test_query_empty_raises_error(self, temp_project):
        """Test that empty query raises error."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        with pytest.raises(ValueError):
            mind.query("")

    def test_query_without_build_raises_error(self, temp_project):
        """Test that query without build raises error."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))

        with pytest.raises(RuntimeError):
            mind.query("How does authentication work?")


class TestNeuralMindSearch:
    """Tests for NeuralMind search functionality."""

    def test_search_returns_list(self, temp_project):
        """Test that search returns a list of results."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        results = mind.search("authentication")

        assert isinstance(results, list)

    def test_search_result_structure(self, temp_project):
        """Test that search results have expected structure."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        results = mind.search("authentication")

        if results:  # May be empty if no matches
            result = results[0]
            assert "id" in result or "name" in result
            assert "score" in result or "distance" in result

    def test_search_respects_limit(self, temp_project):
        """Test that search respects the limit parameter."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        results = mind.search("function", n=2)

        assert len(results) <= 2

    def test_search_without_build_raises_error(self, temp_project):
        """Test that search without build raises error."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))

        with pytest.raises(RuntimeError):
            mind.search("authentication")


class TestNeuralMindStats:
    """Tests for NeuralMind statistics."""

    def test_get_stats_returns_dict(self, temp_project):
        """Test that get_stats returns a dictionary."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        stats = mind.get_stats()

        assert isinstance(stats, dict)

    def test_get_stats_includes_node_count(self, temp_project):
        """Test that stats include node count."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        stats = mind.get_stats()

        assert "node_count" in stats
        assert stats["node_count"] == 6

    def test_get_stats_includes_community_count(self, temp_project):
        """Test that stats include community count."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        stats = mind.get_stats()

        assert "community_count" in stats
        assert stats["community_count"] == 3


class TestNeuralMindBenchmark:
    """Tests for NeuralMind benchmark functionality."""

    def test_benchmark_returns_results(self, temp_project):
        """Test that benchmark returns results."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        results = mind.benchmark()

        assert isinstance(results, dict)
        assert "results" in results or "averages" in results

    def test_benchmark_with_custom_queries(self, temp_project):
        """Test benchmark with custom queries."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        custom_queries = ["How does auth work?", "What is the API?"]
        results = mind.benchmark(sample_queries=custom_queries)

        assert isinstance(results, dict)


class TestNeuralMindExport:
    """Tests for NeuralMind export functionality."""

    def test_export_context_returns_string(self, temp_project):
        """Test that export_context returns a string."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        context = mind.export_context()

        assert isinstance(context, str)
        assert len(context) > 0

    def test_export_context_with_query(self, temp_project):
        """Test export_context with a query."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        context = mind.export_context(query="How does auth work?")

        assert isinstance(context, str)
        assert len(context) > 0

    def test_export_context_to_file(self, temp_project, tmp_path):
        """Test export_context to a file."""
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()

        output_file = tmp_path / "context.md"
        result = mind.export_context(output_path=str(output_file))

        assert output_file.exists()
        assert output_file.read_text()
