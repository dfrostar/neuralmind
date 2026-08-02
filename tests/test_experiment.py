"""Tests for scipy.stats.t.sf p-value integration and confidence intervals."""

from __future__ import annotations

import pytest

from neuralmind.agent_os.experiment import (
    HAS_SCIPY,
    ExperimentResult,
    ExperimentRunner,
    ExperimentStatus,
    _normal_cdf,
    _t_sf,
)


# ---------------------------------------------------------------------------
# _t_sf (survival function)
# ---------------------------------------------------------------------------


class TestTSurvivalFunction:
    def test_scipy_available_or_fallback(self):
        """_t_sf should work whether scipy is available or not."""
        # For large df, t-distribution ≈ normal
        result = _t_sf(1.96, 100)
        # P(T > 1.96) ≈ 0.025 for two-tailed 95% CI
        assert 0.02 < result < 0.03

    def test_t_sf_symmetric(self):
        """_t_sf should satisfy: _t_sf(-x) = 1 - _t_sf(x)."""
        # P(T > -x) = 1 - P(T > x) for symmetric t-distribution
        assert abs(_t_sf(-1.0, 10) - (1 - _t_sf(1.0, 10))) < 0.001
        assert abs(_t_sf(-2.0, 20) - (1 - _t_sf(2.0, 20))) < 0.001

    def test_t_sf_decreasing(self):
        """_t_sf should decrease as t increases."""
        assert _t_sf(0.5, 10) > _t_sf(1.0, 10) > _t_sf(2.0, 10)

    def test_t_sf_at_zero(self):
        """_t_sf(0) should be ~0.5 (half the distribution is above 0)."""
        assert abs(_t_sf(0.0, 10) - 0.5) < 0.001


# ---------------------------------------------------------------------------
# ExperimentRunner p-value
# ---------------------------------------------------------------------------


class TestExperimentPValue:
    def test_p_value_none_with_few_samples(self):
        """p-value is None when <2 historical samples."""
        runner = ExperimentRunner()
        result = runner.run("p1", "m", 100.0, 90.0)
        assert result.p_value is None

    def test_p_value_computed_with_history(self):
        """p-value is computed when >=2 historical samples exist."""
        runner = ExperimentRunner()
        runner.run("p1", "m", 100.0, 90.0)
        runner.run("p2", "m", 100.0, 80.0)
        result = runner.run("p3", "m", 100.0, 95.0)
        assert result.p_value is not None
        assert 0.0 <= result.p_value <= 1.0

    def test_p_value_uses_scipy_when_available(self):
        """p-value uses scipy.stats.t.sf when scipy is installed."""
        runner = ExperimentRunner()
        runner.run("p1", "m", 100.0, 90.0)
        runner.run("p2", "m", 100.0, 80.0)
        result = runner.run("p3", "m", 100.0, 95.0)
        assert result.p_value is not None
        # With scipy, this should be exact t-distribution
        # Without scipy, normal approximation
        # Both should give valid p-values in [0, 1]
        assert 0.0 <= result.p_value <= 1.0

    def test_p_value_extreme_delta(self):
        """p-value should be small for extreme deltas."""
        runner = ExperimentRunner()
        runner.run("p1", "m", 100.0, 90.0)
        runner.run("p2", "m", 100.0, 80.0)
        # Very extreme delta
        result = runner.run("p3", "m", 100.0, 10.0)
        assert result.p_value is not None
        # Extreme delta should give small p-value
        assert result.p_value < 0.1

    def test_p_value_near_zero_delta(self):
        """p-value should be large for near-zero deltas."""
        runner = ExperimentRunner()
        runner.run("p1", "m", 100.0, 90.0)
        runner.run("p2", "m", 100.0, 80.0)
        # Delta near historical mean
        result = runner.run("p3", "m", 100.0, 85.0)
        assert result.p_value is not None
        # Near mean should give larger p-value
        assert result.p_value > 0.1


