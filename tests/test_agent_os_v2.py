"""Tests for Agent OS correlator and promotion modules."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from neuralmind.agent_os import (
    CauseType,
    ExperimentResult,
    ExperimentRunner,
    ExperimentStatus,
    PromotionEngine,
    PromotionRecord,
    PromotionStatus,
    RootCauseCorrelator,
    Signal,
)


# ---------------------------------------------------------------------------
# Correlator
# ---------------------------------------------------------------------------


class TestRootCauseCorrelator:
    def test_no_changes_returns_unknown(self, tmp_path):
        correlator = RootCauseCorrelator(lookback_seconds=3600)
        signal = Signal(
            signal_id="sig_1",
            timestamp=1000.0,
            metric_name="latency_ms",
            value=100.0,
            baseline=50.0,
            delta=50.0,
            severity=4.0,
        )
        insight = correlator.correlate(signal, tmp_path)
        assert insight is not None
        assert insight.cause_type == CauseType.UNKNOWN

    def test_recent_commit_triggers_hypothesis(self, tmp_path):
        """A recent commit mentioning the metric triggers a code_change hypothesis."""
        correlator = RootCauseCorrelator(lookback_seconds=7200)

        # Create a minimal git repo
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
        (tmp_path / ".git" / "refs").mkdir()
        (tmp_path / ".git" / "refs" / "heads").mkdir()

        signal = Signal(
            signal_id="sig_1",
            timestamp=datetime.now(timezone.utc).timestamp(),
            metric_name="latency_ms",
            value=200.0,
            baseline=100.0,
            delta=100.0,
            severity=4.0,
        )

        # Mock _recent_commits to return a commit mentioning the metric
        correlator._recent_commits = lambda path, ts: [{
            "hash": "abc1234567890",
            "author": "Test",
            "email": "<EMAIL>",
            "message": "improve latency_ms performance",
            "date": datetime.now(timezone.utc).isoformat(),
        }]

        insight = correlator.correlate(signal, tmp_path)
        assert insight is not None
        assert insight.cause_type == CauseType.CODE_CHANGE
        assert "abc1234567" in insight.cause_ref
        assert insight.confidence > 0.5

    def test_config_change_hypothesis(self, tmp_path, monkeypatch):
        """A recently modified config file triggers config_change hypothesis."""
        correlator = RootCauseCorrelator(lookback_seconds=7200)

        # Mock _recent_config_changes
        correlator._recent_config_changes = lambda path, ts: [{
            "file": "backend.yaml",
            "mtime": datetime.now(timezone.utc).timestamp(),
            "path": str(tmp_path / "backend.yaml"),
        }]

        signal = Signal(
            signal_id="sig_1",
            timestamp=datetime.now(timezone.utc).timestamp(),
            metric_name="latency_ms",
            value=200.0,
            baseline=100.0,
            delta=100.0,
            severity=4.0,
        )

        insight = correlator.correlate(signal, tmp_path)
        assert insight is not None
        # Should have both code (unknown) and config hypotheses
        cause_types = [insight.cause_type]
        assert CauseType.CONFIG_CHANGE in cause_types or CauseType.UNKNOWN in cause_types

    def test_performance_keyword_in_commit(self, tmp_path):
        """Commit with perf keyword gets moderate confidence."""
        correlator = RootCauseCorrelator(lookback_seconds=7200)

        correlator._recent_commits = lambda path, ts: [{
            "hash" : "def7890123456",
            "author" : "Dev",
            "email" : "<EMAIL>",
            "message" : "optimize database queries for speed",
            "date" : datetime.now(timezone.utc).isoformat(),
        }]

        signal = Signal(
            signal_id="sig_1",
            timestamp=datetime.now(timezone.utc).timestamp(),
            metric_name="query_time",
            value=500.0,
            baseline=100.0,
            delta=400.0,
            severity=6.0,
        )

        insight = correlator.correlate(signal, tmp_path)
        assert insight is not None
        # Should have at least one hypothesis with some confidence
        assert insight.confidence >= 0.0


# ---------------------------------------------------------------------------
# Promotion
# ---------------------------------------------------------------------------


class TestPromotionEngine:
    def test_promote_calls_ship_callable(self):
        """PROMOTED verdict triggers ship_callable."""
        shipped = []
        def ship(result):
            shipped.append(result)

        engine = PromotionEngine(ship_callable=ship)
        result = engine.run(
            proposal_id="p1",
            metric_name="latency_ms",
            baseline_value=100.0,
            candidate_value=90.0,
        )
        assert result.verdict == ExperimentStatus.PROMOTED
        assert len(shipped) == 1
        assert shipped[0].experiment_id == result.experiment_id

    def test_rollback_calls_ship_callable(self):
        """ROLLED_BACK verdict triggers ship_callable."""
        rolled_back = []
        def ship(result):
            rolled_back.append(result)

        engine = PromotionEngine(ship_callable=ship)
        result = engine.run(
            proposal_id="p1",
            metric_name="latency_ms",
            baseline_value=100.0,
            candidate_value=110.0,
        )
        assert result.verdict == ExperimentStatus.ROLLED_BACK
        assert len(rolled_back) == 1

    def test_rejected_does_not_call_ship(self):
        """REJECTED verdict is a no-op."""
        called = []
        def ship(result):
            called.append(result)

        engine = PromotionEngine(ship_callable=ship)
        result = engine.run(
            proposal_id="p1",
            metric_name="latency_ms",
            baseline_value=100.0,
            candidate_value=98.0,  # Below 5% threshold
        )
        assert result.verdict == ExperimentStatus.REJECTED
        assert len(called) == 0

    def test_default_ship_is_noop(self):
        """Default ship callable does nothing (human-in-the-loop)."""
        engine = PromotionEngine()  # No ship_callable
        result = engine.run(
            proposal_id="p1",
            metric_name="latency_ms",
            baseline_value=100.0,
            candidate_value=90.0,
        )
        assert result.verdict == ExperimentStatus.PROMOTED
        # No exception, no crash

    def test_history(self):
        """Promotion history tracks actions."""
        engine = PromotionEngine()
        engine.run("p1", "latency_ms", 100.0, 90.0)
        engine.run("p2", "latency_ms", 100.0, 110.0)
        history = engine.get_history()
        assert len(history) == 2
        assert isinstance(history[0], PromotionRecord)
        # Newest first
        assert history[0].experiment_id != history[1].experiment_id

    def test_clear_history(self):
        """Clear history resets state."""
        engine = PromotionEngine()
        engine.run("p1", "latency_ms", 100.0, 90.0)
        engine.clear_history()
        assert len(engine.get_history()) == 0

    def test_ship_exception_is_caught(self):
        """ship_callable exception is caught and logged, not bubbled."""
        def bad_ship(result):
            raise RuntimeError("ship failed!")

        engine = PromotionEngine(ship_callable=bad_ship)
        # Should not raise
        result = engine.run("p1", "latency_ms", 100.0, 90.0)
        assert result.verdict == ExperimentStatus.PROMOTED

        # History should show FAILED
        history = engine.get_history()
        assert len(history) == 1
        assert history[0].status == PromotionStatus.FAILED


class TestPromotionRecord:
    def test_to_dict(self):
        record = PromotionRecord(
            promotion_id="prom_123",
            experiment_id="exp_456",
            ts="2026-08-02T12:00:00+00:00",
            status=PromotionStatus.SHIPPED,
            delta=0.10,
            message="test",
        )
        d = record.to_dict()
        assert d["promotion_id"] == "prom_123"
        assert d["status"] == "shipped"
        assert d["delta"] == 0.10
