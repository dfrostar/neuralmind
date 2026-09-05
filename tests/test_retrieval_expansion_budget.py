"""The v3.9.0 retrieval pull-in must stay off by default, and stay budget-neutral when on.

Regression cover for the faithfulness failure that blocked the 3.9.0 release
(PR #498). Two separate contracts, because breaking either one reproduced the
outage:

1. **Default off is a strict no-op.** With ``NEURALMIND_RETRIEVAL_EXPANSION``
   unset, ``_apply_retrieval_enhancements`` must not add, remove, or reorder a
   single hit beyond the code-signal re-rank. That is what restores the
   pre-3.9.0 faithfulness delta (+0.013 on ``evals/faithfulness``, built-in
   backend), and it is the same shape as the SCIP precision pass, which the
   parity gate proves is a no-op when unset.

2. **On is budget-neutral.** When enabled, pulled-in candidates take the slots
   of existing hits via ``_displace``; they are never appended. The shipped
   v3.9.0 code appended up to eight nodes to a four-hit list and forced their
   scores to a hardcoded 4.5, so they sorted above every real hit and pushed
   the genuine ones past the L3 token budget.

Why the flag exists at all is recorded on
``ContextSelector._apply_retrieval_enhancements``: making the pull-in
budget-neutral did not rescue it (-0.062 appended, -0.122 displaced, against
+0.013 without it). Displacement is necessary but not sufficient — a candidate
worse than the hit it evicts costs a fact rather than only tokens. So the
budget assertions below are deliberately *not* a claim that the pull-in is
good; they pin the mechanism so the next attempt at candidate quality starts
from a sound base.

Stdlib-only by design, matching ``test_displacement_coverage.py``:
``context_selector`` imports without ChromaDB or numpy, so this keeps running
in the dependency-light test job.
"""

from __future__ import annotations

import os
import unittest
from unittest import mock

from neuralmind.context_selector import ContextSelector, _expansion_enabled


def _hits():
    """Four ranked hits over two modules — the shape `_displace` was written for."""
    return [
        {
            "id": "api_routes_py__refund_fn",
            "score": 1.0,
            "document": "def refund(...)",
            "metadata": {"source_file": "api/routes.py", "file_type": "code"},
        },
        {
            "id": "api_routes_py__charge_fn",
            "score": 0.948,
            "document": "def charge(...)",
            "metadata": {"source_file": "api/routes.py", "file_type": "code"},
        },
        {
            "id": "billing_stripe_client_py__refund_fn",
            "score": 0.947,
            "document": "def issue_refund(...)",
            "metadata": {"source_file": "billing/stripe_client.py", "file_type": "code"},
        },
        {
            "id": "billing_stripe_client_py__charge_fn",
            "score": 0.946,
            "document": "def charge_card(...)",
            "metadata": {"source_file": "billing/stripe_client.py", "file_type": "code"},
        },
    ]


class _StubEmbedder:
    """Returns pull-in candidates that are absent from the ranked hits."""

    project_path = "/nonexistent"

    def __init__(self, extra=3):
        self._extra = [
            {
                "id": f"synapses_py__node_{i}",
                "score": 0.5,
                "document": "def reinforce(...)",
                "metadata": {"source_file": "neuralmind/synapses.py", "file_type": "code"},
            }
            for i in range(extra)
        ]

    def get_all_nodes(self):
        return [dict(n) for n in self._extra]

    def get_nodes_by_ids(self, node_ids):
        return [dict(n) for n in self._extra if n["id"] in set(node_ids)]


def _selector(embedder=None):
    """A ContextSelector with only the attributes this path touches.

    Built without ``__init__`` so the test needs no project on disk and no
    optional backend — the method under test reads four attributes.
    """
    sel = ContextSelector.__new__(ContextSelector)
    sel.embedder = embedder
    sel.synapse_recall = None
    sel._synapse_store = None
    return sel


