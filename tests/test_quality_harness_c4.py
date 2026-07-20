"""Tests for C4 — CI-gated tuner promotion via QualityHarness."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from neuralmind.quality import QualityThresholds
from neuralmind.quality_harness import (
    HarnessVerdict,
    PromotionDecision,
    QualityHarness,
)
from neuralmind.tuner import PopulationTuner


class TestHarnessVerdict:
    """HarnessVerdict dataclass."""

    def test_defaults(self):
        v = HarnessVerdict()
        assert v.fitness == 0.0
        assert v.ragas_score == 0.0
        assert v.retrieval_score == 0.0
        assert v.passed is False
        assert v.failures == []
        assert v.per_query == []


class TestPromotionDecision:
    """PromotionDecision dataclass."""

    def test_defaults(self):
        d = PromotionDecision()
        assert d.verdict == "hold"
        assert d.reason == ""
        assert d.candidate_fitness == 0.0
        assert d.incumbent_fitness == 0.0
        assert d.harness_verdict is None


class TestQualityHarnessEvaluate:
    """QualityHarness.evaluate() — independent validation gate."""

    def test_fail_open_no_fixtures(self, tmp_path: Path):
        """No fixtures available → fail-open (passed=True, fitness=0.0)."""
        harness = QualityHarness(project_path=tmp_path)
        verdict = harness.evaluate({})
        assert verdict.passed is True
        assert verdict.fitness == 0.0

    def test_fail_open_no_embedder(self, tmp_path: Path):
        """Embedder unavailable → fail-open."""
        harness = QualityHarness(project_path=tmp_path)
        with patch(
            "neuralmind.fixtures.load_fixture_queries",
            return_value=[MagicMock(query="test", expected_node_ids=("node1",))],
        ):
            verdict = harness.evaluate({})
            assert verdict.passed is True
            assert verdict.fitness == 0.0

    def test_evaluate_with_fixtures_and_embedder(self, tmp_path: Path):
        """With fixtures and embedder, returns real verdict."""
        from neuralmind.fixtures import FixtureQuery

        fixtures = [
            FixtureQuery(query="auth handler", expected_node_ids=("node1",)),
            FixtureQuery(query="user model", expected_node_ids=("node2",)),
        ]

        mock_embedder = MagicMock()
        mock_embedder.load_graph.return_value = True
        mock_embedder.search.return_value = [
            {"id": "node1", "score": 0.9},
            {"id": "node2", "score": 0.8},
        ]

        harness = QualityHarness(project_path=tmp_path)
        with patch(
            "neuralmind.fixtures.load_fixture_queries",
            return_value=fixtures,
        ), patch(
            "neuralmind.embedder.GraphEmbedder",
            return_value=mock_embedder,
        ):
            verdict = harness.evaluate({})

        assert verdict.passed is True
        assert verdict.fitness > 0.0
        assert verdict.retrieval_score > 0.0
        assert verdict.ragas_score > 0.0
        assert len(verdict.per_query) == 2

    def test_evaluate_with_custom_thresholds(self, tmp_path: Path):
        """Custom thresholds can cause failure."""
        from neuralmind.fixtures import FixtureQuery

        fixtures = [
            FixtureQuery(query="test", expected_node_ids=("node1",)),
        ]

        mock_embedder = MagicMock()
        mock_embedder.load_graph.return_value = True
        mock_embedder.search.return_value = []  # no results → bad retrieval

        thresholds = QualityThresholds(min_mrr=0.99, min_answerability=0.99)
        harness = QualityHarness(project_path=tmp_path, thresholds=thresholds)
        with patch(
            "neuralmind.fixtures.load_fixture_queries",
            return_value=fixtures,
        ), patch(
            "neuralmind.embedder.GraphEmbedder",
            return_value=mock_embedder,
        ):
            verdict = harness.evaluate({})

        assert verdict.passed is False
        assert len(verdict.failures) > 0


class TestQualityHarnessDecide:
    """QualityHarness.decide() — gate logic."""

    def test_promote_when_passes_and_beats_hysteresis(self):
        harness = QualityHarness(project_path=Path("/tmp"))
        verdict = HarnessVerdict(fitness=0.8, passed=True, failures=[])
        decision = harness.decide(
            candidate_fitness=0.8,
            incumbent_fitness=0.5,
            harness_verdict=verdict,
            hysteresis=0.05,
        )
        assert decision.verdict == "promote"
        assert "hysteresis" in decision.reason

    def test_hold_when_within_hysteresis(self):
        harness = QualityHarness(project_path=Path("/tmp"))
        verdict = HarnessVerdict(fitness=0.52, passed=True, failures=[])
        decision = harness.decide(
            candidate_fitness=0.52,
            incumbent_fitness=0.5,
            harness_verdict=verdict,
            hysteresis=0.05,
        )
        assert decision.verdict == "hold"
        assert "hysteresis" in decision.reason

    def test_rollback_when_below_incumbent(self):
        harness = QualityHarness(project_path=Path("/tmp"))
        verdict = HarnessVerdict(fitness=0.4, passed=True, failures=[])
        decision = harness.decide(
            candidate_fitness=0.4,
            incumbent_fitness=0.5,
            harness_verdict=verdict,
            hysteresis=0.05,
        )
        assert decision.verdict == "rollback"
        assert "below incumbent" in decision.reason

    def test_hold_when_harness_fails(self):
        harness = QualityHarness(project_path=Path("/tmp"))
        verdict = HarnessVerdict(
            fitness=0.8, passed=False, failures=["MRR 0.3 < floor 0.5"]
        )
        decision = harness.decide(
            candidate_fitness=0.8,
            incumbent_fitness=0.5,
            harness_verdict=verdict,
            hysteresis=0.05,
        )
        assert decision.verdict == "hold"
        assert "harness failed" in decision.reason


class TestQualityHarnessIntegration:
    """Integration: harness + tuner wiring."""

    def test_tuner_promotes_with_harness(self, tmp_path: Path):
        """Tuner uses harness gate when present."""
        from neuralmind.tuner import PopulationTuner

        harness = QualityHarness(project_path=tmp_path)
        tuner = PopulationTuner(project_path=tmp_path, harness=harness)
        assert tuner.harness is harness

    def test_tuner_falls_back_without_harness(self, tmp_path: Path):
        """Tuner without harness uses hysteresis-only promotion."""
        from neuralmind.tuner import PopulationTuner

        tuner = PopulationTuner(project_path=tmp_path, harness=None)
        assert tuner.harness is None
        # promote_with_harness falls back to hysteresis-only
        decision = tuner.promote_with_harness({}, 0.5, 1.0)
        assert decision.verdict == "hold"  # below hysteresis

    def test_promotion_decision_logging(self, tmp_path: Path):
        """Decision recorded in synapse meta table."""

        harness = QualityHarness(project_path=tmp_path)
        tuner = PopulationTuner(project_path=tmp_path, harness=harness)

        # Create a decision and record it
        verdict = HarnessVerdict(fitness=0.8, passed=True, failures=[])
        decision = PromotionDecision(
            verdict="promote",
            reason="test",
            candidate_fitness=0.8,
            incumbent_fitness=0.5,
            harness_verdict=verdict,
        )
        tuner._record_decision(decision)

        # Verify it was persisted
        store = tuner._store()
        raw = store.get_meta("self_improve:tuner_last_decision")
        assert raw is not None
        data = json.loads(raw)
        assert data["verdict"] == "promote"
        assert data["candidate_fitness"] == 0.8
