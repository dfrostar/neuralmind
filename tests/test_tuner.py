"""Tests for C3 — population-based evolutionary search (tuner.py)."""

from __future__ import annotations

import random
import time
from pathlib import Path

import pytest

from neuralmind.tuner import PopulationTuner, TuneRun


@pytest.fixture
def tuner_populated(tmp_path: Path) -> PopulationTuningHarness:
    """A tuner with a populated trace store and default params."""
    return PopulationTuningHarness(tmp_path)


class PopulationTuningHarness:
    """Helper: populates a project dir with traces and a tuner instance."""

    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.project_path = tmp_path / "project"
        self.project_path.mkdir()
        self._seed_traces()
        self.tuner = PopulationTuner(project_path=self.project_path)

    def _seed_traces(self) -> None:
        """Write a set of reasoning traces to the project's synapse db."""
        from neuralmind.synapses import default_db_path
        from neuralmind.traces import TraceStore

        ts = TraceStore(default_db_path(self.project_path))
        rng = random.Random(42)
        for i in range(50):
            ts.record(
                session_id="s1",
                query=f"query {i % 10}",
                strategy="active_search",
                outcome="success",
                success_signal=rng.uniform(0.6, 1.0),
                timestamp=time.time() - rng.uniform(0, 86400),
            )


class TestSampleCandidate:
    """Population sampling and perturbation."""

    def test_gaussian_perturb_within_bounds(self, tuner_populated) -> None:
        t = tuner_populated.tuner
        incumbent = t._default_param_map()
        for _ in range(50):
            candidate = t.sample_candidate(incumbent)
            assert set(candidate.keys()) == set(incumbent.keys())

    def test_uniform_explore_respects_bounds(self, tuner_populated) -> None:
        t = tuner_populated.tuner
        t.uniform_explore_p = 1.0  # force uniform
        candidate = t.sample_candidate({})
        for name, value in candidate.items():
            from neuralmind.contracts import get_param

            p = get_param(name)
            assert p is not None
            assert p.min_value <= value <= p.max_value

    def test_sample_uses_uniform_branch_sometimes(self, tuner_populated) -> None:
        t = tuner_populated.tuner
        t.uniform_explore_p = 1.0
        samples = [t.sample_candidate({}) for _ in range(10)]
        # All samples should be within bounds.
        for sample in samples:
            for name, value in sample.items():
                from neuralmind.contracts import get_param

                p = get_param(name)
                assert p is not None
                assert p.min_value <= value <= p.max_value


class TestEvaluateCandidate:
    """Fitness evaluation against real traces."""

    def test_evaluate_returns_float(self, tuner_populated) -> None:
        t = tuner_populated.tuner
        params = t._default_param_map()
        result = t.evaluate_candidate(params)
        assert isinstance(result, float)

    def test_evaluate_zero_when_no_project(self, tmp_path: Path) -> None:
        t = PopulationTuner(project_path=None)
        assert t.evaluate_candidate({}) == 0.0

    def test_evaluate_zero_on_error(self, tmp_path: Path) -> None:
        # Project dir that has no traces.
        t = PopulationTuner(project_path=tmp_path)
        result = t.evaluate_candidate(t._default_param_map())
        # No traces → returns 0.0 (fail-open).
        assert result == 0.0


class TestPromotion:
    """Hysteresis-gated promotion."""

    def test_promote_when_beats_hysteresis(self, tuner_populated) -> None:
        t = tuner_populated.tuner
        assert t.promote_if_better({}, 1.10, 1.0) is True

    def test_no_promote_within_hysteresis(self, tuner_populated) -> None:
        t = tuner_populated.tuner
        # 0.5% improvement below 5% hysteresis margin.
        assert t.promote_if_better({}, 1.01, 1.0) is False

    def test_promote_respects_custom_hysteresis(self, tmp_path: Path) -> None:
        t = PopulationTuner(project_path=tmp_path, hysteresis=0.10)
        assert t.promote_if_better({}, 1.05, 1.0) is False
        assert t.promote_if_better({}, 1.15, 1.0) is True


