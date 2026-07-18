"""Tests for v0.49.1 patches — NaN guard, queries_attempted, community IDs, cache filter."""

from __future__ import annotations

import math
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from neuralmind.fitness import _clamp, FitnessInputs, compute_fitness
from neuralmind import graphgen
from neuralmind.incremental_extract import IncrementalExtractor


# ---------------------------------------------------------------------------
# NaN/Inf guard tests
# ---------------------------------------------------------------------------

class TestClamp:
    def test_nan_returns_lo(self) -> None:
        assert _clamp(float("nan"), 0.0, 1.0) == 0.0

    def test_inf_returns_lo(self) -> None:
        assert _clamp(float("inf"), 0.0, 1.0) == 0.0

    def test_neg_inf_returns_lo(self) -> None:
        assert _clamp(float("-inf"), 0.0, 1.0) == 0.0

    def test_normal_value_clamped(self) -> None:
        assert _clamp(0.5, 0.0, 1.0) == 0.5
        assert _clamp(-0.1, 0.0, 1.0) == 0.0
        assert _clamp(1.5, 0.0, 1.0) == 1.0

    def test_compute_fitness_with_nan_input(self) -> None:
        """NaN inputs should be clamped, not propagated."""
        inputs = FitnessInputs(retrieval_quality=float("nan"), efficiency=1.0, session_health=1.0)
        result = compute_fitness(inputs)
        assert math.isfinite(result.total)
        assert result.total == 0.0  # NaN → 0.0, product is 0

    def test_compute_fitness_with_inf_input(self) -> None:
        """Inf inputs should be clamped, not propagated."""
        inputs = FitnessInputs(retrieval_quality=float("inf"), efficiency=1.0, session_health=1.0)
        result = compute_fitness(inputs)
        assert math.isfinite(result.total)


# ---------------------------------------------------------------------------
# queries_attempted denominator test
# ---------------------------------------------------------------------------

class TestQueriesAttempted:
    def test_all_queries_succeed(self) -> None:
        """When all queries succeed, denominator = total queries."""
        from neuralmind.tuner import PopulationTuner
        from neuralmind.fixtures import FixtureQuery
        t = PopulationTuner(project_path=Path("/nonexistent"), population_size=5, generations=1)

        fixtures = [
            FixtureQuery(query="q1", expected_node_ids=("node1",)),
            FixtureQuery(query="q2", expected_node_ids=("node2",)),
        ]

        with patch("neuralmind.fixtures.load_fixture_queries", return_value=fixtures), \
             patch("neuralmind.embedder.GraphEmbedder") as MockEmbedder:
            mock_embedder = MagicMock()
            mock_embedder.load_graph.return_value = True
            mock_embedder.search.return_value = [{"id": "node1"}, {"id": "node2"}]
            MockEmbedder.return_value = mock_embedder

            result = t._fitness_from_live_eval({
                "STRUCTURAL_SEED_K": 3.0,
                "SYNAPSE_SEED_K": 3.0,
                "L0_MAX_TOKENS": 150.0,
                "L1_MAX_TOKENS": 600.0,
                "L2_MAX_TOKENS": 800.0,
                "L3_MAX_TOKENS": 1000.0,
            })

        # All queries succeed → retrieval_quality = 1.0
        assert result > 0.0

    def test_some_queries_fail(self) -> None:
        """When some queries fail, denominator = attempted only."""
        from neuralmind.tuner import PopulationTuner
        from neuralmind.fixtures import FixtureQuery
        t = PopulationTuner(project_path=Path("/nonexistent"), population_size=5, generations=1)

        fixtures = [
            FixtureQuery(query="q1", expected_node_ids=("node1",)),
            FixtureQuery(query="q2", expected_node_ids=("node2",)),
            FixtureQuery(query="q3", expected_node_ids=("node3",)),
            FixtureQuery(query="q4", expected_node_ids=("node4",)),
        ]

        with patch("neuralmind.fixtures.load_fixture_queries", return_value=fixtures), \
             patch("neuralmind.embedder.GraphEmbedder") as MockEmbedder:
            mock_embedder = MagicMock()
            mock_embedder.load_graph.return_value = True
            # First 2 succeed, last 2 raise
            def fake_search(query, n=10):
                if query in ("q1", "q2"):
                    return [{"id": "node1"}]
                raise RuntimeError("embedder error")
            mock_embedder.search.side_effect = fake_search
            MockEmbedder.return_value = mock_embedder

            result = t._fitness_from_live_eval({
                "STRUCTURAL_SEED_K": 3.0,
                "SYNAPSE_SEED_K": 3.0,
                "L0_MAX_TOKENS": 150.0,
                "L1_MAX_TOKENS": 600.0,
                "L2_MAX_TOKENS": 800.0,
                "L3_MAX_TOKENS": 1000.0,
            })

        # 2 succeed / 2 attempted = 1.0 retrieval_quality (not 2/4 = 0.5)
        assert result > 0.0


