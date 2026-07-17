"""Tests for A3 — learned per-edge decay (learned_decay.py)."""

from __future__ import annotations

import time

import pytest

from neuralmind import learned_decay
from neuralmind.contracts import TUNABLE_PARAMS


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


class TestSchemaMigration:
    """A3 schema additions"""

    def test_synapses_table_has_half_life_days(self, tmp_path) -> None:
        import sqlite3
        from pathlib import Path

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
        assert weight < 0.10

    def test_update_learned_half_life_passes_project_path(self, tmp_path) -> None:
        """update_learned_half_life passes project_path to default_bounds."""
        from neuralmind.synapses import SynapseStore, default_db_path

        store = SynapseStore(default_db_path(tmp_path))
        store.reinforce(["a", "b"])
        result = learned_decay.update_learned_half_life(store, "a", "b", project_path=tmp_path)
        assert result is not None
        lo, hi = learned_decay.default_bounds(tmp_path)
        assert lo <= result <= hi
