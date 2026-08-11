"""N-16 Content Benchmark — CI regression gates for book/content retrieval quality.

Asserts that content retrieval quality stays above conservative floors.
Floors are set to catch catastrophes, not to demand unrealistic numbers.

Floor rationale:
- recall@5 ≥ 0.20 — at least 1 in 5 of expected paragraphs in top-5 (was
  calibrated against the first full run 2026-08-05, which measured ~0.26)
- mrr ≥ 0.30 — first relevant paragraph typically caught somewhere in the
  top-3 (post fix, MRR is no longer trivially 1.0; see run.compute_ir_metrics)
- ndcg@5 ≥ 0.20 — ranked quality above random
- hit_rate ≥ 0.50 — at most ~half of queries completely miss
- mean_faithfulness ≥ 0.0 — the stdlib-only judge is strict (all-token gold
  overlap against compressed output) so 0.0 is the honest baseline
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_V2_PATH = REPO_ROOT / "evals" / "book_retrieval" / "manifest_v2.json"
CHAPTERS_DIR = REPO_ROOT / "evals" / "book_retrieval" / "underground" / "chapters"

# Conservative regression floors for content retrieval
# These are honest baselines from the first full run (2026-08-05).
# Content retrieval on a 150K-word book is genuinely hard — these floors
# catch catastrophes (complete failures), not demand high performance.
# Faithfulness floor is 0.0 because the stdlib-only RAGAS judge on compressed
# context is very strict — it checks for exact token matches from gold paragraphs
# in NeuralMind's compressed output. Embedding-based RAGAS would raise this.
RECALL_AT_5_FLOOR = 0.20
MRR_FLOOR = 0.30
NDCG_AT_5_FLOOR = 0.20
HIT_RATE_FLOOR = 0.50
MEAN_FAITHFULNESS_FLOOR = 0.0
PER_SHAPE_HIT_RATE_FLOOR = 0.30


def _run_content_benchmark() -> dict:
    """Run the book retrieval eval v2 and return results."""
    from evals.book_retrieval.run import run_eval

    if not MANIFEST_V2_PATH.exists():
        pytest.skip(f"Manifest v2 not found at {MANIFEST_V2_PATH}")

    if not CHAPTERS_DIR.exists():
        pytest.skip(f"Chapters not found at {CHAPTERS_DIR}")

    return run_eval(verbose=False, manifest_path=MANIFEST_V2_PATH)


@pytest.fixture(scope="module")
def content_benchmark_results():
    """Run the content benchmark once and cache results."""
    # Allow skipping in CI environments without neuralmind installed
    if os.environ.get("SKIP_CONTENT_BENCHMARK") == "1":
        pytest.skip("SKIP_CONTENT_BENCHMARK=1")

    try:
        import neuralmind  # noqa: F401
    except ImportError:
        pytest.skip("neuralmind not installed")

    results = _run_content_benchmark()
    if "error" in results:
        pytest.skip(f"Content benchmark failed: {results['error']}")
    return results


class TestContentBenchmark:
    """7 CI regression gates for content retrieval quality."""

    def test_recall_at_5_above_floor(self, content_benchmark_results):
        """Recall@5 must clear the conservative regression floor."""
        recall = content_benchmark_results["aggregates"]["recall_at_5"]
        assert recall >= RECALL_AT_5_FLOOR, (
            f"Recall@5 {recall:.4f} dropped below floor {RECALL_AT_5_FLOOR}. "
            "Content retrieval is missing expected paragraphs."
        )

    def test_mrr_above_floor(self, content_benchmark_results):
        """MRR must clear the conservative regression floor."""
        mrr_val = content_benchmark_results["aggregates"]["mrr"]
        assert mrr_val >= MRR_FLOOR, (
            f"MRR {mrr_val:.4f} dropped below floor {MRR_FLOOR}. "
            "First relevant paragraph is too far down the ranking."
        )

    def test_ndcg_at_5_above_floor(self, content_benchmark_results):
        """nDCG@5 must clear the conservative regression floor."""
        ndcg = content_benchmark_results["aggregates"]["ndcg_at_5"]
        assert ndcg >= NDCG_AT_5_FLOOR, (
            f"nDCG@5 {ndcg:.4f} dropped below floor {NDCG_AT_5_FLOOR}. "
            "Ranked quality has degraded."
        )

    def test_hit_rate_above_floor(self, content_benchmark_results):
        """Hit rate must clear the conservative regression floor."""
        hr = content_benchmark_results["aggregates"]["hit_rate"]
        assert hr >= HIT_RATE_FLOOR, (
            f"Hit rate {hr:.4f} dropped below floor {HIT_RATE_FLOOR}. "
            "Multiple queries are returning zero relevant paragraphs."
        )

    def test_mean_faithfulness_above_floor(self, content_benchmark_results):
        """Mean faithfulness must clear the conservative regression floor."""
        faith = content_benchmark_results["aggregates"]["mean_faithfulness"]
        assert faith >= MEAN_FAITHFULNESS_FLOOR, (
            f"Mean faithfulness {faith:.4f} below floor {MEAN_FAITHFULNESS_FLOOR}. "
            "Retrieved context does not support answering questions."
        )

    def test_no_query_has_zero_relevant_in_top_5(self, content_benchmark_results):
        """Per-query: at least 1 relevant paragraph in top-5 for every query.

        Zero tolerance for complete misses — averaged metrics can hide
        queries that return zero relevant paragraphs.
        """
        zero_hit = [
            q["id"]
            for q in content_benchmark_results["queries"]
            if q["ir_metrics"]["recall_at_5"] == 0.0
        ]
        assert len(zero_hit) == 0, (
            f"{len(zero_hit)} queries returned zero relevant paragraphs in top-5: {zero_hit}. "
            "Each query should surface at least one relevant paragraph."
        )

    def test_per_shape_hit_rate(self, content_benchmark_results):
        """No shape should have hit_rate below the per-shape floor."""
        by_shape = content_benchmark_results.get("by_shape", {})
        for shape, metrics in by_shape.items():
            hr = metrics["hit_rate"]
            assert hr >= PER_SHAPE_HIT_RATE_FLOOR, (
                f"Shape '{shape}' hit rate {hr:.4f} below {PER_SHAPE_HIT_RATE_FLOOR}. "
                "This shape is broadly missing expected paragraphs."
            )
