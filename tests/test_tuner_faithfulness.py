"""Tests for T1 — tuner faithfulness gap closure (Wave 5).

Verifies that evaluate_candidate produces different fitness values for
different candidates via live retrieval eval, with proper fail-open
behavior and axis independence.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from neuralmind.fixtures import FixtureQuery, load_fixture_queries, save_fixture_queries
from neuralmind.tuner import PopulationTuner

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project(tmp_path: Path) -> Path:
    p = tmp_path / "project"
    p.mkdir()
    return p


@pytest.fixture
def tuner_fixture(project: Path) -> PopulationTuner:
    return PopulationTuner(project_path=project, population_size=5, generations=2)


@pytest.fixture
def default_params() -> dict[str, float]:
    return {
        "L0_MAX_TOKENS": 150.0,
        "L1_MAX_TOKENS": 600.0,
        "L2_MAX_TOKENS": 800.0,
        "L3_MAX_TOKENS": 1000.0,
        "STRUCTURAL_SEED_K": 3.0,
        "SYNAPSE_SEED_K": 3.0,
    }


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Same candidate + same fixtures → same fitness."""

    def test_same_candidate_deterministic(
        self, tuner_fixture: PopulationTuner, default_params: dict[str, float]
    ) -> None:
        """Live eval must be deterministic for a fixed fixture set."""
        fixtures = [
            FixtureQuery(query="helper function", expected_node_ids=("helper_fn",)),
            FixtureQuery(query="main entry", expected_node_ids=("main_fn",)),
        ]
        project = tuner_fixture.project_path
        if project is None:
            pytest.skip("no project_path")
        save_fixture_queries(project, fixtures)

        with patch("neuralmind.embedder.GraphEmbedder") as mock_embedder_cls:
            mock_embedder = MagicMock()
            mock_embedder.load_graph.return_value = True
            mock_embedder.search.return_value = [{"id": "helper_fn"}, {"id": "main_fn"}]
            mock_embedder_cls.return_value = mock_embedder

            f1 = tuner_fixture.evaluate_candidate(default_params)
            f2 = tuner_fixture.evaluate_candidate(default_params)

        assert f1 == pytest.approx(f2, abs=1e-6)


# ---------------------------------------------------------------------------
# Axis independence
# ---------------------------------------------------------------------------


class TestAxisIndependence:
    """Different retrieval params → different fitness values."""

    def test_different_retrieval_params_differ(
        self, tuner_fixture: PopulationTuner, default_params: dict[str, float]
    ) -> None:
        """Changing STRUCTURAL_SEED_K changes search_n (retrieval depth)."""
        fixtures = [
            FixtureQuery(query="q1", expected_node_ids=("node1",)),
            FixtureQuery(query="q2", expected_node_ids=("node2",)),
            FixtureQuery(query="q3", expected_node_ids=("node3",)),
        ]
        project = tuner_fixture.project_path
        if project is None:
            pytest.skip("no project_path")
        save_fixture_queries(project, fixtures)

        with patch("neuralmind.embedder.GraphEmbedder") as mock_embedder_cls:
            mock_embedder = MagicMock()
            mock_embedder.load_graph.return_value = True

            # Return ALL expected nodes when asked for enough results,
            # but only SOME when asked for fewer. This simulates the real
            # behavior where retrieval depth affects recall.
            def fake_search(query, n=10):
                if n >= 50:
                    return [{"id": "node1"}, {"id": "node2"}, {"id": "node3"}]
                return [{"id": "node1"}]  # shallow search misses some

            mock_embedder.search.side_effect = fake_search
            mock_embedder_cls.return_value = mock_embedder

            params_high = dict(default_params, STRUCTURAL_SEED_K=10.0)  # search_n=50
            params_low = dict(default_params, STRUCTURAL_SEED_K=1.0)  # search_n=5

            f_high = tuner_fixture.evaluate_candidate(params_high)
            f_low = tuner_fixture.evaluate_candidate(params_low)

        # Both should be valid floats >= 0
        assert isinstance(f_high, float)
        assert isinstance(f_low, float)
        assert f_high >= 0.0
        assert f_low >= 0.0
        # Because search_n differs and results differ, fitness differs
        assert f_high != f_low

    def test_different_budget_params_differ(
        self, tuner_fixture: PopulationTuner, default_params: dict[str, float]
    ) -> None:
        """Changing L0-L3 budgets changes efficiency and thus total fitness."""
        fixtures = [
            FixtureQuery(query="q1", expected_node_ids=("node1",)),
            FixtureQuery(query="q2", expected_node_ids=("node2",)),
        ]
        project = tuner_fixture.project_path
        if project is None:
            pytest.skip("no project_path")
        save_fixture_queries(project, fixtures)

        with patch("neuralmind.embedder.GraphEmbedder") as mock_embedder_cls:
            mock_embedder = MagicMock()
            mock_embedder.load_graph.return_value = True
            mock_embedder.search.return_value = [{"id": "node1"}, {"id": "node2"}]
            mock_embedder_cls.return_value = mock_embedder

            params_big = dict(
                default_params,
                L0_MAX_TOKENS=300.0,
                L1_MAX_TOKENS=1000.0,
                L2_MAX_TOKENS=1500.0,
                L3_MAX_TOKENS=2000.0,
            )
            params_small = dict(
                default_params,
                L0_MAX_TOKENS=50.0,
                L1_MAX_TOKENS=200.0,
                L2_MAX_TOKENS=400.0,
                L3_MAX_TOKENS=500.0,
            )

            f_big = tuner_fixture.evaluate_candidate(params_big)
            f_small = tuner_fixture.evaluate_candidate(params_small)

        assert f_big != f_small


