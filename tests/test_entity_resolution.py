"""Tests for the entity resolution layer (PRD 2 A2)."""

from __future__ import annotations

import pytest

from neuralmind.entity_resolution import (
    EntityResolver,
    EntityKey,
    norm_label,
    cosine_similarity,
    AUTO_MERGE_THRESHOLD,
    REVIEW_FLAG_THRESHOLD,
)


class TestNormLabel:
    def test_lowercase(self):
        assert norm_label("MyFunction") == "myfunction"

    def test_strips_punctuation(self):
        assert norm_label("app.auth.handle()") == "app_auth_handle"

    def test_collapses_underscores(self):
        assert norm_label("a___b") == "a_b"

    def test_strips_leading_trailing(self):
        assert norm_label("__foo__") == "foo"

    def test_empty(self):
        assert norm_label("") == ""

    def test_complex_path(self):
        assert norm_label("src/utils/helpers.py") == "src_utils_helpers_py"


class TestCosineSimilarity:
    def test_identical(self):
        assert cosine_similarity({"a", "b", "c"}, {"a", "b", "c"}) == pytest.approx(1.0)

    def test_disjoint(self):
        assert cosine_similarity({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self):
        sim = cosine_similarity({"a", "b", "c"}, {"a", "b", "d"})
        assert 0.0 < sim < 1.0

    def test_empty(self):
        assert cosine_similarity(set(), {"a", "b"}) == 0.0


class TestEntityKey:
    def test_from_label(self):
        key = EntityKey.from_label("handle()")
        assert key.norm == "handle"
        assert key.tokens == {"handle"}

    def test_with_anchor(self):
        key = EntityKey.from_label("handle()", anchor="auth.py")
        assert key.structural_anchor == "auth.py"


class TestEntityResolver:
    def test_exact_match(self):
        resolver = EntityResolver()
        resolver.register("node-1", "auth.handle()")
        result = resolver.resolve("auth.handle()")
        assert result.status == "merge"
        assert result.confidence == 1.0
        assert result.target_id == "node-1"

    def test_normalized_match(self):
        resolver = EntityResolver()
        resolver.register("node-1", "auth.Handle")
        result = resolver.resolve("auth.handle")
        assert result.status == "merge"
        assert result.confidence == 1.0

    def test_distinct(self):
        resolver = EntityResolver()
        resolver.register("node-1", "auth.handle()")
        result = resolver.resolve("completely_different_name")
        assert result.status == "distinct"

    def test_resolve_many(self):
        resolver = EntityResolver()
        resolver.register("node-1", "auth.handle()")
        resolver.register("node-2", "db.query()")
        results = resolver.resolve_many(["auth.handle()", "db.query()", "unknown"])
        assert len(results) == 3
        assert results[0].status == "merge"
        assert results[1].status == "merge"
        assert results[2].status == "distinct"

    def test_register_many(self):
        resolver = EntityResolver()
        resolver.register_many([("node-1", "a", None), ("node-2", "b", None)])
        assert resolver.stats()["registered_entities"] == 2

    def test_stats(self):
        resolver = EntityResolver(auto_merge_threshold=0.9, review_threshold=0.8)
        stats = resolver.stats()
        assert stats["registered_entities"] == 0
        assert stats["auto_merge_threshold"] == 0.9
        assert stats["review_threshold"] == 0.8
