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
    what the product is allowed to say, not just what CI tolerates.

    That -2pt tolerance has now been added and removed TWICE, both times for
    the bimodality described below. The first was removed when the harness
    pinned the suspected source instead. The second landed on 2026-08-29 and
    was reverted the same weekend: it renamed this test to
    "stays_within_host_variance", deleted this very paragraph, and rewrote the
    published claim across README, site/claims.json, llms.txt and the wiki
    from a guarantee into a permitted 2-point regression. Note the sizing —
    the tolerance was 2.0 against an observed failure of 1.75, so it was cut
    to clear the symptom rather than derived from a variance measurement.
    The cost of keeping it would have been permanent: the host-dependent
    ranking bug is real, it makes retrieval genuinely worse for users on that
    hardware, and a 2-point allowance hides it from CI forever.

    If you are here because this gate is red and a tolerance looks like the
    fix: it is the third time. Read WHAT DIFFERS below first.

    History of that bimodality, kept because it is the map if this ever
    recurs. The same commit on the same runner image produced both -1.75 and
    +4.0 points, landing on one mode *per job* and returning it bit-for-bit
    on every in-process repeat — so the mean of N in-job runs is N copies of
    one draw, and averaging cannot converge it. `off_hit_rate_runs` /
    `on_hit_rate_runs` publish the spread; read them first.

    RESOLVED 2026-08-31 (PR #492). Kept in full because four recorded causes
    for this were wrong before the right one, and the wrong ones each cost an
    investigation:

    - "Ruled out by measurement: CPU/SIMD feature set" — wrong. Every failing
      run was on an avx512f host and every passing run was not.
    - "What that left was core count" — wrong. cpu_count is 4 on both sides,
      and NEURALMIND_ORT_THREADS=1 did not stop it.
    - "A last-bit float difference decided which node fell off the end" —
      wrong. The margins are ~1e-1 to ~1e-3. A quantised sort key with an id
      tie-break was tried at all eight ranking sites and measured
      byte-identical failure with it in or out; it was reverted.
    - "graph.vector_index_sha256_16 isolates it" — wrong. A third run produced
      a third digest while returning scores identical to another avx512f host,
      so that digest moves with build conditions too.

    THE ACTUAL CAUSE was a product defect, not a determinism quirk.
    _apply_synapse_boost and _apply_structural_expansion displaced the plain
    tail of the ranked list. When several hits share a file that can evict a
    module's only representatives while keeping two of another's. On `refund`
    the four hits are two api/routes.py rows and two billing/stripe_client.py
    rows; tail-drop kept both api/routes.py rows, so the query scored 0.0 with
    its expected module sitting in the candidates.

    The bimodality followed from that. Which pair landed in the tail depended
    on a ~0.8% score difference that varies by host — too small to be ranking
    signal, too large for a tie-break to absorb, which is why the tie-break
    attempt did nothing.

    THE FIX is _displace() in context_selector.py: prefer a victim whose module
    another survivor still covers, bounded by _COVERAGE_MARGIN so coverage only
    decides between hits the ranking cannot separate. The bound is load-bearing
    — unbounded, it took the parity gate's faithfulness delta from +0.041 to
    -0.006 and failed its floor, because keeping one node from each of two
    files costs facts from the file that actually matched.

    MEASURED at the same commit, both host classes:

        avx512f container    0.7456 -> 0.7807 (+3.51)   refund 1.0, 922 tokens
        non-avx512f runner   0.7456 -> 0.7807 (+3.51)   refund 1.0, 922 tokens

    Identical, where before they were -1.75 and +3.51. Total token counts still
    differ by 7 across 19 queries, so some host-dependence remains in node
    selection; it no longer moves any hit rate.

    If this gate fails again: compare graph.refund_decision_probe against a
    passing job, and check whether a displacement site was added that does not
    go through _displace(). A tolerance is not the fix — one was added and
    reverted twice already, and the second time it also rewrote the published
    claim from a guarantee into a permitted 2-point regression.
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