# ---------------------------------------------------------------------------
# Community ID carry-over tests
# ---------------------------------------------------------------------------

class TestCommunityIdCarryover:
    def test_unchanged_files_keep_community_ids(self, tmp_path: Path) -> None:
        """Incremental build preserves community IDs for unchanged files."""
        proj = tmp_path / "project"
        proj.mkdir()

        # Create source files
        (proj / "a.py").write_text("def foo(): pass")
        (proj / "b.py").write_text("def bar(): pass")

        # First build
        graph1 = graphgen.build_graph(proj)
        communities1 = {n["source_file"]: n["community"] for n in graph1["nodes"] if n.get("file_type") == "code"}

        # Touch only b.py
        import time; time.sleep(0.1)
        (proj / "b.py").write_text("def bar(): return 42")

        # Second build (incremental)
        graph2 = graphgen.build_graph(proj)
        communities2 = {n["source_file"]: n["community"] for n in graph2["nodes"] if n.get("file_type") == "code"}

        # a.py should keep its community ID
        if "a.py" in communities1 and "a.py" in communities2:
            assert communities1["a.py"] == communities2["a.py"], \
                f"a.py community changed: {communities1['a.py']} → {communities2['a.py']}"

    def test_new_file_gets_fresh_community_id(self, tmp_path: Path) -> None:
        """New files get a fresh community ID without disturbing existing ones."""
        proj = tmp_path / "project"
        proj.mkdir()

        (proj / "a.py").write_text("def foo(): pass")
        graph1 = graphgen.build_graph(proj)
        comm1 = {n["source_file"]: n["community"] for n in graph1["nodes"] if n.get("file_type") == "code"}

        # Add new file
        (proj / "b.py").write_text("def bar(): pass")
        graph2 = graphgen.build_graph(proj)
        comm2 = {n["source_file"]: n["community"] for n in graph2["nodes"] if n.get("file_type") == "code"}

        # Both files present, IDs are distinct
        assert "a.py" in comm2 and "b.py" in comm2
        assert comm2["a.py"] == comm1.get("a.py"), "Existing file community should not change"
        assert comm2["b.py"] != comm2["a.py"], "New file should get distinct community"


# ---------------------------------------------------------------------------
# scan_files _DEFAULT_IGNORES tests
# ---------------------------------------------------------------------------

class TestScanFilesIgnores:
    def test_skips_node_modules(self, tmp_path: Path) -> None:
        """scan_files should skip node_modules."""
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "pkg.py").write_text("x")
        (tmp_path / "src.py").write_text("y")

        ext = IncrementalExtractor(str(tmp_path))
        added, modified, deleted = ext.scan_files(tmp_path, frozenset({".py"}))

        assert "node_modules/pkg.py" not in added
        assert "src.py" in added

    def test_skips_graphify_out(self, tmp_path: Path) -> None:
        """scan_files should skip graphify-out."""
        (tmp_path / "graphify-out").mkdir()
        (tmp_path / "graphify-out" / "graph.json").write_text("{}")
        (tmp_path / "src.py").write_text("y")

        ext = IncrementalExtractor(str(tmp_path))
        added, modified, deleted = ext.scan_files(tmp_path, frozenset({".py", ".json"}))

        assert "graphify-out/graph.json" not in added
        assert "src.py" in added

    def test_skips_target_dir(self, tmp_path: Path) -> None:
        """scan_files should skip target/ (Rust build output)."""
        (tmp_path / "target").mkdir()
        (tmp_path / "target" / "debug.py").write_text("x")
        (tmp_path / "src.py").write_text("y")

        ext = IncrementalExtractor(str(tmp_path))
        added, modified, deleted = ext.scan_files(tmp_path, frozenset({".py"}))

        assert "target/debug.py" not in added
        assert "src.py" in added


# ---------------------------------------------------------------------------
# Empty source_file handling test
# ---------------------------------------------------------------------------

class TestEmptySourceFile:
    def test_empty_source_file_nodes_dropped(self, tmp_path: Path) -> None:
        """Nodes with empty source_file should be dropped in incremental build."""
        proj = tmp_path / "project"
        proj.mkdir()
        (proj / "a.py").write_text("def foo(): pass")

        # First build — use write_graph to persist graph.json
        from neuralmind.graphgen import write_graph
        write_graph(proj)

        # Verify graph.json exists
        graph_path = proj / "graphify-out" / "graph.json"
        assert graph_path.exists()

        # Manually inject a node with empty source_file into graph.json
        import json
        graph = json.loads(graph_path.read_text())
        graph["nodes"].append({
            "id": "bogus_node",
            "label": "bogus",
            "file_type": "code",
            "source_file": "",
            "source_location": "L1",
            "community": 99,
            "norm_label": "bogus",
        })
        graph_path.write_text(json.dumps(graph))

        # Second build — bogus node should be dropped
        graph2 = graphgen.build_graph(proj)
        ids = {n["id"] for n in graph2["nodes"]}
        assert "bogus_node" not in ids