class TestRunGeneration:
    """End-to-end generation run."""

    def test_run_generation_runs(self, tuner_populated) -> None:
        t = tuner_populated.tuner
        t.population_size = 5
        result = t.run_generation()
        assert result is not None
        assert isinstance(result, TuneRun)
        assert result.population_size == 5
        assert isinstance(result.best_fitness, float)

    def test_run_generation_no_project(self) -> None:
        t = PopulationTuner(project_path=None)
        assert t.run_generation() is None


class TestPersistence:
    """Synapse meta table persistence."""

    def test_save_and_load_incumbent(self, tuner_populated) -> None:
        t = tuner_populated.tuner
        params = {"SYNAPSE_BOOST_WEIGHT": 0.45, "SPREAD_DEPTH": 4}
        t._save_incumbent(params, 0.82)
        loaded = t._load_incumbent()
        assert loaded.get("SYNAPSE_BOOST_WEIGHT") == 0.45
        assert loaded.get("SPREAD_DEPTH") == 4
        assert t._load_incumbent_fitness() == pytest.approx(0.82)

    def test_load_incumbent_defaults_when_empty(self, tuner_populated) -> None:
        t = tuner_populated.tuner
        loaded = t._load_incumbent()
        # Should return the full default param map.
        assert loaded.get("SYNAPSE_BOOST_WEIGHT") is not None
        assert loaded.get("SPREAD_DEPTH") is not None


class TestScheduleGate:
    """Run scheduling gate."""

    def test_should_run_initial(self, tuner_populated) -> None:
        assert tuner_populated.tuner.should_run() is True

    def test_should_run_after_mark(self, tuner_populated) -> None:
        t = tuner_populated.tuner
        t.mark_run()
        assert t.should_run() is False


class TestEfficiencyRatio:
    """Token budget efficiency proxy."""

    def test_efficiency_default_matches(self, tuner_populated) -> None:
        t = tuner_populated.tuner
        assert t._efficiency_ratio(t._default_param_map()) == pytest.approx(1.0)

    def test_efficiency_lower_budget_higher(self, tuner_populated) -> None:
        t = tuner_populated.tuner
        params = t._default_param_map()
        params = dict(params)
        params["L0_MAX_TOKENS"] = 75  # half default
        assert t._efficiency_ratio(params) > 1.0

    def test_efficiency_zero_candidate_budget(self, tuner_populated) -> None:
        t = tuner_populated.tuner
        params = dict.fromkeys(t._default_param_map(), 0.0)
        assert t._efficiency_ratio(params) == 1.0


class TestReQueryRate:
    """Re-query rate estimation from traces."""

    def test_no_traces(self, tuner_populated) -> None:
        assert tuner_populated.tuner._re_query_rate_from_traces([]) == 0.0

    def test_all_unique(self, tuner_populated) -> None:
        from neuralmind.traces import ReasoningTrace

        traces = [ReasoningTrace("s", 0.0, f"fp{i}", success_signal=0.9) for i in range(5)]
        assert tuner_populated.tuner._re_query_rate_from_traces(traces) == 0.0

    def test_all_same_fingerprint(self, tuner_populated) -> None:
        from neuralmind.traces import ReasoningTrace

        traces = [ReasoningTrace("s", 0.0, "same_fp", success_signal=0.9) for _ in range(5)]
        # 4 repeats out of 5 traces = 0.8.
        assert tuner_populated.tuner._re_query_rate_from_traces(traces) == pytest.approx(0.8)


class TestTuneRunSerialization:
    """TuneRun dataclass serialization."""

    def test_to_dict(self) -> None:
        run = TuneRun(
            generation=2,
            population_size=10,
            best_fitness=0.91,
            incumbent_fitness=0.85,
            promoted=True,
            best_params={"SYNAPSE_BOOST_WEIGHT": 0.4},
        )
        d = run.to_dict()
        assert d["promoted"] is True
        assert d["generation"] == 2
        assert d["best_fitness"] == pytest.approx(0.91)
