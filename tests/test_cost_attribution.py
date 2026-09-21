"""Tests for neuralmind.cost_attribution — CFO-facing ROI artifact."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from neuralmind.cost_attribution import (
    DEFAULT_COST_PER_1K_TOKENS,
    _baseline_tokens,
    _cost_per_1k_tokens,
    _parse_ts,
    compute_cost_attribution,
    format_cost_report,
)


class TestBaselineTokens:
    """Tests for _baseline_tokens() — reconstructing baseline from ratio."""

    def test_simple_ratio(self) -> None:
        # 100 tokens used, 10x reduction → baseline 1000
        assert _baseline_tokens(100, 10.0) == 1000

    def test_no_reduction(self) -> None:
        # 500 tokens used, 1.0 ratio → baseline 500
        assert _baseline_tokens(500, 1.0) == 500

    def test_zero_ratio(self) -> None:
        # Zero ratio → return tokens_used (no baseline)
        assert _baseline_tokens(200, 0.0) == 200

    def test_negative_ratio(self) -> None:
        # Negative ratio → return tokens_used
        assert _baseline_tokens(200, -1.0) == 200


class TestCostPer1kTokens:
    """Tests for _cost_per_1k_tokens() — env var override."""

    def test_default(self, monkeypatch) -> None:
        monkeypatch.delenv("NEURALMIND_COST_PER_1K_TOKENS", raising=False)
        assert _cost_per_1k_tokens() == DEFAULT_COST_PER_1K_TOKENS

    def test_override(self, monkeypatch) -> None:
        monkeypatch.setenv("NEURALMIND_COST_PER_1K_TOKENS", "0.025")
        assert _cost_per_1k_tokens() == 0.025

    def test_invalid_falls_back(self, monkeypatch) -> None:
        monkeypatch.setenv("NEURALMIND_COST_PER_1K_TOKENS", "not-a-number")
        assert _cost_per_1k_tokens() == DEFAULT_COST_PER_1K_TOKENS


class TestParseTs:
    """Tests for _parse_ts() — ISO timestamp parsing."""

    def test_valid_iso(self) -> None:
        ts = _parse_ts("2026-09-21T07:00:00+00:00")
        assert ts > 0

    def test_valid_z(self) -> None:
        ts = _parse_ts("2026-09-21T07:00:00Z")
        assert ts > 0

    def test_invalid(self) -> None:
        assert _parse_ts("not-a-timestamp") == 0.0

    def test_empty(self) -> None:
        assert _parse_ts("") == 0.0


class TestComputeCostAttribution:
    """Tests for compute_cost_attribution() — the main function."""

    def _write_events(self, tmp_path: Path, events: list[dict]) -> Path:
        """Write query events to the project's query_events.jsonl."""
        events_dir = tmp_path / ".neuralmind" / "memory"
        events_dir.mkdir(parents=True)
        events_file = events_dir / "query_events.jsonl"
        with events_file.open("w", encoding="utf-8") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")
        return events_file

    def _make_event(
        self,
        tokens: int = 500,
        ratio: float = 10.0,
        session: str = "sess-1",
        ts: str = "2026-09-21T07:00:00+00:00",
    ) -> dict:
        return {
            "event_type": "query",
            "timestamp": ts,
            "project_path": "/tmp/test",
            "session_id": session,
            "query": "test query",
            "retrieval_summary": {
                "layers_used": ["L0", "L1", "L2"],
                "communities_loaded": ["auth"],
                "search_hits": 3,
                "tokens": tokens,
                "reduction_ratio": ratio,
            },
        }

    def test_no_events(self, tmp_path: Path) -> None:
        result = compute_cost_attribution(tmp_path)
        assert result["total_queries"] == 0
        assert result["modeled_cost_savings_usd"] == 0.0

    def test_single_query(self, tmp_path: Path) -> None:
        self._write_events(tmp_path, [self._make_event(tokens=500, ratio=10.0)])
        result = compute_cost_attribution(tmp_path)
        assert result["total_queries"] == 1
        assert result["savings_queries"] == 1
        assert result["total_tokens_used"] == 500
        assert result["total_baseline_tokens"] == 5000
        assert result["total_savings_tokens"] == 4500
        assert result["savings_ratio"] == 0.9
        # 4500 tokens / 1000 * $0.01 = $0.045
        assert result["modeled_cost_savings_usd"] == 0.045

    def test_multiple_queries(self, tmp_path: Path) -> None:
        events = [
            self._make_event(tokens=500, ratio=10.0, session="sess-1"),
            self._make_event(tokens=300, ratio=5.0, session="sess-1"),
            self._make_event(tokens=800, ratio=20.0, session="sess-2"),
        ]
        self._write_events(tmp_path, events)
        result = compute_cost_attribution(tmp_path)
        assert result["total_queries"] == 3
        assert result["savings_queries"] == 3
        assert result["total_tokens_used"] == 1600
        # baseline: 5000 + 1500 + 16000 = 22500
        assert result["total_baseline_tokens"] == 22500
        assert result["total_savings_tokens"] == 20900

    def test_no_savings_queries(self, tmp_path: Path) -> None:
        # ratio = 1.0 → no savings
        self._write_events(tmp_path, [self._make_event(tokens=500, ratio=1.0)])
        result = compute_cost_attribution(tmp_path)
        assert result["total_queries"] == 1
        assert result["savings_queries"] == 0
        assert result["total_savings_tokens"] == 0

    def test_per_session_breakdown(self, tmp_path: Path) -> None:
        events = [
            self._make_event(tokens=500, ratio=10.0, session="sess-1"),
            self._make_event(tokens=300, ratio=5.0, session="sess-2"),
        ]
        self._write_events(tmp_path, events)
        result = compute_cost_attribution(tmp_path)
        assert "sess-1" in result["per_session"]
        assert "sess-2" in result["per_session"]
        assert result["per_session"]["sess-1"]["queries"] == 1
        assert result["per_session"]["sess-2"]["queries"] == 1

    def test_daily_breakdown(self, tmp_path: Path) -> None:
        events = [
            self._make_event(tokens=500, ratio=10.0, ts="2026-09-21T07:00:00+00:00"),
            self._make_event(tokens=300, ratio=5.0, ts="2026-09-20T07:00:00+00:00"),
        ]
        self._write_events(tmp_path, events)
        result = compute_cost_attribution(tmp_path)
        assert "2026-09-21" in result["daily"]
        assert "2026-09-20" in result["daily"]

    def test_custom_cost_model(self, tmp_path: Path) -> None:
        self._write_events(tmp_path, [self._make_event(tokens=500, ratio=10.0)])
        result = compute_cost_attribution(tmp_path, cost_per_1k_tokens=0.025)
        assert result["cost_model"] == 0.025
        # 4500 tokens / 1000 * $0.025 = $0.1125
        assert result["modeled_cost_savings_usd"] == 0.1125

    def test_days_window(self, tmp_path: Path) -> None:
        # Old event (40 days ago) should be excluded with days=30
        old_event = self._make_event(
            tokens=500, ratio=10.0, ts="2026-08-12T07:00:00+00:00"
        )
        recent_event = self._make_event(
            tokens=300, ratio=5.0, ts="2026-09-21T07:00:00+00:00"
        )
        self._write_events(tmp_path, [old_event, recent_event])
        result = compute_cost_attribution(tmp_path, days=30)
        assert result["total_queries"] == 1
        assert result["total_tokens_used"] == 300