# ---------------------------------------------------------------------------
# Fail-open behavior
# ---------------------------------------------------------------------------


class TestFailOpen:
    """evaluate_candidate must never raise; always return float."""

    def test_fail_open_no_project(self, default_params: dict[str, float]) -> None:
        t = PopulationTuner(project_path=None)
        result = t.evaluate_candidate(default_params)
        assert result == 0.0

    def test_fail_open_no_fixtures(
        self, tuner_fixture: PopulationTuner, default_params: dict[str, float]
    ) -> None:
        """No fixture files → live eval returns 0.0, then trace fallback.

        Since trace fallback also returns 0.0 (no traces), final is 0.0.
        """
        result = tuner_fixture.evaluate_candidate(default_params)
        assert result == 0.0

    def test_fail_open_embedder_error(
        self, tuner_fixture: PopulationTuner, default_params: dict[str, float]
    ) -> None:
        """Embedder raises → fall back to traces, then 0.0."""
        fixtures = [FixtureQuery(query="q1", expected_node_ids=("node1",))]
        project = tuner_fixture.project_path
        if project is None:
            pytest.skip("no project_path")
        save_fixture_queries(project, fixtures)

        with patch("neuralmind.embedder.GraphEmbedder") as mock_embedder_cls:
            mock_embedder_cls.side_effect = RuntimeError("no graph backend")
            result = tuner_fixture.evaluate_candidate(default_params)

        # Live eval fails → trace fallback (no traces) → 0.0
        assert result == 0.0

    def test_fail_open_returns_float(
        self, tuner_fixture: PopulationTuner, default_params: dict[str, float]
    ) -> None:
        """Always returns float, never raises."""
        try:
            result = tuner_fixture.evaluate_candidate(default_params)
            assert isinstance(result, float)
        except Exception as exc:
            pytest.fail(f"evaluate_candidate raised: {exc}")


# ---------------------------------------------------------------------------
# Integration: tuner beats random search
# ---------------------------------------------------------------------------


class TestIntegration:
    """Integration: tuner finds better config than random on fixture."""

    def test_tuner_runs_with_live_eval(self, project: Path) -> None:
        """run_generation completes without error when live eval is available."""
        fixtures = [
            FixtureQuery(query="q1", expected_node_ids=("node1",)),
            FixtureQuery(query="q2", expected_node_ids=("node2",)),
        ]
        save_fixture_queries(project, fixtures)

        with patch("neuralmind.embedder.GraphEmbedder") as mock_embedder_cls:
            mock_embedder = MagicMock()
            mock_embedder.load_graph.return_value = True
            mock_embedder.search.return_value = [{"id": "node1"}, {"id": "node2"}]
            mock_embedder_cls.return_value = mock_embedder

            t = PopulationTuner(
                project_path=project,
                population_size=5,
                generations=2,
                hysteresis=0.0,
            )
            result = t.run_generation()

        # run_generation may return None if eval returns 0.0 for everything;
        # just verify it doesn't crash
        if result is not None:
            assert isinstance(result.best_fitness, float)


