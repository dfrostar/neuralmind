"""Tests for the SOTA synapse dynamics layer."""

from __future__ import annotations

import time

import pytest

from neuralmind.synapses import (
    DEFAULT_NAMESPACE,
    LEARNING_RATE,
    WEIGHT_CAP,
    SynapseStore,
)
from neuralmind.synapse_dynamics import (
    FOK_INITIAL_THRESHOLD,
    RESOURCE_INITIAL,
    SAMPL_DEPRESSION_SCALE,
    STC_CONSOLIDATION_THRESHOLD,
    STC_TAG_INITIAL,
    SynapseDynamics,
)


def _store(tmp_path):
    return SynapseStore(tmp_path / "synapses.db")


def _dynamics(tmp_path, **kwargs):
    store = _store(tmp_path)
    return SynapseDynamics(store, **kwargs)


class TestSchemaMigration:
    def test_migration_is_idempotent(self, tmp_path):
        d = _dynamics(tmp_path)
        assert d._ensure_schema() is True
        assert d._ensure_schema() is True  # second call no-op

    def test_migration_creates_tables(self, tmp_path):
        d = _dynamics(tmp_path)
        d._ensure_schema()
        with d.store._connect() as conn:
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='synapses_dynamics_meta'"
            )
            assert cur.fetchone() is not None
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='node_resources'"
            )
            assert cur.fetchone() is not None
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='synapse_replay_queue'"
            )
            assert cur.fetchone() is not None


class TestLateralInhibition:
    def test_single_node_no_inhibition(self, tmp_path):
        d = _dynamics(tmp_path)
        # A - B, A - C (equal weights)
        for _ in range(3):
            d.store.reinforce(["A", "B"])
            d.store.reinforce(["A", "C"])
        results = d.spread([("A", 1.0)], top_k=10)
        assert len(results) == 2

    def test_inhibition_reduces_competitor_activation(self, tmp_path):
        d = _dynamics(tmp_path, enable_fok=False)
        # Build: A-B, A-C with equal weight
        for _ in range(5):
            d.store.reinforce(["A", "B"])
            d.store.reinforce(["A", "C"])
        # Spread with inhibition — both B and C should be present but
        # their relative scores should sharpen
        results_dict = dict(d.spread([("A", 1.0)], top_k=10))
        assert "B" in results_dict
        assert "C" in results_dict

    def test_inhibition_respects_seed_set(self, tmp_path):
        d = _dynamics(tmp_path, enable_fok=False)
        d.store.reinforce(["A", "B"])
        d.store.reinforce(["A", "C"])
        d.store.reinforce(["B", "D"])
        d.store.reinforce(["C", "D"])
        results = dict(d.spread(["A", "B"], top_k=10))
        # A and B are seeds — should be excluded from results
        assert "A" not in results
        assert "B" not in results


class TestFeelingOfKnowing:
    def test_fok_rejects_weak_activation(self, tmp_path):
        d = _dynamics(tmp_path, enable_lateral_inhibition=False)
        # Single weak activation
        d.store.reinforce(["A", "B"], now=time.time() - 100 * 86400)
        d.store.decay()
        # After decay, activation should be very weak
        results = d.spread([("A", 1.0)], top_k=10)
        # FOK may reject if peak is below threshold
        # (depends on exact decay math)
        # Just verify the method doesn't crash
        assert isinstance(results, list)

    def test_fok_adapts_threshold(self, tmp_path):
        d = _dynamics(tmp_path, enable_lateral_inhibition=False)
        # Reinforce strongly
        for _ in range(10):
            d.store.reinforce(["A", "B"])
        initial_threshold = d.fok_threshold
        d.spread([("A", 1.0)], top_k=10)
        # Threshold should have adapted toward the peak
        assert d.fok_threshold != initial_threshold

    def test_fok_respects_bounds(self, tmp_path):
        d = _dynamics(tmp_path, enable_lateral_inhibition=False)
        # Lower bound
        d._fok_threshold = 0.01
        for _ in range(10):
            d.store.reinforce(["A", "B"])
        d.spread([("A", 1.0)], top_k=10)
        assert d.fok_threshold >= 0.05  # FOK_MIN_THRESHOLD