class TestFormatCostReport:
    """Tests for format_cost_report() — human-readable output."""

    def test_basic_report(self) -> None:
        attribution = {
            "project": "test-project",
            "days": 30,
            "cost_model": 0.01,
            "total_queries": 10,
            "savings_queries": 8,
            "total_tokens_used": 5000,
            "total_baseline_tokens": 50000,
            "total_savings_tokens": 45000,
            "savings_ratio": 0.9,
            "modeled_cost_savings_usd": 0.45,
            "per_session": {
                "sess-1": {
                    "queries": 5,
                    "tokens_used": 2500,
                    "baseline_tokens": 25000,
                    "savings_tokens": 22500,
                }
            },
            "daily": {
                "2026-09-21": {"queries": 5, "savings_tokens": 22500},
            },
        }
        report = format_cost_report(attribution)
        assert "test-project" in report
        assert "$0.45" in report
        assert "90.0%" in report
        assert "sess-1" in report
        assert "2026-09-21" in report
        assert "Modeled savings" in report

    def test_empty_report(self) -> None:
        attribution = {
            "project": "empty-project",
            "days": 30,
            "cost_model": 0.01,
            "total_queries": 0,
            "savings_queries": 0,
            "total_tokens_used": 0,
            "total_baseline_tokens": 0,
            "total_savings_tokens": 0,
            "savings_ratio": 0.0,
            "modeled_cost_savings_usd": 0.0,
            "per_session": {},
            "daily": {},
        }
        report = format_cost_report(attribution)
        assert "empty-project" in report
        assert "$0.00" in report
