"""Unit tests for tests/benchmark/metrics.py — hand-computed expected values.

Every expected value below is derived by hand, not by calling the function
under test. If the implementation drifts, these tests catch it.
"""

from __future__ import annotations

import math

import pytest

from tests.benchmark.metrics import (
    hit_rate,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)

# --------------------------------------------------------------------------- #
# recall_at_k
# --------------------------------------------------------------------------- #


class TestRecallAtK:
    def test_all_relevant_in_top_k(self):
        actual = ["a", "b", "c", "d"]
        relevant = {"a", "b"}
        # Top-4: both relevant items captured → 2/2 = 1.0
        assert recall_at_k(actual, relevant, 4) == 1.0

    def test_half_relevant_in_top_k(self):
        actual = ["a", "x", "b", "y"]
        relevant = {"a", "b", "c"}
        # Top-2: only "a" is relevant → 1/3
        assert recall_at_k(actual, relevant, 2) == pytest.approx(1 / 3)

    def test_k_smaller_than_relevant_count(self):
        actual = ["a", "b", "c"]
        relevant = {"a", "b", "c"}
        # Top-1: only "a" → 1/3
        assert recall_at_k(actual, relevant, 1) == pytest.approx(1 / 3)

    def test_no_relevant_items(self):
        actual = ["a", "b"]
        relevant = set()
        assert recall_at_k(actual, relevant, 2) == 0.0

    def test_no_overlap(self):
        actual = ["x", "y"]
        relevant = {"a", "b"}
        assert recall_at_k(actual, relevant, 2) == 0.0

    def test_k_zero(self):
        actual = ["a", "b"]
        relevant = {"a"}
        assert recall_at_k(actual, relevant, 0) == 0.0


# --------------------------------------------------------------------------- #
# precision_at_k
# --------------------------------------------------------------------------- #


class TestPrecisionAtK:
    def test_all_hits(self):
        actual = ["a", "b", "c"]
        relevant = {"a", "b", "c"}
        # Top-3: 3 hits / 3 = 1.0
        assert precision_at_k(actual, relevant, 3) == 1.0

    def test_half_hits(self):
        actual = ["a", "x", "b"]
        relevant = {"a", "b"}
        # Top-2: 1 hit ("a") / 2 = 0.5
        assert precision_at_k(actual, relevant, 2) == 0.5

    def test_k_larger_than_actual(self):
        actual = ["a"]
        relevant = {"a"}
        # Top-5: 1 hit / 5 = 0.2
        assert precision_at_k(actual, relevant, 5) == 0.2

    def test_k_zero(self):
        actual = ["a"]
        relevant = {"a"}
        assert precision_at_k(actual, relevant, 0) == 0.0

    def test_no_hits(self):
        actual = ["x", "y"]
        relevant = {"a"}
        assert precision_at_k(actual, relevant, 2) == 0.0


# --------------------------------------------------------------------------- #
# mrr
# --------------------------------------------------------------------------- #


class TestMrr:
    def test_first_item_relevant(self):
        actual = ["a", "b", "c"]
        relevant = {"a"}
        # First relevant at position 1 → 1/1 = 1.0
        assert mrr(actual, relevant) == 1.0

    def test_second_item_relevant(self):
        actual = ["x", "a", "y"]
        relevant = {"a"}
        # First relevant at position 2 → 1/2 = 0.5
        assert mrr(actual, relevant) == 0.5

    def test_third_item_relevant(self):
        actual = ["x", "y", "a"]
        relevant = {"a"}
        # First relevant at position 3 → 1/3
        assert mrr(actual, relevant) == pytest.approx(1 / 3)

    def test_no_relevant_item(self):
        actual = ["x", "y"]
        relevant = {"a"}
        assert mrr(actual, relevant) == 0.0

    def test_empty_actual(self):
        actual = []
        relevant = {"a"}
        assert mrr(actual, relevant) == 0.0


# --------------------------------------------------------------------------- #
# ndcg_at_k
# --------------------------------------------------------------------------- #


