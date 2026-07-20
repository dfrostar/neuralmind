"""Tests for E4 — team staleness detection."""

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from neuralmind.synapses import (
    SHARED_NAMESPACE,
    SynapseStore,
    default_db_path,
)
from neuralmind.team_staleness import TeamStalenessDetector


class TestTeamStalenessDetector(unittest.TestCase):
    def test_is_stale_shared(self):
        detector = TeamStalenessDetector(stale_days_shared=30)
        assert detector.is_stale(time.time() - 86400 * 60, "shared")

    def test_is_not_stale_recent(self):
        detector = TeamStalenessDetector(stale_days_shared=30)
        assert not detector.is_stale(time.time(), "shared")

    def test_branch_threshold_shorter(self):
        detector = TeamStalenessDetector(stale_days_shared=30, stale_days_branch=14)
        ts = time.time() - 86400 * 20  # 20 days ago
        assert detector.is_stale(ts, "branch:feature")

    def test_personal_threshold_longer(self):
        detector = TeamStalenessDetector()
        ts = time.time() - 86400 * 45  # 45 days ago
        assert not detector.is_stale(ts, "personal")

    def test_fast_decay_multiplier(self):
        detector = TeamStalenessDetector(fast_decay=5.0)
        assert detector.fast_decay == 5.0

    def test_fast_decay_constant_factor(self):
        detector = TeamStalenessDetector()
        half_life = 30
        decay = 2.0 ** (-detector.fast_decay / half_life)
        self.assertLess(decay, 1.0)
        self.assertGreater(decay, 0.0)


class TestDetectStaleInStore(unittest.TestCase):
    def test_store_returns_empty_on_error(self):
        detector = TeamStalenessDetector()
        mock_store = MagicMock()
        mock_store._connect.side_effect = Exception("db gone")
        stale = detector.detect_stale_in_store(mock_store, namespace="shared")
        assert stale == []

    def test_detects_stale_edges_real_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = default_db_path(Path(tmp))
            db.parent.mkdir(parents=True, exist_ok=True)
            store = SynapseStore(db, namespace=SHARED_NAMESPACE)

            store.reinforce(["a.py", "b.py"], strength=5.0, namespace=SHARED_NAMESPACE)

            cutoff = time.time() - (30 * 86400) - 86400
            with store._connect() as conn:
                conn.execute(
                    "UPDATE synapses SET last_activated = ? WHERE namespace = ?",
                    (cutoff, SHARED_NAMESPACE),
                )

            detector = TeamStalenessDetector()
            stale = detector.detect_stale_in_store(store, namespace=SHARED_NAMESPACE)
            self.assertGreater(len(stale), 0)


class TestRunStalenessPass(unittest.TestCase):
    def test_run_staleness_pass_detects_and_decays(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = default_db_path(Path(tmp))
            db.parent.mkdir(parents=True, exist_ok=True)
            store = SynapseStore(db, namespace=SHARED_NAMESPACE)

            store.reinforce(["x.py", "y.py"], strength=10.0, namespace=SHARED_NAMESPACE)

            backdated = time.time() - (30 * 86400) - (10 * 86400)
            with store._connect() as conn:
                conn.execute(
                    "UPDATE synapses SET last_activated = ? WHERE namespace = ?",
                    (backdated, SHARED_NAMESPACE),
                )

            detector = TeamStalenessDetector()
            updated, stale = detector.run_staleness_pass(store, namespace=SHARED_NAMESPACE)
            self.assertGreater(updated, 0)
            self.assertGreater(len(stale), 0)
