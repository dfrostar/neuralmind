"""Tests for A4 — sleep consolidation (sleep.py)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from neuralmind.sleep import DaemonSleep, SleepStats


class TestScheduling:
    """Run scheduling gate."""

    def test_should_run_initial(self, tmp_path: Path) -> None:
        t = DaemonSleep(project_path=tmp_path, interval_days=7.0)
        assert t.should_run() is True

    def test_should_run_after_mark(self, tmp_path: Path) -> None:
        t = DaemonSleep(project_path=tmp_path, interval_days=7.0)
        t.mark_run()
        assert t.should_run() is False

    def test_no_project_returns_false(self) -> None:
        t = DaemonSleep(project_path=None)
        assert t.should_run() is False


class TestPruneRedundantEdges:
    """Prune edges below threshold with no reinforcement."""

    def test_prune_stale_low_weight(self, tmp_path: Path) -> None:
        from neuralmind.synapses import SynapseStore, default_db_path

        store = SynapseStore(default_db_path(tmp_path))
        store.reinforce(["a", "b"])
        # Backdate last_activated to simulate staleness.
        old = time.time() - (100 * 86400)
        with store._connect() as conn:
            conn.execute(
                "UPDATE synapses SET weight = 0.005, last_activated = ?, created_at = ?",
                (old, old),
            )
        ds = DaemonSleep(project_path=tmp_path, stale_days=60)
        ds.store = store
        assert ds.prune_redundant_edges() == 1

    def test_no_prune_recent_edge(self, tmp_path: Path) -> None:
        from neuralmind.synapses import SynapseStore, default_db_path

        store = SynapseStore(default_db_path(tmp_path))
        store.reinforce(["a", "b"])
        ds = DaemonSleep(project_path=tmp_path, stale_days=60)
        ds.store = store
        assert ds.prune_redundant_edges() == 0


class TestPromoteLtpEdges:
    """Promote LTP edges that survived decay."""

    def test_promote_strong_edges(self, tmp_path: Path) -> None:
        from neuralmind.synapses import SynapseStore, default_db_path

        store = SynapseStore(default_db_path(tmp_path))
        # Activate "a"-"b" 6 times (above LTP threshold of 5).
        for _ in range(6):
            store.reinforce(["a", "b"])
        with store._connect() as conn:
            conn.execute("UPDATE synapses SET weight = 0.25")
        ds = DaemonSleep(project_path=tmp_path)
        ds.store = store
        assert ds.promote_ltp_edges() > 0


class TestEmitTeamBundle:
    """Consolidated team-baseline bundle."""

    def test_emit_empty_shared(self, tmp_path: Path) -> None:
        from neuralmind.synapses import SynapseStore, default_db_path

        store = SynapseStore(default_db_path(tmp_path))
        ds = DaemonSleep(project_path=tmp_path)
        ds.store = store
        assert ds.emit_team_bundle() is None

    def test_emit_with_shared_edges(self, tmp_path: Path) -> None:
        from neuralmind.synapses import SynapseStore, default_db_path

        store = SynapseStore(default_db_path(tmp_path))
        with store._connect() as conn:
            conn.execute(
                """INSERT INTO synapses(node_a, node_b, namespace, weight, activation_count, last_activated, created_at)
                   VALUES ('x', 'y', 'shared', 0.5, 3, ?, ?)""",
                (time.time(), time.time()),
            )
        ds = DaemonSleep(project_path=tmp_path)
        ds.store = store
        bundle = ds.emit_team_bundle()
        assert bundle is not None
        assert len(bundle["team_baseline"]) == 1


class TestDetectStaleEdges:
    """Flag stale team edges."""

    def test_detects_stale(self, tmp_path: Path) -> None:
        from neuralmind.synapses import SynapseStore, default_db_path

        store = SynapseStore(default_db_path(tmp_path))
        old = time.time() - (100 * 86400)
        with store._connect() as conn:
            conn.execute(
                """INSERT INTO synapses(node_a, node_b, namespace, weight, activation_count, last_activated, created_at)
                   VALUES ('x', 'y', 'shared', 0.5, 3, ?, ?)""",
                (old, old),
            )
        ds = DaemonSleep(project_path=tmp_path, stale_days=60)
        ds.store = store
        stale = ds.detect_stale_edges()
        assert len(stale) == 1

    def test_no_stale_when_recent(self, tmp_path: Path) -> None:
        from neuralmind.synapses import SynapseStore, default_db_path

        store = SynapseStore(default_db_path(tmp_path))
        with store._connect() as conn:
            conn.execute(
                """INSERT INTO synapses(node_a, node_b, namespace, weight, activation_count, last_activated, created_at)
                   VALUES ('x', 'y', 'shared', 0.5, 3, ?, ?)""",
                (time.time(), time.time()),
            )
        ds = DaemonSleep(project_path=tmp_path, stale_days=60)
        ds.store = store
        assert ds.detect_stale_edges() == []


class TestRunFullPass:
    """End-to-end sleep pass."""

    def test_run_no_project(self) -> None:
        ds = DaemonSleep(project_path=None)
        stats = ds.run()
        assert stats.pruned == 0

    def test_run_populated_project(self, tmp_path: Path) -> None:
        from neuralmind.synapses import SynapseStore, default_db_path

        store = SynapseStore(default_db_path(tmp_path))
        store.reinforce(["a", "b"])
        ds = DaemonSleep(project_path=tmp_path)
        stats = ds.run()
        assert isinstance(stats, SleepStats)
        assert stats.ts > 0