class TestNdcgAtK:
    def test_perfect_ordering(self):
        # Ideal: rel={a:3, b:2, c:1} — actual is already ideal.
        actual = ["a", "b", "c"]
        relevance = {"a": 3, "b": 2, "c": 1}
        # DCG@3 = (2^3-1)/log2(2) + (2^2-1)/log2(3) + (2^1-1)/log2(4)
        #        = 7/1 + 3/log2(3) + 1/2
        # IDCG@3 = same (ideal order)
        # nDCG = 1.0
        assert ndcg_at_k(actual, relevance, 3) == pytest.approx(1.0)

    def test_reversed_ordering(self):
        # Worst case: actual is reverse of ideal.
        actual = ["c", "b", "a"]
        relevance = {"a": 3, "b": 2, "c": 1}
        # DCG@3 = (2^1-1)/log2(2) + (2^2-1)/log2(3) + (2^3-1)/log2(4)
        #        = 1/1 + 3/log2(3) + 7/2
        # IDCG@3 = 7/1 + 3/log2(3) + 1/2
        dcg = 1.1 + 3 / math.log2(3) + 7 / 2  # ≈ 1 + 1.893 + 3.5 = 6.393
        idcg = 7.0 + 3 / math.log2(3) + 0.5  # ≈ 7 + 1.893 + 0.5 = 9.393
        # Wait, let me recompute DCG carefully:
        # DCG@3 = (2^1-1)/log2(2) + (2^2-1)/log2(3) + (2^3-1)/log2(4)
        #        = 1/1 + 3/log2(3) + 7/2
        #        = 1 + 1.8928 + 3.5 = 6.3928
        # IDCG@3 = (2^3-1)/log2(2) + (2^2-1)/log2(3) + (2^1-1)/log2(4)
        #         = 7/1 + 3/log2(3) + 1/2
        #         = 7 + 1.8928 + 0.5 = 9.3928
        # nDCG = 6.3928 / 9.3928 ≈ 0.6806
        expected = (1 / 1 + 3 / math.log2(3) + 7 / 2) / (7 / 1 + 3 / math.log2(3) + 1 / 2)
        assert ndcg_at_k(actual, relevance, 3) == pytest.approx(expected, rel=1e-4)

    def test_partial_relevance(self):
        # Some items have relevance 0 (not in dict).
        actual = ["a", "x", "b"]
        relevance = {"a": 3, "b": 1}
        # DCG@3 = (2^3-1)/log2(2) + (2^0-1)/log2(3) + (2^1-1)/log2(4)
        #        = 7/1 + 0/log2(3) + 1/2
        #        = 7 + 0 + 0.5 = 7.5
        # IDCG@3 = 7/1 + 1/log2(3) + 0/2 = 7 + 0.6309 = 7.6309
        dcg = 7 / 1 + 0 / math.log2(3) + 1 / 2
        idcg = 7 / 1 + 1 / math.log2(3) + 0 / 2
        assert ndcg_at_k(actual, relevance, 3) == pytest.approx(dcg / idcg)

    def test_all_zero_relevance(self):
        actual = ["a", "b"]
        relevance = {}
        # No relevant items → IDCG=0 → nDCG=0
        assert ndcg_at_k(actual, relevance, 2) == 0.0

    def test_k_zero(self):
        actual = ["a"]
        relevance = {"a": 3}
        assert ndcg_at_k(actual, relevance, 0) == 0.0

    def test_k_larger_than_actual(self):
        actual = ["a", "b"]
        relevance = {"a": 3, "b": 2, "c": 1}
        # DCG@4 = (2^3-1)/log2(2) + (2^2-1)/log2(3) + 0 (no more items)
        #        = 7/1 + 3/log2(3)
        # IDCG@4 = 7/1 + 3/log2(3) + 1/log2(4) = 7 + 1.8928 + 0.5 = 9.3928
        dcg = 7 / 1 + 3 / math.log2(3)
        idcg = 7 / 1 + 3 / math.log2(3) + 1 / 2
        assert ndcg_at_k(actual, relevance, 4) == pytest.approx(dcg / idcg)


# --------------------------------------------------------------------------- #
# hit_rate
# --------------------------------------------------------------------------- #


class TestHitRate:
    def test_at_least_one_hit(self):
        actual = ["a", "b"]
        relevant = {"b"}
        assert hit_rate(actual, relevant) == 1.0

    def test_no_hit(self):
        actual = ["a", "b"]
        relevant = {"x"}
        assert hit_rate(actual, relevant) == 0.0

    def test_empty_actual(self):
        actual = []
        relevant = {"a"}
        assert hit_rate(actual, relevant) == 0.0

    def test_empty_relevant(self):
        actual = ["a"]
        relevant = set()
        assert hit_rate(actual, relevant) == 0.0

    def test_multiple_hits(self):
        actual = ["a", "b", "c"]
        relevant = {"a", "c"}
        assert hit_rate(actual, relevant) == 1.0
