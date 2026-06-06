"""Stdlib-only tests for the onboarding-lift eval (E1.5).

Like the faithfulness/synapse tests, these import nothing heavy (no chromadb):
the harness imports ``neuralmind`` lazily, so the seed-history loader, the A/B
math, and the report render are all exercised with injected stub providers.

    python tests/test_onboarding_eval.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evals.faithfulness.runner import ExpectedFact, Query, QuerySet  # noqa: E402
from evals.onboarding import harness  # noqa: E402


def _query(qid: str, facts: list[tuple[str, str]], modules: list[str]) -> Query:
    return Query(
        id=qid,
        question=f"q-{qid}?",
        expected_facts=tuple(ExpectedFact(id=fid, fact=ftext) for fid, ftext in facts),
        expected_modules=tuple(modules),
    )


def _query_set(queries: list[Query]) -> QuerySet:
    return QuerySet(schema_version=1, fixture="tests/fixtures/sample_project", queries=queries)


class SeedHistoryTests(unittest.TestCase):
    def test_loads_committed_baseline(self) -> None:
        seed = harness.load_seed_history()
        self.assertGreaterEqual(len(seed.sessions), 3)
        self.assertGreaterEqual(seed.repeats, 1)
        # every committed session is a co-edit group of >= 2 files
        for sess in seed.sessions:
            self.assertGreaterEqual(len(sess), 2)

    def test_total_activations(self) -> None:
        seed = harness.load_seed_history()
        self.assertEqual(seed.total_activations, seed.repeats * len(seed.sessions))

    def _write_and_load(self, payload: dict):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump(payload, fh)
            path = fh.name
        try:
            return harness.load_seed_history(path)
        finally:
            os.unlink(path)

    def test_rejects_bad_schema_version(self) -> None:
        with self.assertRaises(ValueError):
            self._write_and_load(
                {"schema_version": 99, "fixture": "x", "repeats": 1, "sessions": [["a", "b"]]}
            )

    def test_rejects_empty_sessions(self) -> None:
        with self.assertRaises(ValueError):
            self._write_and_load(
                {"schema_version": 1, "fixture": "x", "repeats": 1, "sessions": []}
            )

    def test_rejects_singleton_session(self) -> None:
        # a co-edit group needs >= 2 files to teach an association
        with self.assertRaises(ValueError):
            self._write_and_load(
                {"schema_version": 1, "fixture": "x", "repeats": 1, "sessions": [["only_one"]]}
            )

    def test_rejects_non_positive_repeats(self) -> None:
        with self.assertRaises(ValueError):
            self._write_and_load(
                {"schema_version": 1, "fixture": "x", "repeats": 0, "sessions": [["a", "b"]]}
            )


class RunABTests(unittest.TestCase):
    def setUp(self) -> None:
        self.qs = _query_set(
            [
                _query("a", [("f1", "alpha fact"), ("f2", "beta fact")], ["m/a.py"]),
                _query("b", [("f3", "gamma fact")], ["m/b.py"]),
            ]
        )
        self.seed = harness.load_seed_history()

    def test_headline_hit_rate_lift_is_positive(self) -> None:
        # cold top-k surfaces no expected module; onboarded surfaces all of them
        # -> headline onboarding lift (top-k module hit-rate) = +1.0.
        results = harness.run_ab(
            self.qs,
            seed=self.seed,
            cold_provider=lambda q: "",
            onboarded_provider=lambda q: " ".join(f.fact for f in q.expected_facts),
            cold_retrieval=lambda q: "",
            onboarded_retrieval=lambda q: " ".join(q.expected_modules),
        )
        report = harness.build_report(self.qs, results, seed=self.seed)
        self.assertAlmostEqual(report.cold_mean_hit_rate, 0.0)
        self.assertAlmostEqual(report.onboarded_mean_hit_rate, 1.0)
        self.assertAlmostEqual(report.onboarding_lift, 1.0)

    def test_recall_lift_is_a_reported_secondary(self) -> None:
        # cold: nothing; onboarded: every gold fact -> fact-recall lift = +1.0.
        results = harness.run_ab(
            self.qs,
            seed=self.seed,
            cold_provider=lambda q: "",
            onboarded_provider=lambda q: " ".join(f.fact for f in q.expected_facts),
        )
        report = harness.build_report(self.qs, results, seed=self.seed)
        self.assertAlmostEqual(report.cold_mean_recall, 0.0)
        self.assertAlmostEqual(report.onboarded_mean_recall, 1.0)
        self.assertAlmostEqual(report.recall_lift, 1.0)

    def test_zero_lift_when_arms_equal(self) -> None:
        same = lambda q: " ".join(q.expected_modules)  # noqa: E731
        results = harness.run_ab(
            self.qs,
            seed=self.seed,
            cold_provider=same,
            onboarded_provider=same,
            cold_retrieval=same,
            onboarded_retrieval=same,
        )
        report = harness.build_report(self.qs, results, seed=self.seed)
        self.assertAlmostEqual(report.onboarding_lift, 0.0)

    def test_per_query_partial_hit_rate_lift(self) -> None:
        # query "a" expects 1 module the cold top-k misses and onboarded surfaces
        # -> +1.0 there; "b"'s module is in both arms -> 0.0 there.
        def cold_ret(q):
            return "m/b.py" if q.id == "b" else ""

        def onboarded_ret(q):
            return " ".join(q.expected_modules)

        results = harness.run_ab(
            self.qs,
            seed=self.seed,
            cold_provider=lambda q: "",
            onboarded_provider=lambda q: "",
            cold_retrieval=cold_ret,
            onboarded_retrieval=onboarded_ret,
        )
        by_id = {r.query_id: r for r in results}
        self.assertAlmostEqual(by_id["a"].hit_rate_lift, 1.0)
        self.assertAlmostEqual(by_id["b"].hit_rate_lift, 0.0)


class ReportRenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.qs = _query_set([_query("a", [("f1", "alpha fact")], ["m/a.py"])])
        self.seed = harness.load_seed_history()
        self.results = harness.run_ab(
            self.qs,
            seed=self.seed,
            cold_provider=lambda q: "",
            onboarded_provider=lambda q: "alpha fact",
            cold_retrieval=lambda q: "",
            onboarded_retrieval=lambda q: " ".join(q.expected_modules),
        )
        self.report = harness.build_report(self.qs, self.results, seed=self.seed)

    def test_json_round_trips(self) -> None:
        d = json.loads(harness.render_json(self.report))
        self.assertEqual(d["n_queries"], 1)
        self.assertAlmostEqual(d["onboarding_lift"], 1.0)
        self.assertAlmostEqual(d["recall_lift"], 1.0)
        self.assertIn("onboarded_mean_hit_rate", d)
        self.assertIn("per_query", d)

    def test_markdown_runs(self) -> None:
        md = harness.render_markdown(self.report)
        self.assertIn("onboarding-lift eval", md)
        self.assertIn("Onboarding lift", md)

    def test_empty_report_does_not_crash(self) -> None:
        empty = harness.build_report(_query_set([]), [], seed=self.seed)
        self.assertEqual(empty.n_queries, 0)
        self.assertAlmostEqual(empty.onboarding_lift, 0.0)
        json.loads(harness.render_json(empty))
        harness.render_markdown(empty)


if __name__ == "__main__":
    unittest.main(verbosity=2)
