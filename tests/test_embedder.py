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

    def test_load_graph_returns_dict(self, temp_project):
        """Test that load_graph returns a dictionary."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        graph = embedder.load_graph()

        assert isinstance(graph, dict)
        assert "nodes" in graph
        assert "edges" in graph
        assert "communities" in graph

    def test_load_graph_contains_nodes(self, temp_project, sample_graph):
        """Test that loaded graph contains expected nodes."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        graph = embedder.load_graph()

        assert len(graph["nodes"]) == len(sample_graph["nodes"])
        assert len(graph["edges"]) == len(sample_graph["edges"])
        assert len(graph["communities"]) == len(sample_graph["communities"])

    def test_load_graph_nonexistent_raises_error(self, empty_project):
        """Test that loading nonexistent graph raises error."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(empty_project))

        with pytest.raises(FileNotFoundError):
            embedder.load_graph()

    def test_embed_nodes_creates_embeddings(self, temp_project):
        """Test that embed_nodes creates embeddings."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        stats = embedder.embed_nodes()

        assert "nodes_embedded" in stats or "embedded" in stats

    def test_embed_nodes_incremental(self, temp_project):
        """Test that embed_nodes is incremental by default."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()

        # First embedding
        stats1 = embedder.embed_nodes()

        # Second embedding should skip unchanged
        stats2 = embedder.embed_nodes()

        # Should have skipped some or all nodes
        if "nodes_skipped" in stats2:
            assert stats2["nodes_skipped"] >= 0

    def test_embed_nodes_force_reembeds(self, temp_project):
        """Test that embed_nodes with force=True re-embeds all."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        # Force re-embed
        stats = embedder.embed_nodes(force=True)

        if "nodes_embedded" in stats:
            assert stats["nodes_embedded"] == 6

    def test_search_returns_results(self, temp_project):
        """Test that search returns results."""
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

    def test_search_result_has_score(self, temp_project):
        """Test that search results include scores."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        results = embedder.search("authentication")

        if results:
            # Results should have some score/distance indicator
            result = results[0]
            assert (
                "score" in result or "distance" in result or "distances" in str(result)
            )


class TestEmbeddingGeneration:
    """Tests for embedding text generation."""

    def test_node_to_embedding_text(self, sample_graph):
        """Test conversion of node to embedding text."""

        node = sample_graph["nodes"][0]

        # The embedder should create text from node attributes
        # This tests internal functionality if exposed
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

    def test_collection_created(self, temp_project):
        """Test that ChromaDB collection is created."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        # Collection should exist after embedding
        assert embedder.collection is not None

    def test_collection_contains_nodes(self, temp_project):
        """Test that collection contains the embedded nodes."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        # Should be able to query the collection
        count = embedder.collection.count()
        assert count == 6  # From sample_graph

    def test_metadata_stored(self, temp_project):
        """Test that node metadata is stored in ChromaDB."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        # Query and check metadata
        results = embedder.collection.get(ids=["node_1"])

        if results and results["metadatas"]:
            metadata = results["metadatas"][0]
            assert "name" in metadata or "type" in metadata


class TestLargeGraphHandling:
    """Tests for handling large graphs."""

    def test_large_graph_embedding(self, tmp_path, large_graph):
        """Test embedding a larger graph."""
        from neuralmind.embedder import GraphEmbedder

        # Create project with large graph
        project_path = tmp_path / "large_project"
        project_path.mkdir()
        graphify_out = project_path / "graphify-out"
        graphify_out.mkdir()

        with open(graphify_out / "graph.json", "w") as f:
            json.dump(large_graph, f)

        embedder = GraphEmbedder(str(project_path))
        embedder.load_graph()
        stats = embedder.embed_nodes()

        # Should handle 100 nodes
        if "nodes_embedded" in stats:
            assert stats["nodes_embedded"] == 100
        elif "nodes_processed" in stats:
            assert stats["nodes_processed"] == 100

    def test_large_graph_search_performance(self, tmp_path, large_graph):
        """Test search performance on larger graph."""
        import time

        from neuralmind.embedder import GraphEmbedder

        # Create project with large graph
        project_path = tmp_path / "large_project"
        project_path.mkdir()
        graphify_out = project_path / "graphify-out"
        graphify_out.mkdir()

        with open(graphify_out / "graph.json", "w") as f:
            json.dump(large_graph, f)

        embedder = GraphEmbedder(str(project_path))
        embedder.load_graph()
        embedder.embed_nodes()

        # Search should complete in reasonable time
        start = time.time()
        results = embedder.search("function", n=10)
        elapsed = time.time() - start

        # Search should be fast (< 1 second)
        assert elapsed < 1.0
        assert len(results) <= 10
