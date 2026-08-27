"""Regression gate for the self-benchmark.

Runs the full benchmark as part of the normal pytest suite and asserts
that the aggregate reduction ratio stays above a conservative floor.
Far below NeuralMind's real-world 12–50× — this test catches only
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

REDUCTION_FLOOR = 4.0  # keep in sync with tests/benchmark/run.py
HIT_RATE_FLOOR = 0.50  # at least half of expected modules should show up


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


def test_synapse_recall_does_not_reduce_hit_rate(benchmark_results):
    """Synapse recall must never make retrieval worse.

    Budget-neutral displacement could in principle drop a relevant vector
    hit for a co-activated-but-wrong one. This gate catches that: with the
    same warm graph, recall on must surface at least as many expected
    modules as recall off. This is the CI enforcement behind the published
    "recall-on ≥ recall-off" claim (README, site) — loosening it changes
    what the product is allowed to say, not just what CI tolerates. A -2pt
    tolerance briefly lived here for the bimodality described below; it was
    removed when the harness pinned the suspected source instead.

    History of that bimodality, kept because it is the map if this ever
    recurs. The same commit on the same runner image produced both -1.75 and
    +4.0 points, landing on one mode *per job* and returning it bit-for-bit
    on every in-process repeat — so the mean of N in-job runs is N copies of
    one draw, and averaging cannot converge it. `off_hit_rate_runs` /
    `on_hit_rate_runs` publish the spread; read them first. Ruled out by
    measurement: CPU/SIMD feature set, PYTHONHASHSEED, the graph partition
    (identical digest across a passing and a failing job), Python patch
    version, resolved dependency versions, neighbour-row order out of the
    un-ORDER BY'd synapse query, and the recall ranking reverted in #464.

    What that left was the vector path, and the one machine property none of
    the fingerprints captured: core count. ORT sizes its intra-op pool to the
    host, and parallel-summation order moves the last bits of the embedding
    floats — machine-fixed, rebuild-stable, exactly the observed profile. The
    harness now pins NEURALMIND_ORT_THREADS=1 and records cpu_count plus an
    embedding-probe digest (graph.embedding_probe_sha256_16). If this gate
    fails again: compare that probe digest and per-query hit_modules
    (phase2_synapse.queries vs .off_queries) against a passing job before
    anything else — matching probes with a real delta means displacement
    genuinely regressed; differing probes falsify the thread pin and name
    the next suspect.
    """
    p3 = benchmark_results["phase2_synapse"]
    runs = ", ".join(
        f"{(on - off) * 100:+.1f}"
        for off, on in zip(
            p3.get("off_hit_rate_runs", []), p3.get("on_hit_rate_runs", []), strict=False
        )
    )
    assert p3["on_avg_top_k_hit_rate"] >= p3["off_avg_top_k_hit_rate"] - 1e-9, (
        f"Synapse recall lowered hit rate: {p3['off_avg_top_k_hit_rate']:.2%} off → "
        f"{p3['on_avg_top_k_hit_rate']:.2%} on, averaged over "
        f"{p3.get('ab_runs', 1)} run(s) [{runs}] points. "
        "Displacement is dropping relevant hits — see this test's docstring "
        "for the probe-digest diagnosis path before assuming a flake."
    )


def test_synapse_ab_is_averaged_over_several_runs(benchmark_results):
    """The gate above is only meaningful if it publishes more than one sample.

    Not because the mean converges — it does not, see above — but because the
    per-run list is the evidence that distinguishes "this job drew the low
    mode" from "retrieval genuinely regressed". Dropping the repeat, or
    setting NEURALMIND_SYNAPSE_AB_RUNS=1 to make a red build go green, would
    throw away exactly the signal needed to tell those two apart, and nothing
    else would say so.
    """
    p3 = benchmark_results["phase2_synapse"]
    assert p3.get("ab_runs", 1) >= 2, (
        f"Phase-2 A/B ran {p3.get('ab_runs', 1)} time(s). The hit-rate gate "
        "decides a directional claim from a metric that moves between runs, so "
        "it must average at least two."
    )
    assert len(p3.get("on_hit_rate_runs", [])) == p3.get("ab_runs", 1), (
        "Per-run hit rates must be published alongside the mean — a mean that "
        "hides its own spread is what let this metric look stable."
    )


def test_synapse_recall_is_budget_neutral(benchmark_results):
    """Synapse recall reshapes selection without growing the token budget."""
    p3 = benchmark_results["phase2_synapse"]
    assert abs(p3["reduction_delta"]) <= 0.5, (
        f"Synapse recall moved the reduction ratio by {p3['reduction_delta']:+.2f}× "
        f"({p3['off_avg_reduction_ratio']:.1f}× off → {p3['on_avg_reduction_ratio']:.1f}× on). "
        "It should be budget-neutral — recalled nodes displace, not append."
    )


def test_every_query_has_at_least_one_module_hit(benchmark_results):
    """No single query should return zero relevant modules.

    The benchmark explicitly allows partial misses (documented in the
    query set's ``_comment``). On a small hermetic fixture (~500 lines),
    a query can legitimately miss without synapse recall — the point of
    Phase 2 is to show synapse recall closing exactly this gap. Allow at
    most one zero-hit query in Phase 1; more than that signals a genuine
    retrieval regression.
    """
    zero_hit = [
        q["id"]
        for q in benchmark_results["phase1_reduction"]["queries"]
        if q["top_k_hit_rate"] == 0.0
    ]
    assert len(zero_hit) <= 1, (
        f"{len(zero_hit)} queries returned no expected modules: {zero_hit}. "
        "The benchmark allows partial misses, but multiple zero-hit queries "
        "indicate the retrieval is broadly missing the intended area."
    )
