"""Regression gate for the self-benchmark.

Runs the full benchmark as part of the normal pytest suite and asserts
that the aggregate reduction ratio stays above a conservative floor.
Far below NeuralMind's real-world 40–70× — this test catches only
catastrophic regressions.

Skipped cleanly if the fixture has not been built yet (missing
``graphify-out/graph.json``). CI handles the build step before calling
pytest so the skip only triggers during local-dev runs where the user
opted out of benchmark-gating.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "sample_project"
GRAPH_JSON = FIXTURE_DIR / "graphify-out" / "graph.json"
RESULTS_PATH = REPO_ROOT / "tests" / "benchmark" / "results.json"

REDUCTION_FLOOR = 20.0  # keep in sync with tests/benchmark/run.py
HIT_RATE_FLOOR = 0.50   # at least half of expected modules should show up


@pytest.fixture(scope="module")
def benchmark_results():
    """Run the benchmark once per session and cache results for all tests."""
    if not GRAPH_JSON.exists():
        pytest.skip(
            f"Fixture graph not built at {GRAPH_JSON}. "
            "CI builds it via graphify; run `graphify update tests/fixtures/sample_project` locally."
        )

    # Import lazily so pytest collection doesn't require tiktoken when
    # the fixture isn't built.
    from tests.benchmark import run as bench_run

    bench_run.main()
    assert RESULTS_PATH.exists(), "benchmark did not write results.json"
    return json.loads(RESULTS_PATH.read_text())


def test_reduction_ratio_above_floor(benchmark_results):
    """Aggregate reduction must clear the conservative regression floor."""
    ratio = benchmark_results["phase1_reduction"]["avg_reduction_ratio"]
    assert ratio >= REDUCTION_FLOOR, (
        f"Reduction ratio {ratio:.1f}× dropped below floor {REDUCTION_FLOOR}×. "
        "Something genuinely regressed — inspect the per-query table in report.md."
    )


def test_top_k_hit_rate_above_floor(benchmark_results):
    """Retrieval should find at least half of the expected modules on average."""
    hit_rate = benchmark_results["phase1_reduction"]["avg_top_k_hit_rate"]
    assert hit_rate >= HIT_RATE_FLOOR, (
        f"Top-k hit rate {hit_rate:.2%} dropped below floor {HIT_RATE_FLOOR:.0%}. "
        "Retrieval is surfacing the wrong modules — suspect embedding or cluster regressions."
    )


def test_every_query_has_at_least_one_module_hit(benchmark_results):
    """No single query should return zero relevant modules."""
    zero_hit = [
        q["id"] for q in benchmark_results["phase1_reduction"]["queries"]
        if q["top_k_hit_rate"] == 0.0
    ]
    assert not zero_hit, (
        f"Queries returned no expected modules at all: {zero_hit}. "
        "The benchmark allows partial misses, but zero-hit queries indicate "
        "the retrieval is completely missing the intended area."
    )
