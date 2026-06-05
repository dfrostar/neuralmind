"""Stdlib-only tests for the faithfulness eval (issue #172, E1.1–E1.4).

These deliberately use ``unittest`` (no pytest) and import nothing heavy, so
they run in a minimal environment that has neither pytest nor chromadb:

    python tests/test_eval_faithfulness.py

Covers: queries.json loading/validation, the three offline judge dimensions
(expected-fact recall, grounding, contradiction), and the A/B harness +
report (E1.2/E1.4) exercised with injected stub context providers so the real
retrieval stack is never required.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

# Make ``evals`` importable without installing the package.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evals.faithfulness import harness  # noqa: E402
from evals.faithfulness.runner import (  # noqa: E402
    SCHEMA_VERSION,
    ExpectedFact,
    OfflineJudge,
    Query,
    QuerySet,
    load_query_set,
)


class LoadQuerySetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.qs = load_query_set()

    def test_schema_version_matches(self) -> None:
        self.assertEqual(self.qs.schema_version, SCHEMA_VERSION)

    def test_at_least_fifteen_queries(self) -> None:
        self.assertGreaterEqual(len(self.qs), 15)

    def test_query_ids_unique(self) -> None:
        ids = [q.id for q in self.qs.queries]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_query_has_facts_and_modules(self) -> None:
        for q in self.qs.queries:
            with self.subTest(query=q.id):
                self.assertTrue(q.expected_facts, "needs >=1 expected fact")
                self.assertTrue(q.expected_modules, "needs >=1 expected module")
                self.assertTrue(q.question.strip(), "needs a question")

    def test_fact_ids_unique_within_query(self) -> None:
        for q in self.qs.queries:
            fact_ids = [f.id for f in q.expected_facts]
            with self.subTest(query=q.id):
                self.assertEqual(len(fact_ids), len(set(fact_ids)))

    def test_unsupported_version_rejected(self) -> None:
        import json
        import os
        import tempfile

        bad = {
            "schema_version": 999,
            "fixture": "x",
            "queries": [
                {
                    "id": "q",
                    "question": "?",
                    "expected_modules": ["m"],
                    "expected_facts": [{"id": "f", "fact": "x"}],
                }
            ],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump(bad, fh)
            path = fh.name
        try:
            with self.assertRaises(ValueError):
                load_query_set(path)
        finally:
            os.unlink(path)


class OfflineRecallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.judge = OfflineJudge()
        self.query = Query(
            id="demo",
            question="how does X work?",
            expected_facts=(
                ExpectedFact("f-sqlite", "the fixture uses SQLite", ("sqlite3",)),
                ExpectedFact("f-hash", "the password hash is verified", ("verify_password",)),
            ),
        )

    def test_perfect_answer_scores_full_recall(self) -> None:
        answer = "The fixture uses SQLite and the password hash is verified."
        result = self.judge.fact_recall(self.query, answer)
        self.assertEqual(result.matched, 2)
        self.assertEqual(result.total, 2)
        self.assertEqual(result.recall, 1.0)

    def test_empty_answer_scores_zero(self) -> None:
        result = self.judge.fact_recall(self.query, "")
        self.assertEqual(result.matched, 0)
        self.assertEqual(result.recall, 0.0)

    def test_alias_matches_when_canonical_absent(self) -> None:
        # Names the code symbols, never the prose.
        answer = "It calls sqlite3.connect and verify_password()."
        result = self.judge.fact_recall(self.query, answer)
        self.assertEqual(result.matched, 2)
        self.assertEqual(result.recall, 1.0)

    def test_partial_recall(self) -> None:
        # Matches the SQLite fact (alias "sqlite3") but says nothing about the
        # password hash, so recall is 1/2.
        answer = "It stores data via sqlite3."
        result = self.judge.fact_recall(self.query, answer)
        self.assertEqual(result.matched, 1)
        self.assertEqual(result.recall, 0.5)

    def test_matching_ignores_case_and_punctuation(self) -> None:
        # The alias "verify_password" must still match "VERIFY-PASSWORD"
        # because normalisation lowercases and collapses punctuation.
        answer = "the password hash is VERIFY-PASSWORD checked"
        result = self.judge.fact_recall(self.query, answer)
        self.assertTrue(any(f.fact_id == "f-hash" and f.matched for f in result.facts))

    def test_mean_recall_averages_per_query(self) -> None:
        full = "the fixture uses SQLite; the password hash is verified"
        half = "the fixture uses SQLite"
        mean = self.judge.mean_recall([(self.query, full), (self.query, half)])
        self.assertAlmostEqual(mean, 0.75)

    def test_short_alias_does_not_match_inside_words(self) -> None:
        # A two-letter alias must not match *inside* an unrelated word
        # (e.g. "id" inside "valid") — that would inflate the CI-gate recall.
        q = Query(
            id="boundary",
            question="?",
            expected_facts=(ExpectedFact("f-id", "the record has an id column", ("id",)),),
        )
        self.assertEqual(self.judge.fact_recall(q, "the token is valid and invalid").matched, 0)
        # but it still matches as a standalone token.
        self.assertEqual(self.judge.fact_recall(q, "the record id is a primary key").matched, 1)

    def test_ultra_short_alias_is_ignored(self) -> None:
        # A single-character needle (e.g. an alias like "t=" → "t") is too
        # noisy to be a reliable match and is skipped entirely.
        q = Query(
            id="tiny",
            question="?",
            expected_facts=(ExpectedFact("f-t", "the header carries a t field", ("t=",)),),
        )
        self.assertEqual(self.judge.fact_recall(q, "there is a t value here").matched, 0)

    def test_grounding_rate_counts_cited_modules(self) -> None:
        q = Query(
            id="g",
            question="?",
            expected_facts=(ExpectedFact("f", "x"),),
            expected_modules=("auth/handlers.py", "auth/jwt_utils.py"),
        )
        # Cites one of the two expected modules → 0.5.
        self.assertEqual(self.judge.grounding_rate(q, "see auth/handlers.py for login"), 0.5)
        self.assertEqual(self.judge.grounding_rate(q, "nothing relevant here"), 0.0)

    def test_contradiction_flags_wrong_choice(self) -> None:
        q = Query(
            id="db",
            question="?",
            expected_facts=(ExpectedFact("f", "the fixture uses SQLite", ("sqlite",)),),
            expected_modules=("db/connection.py",),
        )
        # Gold says SQLite; answer asserts PostgreSQL → contradiction.
        self.assertGreater(self.judge.contradiction_score(q, "it uses PostgreSQL"), 0.0)
        # Correct choice → none.
        self.assertEqual(self.judge.contradiction_score(q, "it uses sqlite"), 0.0)

    def test_contradiction_zero_when_no_group_applies(self) -> None:
        # No gold fact selects a side of any contradiction group → 0.0.
        q = Query(
            id="none",
            question="?",
            expected_facts=(ExpectedFact("f", "the password hash is verified"),),
            expected_modules=("auth/handlers.py",),
        )
        self.assertEqual(self.judge.contradiction_score(q, "anything at all"), 0.0)


class GoldSetSanityTests(unittest.TestCase):
    """A 'perfect' answer naming every fact should always score recall 1.0;
    this guards against an alias/canonical typo silently breaking a fact."""

    def test_perfect_answer_scores_full_on_real_gold_set(self) -> None:
        qs = load_query_set()
        judge = OfflineJudge()
        for q in qs.queries:
            perfect = " ".join(f.fact for f in q.expected_facts)
            result = judge.fact_recall(q, perfect)
            with self.subTest(query=q.id):
                self.assertEqual(result.recall, 1.0)


class HarnessTests(unittest.TestCase):
    """E1.2/E1.4 — the A/B harness + report, run with injected stub providers
    so no chromadb/tiktoken is required."""

    def setUp(self) -> None:
        self.qs = QuerySet(
            schema_version=1,
            fixture="x",
            queries=[
                Query(
                    id="q1",
                    question="?",
                    expected_facts=(ExpectedFact("a", "alpha"), ExpectedFact("b", "beta")),
                    expected_modules=("m1.py",),
                ),
            ],
        )

    def test_truncate_to_budget_is_bounded(self) -> None:
        text = " ".join(["word"] * 1000)
        out = harness._truncate_to_tokens(text, 10)
        self.assertTrue(out)
        self.assertLessEqual(harness.count_tokens(out), 10)
        self.assertEqual(harness._truncate_to_tokens(text, 0), "")

    def test_context_answerer_echoes_context(self) -> None:
        ans = harness.ContextAnswerer().answer(self.qs.queries[0], "ctx text")
        self.assertEqual(ans, "ctx text")

    def test_run_ab_neuralmind_beats_naive(self) -> None:
        results = harness.run_ab(
            self.qs,
            context_provider=lambda q: "alpha and beta are both here",
            naive_provider=lambda budget: "alpha only",
        )
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r.nm_recall, 1.0)
        self.assertEqual(r.naive_recall, 0.5)
        self.assertGreater(r.recall_delta, 0.0)

    def test_build_and_render_report(self) -> None:
        results = harness.run_ab(
            self.qs,
            context_provider=lambda q: "alpha and beta",
            naive_provider=lambda budget: "",
        )
        report = harness.build_report(self.qs, results)
        self.assertAlmostEqual(report.faithfulness_delta, 1.0)

        payload = json.loads(harness.render_json(report))
        self.assertEqual(payload["faithfulness_delta"], 1.0)
        self.assertEqual(payload["n_queries"], 1)
        self.assertIn("per_query", payload)

        md = harness.render_markdown(report)
        self.assertIn("faithfulness delta", md.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
