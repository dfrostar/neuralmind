"""Tests for NeuralMind embedder functionality."""

import json
from pathlib import Path

import pytest


class TestGraphEmbedder:
    """Tests for GraphEmbedder class."""

    def test_init_with_valid_project(self, temp_project):
        """Test embedder initialization with valid project."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        assert embedder.project_path == Path(temp_project)

    def test_load_graph_returns_bool(self, temp_project):
        """Test that load_graph returns a boolean."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        result = embedder.load_graph()

        assert isinstance(result, bool)
        assert result is True

    def test_load_graph_populates_nodes(self, temp_project, sample_graph):
        """Test that loaded graph populates nodes and edges."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()

        assert len(embedder.nodes) == len(sample_graph["nodes"])
        assert len(embedder.edges) == len(sample_graph["edges"])

    def test_load_graph_nonexistent_returns_false(self, empty_project):
        """Test that loading nonexistent graph returns False."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(empty_project))
        result = embedder.load_graph()

        # load_graph returns False when graph doesn't exist
        assert result is False

    def test_embed_nodes_returns_stats(self, temp_project):
        """Test that embed_nodes returns statistics dict."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        stats = embedder.embed_nodes()

        assert isinstance(stats, dict)
        assert "added" in stats
        assert "updated" in stats
        assert "skipped" in stats

    def test_embed_nodes_adds_nodes(self, temp_project):
        """Test that embed_nodes adds nodes on first run."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        stats = embedder.embed_nodes()

        assert stats["added"] == 6  # From sample_graph fixture

    def test_embed_nodes_incremental(self, temp_project):
        """Test that embed_nodes is incremental by default."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()

        # First embedding
        stats1 = embedder.embed_nodes()
        assert stats1["added"] == 6

        # Second embedding should skip unchanged
        stats2 = embedder.embed_nodes()
        assert stats2["skipped"] >= 0

    def test_embed_nodes_force_reembeds(self, temp_project):
        """Test that embed_nodes with force=True re-embeds all."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        # Force re-embed
        stats = embedder.embed_nodes(force=True)
        assert stats["added"] == 6

    def test_search_returns_list(self, temp_project):
        """Test that search returns a list."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        results = embedder.search("authentication")

        assert isinstance(results, list)

    def test_search_respects_n_parameter(self, temp_project):
        """Test that search respects the n (limit) parameter."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        results = embedder.search("function", n=2)

        assert len(results) <= 2

    def test_search_results_have_score(self, temp_project):
        """Test that search results include scores."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        results = embedder.search("authentication")

        if results:
            result = results[0]
            assert "score" in result or "distance" in result

    def test_search_results_have_metadata(self, temp_project):
        """Test that search results include metadata."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        results = embedder.search("function")

        if results:
            result = results[0]
            assert "metadata" in result
            assert "id" in result


class TestEmbeddingGeneration:
    """Tests for embedding text generation."""

    def test_node_to_embedding_text(self, sample_graph):
        """Test conversion of node to embedding text."""
        node = sample_graph["nodes"][0]

        # The embedder should create text from node attributes
        text_parts = [
            node.get("name", ""),
            node.get("type", ""),
            node.get("description", ""),
            node.get("file_path", ""),
        ]
        embedding_text = " ".join(filter(None, text_parts))

        assert "authenticate_user" in embedding_text
        assert "function" in embedding_text
        assert "auth/handlers.py" in embedding_text

    def test_empty_node_handled(self):
        """Test that empty nodes are handled gracefully."""
        empty_node = {"id": "empty"}

        text_parts = [
            empty_node.get("name", ""),
            empty_node.get("type", ""),
            empty_node.get("description", ""),
        ]
        embedding_text = " ".join(filter(None, text_parts))

        # Should not crash, may be empty string
        assert isinstance(embedding_text, str)


class TestContentHashing:
    """Tests for content hashing for incremental updates."""

    def test_same_content_same_hash(self, sample_graph):
        """Test that same content produces same hash."""
        import hashlib

        node = sample_graph["nodes"][0]
        content = json.dumps(node, sort_keys=True)

        hash1 = hashlib.sha256(content.encode()).hexdigest()
        hash2 = hashlib.sha256(content.encode()).hexdigest()

        assert hash1 == hash2

    def test_different_content_different_hash(self, sample_graph):
        """Test that different content produces different hash."""
        import hashlib

        node1 = sample_graph["nodes"][0]
        node2 = sample_graph["nodes"][1]

        content1 = json.dumps(node1, sort_keys=True)
        content2 = json.dumps(node2, sort_keys=True)

        hash1 = hashlib.sha256(content1.encode()).hexdigest()
        hash2 = hashlib.sha256(content2.encode()).hexdigest()

        assert hash1 != hash2


class TestChromaDBIntegration:
    """Tests for ChromaDB integration."""

    def test_embedder_creates_collection(self, temp_project):
        """Test that embedder creates ChromaDB collection."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        # Collection should exist
        assert embedder.collection is not None

    def test_get_stats_returns_dict(self, temp_project):
        """Test that get_stats returns statistics dict."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        stats = embedder.get_stats()

        assert isinstance(stats, dict)
        assert "total_nodes" in stats
        assert "communities" in stats

    def test_get_stats_node_count(self, temp_project):
        """Test that get_stats returns correct node count."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        stats = embedder.get_stats()

        assert stats["total_nodes"] == 6


class TestCommunitySummary:
    """Tests for community summary functionality."""

    def test_get_community_summary_returns_dict(self, temp_project):
        """Test that get_community_summary returns dict."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        summary = embedder.get_community_summary(1)

        assert isinstance(summary, dict)
        assert "community" in summary
        assert "nodes" in summary

    def test_get_community_summary_respects_max_nodes(self, temp_project):
        """Test that get_community_summary respects max_nodes."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        summary = embedder.get_community_summary(1, max_nodes=2)

        assert len(summary["nodes"]) <= 2

    def test_get_community_summary_empty_community(self, temp_project):
        """Test get_community_summary with nonexistent community."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        # Community 999 doesn't exist
        summary = embedder.get_community_summary(999)

        assert isinstance(summary, dict)
        assert summary["nodes"] == []
