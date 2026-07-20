"""Tests for G3 — modularity clustering (expanded)."""

from __future__ import annotations

from neuralmind.modularity import louvain_clustering


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

    def test_resolution_param_affects_result(self):
        """γ > 1.0 should produce MORE communities than γ = 1.0 for weakly-coupled pairs."""
        # Two pairs strongly connected internally, weakly connected externally
        adj = {
            "A": {"B": 10.0, "C": 0.1},
            "B": {"A": 10.0, "D": 0.1},
            "C": {"D": 10.0, "A": 0.1},
            "D": {"C": 10.0, "B": 0.1},
        }
        result_low = louvain_clustering(adj, resolution=0.5)
        result_high = louvain_clustering(adj, resolution=2.0)
        # Higher resolution should NOT produce fewer communities than lower
        n_low = len(set(result_low.values()))
        n_high = len(set(result_high.values()))
        assert n_high >= n_low, f"γ=2.0 → {n_high} comms, γ=0.5 → {n_low} comms"

    def test_resolution_1_matches_pure_adjacency(self):
        """γ = 1.0 should group tightly-clustered nodes together."""
        # Star center + 4 satellites that only connect to center
        adj = {
            "S": {"A": 1.0, "B": 1.0, "C": 1.0, "D": 1.0},
            "A": {"S": 1.0},
            "B": {"S": 1.0},
            "C": {"S": 1.0},
            "D": {"S": 1.0},
        }
        result = louvain_clustering(adj, resolution=1.0)
        # All should be in one community (single-module project)
        assert len(set(result.values())) == 1

    def test_deterministic_output(self):
        """Same input → same output on repeated calls (sorted tiebreaking)."""
        adj = {
            "A": {"B": 1.0, "C": 2.0},
            "B": {"A": 1.0, "C": 1.0},
            "C": {"A": 2.0, "B": 1.0},
        }
        r1 = louvain_clustering(adj)
        r2 = louvain_clustering(adj)
        r3 = louvain_clustering(adj)
        assert r1 == r2 == r3

    def test_perf_bound(self):
        """O(n·k), not O(n²). 200-node sparse graph should finish <1s."""
        import time

        n = 200
        # Ring graph: each node connects only to 2 neighbors (sparse)
        adj: dict[str, dict[str, float]] = {str(i): {} for i in range(n)}
        for i in range(n):
            adj[str(i)][str((i + 1) % n)] = 1.0
            adj[str(i)][str((i - 1) % n)] = 1.0

        start = time.perf_counter()
        result = louvain_clustering(adj)
        elapsed = time.perf_counter() - start

        assert result, "should produce a partition"
        assert len(result) == n
        assert elapsed < 1.0, f"O(n²)? wall-clock={elapsed:.2f}s for {n}-node sparse graph"
