"""Tests for A3 — learned per-edge decay (learned_decay.py)."""

from __future__ import annotations

import time

import pytest

from neuralmind import learned_decay


class TestDefaultBounds:
    """Read (DECAY_RATE_MIN, DECAY_RATE_MAX) from effective param map."""

    def test_default_bounds(self) -> None:
        lo, hi = learned_decay.default_bounds()
        assert lo == 3.0
        assert hi == 120.0

    def test_bounds_ordering(self) -> None:
        lo, hi = learned_decay.default_bounds()
        assert lo < hi


class TestComputeEdgeHalfLife:
    """Per-edge rate computation."""

    def test_frequent_reinforcement_longer(self) -> None:
        now = time.time()
        # 100 activations over 10 days = 10/day
        frequent = learned_decay.compute_edge_half_life(
            activation_count=100,
            last_activated=now - 3600,
            first_activated=now - 864000,
            namespace_default=30.0,
        )
        rare = learned_decay.compute_edge_half_life(
            activation_count=2,
            last_activated=now - 3600,
            first_activated=now - 864000,
            namespace_default=30.0,
        )
        assert frequent > rare

    def test_bounded_within_range(self) -> None:
        now = time.time()
        for count in [1, 10, 100, 1000]:
            result = learned_decay.compute_edge_half_life(
                activation_count=count,
                last_activated=now - 3600,
                first_activated=now - 86400,
                namespace_default=30.0,
            )
            lo, hi = learned_decay.default_bounds()
            assert lo <= result <= hi

    def test_new_edge_falls_back(self) -> None:
        now = time.time()
        # first_activated == now → too young.
        result = learned_decay.compute_edge_half_life(
            activation_count=5,
            last_activated=now,
            first_activated=now,
            namespace_default=30.0,
        )
        assert result == 30.0

    def test_decay_increases_with_stale(self) -> None:
        now = time.time()
        fresh = learned_decay.compute_edge_half_life(
            activation_count=100,
            last_activated=now - 3600,
            first_activated=now - 864000,
            namespace_default=30.0,
        )
        stale = learned_decay.compute_edge_half_life(
            activation_count=100,
            last_activated=now - 864000,
            first_activated=now - 864000,
            namespace_default=30.0,
        )
        assert fresh >= stale


class TestFrequencySignal:
    """The learned half-life follows activations *per day*, not raw count."""

    def test_same_count_over_longer_span_is_shorter(self) -> None:
        # 10 activations in 2 days (5/day) is a hotter edge than 10 in 100
        # days (0.1/day). The old formula multiplied freq back by age, so
        # both returned the same value.
        now = time.time()
        hot = learned_decay.compute_edge_half_life(10, now, now - 2 * 86400, 30.0)
        cold = learned_decay.compute_edge_half_life(10, now, now - 100 * 86400, 30.0)
        assert hot > cold + 10.0

    def test_one_activation_per_day_is_midpoint(self) -> None:
        # Docstring contract: freq=1/day maps to the midpoint of [lo, hi]
        # (for a just-activated edge, where recency confidence is ~1).
        lo, hi = learned_decay.default_bounds()
        now = time.time()
        for days in (2, 50, 500):
            hl = learned_decay.compute_edge_half_life(days, now, now - days * 86400, 30.0)
            assert hl == pytest.approx((lo + hi) / 2, rel=1e-3)

    def test_monotonic_in_frequency_and_bounded(self) -> None:
        lo, hi = learned_decay.default_bounds()
        now = time.time()
        span = 20 * 86400
        values = [
            learned_decay.compute_edge_half_life(count, now, now - span, 30.0)
            for count in (0, 1, 5, 20, 200, 20000)
        ]
        assert values == sorted(values)
        assert all(lo <= v <= hi for v in values)


