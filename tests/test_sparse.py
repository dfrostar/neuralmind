"""Tests for the SPLADE-style learned sparse retrieval (PRD 2 B2)."""

from __future__ import annotations

import pytest

from neuralmind.sparse import (
    SpladeExpander,
    SpladeConfig,
    SparseIndex,
    tokenize,
    sparse_dot,
    sparse_norm,
    cosine_sparse,
    normalize_sparse,
    truncate_sparse,
)


class TestTokenize:
    def test_basic(self):
        assert tokenize("Hello World") == ["hello", "world"]

    def test_punctuation(self):
        assert tokenize("handle()") == ["handle"]

    def test_empty(self):
        assert tokenize("") == []


class TestSparseDot:
    def test_overlap(self):
        assert sparse_dot({"a": 1.0, "b": 2.0}, {"a": 3.0, "c": 4.0}) == 3.0

    def test_disjoint(self):
        assert sparse_dot({"a": 1.0}, {"b": 2.0}) == 0.0

    def test_empty(self):
        assert sparse_dot({}, {"a": 1.0}) == 0.0


class TestSparseNorm:
    def test_basic(self):
        assert sparse_norm({"a": 3.0, "b": 4.0}) == pytest.approx(5.0)

    def test_empty(self):
        assert sparse_norm({}) == 0.0


class TestCosineSparse:
    def test_identical(self):
        v = {"a": 1.0, "b": 2.0}
        assert cosine_sparse(v, v) == pytest.approx(1.0)

    def test_orthogonal(self):
        assert cosine_sparse({"a": 1.0}, {"b": 1.0}) == 0.0

    def test_empty(self):
        assert cosine_sparse({}, {"a": 1.0}) == 0.0


class TestNormalizeSparse:
    def test_basic(self):
        v = normalize_sparse({"a": 3.0, "b": 4.0})
        assert sparse_norm(v) == pytest.approx(1.0)

    def test_empty(self):
        assert normalize_sparse({}) == {}


class TestTruncateSparse:
    def test_within_limit(self):
        v = {"a": 1.0, "b": 2.0, "c": 3.0}
        assert len(truncate_sparse(v, top_k=5)) == 3

    def test_truncates(self):
        v = {str(i): float(i) for i in range(100)}
        result = truncate_sparse(v, top_k=10)
        assert len(result) == 10
        assert "99" in result  # highest weight


class TestSpladeExpander:
    def test_expand_basic(self):
        expander = SpladeExpander(SpladeConfig(use_idf=False, normalize=False))
        vec = expander.expand("hello world hello")
        assert "hello" in vec
        assert "world" in vec

    def test_expand_empty(self):
        expander = SpladeExpander(SpladeConfig(use_idf=False))
        assert expander.expand("") == {}

    def test_fit_and_expand(self):
        expander = SpladeExpander(SpladeConfig(normalize=False))
        expander.fit(["hello world", "foo bar", "hello foo"])
        vec = expander.expand("hello")
        # After fitting, IDF weighting is active.
        assert "hello" in vec

    def test_expand_query(self):
        expander = SpladeExpander(SpladeConfig(use_idf=False, normalize=True))
        qvec = expander.expand_query("hello world")
        assert "hello" in qvec
        assert "world" in qvec
        assert sparse_norm(qvec) == pytest.approx(1.0)

    def test_score(self):
        expander = SpladeExpander(SpladeConfig(use_idf=False, normalize=True))
        qvec = expander.expand_query("hello world")
        cvec = expander.expand("hello world foo")
        score = expander.score(qvec, cvec)
        assert 0.0 < score <= 1.0

    def test_search(self):
        expander = SpladeExpander(SpladeConfig(use_idf=False, normalize=True))
        chunks = [
            "authentication handler for JWT tokens",
            "database connection pool config",
            "user profile model schema",
        ]
        results = expander.search("auth JWT", chunks, top_k=2)
        assert len(results) == 2
        # The auth chunk should rank highest.
        assert "authentication" in results[0][0]

    def test_expand_batch(self):
        expander = SpladeExpander(SpladeConfig(use_idf=False))
        results = expander.expand_batch(["hello", "world"])
        assert len(results) == 2


class TestSparseIndex:
    def test_add_and_search(self):
        idx = SparseIndex(SpladeExpander(SpladeConfig(use_idf=False, normalize=True)))
        idx.add("doc1", "authentication handler")
        idx.add("doc2", "database config")
        results = idx.search("auth handler", top_k=1)
        assert len(results) == 1
        assert results[0][0] == "doc1"

    def test_search_empty_index(self):
        idx = SparseIndex(SpladeExpander(SpladeConfig(use_idf=False)))
        assert idx.search("query", top_k=5) == []
