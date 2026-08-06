"""N-15 SOTA Retrieval Quality Benchmark — CI regression gates.

Asserts that retrieval quality and faithfulness stay above conservative
floors. Floors are set to catch catastrophes, not to demand unrealistic
numbers from the stdlib-only RAGAS judge on compressed retrieval output.

Floor rationale:
- recall@5 ≥ 0.50 — at least half of expected modules appear in top-5
- mrr ≥ 0.40 — first relevant result typically in top-2.5
- ndcg@5 ≥ 0.50 — ranked quality above random
- hit_rate ≥ 0.80 — at most ~4/20 queries completely miss
- mean_faithfulness ≥ 0.0 — stdlib-only judge on compressed context;
  floor catches complete failures (faithfulness=0 for all queries).
  Embedding-dependent RAGAS scores would raise this substantially.
- mean_contradiction ≤ 0.20 — contradiction rate below 20%
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "sample_project"
GRAPH_JSON = FIXTURE_DIR / "graphify-out" / "graph.json"
RESULTS_PATH = REPO_ROOT / "tests" / "benchmark" / "retrieval_results.json"

# Conservative regression floors
RECALL_AT_5_FLOOR = 0.50
MRR_FLOOR = 0.40
NDCG_AT_5_FLOOR = 0.50
HIT_RATE_FLOOR = 0.80
MEAN_FAITHFULNESS_FLOOR = 0.0  # stdlib-only judge on compressed context
MEAN_CONTRADICTION_CEILING = 0.20


@pytest.fixture(scope="module")
def retrieval_results():
    """Run the retrieval benchmark once and cache results."""
    if not GRAPH_JSON.exists():
        pytest.skip(
            f"Fixture graph not built at {GRAPH_JSON}. "
            "CI builds it via graphify; run `graphify update tests/fixtures/sample_project` locally."
        )

    from tests.benchmark.retrieval_run import run_benchmark, write_results

    results = run_benchmark()
    write_results(results)
    assert RESULTS_PATH.exists(), "retrieval benchmark did not write results.json"
    return results


class TestRetrievalBenchmark:
    """7 CI regression gates for retrieval quality."""

    def test_recall_at_5_above_floor(self, retrieval_results):
        """Recall@5 must clear the conservative regression floor."""
        recall = retrieval_results.aggregates["recall_at_5"]
        assert recall >= RECALL_AT_5_FLOOR, (
            f"Recall@5 {recall:.4f} dropped below floor {RECALL_AT_5_FLOOR}. "
            "Retrieval is missing expected modules."
        )

    def test_mrr_above_floor(self, retrieval_results):
        """MRR must clear the conservative regression floor."""
        mrr_val = retrieval_results.aggregates["mrr"]
        assert mrr_val >= MRR_FLOOR, (
            f"MRR {mrr_val:.4f} dropped below floor {MRR_FLOOR}. "
            "First relevant result is too far down the ranking."
        )

    def test_ndcg_at_5_above_floor(self, retrieval_results):
        """nDCG@5 must clear the conservative regression floor."""
        ndcg = retrieval_results.aggregates["ndcg_at_5"]
        assert ndcg >= NDCG_AT_5_FLOOR, (
            f"nDCG@5 {ndcg:.4f} dropped below floor {NDCG_AT_5_FLOOR}. "
            "Ranked quality has degraded."
        )

    def test_hit_rate_above_floor(self, retrieval_results):
        """Hit rate must clear the conservative regression floor."""
        hr = retrieval_results.aggregates["hit_rate"]
        assert hr >= HIT_RATE_FLOOR, (
            f"Hit rate {hr:.4f} dropped below floor {HIT_RATE_FLOOR}. "
            "Multiple queries are returning zero relevant modules."
        )

    def test_mean_faithfulness_above_floor(self, retrieval_results):
        """Mean faithfulness must not drop to zero (complete failure)."""
        faith = retrieval_results.aggregates["faithfulness"]
        assert faith > MEAN_FAITHFULNESS_FLOOR, (
            f"Mean faithfulness {faith:.4f} is at zero — all queries scoring 0. "
            "The stdlib-only RAGAS judge detects no fact recall on compressed context."
        )

    def test_mean_contradiction_below_ceiling(self, retrieval_results):
        """Mean contradiction rate must stay below ceiling."""
        contra = retrieval_results.aggregates["contradiction"]
        assert contra <= MEAN_CONTRADICTION_CEILING, (
            f"Mean contradiction {contra:.4f} exceeds ceiling {MEAN_CONTRADICTION_CEILING}. "
            "Contradiction rate is too high — possible negation-flip or choice-violation surge."
        )

    def test_no_query_has_zero_relevant_in_top_5(self, retrieval_results):
        """Per-query: at least 1 expected module in top 5 for every query.

        Zero tolerance for complete misses — averaged metrics can hide
        queries that return zero relevant modules. This test catches them.
        """
        zero_hit = [q["id"] for q in retrieval_results.queries if q["recall_at_5"] == 0.0]
        assert len(zero_hit) == 0, (
            f"{len(zero_hit)} queries returned zero relevant modules in top-5: {zero_hit}. "
            "Each query should surface at least one expected module."
        )

    def test_per_shape_hit_rate(self, retrieval_results):
        """No shape should have hit_rate below 0.70.

        Per-shape breakdown catches regressions that only hit specific
        query shapes (e.g., cross-file queries suddenly missing).
        """
        for shape, metrics in retrieval_results.by_shape.items():
            hr = metrics["hit_rate"]
            assert hr >= 0.70, (
                f"Shape '{shape}' hit rate {hr:.4f} below 0.70. "
                "This shape is broadly missing expected modules."
            )