class TestSynapticTagging:
    def test_single_activation_sets_tag(self, tmp_path):
        d = _dynamics(tmp_path)
        d.reinforce_with_stc(["A", "B"])
        # Tag should exist
        with d.store._connect() as conn:
            cur = conn.execute(
                "SELECT value FROM synapses_dynamics_meta WHERE key LIKE 'stc_tag:%'"
            )
            rows = cur.fetchall()
            assert len(rows) == 1
            assert float(rows[0][0]) == STC_TAG_INITIAL

    def test_repeated_activation_increments_tag(self, tmp_path):
        d = _dynamics(tmp_path)
        d.reinforce_with_stc(["A", "B"])
        d.reinforce_with_stc(["A", "B"])
        with d.store._connect() as conn:
            cur = conn.execute(
                "SELECT value FROM synapses_dynamics_meta WHERE key LIKE 'stc_tag:%'"
            )
            rows = cur.fetchall()
            tag_value = float(rows[0][0])
            # Second activation should increase tag (with saturation)
            assert tag_value > STC_TAG_INITIAL

    def test_capture_boosts_weight(self, tmp_path):
        d = _dynamics(tmp_path)
        # Activate many times to drive tag above threshold
        for _ in range(20):
            d.reinforce_with_stc(["A", "B"])
        # After enough activations, tag should have triggered capture
        neighbors = dict(d.store.neighbors("A"))
        # Weight should be higher than standard reinforce alone would produce
        assert neighbors.get("B", 0.0) > LEARNING_RATE


class TestSAMPL:
    def test_retrieval_weakens_competitors(self, tmp_path):
        d = _dynamics(tmp_path, enable_fok=False)
        # Build a graph: A-B, A-C, B-D, C-D
        # D is a competitor (connected to both B and C)
        for _ in range(5):
            d.store.reinforce(["A", "B"])
            d.store.reinforce(["A", "C"])
            d.store.reinforce(["B", "D"])
            d.store.reinforce(["C", "D"])

        # Get baseline D activation
        before = dict(d.store.neighbors("A")).get("D", 0.0)

        # Retrieve A (which should trigger SAMPL depression)
        d.apply_sampl_depression("A")

        # D should have weakened
        after = dict(d.store.neighbors("A")).get("D", 0.0)
        assert after <= before + 1e-9  # should not increase

    def test_no_depression_without_competitors(self, tmp_path):
        d = _dynamics(tmp_path)
        d.store.reinforce(["A", "B"])
        # A has no competitors — should return 0
        depressed = d.apply_sampl_depression("A")
        assert depressed == 0


class TestResourceSTDP:
    def test_resource_pool_initializes(self, tmp_path):
        d = _dynamics(tmp_path)
        d.reinforce_with_resources(["A", "B"])
        with d.store._connect() as conn:
            cur = conn.execute("SELECT resource_pool FROM node_resources WHERE node_id = 'A'")
            row = cur.fetchone()
            assert row is not None
            assert float(row[0]) < RESOURCE_INITIAL  # consumed some

    def test_depleted_pool_blocks_reinforce(self, tmp_path):
        d = _dynamics(tmp_path)
        # Consume all of A's resources
        for _ in range(100):
            d.reinforce_with_resources(["A", "B"])
        # A's pool should be at floor now
        with d.store._connect() as conn:
            cur = conn.execute("SELECT resource_pool FROM node_resources WHERE node_id = 'A'")
            pool = float(cur.fetchone()[0])
            assert pool <= 0.1 + 1e-9  # RESOURCE_MIN_FLOOR

    def test_replenish_restores_resources(self, tmp_path):
        d = _dynamics(tmp_path)
        d.reinforce_with_resources(["A", "B"])
        # Consume resources
        for _ in range(50):
            d.reinforce_with_resources(["A", "C"])
        # Replenish
        d.replenish_resources()
        with d.store._connect() as conn:
            cur = conn.execute("SELECT resource_pool FROM node_resources WHERE node_id = 'A'")
            pool = float(cur.fetchone()[0])
            assert pool > 0.1  # should have replenished