class TestBlendedDecayFactor:
    """Decay while the learned half-life blends back to the namespace default."""

    @staticmethod
    def _integrated(learned: float, default: float, t1: float, elapsed: float) -> float:
        # exp(-∫ ln2 / H(t) dt) over [t1, t1 + elapsed] by Simpson's rule, with
        # H(t) the blend compute_edge_half_life describes.
        import math

        def rate(t: float) -> float:
            c = 2.0 ** (-t / default)
            return math.log(2) / ((1.0 - c) * default + c * learned)

        n = 2000
        h = elapsed / n
        total = rate(t1) + rate(t1 + elapsed)
        for i in range(1, n):
            total += (4 if i % 2 else 2) * rate(t1 + i * h)
        return math.exp(-total * h / 3.0)

    @pytest.mark.parametrize("learned", [3.0, 10.7, 30.0, 63.7, 120.0])
    @pytest.mark.parametrize("t1", [0.0, 5.0, 40.0])
    @pytest.mark.parametrize("elapsed", [1.0, 14.0, 60.0])
    def test_matches_the_integrated_blend(self, learned, t1, elapsed) -> None:
        factor = learned_decay.blended_decay_factor(learned, 30.0, t1, elapsed)
        assert factor == pytest.approx(self._integrated(learned, 30.0, t1, elapsed), rel=1e-6)

    def test_equal_rates_is_the_plain_half_life(self) -> None:
        for t1, elapsed in [(0.0, 30.0), (12.0, 7.5), (300.0, 60.0)]:
            factor = learned_decay.blended_decay_factor(30.0, 30.0, t1, elapsed)
            assert factor == pytest.approx(2.0 ** (-elapsed / 30.0), rel=1e-12)

    def test_composes_exactly(self) -> None:
        # Two decay passes owe exactly what one pass over the same span does.
        for learned in (3.0, 63.7):
            split = learned_decay.blended_decay_factor(
                learned, 30.0, 4.0, 10.0
            ) * learned_decay.blended_decay_factor(learned, 30.0, 14.0, 50.0)
            whole = learned_decay.blended_decay_factor(learned, 30.0, 4.0, 60.0)
            assert split == pytest.approx(whole, rel=1e-12)

    def test_fresh_edge_decays_at_its_learned_rate(self) -> None:
        for learned in (3.0, 120.0):
            factor = learned_decay.blended_decay_factor(learned, 30.0, 0.0, 0.01)
            assert factor == pytest.approx(2.0 ** (-0.01 / learned), rel=1e-5)

    def test_stale_edge_decays_at_the_default_rate(self) -> None:
        for learned in (3.0, 120.0):
            factor = learned_decay.blended_decay_factor(learned, 30.0, 365.0, 1.0)
            assert factor == pytest.approx(2.0 ** (-1.0 / 30.0), rel=1e-3)

    def test_never_raises_a_weight_or_overflows(self) -> None:
        assert learned_decay.blended_decay_factor(3.0, 30.0, 10.0, 0.0) == 1.0
        assert learned_decay.blended_decay_factor(3.0, 30.0, 10.0, -5.0) == 1.0
        for learned in (3.0, 120.0):
            factor = learned_decay.blended_decay_factor(learned, 30.0, 1e6, 1e6)
            assert 0.0 <= factor <= 1.0


class TestSchemaMigration:
    """A3 schema additions"""

    def test_synapses_table_has_half_life_days(self, tmp_path) -> None:

        from neuralmind.synapses import SynapseStore, default_db_path

        store = SynapseStore(default_db_path(tmp_path))
        with store._connect() as conn:
            cur = conn.execute("PRAGMA table_info(synapses)")
            cols = [row[1] for row in cur.fetchall()]
        assert "half_life_days" in cols
        assert "learned_at" in cols

    def test_reinforce_writes_learned_half_life(self, tmp_path) -> None:
        """A3: reinforce() now writes non-NULL half_life_days via update_learned_half_life."""
        import time

        from neuralmind.synapses import SynapseStore, default_db_path

        store = SynapseStore(default_db_path(tmp_path))
        store.reinforce(["a", "b"])
        time.sleep(0.01)
        with store._connect() as conn:
            cur = conn.execute(
                "SELECT half_life_days FROM synapses WHERE node_a='a' AND node_b='b'"
            )
            row = cur.fetchone()
            assert row is not None
            # After reinforce, half_life_days should be a non-None float.
            assert row[0] is not None
            assert row[0] > 0


