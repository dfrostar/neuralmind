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
    `on_hit_rate_runs` publish the spread; read them first.

    RESOLVED 2026-08-28 (PR #484). Two conclusions previously recorded here
    were wrong. They are corrected rather than deleted, because each one sent
    an investigation down a dead end:

    - "Ruled out by measurement: CPU/SIMD feature set" — SIMD in fact
      correlates perfectly. Every failing run observed was on an avx512f host
      and every passing run was not. What that earlier measurement got right
      is narrower than it sounds: SIMD does not reach the *embeddings*.
    - "What that left was core count" — it did not. One failing and three
      passing runs all reported cpu_count 4, and NEURALMIND_ORT_THREADS=1 did
      not stop the failure: a run with the pin active in its step env still
      failed with the same numbers.

    What the artifacts showed, once `if: always()` began keeping results.json
    on failing runs: graph.embedding_probe_sha256_16 was IDENTICAL between
    passing and failing runs, so the embeddings are bit-identical and the
    embedding path was never the variable. The vector-only baseline
    (off_queries) matched on all 19 queries. Exactly one query differed with
    recall on — `refund` lost its single expected module,
    billing/stripe_client.py, from the kept results. One query of nineteen
    flipping 1.0 -> 0.0 is 100/19 = 5.26 points, exactly the gap between the
    two observed modes.

    Cause: the ranking sorts in neuralmind/context_selector.py ordered on a
    raw float score. _apply_synapse_recall re-sorts the kept results after
    boosting and then drops the tail to hold the displacement budget, so a
    last-bit difference in a score decided which node fell off the end — and
    that difference was host-dependent. Those sites now use _rank_key(), which
    quantises the score and breaks ties on node id, making the order a
    function of the data alone. tests/test_rank_determinism.py pins that
    contract; its two-host case fails against the old sort.

    If this gate fails again: compare the probe digest and per-query
    hit_modules (phase2_synapse.queries vs .off_queries) against a passing job
    before anything else. Matching probes with a real delta means displacement
    regressed again — check whether a ranking site was added without
    _rank_key(). Differing probes would be genuinely new; the embedding path
    has been stable across every run measured so far.
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
