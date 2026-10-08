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

    def _log_recalls(self) -> MetricsCollector:
        collector = MetricsCollector(self.project)
        collector.log_recall_metrics(outcome="injected", injected=8, similarity=0.61)
        collector.log_recall_metrics(outcome="low_similarity", injected=0, similarity=0.2)
        collector.log_recall_metrics(outcome="low_similarity", injected=0, similarity=0.31)
        collector.log_recall_metrics(outcome="no_neighbors", injected=0, similarity=0.5)
        return collector

    def test_recall_outcomes_are_summarized(self) -> None:
        recall = self._log_recalls().summarize(days=7, event_type="recall")["recall"]
        self.assertEqual(recall["n_prompts"], 4)
        self.assertEqual(recall["n_injected"], 1)
        self.assertEqual(recall["abstain_rate"], 0.75)
        self.assertEqual(
            recall["outcomes"], {"injected": 1, "low_similarity": 2, "no_neighbors": 1}
        )

    def test_recall_records_keep_no_prompt_text(self) -> None:
        self._log_recalls()
        records = [
            json.loads(line)
            for f in (self.project / ".neuralmind" / "metrics").glob("*.jsonl")
            for line in f.read_text().splitlines()
        ]
        self.assertEqual(
            {key for r in records for key in r},
            {"event", "ts", "outcome", "injected", "similarity"},
        )

    def test_cli_metrics_shows_recall(self) -> None:
        import contextlib
        import io
        from argparse import Namespace

        from neuralmind.cli import cmd_metrics

        self._log_recalls()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cmd_metrics(Namespace(project_path=str(self.project), days=7, json=False))
        text = out.getvalue()
        self.assertIn("Recall injected", text)
        self.assertIn("75.0%", text)

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cmd_metrics(Namespace(project_path=str(self.project), days=7, json=True))
        self.assertEqual(json.loads(out.getvalue())["recall"]["n_prompts"], 4)

    def test_cli_metrics_json_counts_every_event_in_one_window(self) -> None:
        import contextlib
        import io
        from argparse import Namespace

        from neuralmind.cli import cmd_metrics

        collector = self._log_recalls()
        collector.log_build_metrics(
            duration_s=1.5, files_processed=3, synapse_edges=0, graph_edges=2
        )
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cmd_metrics(Namespace(project_path=str(self.project), days=7, json=True))
        summary = json.loads(out.getvalue())
        self.assertEqual(summary["n_events"], 5)
        self.assertEqual(summary["recall"]["n_prompts"], 4)
        self.assertEqual(summary["builds"]["n_builds"], 1)

    def test_starting_a_new_day_applies_retention(self) -> None:
        metrics = self.project / ".neuralmind" / "metrics"
        metrics.mkdir(parents=True)
        old = metrics / "metrics_2000-01-01.jsonl"
        old.write_text('{"event": "recall", "ts": 0}\n')
        collector = MetricsCollector(self.project)
        collector.log_recall_metrics(outcome="injected", injected=1, similarity=0.5)
        self.assertFalse(old.exists())
        # Later appends to the same day's file don't rescan.
        old.write_text('{"event": "recall", "ts": 0}\n')
        collector.log_recall_metrics(outcome="injected", injected=1, similarity=0.5)
        self.assertTrue(old.exists())

    def test_a_full_day_file_stops_growing_and_is_never_rewritten(self) -> None:
        collector = MetricsCollector(self.project, max_bytes=2000)
        collector.log_recall_metrics(outcome="injected", injected=1, similarity=0.5)
        today = next((self.project / ".neuralmind" / "metrics").glob("metrics_*.jsonl"))
        today.write_text(today.read_text() * 40)  # past the cap
        before = today.read_text()
        collector.log_recall_metrics(outcome="injected", injected=1, similarity=0.5)
        collector.rotate()
        # Not appended to, and not rewritten: other processes may append to it.
        self.assertEqual(today.read_text(), before)

    def test_a_record_that_would_pass_the_cap_is_dropped(self) -> None:
        collector = MetricsCollector(self.project, max_bytes=2000)
        metrics = self.project / ".neuralmind" / "metrics"

        def log(query: str) -> bool:
            return collector.log_query_metrics(
                session_id="s",
                query=query,
                latency_ms=1.0,
                retrieval_reuse_rate=0.0,
                tool_calls=0,
                tool_successes=0,
                tokens_used=0,
                synapses_activated=0,
            )

        # Too big on its own, as the day's first record: no file at all.
        self.assertFalse(log("x" * 5000))
        self.assertFalse(list(metrics.glob("metrics_*.jsonl")))
        # Small records fit; one that would cross the cap doesn't.
        self.assertTrue(log("q"))
        self.assertFalse(log("x" * 1900))
        today = next(metrics.glob("metrics_*.jsonl"))
        self.assertLessEqual(today.stat().st_size, 2000)

    def test_a_record_over_the_record_limit_is_dropped_under_any_cap(self) -> None:
        from neuralmind.metrics_pipeline import METRICS_MAX_RECORD_BYTES

        collector = MetricsCollector(self.project)  # the default 10 MB cap
        ok = collector.log_query_metrics(
            session_id="s",
            query="x" * (METRICS_MAX_RECORD_BYTES + 1),
            latency_ms=1.0,
            retrieval_reuse_rate=0.0,
            tool_calls=0,
            tool_successes=0,
            tokens_used=0,
            synapses_activated=0,
        )
        self.assertFalse(ok)
        self.assertFalse(list((self.project / ".neuralmind" / "metrics").glob("metrics_*.jsonl")))

    def test_rotation_brings_a_file_of_large_records_under_the_cap(self) -> None:
        collector = MetricsCollector(self.project, max_bytes=4000)
        metrics = self.project / ".neuralmind" / "metrics"
        metrics.mkdir(parents=True)
        yesterday = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 86400))
        past = metrics / f"metrics_{yesterday}.jsonl"
        big = json.dumps({"event": "query", "query": "x" * 1500, "ts": time.time()})
        past.write_text("".join(f"{big}\n" for _ in range(10)))
        collector.rotate()
        self.assertLessEqual(past.stat().st_size, 2000)
        # The newest whole records are the ones kept.
        lines = past.read_text().splitlines()
        self.assertTrue(lines)
        self.assertTrue(all(json.loads(line)["query"] == "x" * 1500 for line in lines))

    def test_the_cap_counts_what_another_process_appended_while_waiting(self) -> None:
        from unittest import mock

        from neuralmind import metrics_pipeline

        collector = MetricsCollector(self.project, max_bytes=300)
        self.assertTrue(
            collector.log_recall_metrics(outcome="injected", injected=1, similarity=0.5)
        )
        today = next((self.project / ".neuralmind" / "metrics").glob("metrics_*.jsonl"))
        real_lock = metrics_pipeline._lock_file

        def lock_after_another_append(fd: int) -> bool:
            # Another hook process's record lands while this one waits.
            with open(today, "ab") as f:
                f.write(b'{"event": "other", "pad": "' + b"x" * 150 + b'"}\n')
            return real_lock(fd)

        with mock.patch.object(metrics_pipeline, "_lock_file", lock_after_another_append):
            ok = collector.log_recall_metrics(outcome="injected", injected=1, similarity=0.5)
        self.assertFalse(ok)
        self.assertLessEqual(today.stat().st_size, 300)

    def test_concurrent_processes_lose_and_tear_no_records(self) -> None:
        import os
        import subprocess
        import sys

        root = Path(__file__).resolve().parents[1]
        code = (
            "import sys\n"
            "from neuralmind.metrics_pipeline import MetricsCollector\n"
            "c = MetricsCollector(sys.argv[1])\n"
            "for i in range(40):\n"
            "    assert c.log_recall_metrics(outcome='injected', injected=i, similarity=0.5)\n"
        )
        env = dict(
            os.environ, PYTHONPATH=os.pathsep.join([str(root), os.environ.get("PYTHONPATH", "")])
        )
        procs = [
            subprocess.Popen([sys.executable, "-c", code, str(self.project)], env=env)
            for _ in range(4)
        ]
        self.assertEqual([p.wait(timeout=120) for p in procs], [0, 0, 0, 0])
        lines = [
            line
            for f in (self.project / ".neuralmind" / "metrics").glob("metrics_*.jsonl")
            for line in f.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(len(lines), 160)
        self.assertTrue(all(json.loads(line)["event"] == "recall" for line in lines))


if __name__ == "__main__":
    unittest.main(verbosity=2)