class TestUpdateLearnedHalfLife:
    """Persist learned half-life to synapses table."""

    def test_update_after_reinforce(self, tmp_path) -> None:
        import time

        from neuralmind.synapses import SynapseStore, default_db_path

        store = SynapseStore(default_db_path(tmp_path))
        store.reinforce(["a", "b"])
        time.sleep(0.01)
        result = learned_decay.update_learned_half_life(store, "a", "b")
        assert result is not None
        lo, hi = learned_decay.default_bounds()
        assert lo <= result <= hi

    def test_update_nonexistent_edge(self, tmp_path) -> None:
        from neuralmind.synapses import SynapseStore, default_db_path

        store = SynapseStore(default_db_path(tmp_path))
        result = learned_decay.update_learned_half_life(store, "x", "y")
        assert result is None


class TestDecayFunctionWithLearnedRate:
    """Decay with per-edge half_life_days."""

    def test_learned_half_life_decays_slower(self, tmp_path) -> None:
        """Edge with a long learned half-life should decay slower than a short one."""
        from neuralmind.synapses import SynapseStore, default_db_path

        store = SynapseStore(default_db_path(tmp_path))
        # Reinforce two edges with different activation counts so per-edge
        # half-lives diverge.
        store.reinforce(["a", "b"])
        for _ in range(10):
            store.reinforce(["c", "d"])
        # Manually set learned half-lives to diverge.
        # Short rate (10-day HL) decays to ~12% over 30 days — survives PRUNE_THRESHOLD (0.01).
        # Long rate (120-day HL) decays to ~84% — strong contrast.
        with store._connect() as conn:
            conn.execute(
                "UPDATE synapses SET half_life_days = ? WHERE node_a = ? AND node_b = ?",
                (120.0, "c", "d"),
            )
            conn.execute(
                "UPDATE synapses SET half_life_days = ? WHERE node_a = ? AND node_b = ?",
                (10.0, "a", "b"),
            )
            conn.execute(
                "UPDATE synapses SET learned_at = ? WHERE node_a IN (?, ?)",
                (time.time(), "a", "c"),
            )
        # Decay over a simulated 30 days.
        future = time.time() + 86400 * 30
        store.decay(now=future)
        with store._connect() as conn:
            cur = conn.execute(
                "SELECT weight FROM synapses WHERE node_a=? AND node_b=? ORDER BY node_a",
                ("c", "d"),
            )
            w_long = cur.fetchone()[0]
            cur = conn.execute(
                "SELECT weight FROM synapses WHERE node_a=? AND node_b=?",
                ("a", "b"),
            )
            w_short = cur.fetchone()[0]
        assert w_long > w_short

    def test_personal_namespace_uses_learned_rate(self, tmp_path) -> None:
        """Personal namespace edges with non-null half_life_days use the learned rate."""
        import time

        from neuralmind.synapses import SynapseStore, default_db_path

        store = SynapseStore(default_db_path(tmp_path))
        store.reinforce(["a", "b"])
        # Set a long learned half-life on a personal edge.
        with store._connect() as conn:
            conn.execute(
                "UPDATE synapses SET half_life_days = ?, learned_at = ? WHERE node_a = ? AND node_b = ?",
                (120.0, time.time(), "a", "b"),
            )
        # Decay 30 days into the future.
        future = time.time() + 86400 * 30
        store.decay(now=future)
        with store._connect() as conn:
            cur = conn.execute(
                "SELECT weight FROM synapses WHERE node_a=? AND node_b=?",
                ("a", "b"),
            )
            weight = cur.fetchone()[0]
        # With 120-day half-life over 30 days: retention ≈ 0.84.
        # With 30-day namespace default: retention = 0.5.
        # The learned rate should give significantly more retention.
        assert weight > 0.10

    def test_null_half_life_uses_namespace_default(self, tmp_path) -> None:
        """Edges with NULL half_life_days fall back to namespace default."""
        import time

        from neuralmind.synapses import SynapseStore, default_db_path

        store = SynapseStore(default_db_path(tmp_path))
        store.reinforce(["a", "b"])
        # Ensure half_life_days is NULL (default).
        with store._connect() as conn:
            conn.execute(
                "UPDATE synapses SET half_life_days = NULL WHERE node_a = ? AND node_b = ?",
                ("a", "b"),
            )
        future = time.time() + 86400 * 30
        store.decay(now=future)
        with store._connect() as conn:
            cur = conn.execute(
                "SELECT weight FROM synapses WHERE node_a=? AND node_b=?",
                ("a", "b"),
            )
            weight = cur.fetchone()[0]
        # With 30-day namespace default over 30 days: retention = 0.5.
        # LEARNING_RATE=0.30 → initial=0.30, final=0.30*0.5=0.15
        assert weight < 0.20

    def test_update_learned_half_life_passes_project_path(self, tmp_path) -> None:
        """update_learned_half_life passes project_path to default_bounds."""
        from neuralmind.synapses import SynapseStore, default_db_path

        store = SynapseStore(default_db_path(tmp_path))
        store.reinforce(["a", "b"])
        result = learned_decay.update_learned_half_life(store, "a", "b", project_path=tmp_path)
        assert result is not None
        lo, hi = learned_decay.default_bounds(tmp_path)
        assert lo <= result <= hi