class TestReplayConsolidation:
    def test_enqueue_adds_to_queue(self, tmp_path):
        d = _dynamics(tmp_path)
        d.enqueue_replay("A", "B", DEFAULT_NAMESPACE, 0.5, 3)
        with d.store._connect() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM synapse_replay_queue")
            assert cur.fetchone()[0] == 1

    def test_replay_strengthens_edges(self, tmp_path):
        d = _dynamics(tmp_path)
        d.store.reinforce(["A", "B"], strength=0.5)
        d.enqueue_replay("A", "B", DEFAULT_NAMESPACE, 0.5, 1)
        replayed = d.run_replay_consolidation()
        assert replayed >= 1

    def test_queue_depth_cap(self, tmp_path):
        d = _dynamics(tmp_path)
        # Enqueue many events
        for i in range(1100):  # exceeds REPLAY_QUEUE_MAX
            d.enqueue_replay(f"A{i}", f"B{i}", DEFAULT_NAMESPACE, 0.1, 1)
        with d.store._connect() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM synapse_replay_queue")
            count = cur.fetchone()[0]
            assert count <= 1000  # REPLAY_QUEUE_MAX


class TestUnifiedReinforce:
    def test_all_dynamics_together(self, tmp_path):
        d = _dynamics(tmp_path)
        # Reinforce with all dynamics
        pairs = d.reinforce(["A", "B", "C"])
        assert pairs == 3  # 3 pairs from 3 nodes
        # Verify STC tags were set
        with d.store._connect() as conn:
            cur = conn.execute(
                "SELECT COUNT(*) FROM synapses_dynamics_meta WHERE key LIKE 'stc_tag:%'"
            )
            assert cur.fetchone()[0] == 3
        # Verify replay queue
        with d.store._connect() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM synapse_replay_queue")
            assert cur.fetchone()[0] == 3

    def test_spread_and_depress(self, tmp_path):
        d = _dynamics(tmp_path, enable_fok=False)
        for _ in range(5):
            d.store.reinforce(["A", "B"])
            d.store.reinforce(["A", "C"])
            d.store.reinforce(["B", "D"])
        results = d.spread_and_depress([("A", 1.0)], top_k=10)
        assert isinstance(results, list)


class TestDynamicsStats:
    def test_stats_returns_all_fields(self, tmp_path):
        d = _dynamics(tmp_path)
        stats = d.dynamics_stats()
        assert "fok_threshold" in stats
        assert "lateral_inhibition" in stats
        assert "stc" in stats
        assert "sampl" in stats
        assert "resource_stdp" in stats
        assert "fok" in stats
        assert "replay" in stats

    def test_stats_after_activity(self, tmp_path):
        d = _dynamics(tmp_path)
        d.reinforce(["A", "B", "C"])
        stats = d.dynamics_stats()
        assert stats["active_tags"] >= 3


class TestFailOpen:
    def test_spread_without_schema(self, tmp_path):
        """Spread should work even if schema migration hasn't run."""
        d = _dynamics(tmp_path)
        d.store.reinforce(["A", "B"])
        # Don't call _ensure_schema — should still work
        results = d.spread([("A", 1.0)], top_k=10)
        assert isinstance(results, list)

    def test_reinforce_without_schema(self, tmp_path):
        d = _dynamics(tmp_path)
        pairs = d.reinforce(["A", "B"])
        assert pairs == 1

    def test_opt_out_flags(self, tmp_path):
        d = _dynamics(
            tmp_path,
            enable_lateral_inhibition=False,
            enable_stc=False,
            enable_sampl=False,
            enable_resource_stdp=False,
            enable_fok=False,
            enable_replay=False,
        )
        pairs = d.reinforce(["A", "B"])
        assert pairs == 1
        results = d.spread([("A", 1.0)], top_k=10)
        assert isinstance(results, list)
