"""Tests for G3 — modularity clustering."""
from neuralmind.modularity import louvain_clustering, _build_adjacency


class TestLouvain:
    def test_empty_graph(self):
        assert louvain_clustering({}) == {}

    def test_single_node(self):
        result = louvain_clustering({"A": {}})
        assert result == {"A": 0}

    def test_two_connected_nodes_in_same_community(self):
        adj = {"A": {"B": 1.0}, "B": {"A": 1.0}}
        result = louvain_clustering(adj)
        # Both should be in the same community
        assert result["A"] == result["B"]

    def test_disconnected_graph(self):
        adj = {"A": {}, "B": {}, "C": {}}
        result = louvain_clustering(adj)
        # All isolated: all in community 0
        assert all(v == 0 for v in result.values())

    def test_triangle_graph(self):
        # Triangle: A-B, B-C, C-A — all should end up together
        adj = {
            "A": {"B": 1.0, "C": 1.0},
            "B": {"A": 1.0, "C": 1.0},
            "C": {"A": 1.0, "B": 1.0},
        }
        result = louvain_clustering(adj)
        assert result["A"] == result["B"] == result["C"]