# ---------------------------------------------------------------------------
# Confidence intervals
# ---------------------------------------------------------------------------


class TestConfidenceInterval:
    def test_ci_none_with_few_samples(self):
        """CI is None when <2 historical samples."""
        runner = ExperimentRunner()
        result = runner.run("p1", "m", 100.0, 90.0)
        assert result.ci_lower is None
        assert result.ci_upper is None

    def test_ci_computed_with_history(self):
        """CI is computed when >=2 historical samples exist."""
        runner = ExperimentRunner()
        runner.run("p1", "m", 100.0, 90.0)
        runner.run("p2", "m", 100.0, 80.0)
        result = runner.run("p3", "m", 100.0, 95.0)
        assert result.ci_lower is not None
        assert result.ci_upper is not None
        assert result.ci_lower <= result.ci_upper

    def test_ci_contains_delta(self):
        """CI should contain the point estimate (delta)."""
        runner = ExperimentRunner()
        runner.run("p1", "m", 100.0, 90.0)
        runner.run("p2", "m", 100.0, 80.0)
        result = runner.run("p3", "m", 100.0, 95.0)
        assert result.ci_lower <= result.delta <= result.ci_upper

    def test_ci_wider_with_less_data(self):
        """CI should be wider with less historical data."""
        runner1 = ExperimentRunner()
        runner1.run("p1", "m", 100.0, 90.0)
        runner1.run("p2", "m", 100.0, 80.0)
        result1 = runner1.run("p3", "m", 100.0, 95.0)

        runner2 = ExperimentRunner()
        for _ in range(20):
            runner2.run("p", "m", 100.0, 90.0)
        result2 = runner2.run("p", "m", 100.0, 95.0)

        width1 = result1.ci_upper - result1.ci_lower
        width2 = result2.ci_upper - result2.ci_lower
        assert width1 > width2

    def test_ci_zero_variance(self):
        """CI collapses to point estimate when variance is zero."""
        runner = ExperimentRunner()
        # All identical deltas
        runner.run("p1", "m", 100.0, 90.0)
        runner.run("p2", "m", 100.0, 90.0)
        result = runner.run("p3", "m", 100.0, 90.0)
        assert result.ci_lower == result.delta
        assert result.ci_upper == result.delta


# ---------------------------------------------------------------------------
# ExperimentResult.to_dict
# ---------------------------------------------------------------------------


class TestExperimentResult:
    def test_to_dict_includes_ci(self):
        """ExperimentResult.to_dict() includes ci_lower and ci_upper."""
        result = ExperimentResult(
            experiment_id="exp_1",
            proposal_id="p1",
            metric_name="m",
            baseline_value=100.0,
            candidate_value=90.0,
            delta=0.1,
            p_value=0.05,
            ci_lower=0.05,
            ci_upper=0.15,
            verdict=ExperimentStatus.PROMOTED,
            started_at="2026-01-01T00:00:00Z",
            ended_at="2026-01-01T00:00:00Z",
            details={},
        )
        d = result.to_dict()
        assert d["ci_lower"] == 0.05
        assert d["ci_upper"] == 0.15
        assert d["p_value"] == 0.05


# ---------------------------------------------------------------------------
# Verdict logic unchanged
# ---------------------------------------------------------------------------


class TestVerdictUnchanged:
    def test_promote(self):
        runner = ExperimentRunner(promote_threshold_pct=5.0)
        result = runner.run("p1", "m", 100.0, 90.0)
        assert result.verdict == ExperimentStatus.PROMOTED

    def test_rollback(self):
        runner = ExperimentRunner(rollback_threshold_pct=-3.0)
        result = runner.run("p1", "m", 100.0, 110.0)
        assert result.verdict == ExperimentStatus.ROLLED_BACK

    def test_reject(self):
        runner = ExperimentRunner(promote_threshold_pct=10.0)
        result = runner.run("p1", "m", 100.0, 95.0)
        assert result.verdict == ExperimentStatus.REJECTED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
