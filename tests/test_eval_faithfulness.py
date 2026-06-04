"""Stdlib-only tests for the faithfulness eval foundation (issue #172, E1.1).

These deliberately use ``unittest`` (no pytest) and import nothing heavy, so
they run in a minimal environment that has neither pytest nor chromadb:

    python tests/test_eval_faithfulness.py

Covers: queries.json loading/validation and the offline expected-fact-recall
scorer. Answer generation (E1.2) and the full judge (E1.3) are not tested
here because they are not implemented yet.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Make ``evals`` importable without installing the package.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evals.faithfulness.runner import (  # noqa: E402
    SCHEMA_VERSION,
    ExpectedFact,
    OfflineJudge,
    Query,
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
        with self.assertRaises(ValueError):
            load_query_set(path)


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

    def test_e1_3_methods_are_stubbed(self) -> None:
        with self.assertRaises(NotImplementedError):
            self.judge.grounding_rate(self.query, "x")
        with self.assertRaises(NotImplementedError):
            self.judge.contradiction_score(self.query, "x")


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
