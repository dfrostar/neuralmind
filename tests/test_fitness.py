"""Tests for the multi-objective fitness function (PRD 2 C1)."""

from __future__ import annotations

import pytest

from neuralmind.fitness import (
    DEFAULT_WEIGHTS,
    FitnessInputs,
    _clamp,
    _parse_weights,
    compute_fitness,
    get_weights,
    session_health_from_events,
    set_weights,
)


class TestParseWeights:
    def test_default_when_empty(self):
        assert _parse_weights(None) == DEFAULT_WEIGHTS
        assert _parse_weights("") == DEFAULT_WEIGHTS

    def test_default_when_malformed(self):
        assert _parse_weights("abc") == DEFAULT_WEIGHTS
        assert _parse_weights("1.0") == DEFAULT_WEIGHTS
        assert _parse_weights("1.0,2.0") == DEFAULT_WEIGHTS
        assert _parse_weights("1.0,2.0,3.0,4.0") == DEFAULT_WEIGHTS

    def test_default_when_negative_sum(self):
        assert _parse_weights("-1.0,-2.0,-3.0") == DEFAULT_WEIGHTS

    def test_parses_and_normalizes(self):
        result = _parse_weights("0.5, 0.3, 0.2")
        assert result == pytest.approx((0.5, 0.3, 0.2))

    def test_normalizes_non_unit_weights(self):
        result = _parse_weights("5, 3, 2")
        assert result == pytest.approx((0.5, 0.3, 0.2))


class TestClamp:
    def test_within_range(self):
        assert _clamp(0.5) == 0.5

    def test_below_lo(self):
        assert _clamp(-0.5) == 0.0

    def test_above_hi_with_bound(self):
        assert _clamp(1.5, hi=1.0) == 1.0

    def test_above_hi_no_bound(self):
        assert _clamp(1.5) == 1.5

    def test_no_upper_bound(self):
        assert _clamp(100.0, lo=0.0) == 100.0


class TestComputeFitness:
    def test_equal_inputs(self):
        inputs = FitnessInputs(retrieval_quality=0.8, efficiency=1.2, session_health=0.9)
        score = compute_fitness(inputs)
        assert 0.0 <= score.total <= 1.0
        assert score.retrieval_quality == 0.8
        assert score.efficiency == 1.2  # not clamped (efficiency > 1.0 is valid)
        assert score.session_health == 0.9

    def test_zero_on_any_axis_dominates(self):
        """Zero on any axis → total = 0 (product form)."""
        for axis in ["retrieval_quality", "efficiency", "session_health"]:
            inputs = FitnessInputs(retrieval_quality=0.8, efficiency=1.0, session_health=0.9)
            setattr(inputs, axis, 0.0)
            score = compute_fitness(inputs)
            assert score.total == pytest.approx(0.0)

    def test_perfect_score(self):
        inputs = FitnessInputs(retrieval_quality=1.0, efficiency=1.0, session_health=1.0)
        score = compute_fitness(inputs)
        assert score.total == pytest.approx(1.0)

    def test_weights_persist(self):
        total = sum(score := compute_fitness(FitnessInputs(0.5, 0.5, 0.5)).weights)
        assert total == pytest.approx(1.0)

    def test_effective_weights_sum_to_one(self):
        score = compute_fitness(FitnessInputs(0.5, 0.5, 0.5))
        assert sum(score.weights) == pytest.approx(1.0)

    def test_efficiency_above_one_not_clamped(self):
        """Efficiency > 1.0 is valid (reduction ratio). Must NOT be clamped."""
        inputs = FitnessInputs(retrieval_quality=0.8, efficiency=1.5, session_health=0.8)
        score = compute_fitness(inputs)
        assert score.efficiency == 1.5

    def test_nan_weight_rejected(self):
        """NaN weights → score = 0 (not NaN)."""
        score = compute_fitness(FitnessInputs(0.5, 1.0, 0.5), weights=(float("nan"), 0.3, 0.2))
        assert score.total == 0.0

    def test_inf_weight_rejected(self):
        """Inf weights → score = 0 (not Inf)."""
        score = compute_fitness(FitnessInputs(0.5, 1.0, 0.5), weights=(float("inf"), 0.3, 0.2))
        assert score.total == 0.0

    def test_negative_weight_rejected(self):
        """Negative weights break product semantics → score = 0."""
        score = compute_fitness(FitnessInputs(0.5, 1.0, 0.5), weights=(-1.0, 0.5, 0.5))
        assert score.total == 0.0

    def test_nan_efficiency_rejected(self):
        """NaN efficiency → score = 0 (not NaN)."""
        score = compute_fitness(FitnessInputs(0.5, float("nan"), 0.5))
        assert score.total == 0.0
        assert score.efficiency == 0.0

    def test_inf_efficiency_clamped_to_max(self):
        """Inf efficiency → clamped to 10.0 (upper bound)."""
        score = compute_fitness(FitnessInputs(0.5, float("inf"), 0.5))
        assert score.efficiency == 10.0


class TestGetSetWeights:
    def test_get_default(self, monkeypatch):
        monkeypatch.delenv("NEURALMIND_FITNESS_WEIGHTS", raising=False)
        assert get_weights(None) == DEFAULT_WEIGHTS

    def test_get_from_env(self, monkeypatch):
        monkeypatch.setenv("NEURALMIND_FITNESS_WEIGHTS", "0.6,0.2,0.2")
        result = get_weights(None)
        assert result == pytest.approx((0.6, 0.2, 0.2))

    def test_set_and_get(self, tmp_path):
        set_weights(tmp_path, (0.6, 0.2, 0.2))
        result = get_weights(tmp_path)
        assert result == pytest.approx((0.6, 0.2, 0.2), abs=1e-3)


class TestSessionHealthFromEvents:
    def test_empty_events(self):
        assert session_health_from_events([]) == 1.0

    def test_override(self):
        assert session_health_from_events([], re_query_rate_override=0.3) == pytest.approx(0.7)

    def test_clamp_low(self):
        assert session_health_from_events([], re_query_rate_override=1.5) == 0.0

    def test_clamp_high(self):
        assert session_health_from_events([], re_query_rate_override=-0.5) == 1.0
