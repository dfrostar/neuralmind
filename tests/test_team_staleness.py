"""Tests for E4 — team staleness detection."""
import time
from unittest.mock import MagicMock, patch
from neuralmind.team_staleness import TeamStalenessDetector, StaleEdge


class TestTeamStalenessDetector:
    def test_is_stale_shared(self):
        detector = TeamStalenessDetector(stale_days_shared=30)
        assert detector.is_stale(time.time() - 86400 * 60, "shared")
    
    def test_is_not_stale_recent(self):
        detector = TeamStalenessDetector(stale_days_shared=30)
        assert not detector.is_stale(time.time(), "shared")
    
    def test_branch_threshold_shorter(self):
        detector = TeamStalenessDetector(
            stale_days_shared=30, stale_days_branch=14
        )
        ts = time.time() - 86400 * 20  # 20 days ago
        assert detector.is_stale(ts, "branch:feature")
    
    def test_personal_threshold_longer(self):
        detector = TeamStalenessDetector()
        ts = time.time() - 86400 * 45  # 45 days ago
        assert not detector.is_stale(ts, "personal")
    
    def test_fast_decay_multiplier(self):
        detector = TeamStalenessDetector(fast_decay=5.0)
        assert detector.fast_decay == 5.0


class TestDetectStaleInStore:
    def test_store_returns_empty_on_error(self):
        detector = TeamStalenessDetector()
        mock_store = MagicMock()
        mock_store._connect.side_effect = Exception("db gone")
        stale = detector.detect_stale_in_store(mock_store, namespace="shared")
        assert stale == []
