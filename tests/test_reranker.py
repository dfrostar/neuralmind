"""
test_reranker.py — Tests for Cooccurrence-Based Reranking
=========================================================

Tests CooccurrenceIndex and SemanticReranker classes.
"""

import json
import tempfile
from pathlib import Path

import pytest

from neuralmind.reranker import CooccurrenceIndex, SemanticReranker


@pytest.fixture
def sample_patterns_json() -> dict:
    """Sample learned patterns JSON."""
    return {
        "metadata": {
            "version": "1",
            "created_at": "2026-04-20T00:00:00Z",
            "events_analyzed": 42,
            "patterns_learned": 3,
        },
        "cooccurrence": {
            "auth|validation": 10,
            "auth|middleware": 8,
            "db|cache": 5,
            "api|routes": 3,
        },
        "module_frequency": {
            "auth": 15,
            "validation": 12,
            "middleware": 8,
            "db": 10,
            "cache": 7,
            "api": 5,
            "routes": 4,
        },
    }


@pytest.fixture
def patterns_file(sample_patterns_json):
    """Temporary patterns file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(sample_patterns_json, f)
        path = Path(f.name)
    yield path
    path.unlink()


@pytest.fixture
def sample_search_results() -> list[dict]:
    """Sample search results from embedder."""
    return [
        {
            "id": "auth_module",
            "text": "Authentication handler",
            "metadata": {"source_file": "auth.py", "community": 0},
            "distance": 0.2,
        },
        {
            "id": "api_module",
            "text": "API routes",
            "metadata": {"source_file": "api.py", "community": 1},
            "distance": 0.5,
        },
        {
            "id": "validation_module",
            "text": "Input validation",
            "metadata": {"source_file": "validation.py", "community": 0},
            "distance": 0.7,
        },
    ]


class TestCooccurrenceIndex:
    """Tests for CooccurrenceIndex class."""

    def test_load_valid_file(self, patterns_file, sample_patterns_json):
        """Test loading valid patterns JSON file."""
        index = CooccurrenceIndex.load(patterns_file)

        assert index.is_valid()
        assert index.pattern_count() == 4
        assert index.cooccurrence["auth|validation"] == 10

    def test_load_missing_file(self):
        """Test loading from non-existent file."""
        index = CooccurrenceIndex.load(Path("/nonexistent/file.json"))

        assert not index.is_valid()
        assert index.pattern_count() == 0

    def test_load_invalid_json(self):
        """Test loading from invalid JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json }")
            path = Path(f.name)

        try:
            index = CooccurrenceIndex.load(path)
            assert not index.is_valid()
        finally:
            path.unlink()

    def test_score_pair_normalizes_to_0_1(self, patterns_file):
        """Test that score_pair returns normalized 0-1 values."""
        index = CooccurrenceIndex.load(patterns_file)

        # auth|validation has count 10 (highest)
        score = index.score_pair("auth", "validation")
        assert 0.0 <= score <= 1.0
        assert score == 1.0  # Highest count normalized to 1.0

        # api|routes has count 3 (lowest)
        score = index.score_pair("api", "routes")
        assert 0.0 <= score <= 1.0
        assert score < 1.0

    def test_score_pair_symmetric(self, patterns_file):
        """Test that score is same regardless of module order."""
        index = CooccurrenceIndex.load(patterns_file)

        score1 = index.score_pair("auth", "validation")
        score2 = index.score_pair("validation", "auth")
        assert score1 == score2

    def test_score_pair_unknown_modules(self, patterns_file):
        """Test score for modules not in patterns."""
        index = CooccurrenceIndex.load(patterns_file)

        score = index.score_pair("unknown", "also_unknown")
        assert score == 0.0

    def test_score_pair_empty_index(self):
        """Test score on empty index."""
        index = CooccurrenceIndex()
        score = index.score_pair("any", "thing")
        assert score == 0.0

    def test_get_top_cooccurrences_sorted(self, patterns_file):
        """Test that top cooccurrences are sorted by count."""
        index = CooccurrenceIndex.load(patterns_file)

        # auth has cooccurrence with: validation (10), middleware (8)
        top = index.get_top_cooccurrences("auth", n=2)
        assert len(top) == 2
        assert top[0][0] == "validation"  # Higher count first
        assert top[1][0] == "middleware"

    def test_get_top_cooccurrences_respects_n(self, patterns_file):
        """Test that result count respects n parameter."""
        index = CooccurrenceIndex.load(patterns_file)

        top3 = index.get_top_cooccurrences("auth", n=3)
        assert len(top3) <= 3

        top1 = index.get_top_cooccurrences("auth", n=1)
        assert len(top1) == 1

    def test_get_top_cooccurrences_empty_index(self):
        """Test top cooccurrences on empty index."""
        index = CooccurrenceIndex()
        top = index.get_top_cooccurrences("any", n=5)
        assert top == []

    def test_is_valid_empty_index(self):
        """Test is_valid on empty index."""
        index = CooccurrenceIndex()
        assert not index.is_valid()

    def test_pattern_count(self, patterns_file):
        """Test pattern_count returns correct number."""
        index = CooccurrenceIndex.load(patterns_file)
        assert index.pattern_count() == 4