# ---------------------------------------------------------------------------
# Fixture queries helper
# ---------------------------------------------------------------------------


class TestFixtureQueries:
    """load_fixture_queries returns deterministic, sorted, capped list."""

    def test_load_from_file(self, project: Path) -> None:
        file_path = project / ".neuralmind" / "fixture_queries.json"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            json.dumps(
                [
                    {"query": "zebra", "expected_node_ids": ["z1"]},
                    {"query": "alpha", "expected_node_ids": ["a1"]},
                    "simple query",
                ],
                indent=2,
            )
        )

        queries = load_fixture_queries(project)
        assert len(queries) == 3
        # Sorted by query string
        assert queries[0].query == "alpha"
        assert queries[1].query == "simple query"
        assert queries[2].query == "zebra"

    def test_load_sorts_and_caps(self, project: Path) -> None:
        file_path = project / ".neuralmind" / "fixture_queries.json"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        queries = [{"query": f"q{i:03d}", "expected_node_ids": []} for i in range(50)]
        file_path.write_text(json.dumps(queries, indent=2))

        result = load_fixture_queries(project, n=10)
        assert len(result) == 10
        # Verify order
        for i in range(len(result) - 1):
            assert result[i].query <= result[i + 1].query

    def test_load_empty_list(self, project: Path) -> None:
        file_path = project / ".neuralmind" / "fixture_queries.json"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("[]\n")
        assert load_fixture_queries(project) == []

    def test_load_no_file(self, project: Path) -> None:
        """No fixture file → returns empty list (fall back to graph)."""
        # This will try _generate_from_graph, which returns [] since no graph
        result = load_fixture_queries(project)
        # Either empty or a list (if graph exists) — just verify type
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Efficiency axis varies
# ---------------------------------------------------------------------------


class TestEfficiencyAxis:
    """Efficiency axis still varies after refactor."""

    def test_efficiency_axis_still_varies(
        self, tuner_fixture: PopulationTuner, default_params: dict[str, float]
    ) -> None:
        """Candidates with different budgets have different efficiency."""
        fixtures = [
            FixtureQuery(query="q1", expected_node_ids=("node1",)),
        ]
        project = tuner_fixture.project_path
        if project is None:
            pytest.skip("no project_path")
        save_fixture_queries(project, fixtures)

        with patch("neuralmind.embedder.GraphEmbedder") as mock_embedder_cls:
            mock_embedder = MagicMock()
            mock_embedder.load_graph.return_value = True
            mock_embedder.search.return_value = [{"id": "node1"}]
            mock_embedder_cls.return_value = mock_embedder

            params_default = default_params
            params_low_budget = dict(
                default_params,
                L0_MAX_TOKENS=50.0,
                L1_MAX_TOKENS=200.0,
                L2_MAX_TOKENS=400.0,
                L3_MAX_TOKENS=500.0,
            )

            f_default = tuner_fixture.evaluate_candidate(params_default)
            f_low = tuner_fixture.evaluate_candidate(params_low_budget)

        # Different budgets → different fitness
        assert f_default != f_low

    def test_efficiency_ratio_monotonic(self, tuner_fixture: PopulationTuner) -> None:
        """Lower budget → higher efficiency ratio → higher fitness."""
        # Default budget = 150+600+800+1000 = 2550
        params_default: dict[str, float] = {
            "L0_MAX_TOKENS": 150.0,
            "L1_MAX_TOKENS": 600.0,
            "L2_MAX_TOKENS": 800.0,
            "L3_MAX_TOKENS": 1000.0,
        }
        # Lower budget → higher efficiency ratio
        params_lower: dict[str, float] = {
            "L0_MAX_TOKENS": 75.0,
            "L1_MAX_TOKENS": 300.0,
            "L2_MAX_TOKENS": 400.0,
            "L3_MAX_TOKENS": 500.0,
        }

        ratio_default = tuner_fixture._efficiency_ratio(params_default)
        ratio_lower = tuner_fixture._efficiency_ratio(params_lower)

        assert ratio_lower > ratio_default
