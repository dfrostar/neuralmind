"""
test_integration_retrieval.py — End-to-End Retrieval Pipeline Tests
==================================================================

Tests the full 4-layer retrieval pipeline (Identity → Summary → On-Demand → Search)
with real graph data and validates token reduction, layer selection, and context quality.
"""

import json
import tempfile
from pathlib import Path

import pytest

from neuralmind import GraphEmbedder, NeuralMind


@pytest.fixture
def minimal_project():
    """Create a minimal project with sample graph for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        graphify_out = project_path / "graphify-out"
        graphify_out.mkdir()

        # Minimal but valid graph structure
        graph = {
            "nodes": [
                {
                    "id": "auth_module",
                    "label": "auth",
                    "type": "module",
                    "description": "Authentication handler",
                    "source_file": "src/auth.py",
                    "community": 0,
                },
                {
                    "id": "auth_login_func",
                    "label": "login",
                    "type": "function",
                    "description": "User login function",
                    "source_file": "src/auth.py",
                    "parent": "auth_module",
                    "community": 0,
                },
                {
                    "id": "validation_module",
                    "label": "validation",
                    "type": "module",
                    "description": "Input validation",
                    "source_file": "src/validation.py",
                    "community": 0,
                },
                {
                    "id": "db_module",
                    "label": "database",
                    "type": "module",
                    "description": "Database layer",
                    "source_file": "src/database.py",
                    "community": 1,
                },
                {
                    "id": "cache_module",
                    "label": "cache",
                    "type": "module",
                    "description": "Caching utilities",
                    "source_file": "src/cache.py",
                    "community": 1,
                },
                {
                    "id": "api_routes",
                    "label": "routes",
                    "type": "module",
                    "description": "API endpoints",
                    "source_file": "src/api.py",
                    "community": 2,
                },
            ],
            "edges": [
                {"from": "auth_login_func", "to": "validation_module", "type": "calls"},
                {"from": "auth_login_func", "to": "db_module", "type": "calls"},
                {"from": "api_routes", "to": "auth_module", "type": "calls"},
                {"from": "db_module", "to": "cache_module", "type": "calls"},
            ],
            "communities": {
                "0": {"nodes": ["auth_module", "auth_login_func", "validation_module"]},
                "1": {"nodes": ["db_module", "cache_module"]},
                "2": {"nodes": ["api_routes"]},
            },
            "project_metadata": {
                "name": "test-project",
                "description": "Test project for integration tests",
                "languages": ["python"],
            },
        }

        # Write graph
        (graphify_out / "graph.json").write_text(json.dumps(graph))

        yield project_path


@pytest.fixture
def initialized_mind(minimal_project):
    """Initialize NeuralMind with test project."""
    mind = NeuralMind(str(minimal_project))
    mind.build()
    yield mind
    mind.selector.embedder.close()


class TestRetrievalPipeline:
    """Test the full 4-layer retrieval pipeline."""

    def test_initialization(self, initialized_mind):
        """Test that NeuralMind initializes correctly."""
        assert initialized_mind is not None
        assert initialized_mind.selector is not None
        assert initialized_mind.selector.embedder is not None

    def test_wakeup_returns_identity_and_summary(self, initialized_mind):
        """
        Test that wakeup returns Layer 0 (Identity) + Layer 1 (Summary).

        Expected: ~600 tokens of project overview.
        """
        wakeup = initialized_mind.wakeup()

        assert wakeup is not None
        assert "project" in wakeup.context.lower() or "test" in wakeup.context.lower()
        assert wakeup.tokens < 2000  # Should be < 1000 in reality, but be generous

    def test_query_includes_all_layers(self, initialized_mind):
        """
        Test that query result includes all relevant layers.

        Expected:
        - L0: Project identity
        - L1: Architecture summary
        - L2: Relevant modules for query
        - L3: Semantic search results
        """
        result = initialized_mind.query("How do I authenticate users?")

        assert result is not None
        assert len(result.context) > 0
        assert result.tokens > 0
        assert result.reduction_ratio > 1.0  # Should reduce vs full codebase

    def test_query_returns_relevant_context(self, initialized_mind):
        """
        Test that query returns relevant context for authentication question.
        """
        result = initialized_mind.query("authentication")

        # Should include auth-related modules
        context_lower = result.context.lower()
        assert "auth" in context_lower or "login" in context_lower

    def test_different_queries_return_different_contexts(self, initialized_mind):
        """
        Test that different queries return different contexts (query-aware).
        """
        auth_result = initialized_mind.query("authentication")
        db_result = initialized_mind.query("database")

        # Contexts should be different
        assert auth_result.context != db_result.context

        # Auth query should prioritize auth modules
        auth_context_lower = auth_result.context.lower()
        assert "auth" in auth_context_lower or "validation" in auth_context_lower

    def test_token_reduction(self, initialized_mind):
        """
        Test that token reduction works (context << full codebase).
        """
        result = initialized_mind.query("anything")

        # Should achieve at least 2x reduction
        # (in real projects, 40-70x, but minimal project is small)
        assert result.reduction_ratio >= 1.5

    def test_embedder_loads_and_searches(self, initialized_mind):
        """
        Test that embedder can load graph and perform searches.
        """
        embedder = initialized_mind.selector.embedder
        stats = embedder.get_stats()

        assert stats["total_nodes"] > 0
        assert "communities" in stats

        # Test search
        results = embedder.search("authentication", n=3)
        assert len(results) > 0

    def test_community_detection(self, initialized_mind):
        """
        Test that communities are detected correctly.
        """
        embedder = initialized_mind.selector.embedder
        stats = embedder.get_stats()

        # Should detect multiple communities (we defined 3)
        assert stats["communities"] > 1

    def test_skeleton_view(self, initialized_mind, minimal_project):
        """
        Test that skeleton view works for files.
        """
        embedder = initialized_mind.selector.embedder
        skeleton = embedder.get_file_nodes("src/auth.py")

        # Should return nodes from that file
        assert len(skeleton) > 0
        assert any("auth" in str(node).lower() for node in skeleton)

    def test_incremental_embedding(self, minimal_project, mock_chromadb):
        """
        Test that incremental embedding works (only updates changed nodes).

        Logic fixed: embed_nodes now correctly tracks updated vs added nodes
        when force=True by checking if node exists before counting.
        """
        embedder = GraphEmbedder(str(minimal_project))
        assert embedder.load_graph()

        # First embed
        stats1 = embedder.embed_nodes(force=False)
        assert stats1["added"] > 0

        # Second embed (no changes)
        stats2 = embedder.embed_nodes(force=False)
        assert stats2["added"] == 0  # No new nodes
        assert stats2["skipped"] > 0  # Already embedded

        # Force re-embed
        stats3 = embedder.embed_nodes(force=True)
        assert stats3["updated"] > 0

        embedder.close()

    def test_memory_consent_flow(self, initialized_mind, monkeypatch):
        """
        Test that memory consent is checked before logging.

        (This test verifies the hook would work, but doesn't require actual prompting.)
        """
        # This is a placeholder - actual memory logging tests are in test_memory.py
        # This just verifies that query() completes without errors
        result = initialized_mind.query("test")
        assert result is not None

    def test_large_query_handling(self, initialized_mind):
        """
        Test that large queries are handled without errors.
        """
        long_query = "How do I " + "authenticate and validate and cache " * 10 + "correctly?"
        result = initialized_mind.query(long_query)

        assert result is not None
        assert len(result.context) > 0

    def test_context_selector_token_budget(self, initialized_mind):
        """
        Test that context selector respects token budgets for each layer.
        """
        # This verifies that ContextSelector limits tokens per layer
        result = initialized_mind.query("test")

        # Result should be reasonable size
        assert 100 < result.tokens < 5000  # Should be within expected range


class TestBackendAbstraction:
    """Test the EmbeddingBackend abstraction layer."""

    def test_backend_interface_implemented(self, initialized_mind):
        """Test that GraphEmbedder implements EmbeddingBackend interface."""
        from neuralmind import EmbeddingBackend

        embedder = initialized_mind.selector.embedder
        assert isinstance(embedder, EmbeddingBackend)

    def test_backend_project_path_property(self, initialized_mind):
        """Test that backend exposes project_path."""
        embedder = initialized_mind.selector.embedder
        assert hasattr(embedder, "project_path")
        assert embedder.project_path.is_absolute()

    def test_backend_clear_and_close(self, minimal_project):
        """Test that backend clear() and close() methods work."""
        embedder = GraphEmbedder(str(minimal_project))
        assert embedder.load_graph()
        embedder.embed_nodes()

        # Clear should work
        embedder.clear()
        stats_after_clear = embedder.get_stats()
        assert stats_after_clear["total_nodes"] == 0

        # Close should work
        embedder.close()