class TestDecayAppliesTheBlend:
    """SynapseStore.decay() integrates the blend, in SQL, as the Python does.

    Before this, decay() applied the learned half-life as a constant rate.
    reinforce() stores it the moment it sets ``last_activated``, where the
    recency blend's confidence is 1, so the blend never took effect: an edge
    reinforced rarely kept its short half-life however long it sat idle.
    """

    T0 = 1_700_000_000.0
    DAY = 86400.0

    def _edge(self, tmp_path, namespace: str, half_life: float, count: int = 1):
        from neuralmind.synapses import SynapseStore, default_db_path

        store = SynapseStore(default_db_path(tmp_path), namespace=namespace)
        store.reinforce(["a", "b"], now=self.T0)
        with store._connect() as conn:
            conn.execute(
                "UPDATE synapses SET half_life_days = ?, activation_count = ?",
                (half_life, count),
            )
            weight = conn.execute("SELECT weight FROM synapses").fetchone()[0]
        return store, weight

    @staticmethod
    def _weight(store):
        with store._connect() as conn:
            row = conn.execute("SELECT weight FROM synapses").fetchone()
        return row[0] if row else None

    @pytest.mark.parametrize(
        "namespace, default",
        [("personal", 30.0), ("branch:feature-x", 30.0), ("shared", 60.0)],
    )
    @pytest.mark.parametrize("half_life", [5.0, 75.0])
    def test_sql_matches_blended_decay_factor(
        self, tmp_path, namespace, default, half_life
    ) -> None:
        store, w0 = self._edge(tmp_path, namespace, half_life)
        store.decay(now=self.T0 + 10 * self.DAY)
        store.decay(now=self.T0 + 40 * self.DAY)
        expected = (
            w0
            * learned_decay.blended_decay_factor(half_life, default, 0.0, 10.0)
            * learned_decay.blended_decay_factor(half_life, default, 10.0, 30.0)
        )
        assert self._weight(store) == pytest.approx(expected, rel=1e-9)

    def test_many_passes_decay_as_much_as_one(self, tmp_path) -> None:
        from neuralmind.synapses import PRUNE_THRESHOLD

        daily, w0 = self._edge(tmp_path / "daily", "personal", 5.0)
        once, _ = self._edge(tmp_path / "once", "personal", 5.0)
        for day in range(1, 61):
            daily.decay(now=self.T0 + day * self.DAY)
        once.decay(now=self.T0 + 60 * self.DAY)
        expected = w0 * learned_decay.blended_decay_factor(5.0, 30.0, 0.0, 60.0)
        assert expected > PRUNE_THRESHOLD
        assert self._weight(daily) == pytest.approx(expected, rel=1e-9)
        assert self._weight(once) == pytest.approx(expected, rel=1e-9)

    def test_idle_rare_edge_relaxes_toward_the_default(self, tmp_path) -> None:
        store, w0 = self._edge(tmp_path, "personal", 5.0)
        store.decay(now=self.T0 + 30 * self.DAY)
        weight = self._weight(store)
        # More than five times what a constant 5-day half-life leaves (the
        # old behaviour), and still less than the 30-day default leaves.
        assert w0 * 2.0 ** (-30 / 5.0) * 5 < weight < w0 * 2.0 ** (-30 / 30.0)

    def test_idle_hot_edge_relaxes_toward_the_default(self, tmp_path) -> None:
        store, w0 = self._edge(tmp_path, "personal", 120.0)
        store.decay(now=self.T0 + 60 * self.DAY)
        weight = self._weight(store)
        assert w0 * 2.0 ** (-60 / 30.0) < weight < w0 * 2.0 ** (-60 / 120.0)

    def test_ltp_floor_still_holds(self, tmp_path) -> None:
        from neuralmind.synapses import LTP_FLOOR, LTP_THRESHOLD

        store, _ = self._edge(tmp_path, "personal", 5.0, count=LTP_THRESHOLD)
        with store._connect() as conn:
            conn.execute("UPDATE synapses SET weight = 1.0")
        store.decay(now=self.T0 + 365 * self.DAY)
        assert self._weight(store) == pytest.approx(LTP_FLOOR)