class TestSemanticReranker:
    """Tests for SemanticReranker class."""

    def test_rerank_with_no_index_passes_through(self, sample_search_results):
        """Test that reranking is skipped with empty index."""
        reranker = SemanticReranker(CooccurrenceIndex())
        reranked = reranker.rerank(sample_search_results)

        assert reranked == sample_search_results

    def test_rerank_with_patterns_returns_results(
        self, sample_search_results, patterns_file
    ):
        """Test that reranking returns same number of results."""
        index = CooccurrenceIndex.load(patterns_file)
        reranker = SemanticReranker(index)

        reranked = reranker.rerank(sample_search_results)
        assert len(reranked) == len(sample_search_results)

    def test_rerank_preserves_result_fields(
        self, sample_search_results, patterns_file
    ):
        """Test that reranking preserves original result fields."""
        index = CooccurrenceIndex.load(patterns_file)
        reranker = SemanticReranker(index)

        reranked = reranker.rerank(sample_search_results)

        for original, result in zip(sample_search_results, reranked):
            assert result["id"] == original["id"]
            assert result["text"] == original["text"]

    def test_rerank_adds_boost_fields(self, sample_search_results, patterns_file):
        """Test that reranking adds _reranker_boost and _combined_score."""
        index = CooccurrenceIndex.load(patterns_file)
        reranker = SemanticReranker(index)

        reranked = reranker.rerank(sample_search_results)

        for result in reranked:
            assert "_reranker_boost" in result
            assert "_combined_score" in result

    def test_rerank_with_context_modules(
        self, sample_search_results, patterns_file
    ):
        """Test reranking with context modules specified."""
        index = CooccurrenceIndex.load(patterns_file)
        reranker = SemanticReranker(index)

        # auth and validation have high cooccurrence
        context = ["auth"]
        reranked = reranker.rerank(sample_search_results, context_modules=context)

        # validation should get boost
        validation_result = [r for r in reranked if r["id"] == "validation_module"][0]
        assert validation_result["_reranker_boost"] > 0.0

    def test_rerank_empty_results(self, patterns_file):
        """Test reranking with empty results list."""
        index = CooccurrenceIndex.load(patterns_file)
        reranker = SemanticReranker(index)

        reranked = reranker.rerank([])
        assert reranked == []

    def test_rerank_single_result(self, patterns_file):
        """Test reranking with single result."""
        index = CooccurrenceIndex.load(patterns_file)
        reranker = SemanticReranker(index)

        single = [
            {
                "id": "test",
                "text": "test",
                "metadata": {"source_file": "test.py"},
                "distance": 0.5,
            }
        ]

        reranked = reranker.rerank(single)
        assert len(reranked) == 1

    def test_extract_module_id_from_source_file(self):
        """Test module ID extraction from source_file metadata."""
        result = {
            "id": "ignored",
            "metadata": {"source_file": "auth.py"},
        }
        module_id = SemanticReranker._extract_module_id(result)
        assert module_id == "auth.py"

    def test_extract_module_id_from_community(self):
        """Test module ID extraction from community metadata."""
        result = {
            "id": "ignored",
            "metadata": {"community": 5},
        }
        module_id = SemanticReranker._extract_module_id(result)
        assert module_id == "community_5"

    def test_extract_module_id_from_id_field(self):
        """Test module ID extraction falls back to id field."""
        result = {"id": "module_123", "metadata": {}}
        module_id = SemanticReranker._extract_module_id(result)
        assert module_id == "module_123"

    def test_extract_module_id_none_on_empty(self):
        """Test module ID extraction returns None for empty result."""
        module_id = SemanticReranker._extract_module_id({})
        assert module_id is None

    def test_measure_savings_no_results(self):
        """Test savings measurement with no results."""
        reranker = SemanticReranker()
        savings = reranker.measure_savings([], [])
        assert savings["estimated_savings_tokens"] == 0
        assert savings["estimated_savings_pct"] == 0.0

    def test_measure_savings_no_change(self, sample_search_results):
        """Test savings when reranking doesn't change result order."""
        reranker = SemanticReranker()
        savings = reranker.measure_savings(
            sample_search_results, sample_search_results
        )
        assert savings["estimated_savings_tokens"] == 0

    def test_measure_savings_with_reranking(self, sample_search_results):
        """Test savings when top result changes."""
        reranker = SemanticReranker()

        # Simulate reranking changing top result
        reranked = sample_search_results[1:] + [sample_search_results[0]]

        savings = reranker.measure_savings(sample_search_results, reranked)
        assert savings["estimated_savings_tokens"] > 0
        assert "reason" in savings

    def test_reranker_graceful_on_none_index(self, sample_search_results):
        """Test reranker handles None index gracefully."""
        reranker = SemanticReranker(None)
        reranked = reranker.rerank(sample_search_results)

        # Should pass through unchanged
        assert len(reranked) == len(sample_search_results)

    def test_reranker_with_missing_metadata(self, patterns_file):
        """Test reranking results with missing metadata."""
        index = CooccurrenceIndex.load(patterns_file)
        reranker = SemanticReranker(index)

        results_no_metadata = [
            {"id": "test1", "distance": 0.2},
            {"id": "test2", "distance": 0.5},
        ]

        reranked = reranker.rerank(results_no_metadata)
        assert len(reranked) == 2


class TestIntegration:
    """Integration tests for learning pipeline."""

    def test_index_load_and_rerank_end_to_end(
        self, sample_search_results, patterns_file
    ):
        """Test complete flow: load index → rerank results."""
        # Load patterns
        index = CooccurrenceIndex.load(patterns_file)
        assert index.is_valid()

        # Create reranker
        reranker = SemanticReranker(index)

        # Rerank
        reranked = reranker.rerank(sample_search_results, context_modules=["auth"])

        # Validate
        assert len(reranked) == len(sample_search_results)
        assert all("_reranker_boost" in r for r in reranked)

    def test_multiple_reranks_consistent(
        self, sample_search_results, patterns_file
    ):
        """Test that reranking same results multiple times is consistent."""
        index = CooccurrenceIndex.load(patterns_file)
        reranker = SemanticReranker(index)

        reranked1 = reranker.rerank(sample_search_results)
        reranked2 = reranker.rerank(sample_search_results)

        # Results should be same
        assert reranked1[0]["id"] == reranked2[0]["id"]
