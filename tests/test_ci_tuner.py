"""Tests for C4 — CI-gated tuner promotion."""
import pytest
from unittest.mock import MagicMock, patch
from neuralmind.ci_tuner import CIGatedTuner, PromotionVerdict, run_ci_gated_promotion


class TestCIGatedTuner:
    def test_builds_tuner_with_defaults(self):
        tuner = CIGatedTuner(project_path=None)
        assert tuner.tuner is not None

    def test_run_ci_eval_returns_verdict(self):
        # Can't run real tuner without project, but verify structure
        tuner = CIGatedTuner(project_path=None)
        # With no project_path, tuner.run_generation returns None
        verdict = tuner.run_ci_eval()
        assert isinstance(verdict, PromotionVerdict)

    def test_promote_false_without_project(self):
        tuner = CIGatedTuner(project_path=None)
        assert not tuner.promote({"L0_MAX_TOKENS": 100})

    def test_verdict_to_dict(self):
        verdict = PromotionVerdict(
            promoted=True,
            candidate_fitness=0.8,
            incumbent_fitness=0.6,
            best_params={"L0_MAX_TOKENS": 200},
            reason="test promotion",
        )
        d = verdict.to_dict()
        assert d["promoted"]
        assert d["candidate_fitness"] == 0.8