class TestForgettingInPractice:
    """How long a learned association lasts, from first use to idle.

    The answer to "will it forget code I haven't touched?" on the marketing
    site (site/src/app/what-it-remembers/page.tsx) quotes these three cases.
    Change them together: if decay tuning moves, the page has to say so.

    Each case reinforces one pair on a schedule, running a decay pass before
    each use the way the SessionStart hook does, then leaves it idle. The
    half-life is learned at each reinforcement; while the pair sits idle its
    rate blends back toward the 30-day default.
    """

    DAY = 86400.0

    def _use_then_idle(self, tmp_path, monkeypatch, every_days, uses, *idle_days):
        from neuralmind.synapses import SynapseStore, default_db_path

        # compute_edge_half_life reads the wall clock; pin it to the schedule.
        clock = [1_700_000_000.0]
        monkeypatch.setattr(learned_decay.time, "time", lambda: clock[0])
        store = SynapseStore(default_db_path(tmp_path))
        start = clock[0]
        for i in range(uses):
            clock[0] = start + i * every_days * self.DAY
            store.decay(now=clock[0])
            store.reinforce(["api_handler", "db_model"], now=clock[0])
        with store._connect() as conn:
            half_life = conn.execute("SELECT half_life_days FROM synapses").fetchone()[0]
        last_use = clock[0]
        weights = []
        for idle in idle_days:
            store.decay(now=last_use + idle * self.DAY)
            with store._connect() as conn:
                row = conn.execute("SELECT weight FROM synapses").fetchone()
            weights.append(row[0] if row else None)
        return half_life, *weights

    def test_daily_use_outlasts_the_default_half_life(self, tmp_path, monkeypatch) -> None:
        from neuralmind.synapses import HALF_LIFE_DAYS

        half_life, weight = self._use_then_idle(tmp_path, monkeypatch, 1, 10, 14)
        assert HALF_LIFE_DAYS < 60 < half_life
        # Two idle weeks keep more than 80% of a full-strength edge.
        assert weight > 0.8

    def test_five_uses_keep_the_ltp_floor_however_long_idle(self, tmp_path, monkeypatch) -> None:
        from neuralmind.synapses import LTP_FLOOR, LTP_THRESHOLD

        assert LTP_THRESHOLD <= 6
        _, weight = self._use_then_idle(tmp_path, monkeypatch, 7, 6, 365)
        assert weight == pytest.approx(LTP_FLOOR)

    def test_rare_use_learns_a_short_half_life_and_is_pruned(self, tmp_path, monkeypatch) -> None:
        from neuralmind.synapses import HALF_LIFE_DAYS, PRUNE_THRESHOLD

        half_life, after_two_months, after_five_months = self._use_then_idle(
            tmp_path, monkeypatch, 30, 3, 60, 150
        )
        # Three uses a month apart: shorter than the 30-day default, not longer.
        assert half_life < 15 < HALF_LIFE_DAYS
        # Its rate relaxes toward the default while idle: two idle months
        # leave it in the store, five remove it. (Before the blend applied
        # during decay, two idle months were enough.)
        assert after_two_months is not None and after_two_months > PRUNE_THRESHOLD
        assert after_five_months is None
