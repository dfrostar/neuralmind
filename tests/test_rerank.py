"""Tests for the cross-encoder reranking (PRD 2 B3)."""

from __future__ import annotations

import pytest

from neuralmind.rerank import (
    CrossEncoderReranker,
    HeuristicReranker,
    RerankConfig,
)


class TestHeuristicReranker:
    def test_score_pair_identical(self):
        r = HeuristicReranker()
        assert r.score_pair("hello world", "hello world") == pytest.approx(1.0)

    def test_score_pair_no_overlap(self):
        r = HeuristicReranker()
        assert r.score_pair("hello", "foobar") == 0.0

    def test_score_pair_partial(self):
        r = HeuristicReranker()
        score = r.score_pair("auth handler JWT", "database pool")
        assert 0.0 <= score <= 1.0


class TestCrossEncoderReranker:
    def test_disabled_returns_unchanged(self):
        r = CrossEncoderReranker(RerankConfig(enabled=False))
        cands = ["a", "b", "c"]
        results = r.rerank("query", cands)
        assert [x[0] for x in results] == cands

    def test_enabled_reranks(self):
        r = CrossEncoderReranker(RerankConfig(enabled=True, max_latency_ms=1000))
        cands = [
            "authentication handler JWT",
            "database connection pool",
            "user profile schema",
        ]
        results = r.rerank("auth JWT handler", cands, top_k=2)
        assert len(results) == 2
        # The auth chunk should rank highest.
        assert "authentication" in results[0][0]

    def test_stats(self):
        r = CrossEncoderReranker(RerankConfig(enabled=True, max_latency_ms=1000))
        r.rerank("query", ["a", "b"])
        stats = r.stats()
        assert stats["enabled"] is True
        assert stats["num_queries"] == 1
        assert stats["model_loaded"] is False  # no model path

    def test_latency_budget_exceeded(self):
        r = CrossEncoderReranker(RerankConfig(enabled=True, max_latency_ms=0.0001))
        # Force the avg latency above budget.
        r._avg_latency_ms = 100.0
        cands = ["a", "b", "c"]
        results = r.rerank("query", cands)
        # Returns unscored (latency budget exceeded).
        assert all(score == 0.0 for _, score in results)
        assert [x[0] for x in results] == cands
