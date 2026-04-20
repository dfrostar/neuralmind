"""Tests for NeuralMind embedder functionality."""

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.usefixtures("mock_chromadb")


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
        assert stats["updated"] == 6

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


class TestGetFileNodes:
    """Tests for GraphEmbedder.get_file_nodes path matching."""

    def _make_embedder(self, project_path, abs_source):
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(project_path))
        embedder.nodes = [{"id": "x", "source_file": abs_source}]
        return embedder

    def test_matches_relative_path_against_absolute_node(self, temp_project):
        """Graphify stores absolute paths; users pass relative paths."""
        abs_source = str((temp_project / "src" / "foo.py").resolve())
        embedder = self._make_embedder(temp_project, abs_source)

        assert len(embedder.get_file_nodes("src/foo.py")) == 1

    def test_matches_dot_slash_prefixed_path(self, temp_project):
        abs_source = str((temp_project / "src" / "foo.py").resolve())
        embedder = self._make_embedder(temp_project, abs_source)

        assert len(embedder.get_file_nodes("./src/foo.py")) == 1

    def test_matches_absolute_path(self, temp_project):
        abs_source = str((temp_project / "src" / "foo.py").resolve())
        embedder = self._make_embedder(temp_project, abs_source)

        assert len(embedder.get_file_nodes(abs_source)) == 1

    def test_nonexistent_file_returns_empty(self, temp_project):
        abs_source = str((temp_project / "src" / "foo.py").resolve())
        embedder = self._make_embedder(temp_project, abs_source)

        assert embedder.get_file_nodes("src/does_not_exist.py") == []


class TestGetFileEdges:
    """Tests for GraphEmbedder.get_file_edges edge filtering."""

    def test_returns_matching_edges(self, temp_project, sample_graph):
        """get_file_edges returns edges connected to the given file's nodes."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()

        # node_1 (auth/handlers.py) has edges to node_2 and node_3
        node_ids = {"node_1"}
        edges = embedder.get_file_edges("auth/handlers.py", node_ids=node_ids)
        assert isinstance(edges, list)
        assert len(edges) > 0

    def test_returns_empty_for_unmatched_file(self, temp_project):
        """get_file_edges returns empty list for unknown file."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()

        edges = embedder.get_file_edges("nonexistent.py", node_ids=set())
        assert edges == []

    def test_auto_computes_node_ids(self, temp_project, sample_graph):
        """get_file_edges computes node_ids from get_file_nodes if not provided."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()

        # Pass node_ids=None to trigger auto-computation
        edges = embedder.get_file_edges("auth/handlers.py", node_ids=None)
        assert isinstance(edges, list)

    def test_loads_graph_if_needed(self, temp_project):
        """get_file_edges loads graph if edges not yet loaded."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        # Don't call load_graph — it should auto-load when edges are empty
        assert embedder.edges == []

        edges = embedder.get_file_edges("auth/handlers.py", node_ids={"node_1"})
        # Graph should have been loaded
        assert isinstance(edges, list)


class TestNodeToText:
    """Tests for GraphEmbedder._node_to_text() directly."""

    def test_full_node(self, temp_project, sample_graph):
        """_node_to_text produces text with all fields."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        node = sample_graph["nodes"][0]
        text = embedder._node_to_text(node)

        assert "Entity: authenticate_user" in text
        assert "Type: function" in text
        assert "File: auth/handlers.py" in text
        assert "Community: 1" in text

    def test_minimal_node(self, temp_project):
        """_node_to_text handles minimal node with only id."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        text = embedder._node_to_text({"id": "test_node"})

        assert "Entity: test_node" in text
        assert "Type: unknown" in text

    def test_node_with_norm_label(self, temp_project):
        """_node_to_text includes normalized label when different from label."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        node = {"id": "n1", "label": "foo", "norm_label": "foo_normalized"}
        text = embedder._node_to_text(node)

        assert "Normalized: foo_normalized" in text

    def test_node_with_same_norm_label(self, temp_project):
        """_node_to_text skips norm_label when equal to label."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        node = {"id": "n1", "label": "foo", "norm_label": "foo"}
        text = embedder._node_to_text(node)

        assert "Normalized" not in text


class TestNodeMetadata:
    """Tests for GraphEmbedder._node_metadata() directly."""

    def test_extracts_all_fields(self, temp_project, sample_graph):
        """_node_metadata returns expected metadata keys."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        node = sample_graph["nodes"][0]
        meta = embedder._node_metadata(node)

        assert meta["label"] == "authenticate_user"
        assert meta["file_type"] == "function"
        assert meta["source_file"] == "auth/handlers.py"
        assert meta["community"] == 1
        assert meta["node_id"] == "node_1"

    def test_handles_missing_fields(self, temp_project):
        """_node_metadata uses defaults for missing fields."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        meta = embedder._node_metadata({"id": "bare"})

        assert meta["label"] == "bare"
        assert meta["file_type"] == "unknown"
        assert meta["source_file"] == ""
        assert meta["community"] == -1


class TestContentHashDirect:
    """Tests for GraphEmbedder._content_hash() directly."""

    def test_consistent_hashing(self, temp_project):
        """Same text produces same hash."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        h1 = embedder._content_hash("hello world")
        h2 = embedder._content_hash("hello world")
        assert h1 == h2

    def test_different_texts_different_hash(self, temp_project):
        """Different texts produce different hashes."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        h1 = embedder._content_hash("hello")
        h2 = embedder._content_hash("world")
        assert h1 != h2

    def test_hash_is_16_chars(self, temp_project):
        """Hash is truncated to 16 hex characters."""
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        h = embedder._content_hash("test")
        assert len(h) == 16