class TestFlagParsing(unittest.TestCase):
    """The flag is read at call time, so it can be flipped per-test and per-run."""

    def test_unset_is_off(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(_expansion_enabled())

    def test_zero_is_off(self):
        for value in ("0", "", "false", "no", "off"):
            with mock.patch.dict(os.environ, {"NEURALMIND_RETRIEVAL_EXPANSION": value}):
                self.assertFalse(_expansion_enabled(), value)

    def test_truthy_values_are_on(self):
        for value in ("1", "true", "TRUE", "yes", "on", " 1 "):
            with mock.patch.dict(os.environ, {"NEURALMIND_RETRIEVAL_EXPANSION": value}):
                self.assertTrue(_expansion_enabled(), value)


class TestDefaultOffIsANoOp(unittest.TestCase):
    """Contract 1: unset means the pull-in cannot touch the ranked hits."""

    def test_hit_count_and_ids_unchanged(self):
        sel = _selector(_StubEmbedder())
        before = _hits()
        with mock.patch.dict(os.environ, {}, clear=True):
            after = sel._apply_retrieval_enhancements(
                "How does the synapse layer implement reinforce?", _hits(), "code"
            )
        self.assertEqual([r["id"] for r in after], [r["id"] for r in before])

    def test_no_pulled_in_node_appears(self):
        sel = _selector(_StubEmbedder())
        with mock.patch.dict(os.environ, {}, clear=True):
            after = sel._apply_retrieval_enhancements(
                "How does the synapse layer implement reinforce?", _hits(), "code"
            )
        self.assertFalse([r for r in after if r.get("_source_file_match")])

    def test_candidate_gathering_is_never_reached(self):
        """Not just "no candidates survive" — the scan must not run at all.

        ``_search_source_files`` walks every node in the index, so leaving it
        on the default query path is a latency cost even when its output is
        discarded.
        """
        sel = _selector(_StubEmbedder())
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(ContextSelector, "_enhancement_candidates") as gather,
        ):
            sel._apply_retrieval_enhancements("How does X implement Y?", _hits(), "code")
        gather.assert_not_called()

    def test_docs_intent_is_untouched(self):
        sel = _selector(_StubEmbedder())
        with mock.patch.dict(os.environ, {}, clear=True):
            after = sel._apply_retrieval_enhancements("What is a synapse?", _hits(), "docs")
        self.assertEqual([r["id"] for r in after], [r["id"] for r in _hits()])


class TestEnabledStaysBudgetNeutral(unittest.TestCase):
    """Contract 2: enabled, candidates displace rather than accumulate."""

    def _run(self, hits, embedder):
        sel = _selector(embedder)
        with mock.patch.dict(os.environ, {"NEURALMIND_RETRIEVAL_EXPANSION": "1"}):
            return sel._apply_retrieval_enhancements(
                "How does the synapse layer implement reinforce?", hits, "code"
            )

    def test_hit_count_is_fixed(self):
        hits = _hits()
        after = self._run(hits, _StubEmbedder(extra=3))
        self.assertEqual(len(after), len(_hits()))

    def test_more_candidates_than_slots_still_does_not_grow(self):
        """The shipped bug in one assertion: eight candidates, four slots."""
        after = self._run(_hits(), _StubEmbedder(extra=8))
        self.assertEqual(len(after), len(_hits()))

    def test_at_least_one_vector_hit_survives(self):
        after = self._run(_hits(), _StubEmbedder(extra=8))
        original = {r["id"] for r in _hits()}
        self.assertTrue(original.intersection(r["id"] for r in after))

    def test_pulled_in_candidates_keep_their_producer_score(self):
        """A candidate may not have its score rewritten to win the comparison.

        ``_search_source_files`` caps its own score at 2.0. v3.9.0 threw that
        away with ``max(score, 4.5)`` and then doubled every code score, so
        injected nodes outranked every real hit by construction and ranking
        stopped deciding anything.

        Scoped to pulled-in candidates on purpose: the surviving vector hits
        legitimately carry a much larger number here, because
        ``apply_code_signal_boost`` multiplies a matching hit by up to 10x.
        That is a re-rank of something retrieval actually returned, which is
        the distinction this test exists to hold.
        """
        after = self._run(_hits(), _StubEmbedder(extra=3))
        pulled_in = [r for r in after if r.get("_source_file_match")]
        self.assertTrue(pulled_in, "expected the stub embedder's candidates to be pulled in")
        for hit in pulled_in:
            self.assertLessEqual(float(hit.get("score") or 0.0), 2.0, hit.get("id"))

    def test_no_duplicate_ids(self):
        after = self._run(_hits(), _StubEmbedder(extra=3))
        ids = [r["id"] for r in after]
        self.assertEqual(len(ids), len(set(ids)))

    def test_absent_embedder_is_survivable(self):
        after = self._run(_hits(), None)
        self.assertEqual(len(after), len(_hits()))


class TestFailsOpen(unittest.TestCase):
    """A broken enhancement must degrade to plain vector ranking, never raise."""

    def test_empty_results_pass_through(self):
        sel = _selector(_StubEmbedder())
        self.assertEqual(sel._apply_retrieval_enhancements("anything", [], "code"), [])

    def test_candidate_gathering_failure_returns_ranked_hits(self):
        sel = _selector(_StubEmbedder())
        with (
            mock.patch.dict(os.environ, {"NEURALMIND_RETRIEVAL_EXPANSION": "1"}),
            mock.patch(
                "neuralmind.retrieval_enhancement._search_source_files",
                side_effect=RuntimeError("index unavailable"),
            ),
        ):
            after = sel._apply_retrieval_enhancements("How does X implement Y?", _hits(), "code")
        self.assertEqual(len(after), len(_hits()))


if __name__ == "__main__":
    unittest.main()
