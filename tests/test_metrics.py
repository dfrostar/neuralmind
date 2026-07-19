"""Tests for the new metrics CLI command."""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from neuralmind.metrics_pipeline import MetricsCollector


class TestMetricsCollector(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_summarize_no_data_returns_empty(self) -> None:
        collector = MetricsCollector(self.project)
        summary = collector.summarize(days=7)
        # No metrics dir exists → empty dict
        self.assertFalse(summary)

    def test_summarize_empty_dir_returns_zero(self) -> None:

        metrics_dir = self.project / ".neuralmind" / "metrics"
        metrics_dir.mkdir(parents=True)
        collector = MetricsCollector(self.project)
        summary = collector.summarize(days=7)
        self.assertEqual(summary.get("n_events"), 0)

    def test_summarize_with_query_events(self) -> None:
        # Seed metrics directory with a query event
        metrics_dir = self.project / ".neuralmind" / "metrics"
        metrics_dir.mkdir(parents=True)
        day_file = metrics_dir / f"metrics_{time.strftime('%Y-%m-%d')}.jsonl"
        day_file.write_text(
            json.dumps(
                {
                    "event": "query",
                    "ts": time.time(),
                    "session_id": "s1",
                    "query": "test query",
                    "latency_ms": 150.0,
                    "retrieval_reuse_rate": 0.75,
                    "tool_calls": 3,
                    "tool_successes": 2,
                    "tokens_used": 1200,
                    "synapses_activated": 5,
                }
            )
            + "\n"
        )

        collector = MetricsCollector(self.project)
        summary = collector.summarize(days=7, event_type="query")

        self.assertGreater(summary.get("n_events", 0), 0)
        queries = summary.get("queries", {})
        self.assertEqual(queries.get("n_queries"), 1)
        self.assertEqual(queries.get("mean_latency_ms"), 150.0)
        self.assertEqual(queries.get("mean_tokens_used"), 1200)

    def test_summarize_filters_by_day(self) -> None:
        # Write an event from 60 days ago
        metrics_dir = self.project / ".neuralmind" / "metrics"
        metrics_dir.mkdir(parents=True)
        old_ts = time.time() - (60 * 86400)
        old_day = time.strftime("%Y-%m-%d", time.gmtime(old_ts))
        day_file = metrics_dir / f"metrics_{old_day}.jsonl"
        day_file.write_text(
            json.dumps(
                {
                    "event": "query",
                    "ts": old_ts,
                    "session_id": "old",
                    "query": "old query",
                    "latency_ms": 200.0,
                    "tool_calls": 1,
                    "tool_successes": 1,
                    "tokens_used": 500,
                    "synapses_activated": 2,
                }
            )
            + "\n"
        )

        collector = MetricsCollector(self.project)
        # Default 7-day window should exclude the old event
        summary = collector.summarize(days=7, event_type="query")
        self.assertEqual(summary.get("n_events"), 0)

        # 90-day window should include it
        summary = collector.summarize(days=90, event_type="query")
        self.assertGreater(summary.get("n_events", 0), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
