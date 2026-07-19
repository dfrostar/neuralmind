"""Tests for C2 — expanded parameter space (tuning.py)."""

from __future__ import annotations

from neuralmind import tuning
from neuralmind.contracts import TUNABLE_PARAMS, clamp_value, get_param, register_param


class TestParamRegistration:
    """Registry lookup, idempotency, and completeness."""

    def test_all_default_params_registered(self) -> None:
        # init_registry happened at import time; the canonical set must be there.
        expected = {p.name for p in tuning.DEFAULT_PARAMS}
        assert expected == set(TUNABLE_PARAMS.keys())

    def test_register_param_idempotent(self) -> None:
        original = get_param("SYNAPSE_BOOST_WEIGHT")
        assert original is not None
        register_param(original)
        assert get_param("SYNAPSE_BOOST_WEIGHT") is original

    def test_known_param_lookup(self) -> None:
        p = get_param("SPREAD_DEPTH")
        assert p is not None
        assert p.min_value <= p.default <= p.max_value

    def test_unknown_param_lookup(self) -> None:
        assert get_param("NONEXISTENT") is None


class TestBoundsAndClamping:
    """Bounds queries and clamping behaviour."""

    def test_get_bounds_known(self) -> None:
        lo, hi = tuning.get_bounds("SYNAPSE_BOOST_WEIGHT")
        p = get_param("SYNAPSE_BOOST_WEIGHT")
        assert p is not None
        assert lo == p.min_value
        assert hi == p.max_value

    def test_get_bounds_unknown(self) -> None:
        # Fail-open: unknown params get a neutral (0, 1) range.
        assert tuning.get_bounds("NONEXISTENT") == (0.0, 1.0)

    def test_clamp_within_bounds(self) -> None:
        assert clamp_value("SYNAPSE_BOOST_WEIGHT", 1.0) == 1.0

    def test_clamp_below_min(self) -> None:
        p = get_param("SYNAPSE_BOOST_WEIGHT")
        assert p is not None
        assert clamp_value("SYNAPSE_BOOST_WEIGHT", -5.0) >= p.min_value

    def test_clamp_above_max(self) -> None:
        p = get_param("SYNAPSE_BOOST_WEIGHT")
        assert p is not None
        assert clamp_value("SYNAPSE_BOOST_WEIGHT", 99.0) <= p.max_value

    def test_clamp_unknown_returns_unmodified(self) -> None:
        assert clamp_value("NONEXISTENT", 7.5) == 7.5

    def test_clamp_int_param(self) -> None:
        p = get_param("SPREAD_DEPTH")
        assert p is not None
        assert clamp_value("SPREAD_DEPTH", 999) == p.max_value
        assert clamp_value("SPREAD_DEPTH", -1) == p.min_value


class TestDefaults:
    """Default values match legacy hardcoded constants."""

    def test_default_matches_context_selector_constants(self) -> None:
        # The hardcoded constants the selector currently uses must be
        # recoverable as defaults, so no behaviour change when wiring later.
        assert get_param("SYNAPSE_BOOST_WEIGHT").default == 0.3
        assert get_param("STRUCTURAL_BOOST_WEIGHT").default == 0.35
        assert get_param("L0_MAX_TOKENS").default == 150
        assert get_param("L1_MAX_TOKENS").default == 600
        assert get_param("L2_MAX_TOKENS").default == 800
        assert get_param("L3_MAX_TOKENS").default == 1000

    def test_get_default_unknown(self) -> None:
        assert tuning.get_default("NONEXISTENT") == 0.0


class TestPersistenceRoundTrip:
    """Params can be saved to and loaded from a SynapseStore."""

    def test_save_and_load_params(self, tmp_path) -> None:
        params = {
            "SYNAPSE_BOOST_WEIGHT": 0.45,
            "SPREAD_DEPTH": 4,
            "DECAY_RATE_MAX": 90.0,
        }
        assert tuning.save_params(tmp_path, params) is True
        loaded = tuning.load_params(tmp_path)
        assert loaded == params

    def test_save_unknown_param_is_skipped(self, tmp_path) -> None:
        tuning.save_params(tmp_path, {"NONEXISTENT": 99.0, "SPREAD_DEPTH": 4})
        loaded = tuning.load_params(tmp_path)
        assert "NONEXISTENT" not in loaded
        assert loaded.get("SPREAD_DEPTH") == 4

    def test_load_empty_project(self, tmp_path) -> None:
        assert tuning.load_params(tmp_path) == {}

    def test_save_returns_false_on_error(self, tmp_path) -> None:
        bad = tmp_path / "not_a_directory"
        bad.write_text("This is a file, not a directory.")
        result = tuning.save_params(bad / "inside_file", {"SPREAD_DEPTH": 4})
        assert result is False


class TestResolveEffective:
    """Effective params merge persisted on top of defaults."""

    def test_defaults_when_no_persistence(self, tmp_path) -> None:
        eff = tuning.resolve_effective(tmp_path)
        assert eff["SYNAPSE_BOOST_WEIGHT"] == 0.3
        assert eff["SPREAD_DEPTH"] == 2

    def test_persisted_overrides_default(self, tmp_path) -> None:
        tuning.save_params(tmp_path, {"SYNAPSE_BOOST_WEIGHT": 0.88})
        eff = tuning.resolve_effective(tmp_path)
        assert eff["SYNAPSE_BOOST_WEIGHT"] == 0.88
        # Other params remain defaulted.
        assert eff["SPREAD_DEPTH"] == 2

    def test_resolve_effective_without_project(self) -> None:
        # Caller passes ``None`` to get the pure default map.
        eff = tuning.resolve_effective(None)
        assert eff["SYNAPSE_BOOST_WEIGHT"] == 0.3
        assert len(eff) == len(TUNABLE_PARAMS)


class TestEffectiveAccessors:
    """Typed effective-value accessors."""

    def test_effective_int(self, tmp_path) -> None:
        tuning.save_params(tmp_path, {"L0_MAX_TOKENS": 200})
        assert tuning.effective_int(tmp_path, "L0_MAX_TOKENS") == 200

    def test_effective_float(self, tmp_path) -> None:
        tuning.save_params(tmp_path, {"SYNAPSE_BOOST_WEIGHT": 0.55})
        assert tuning.effective_float(tmp_path, "SYNAPSE_BOOST_WEIGHT") == 0.55

    def test_effective_defaults_without_persistence(self, tmp_path) -> None:
        assert tuning.effective_int(tmp_path, "L0_MAX_TOKENS") == 150
        assert tuning.effective_float(tmp_path, "DECAY_RATE_MIN") == 3.0
