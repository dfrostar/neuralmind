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

    NOT RESOLVED. Reproduced on demand 2026-08-28 (PR #484); the cause is
    still open. Read the corrections below before forming a hypothesis —
    three recorded conclusions were wrong, and each one cost an
    investigation:

    - "Ruled out by measurement: CPU/SIMD feature set" — wrong. SIMD
      correlates perfectly: every failing run observed was on an avx512f
      host, every passing run was not. What the earlier measurement got
      right is narrower than it sounds — SIMD does not reach the
      *embeddings*.
    - "What that left was core count" — wrong. cpu_count is 4 on both
      sides, and NEURALMIND_ORT_THREADS=1 did not stop the failure.
    - "A last-bit float difference decided which node fell off the end"
      (PR #484's own first hypothesis) — wrong. Every margin at every
      decision boundary is ~1e-1 to ~1e-3, orders of magnitude above float
      noise. A 1e-9 quantised sort key with an id tie-break was tried at
      all eight ranking sites in context_selector.py and measured on an
      avx512f host: byte-identical -1.75 with the change in or out. It was
      reverted, because it moved token counts on 3 of 19 queries and hit
      rate on none (+141 tokens, reduction 5.0096 -> 4.9719).

    HOW TO REPRODUCE (this is the thing that was missing for months). The
    failure is not flaky — it is a deterministic function of the host, and
    it reproduces on any avx512f machine:

        pip install ".[dev]" tiktoken matplotlib "graphifyy==0.9.5"
        graphify update tests/fixtures/sample_project
        neuralmind build tests/fixtures/sample_project --force
        NEURALMIND_ORT_THREADS=1 python -m tests.benchmark.run

    On avx512f this returns 0.7456 -> 0.7281 every time; on a host without
    avx512f, 0.7456 -> 0.7807 every time. Bit-stable across three A/B
    iterations, each a full index rebuild. Check with:
    grep -o 'avx512f' /proc/cpuinfo | head -1

    WHAT IS ESTABLISHED. graph.embedding_probe_sha256_16 is IDENTICAL on
    every run of both classes, so embeddings are bit-identical and the
    embedding path is not the variable. With recall OFF the two classes
    agree exactly on all 19 queries. They diverge only with recall ON, and
    only through _recall_energy. On avx512f the `refund` query loses its
    single expected module, billing/stripe_client.py; one query of nineteen
    flipping 1.0 -> 0.0 is 100/19 = 5.26 points, exactly the gap between the
    two modes.

    The displacement mechanism itself is ordinary and not in doubt.
    _apply_synapse_boost step (b) drops the tail of the ranked results and
    appends the strongest absent neighbours:

        results BEFORE boost (4)
           1.000  api_routes_rationale_86
           0.948  api_routes_refund_endpoint
           0.947  billing_stripe_client_rationale_44     <- dropped
           0.946  billing_stripe_client_rationale_132    <- dropped
        pull-in candidates (max 2)
          42.201  users_crud
          41.927  users_crud_get_user      <== cutoff
          41.725  users_crud_create_user

    WHERE TO LOOK NEXT. The divergence enters at or after spreading
    activation, since that is the only stage between an identical vector
    baseline and a differing result. Instrument SynapseStore._spread and
    compare the activation map across host classes before anything else.
    Note that _spread truncates with an untie-broken sort:

        ranked = sorted(activation.items(), key=lambda x: x[1],
                        reverse=True)[:top_k]

    and exact ties do occur in this data (users_crud_get_user_by_email and
    users_crud_update_last_login both at 41.400389273295552). That is a
    genuine latent nondeterminism worth fixing on its own, but it is not
    this bug: the refund cutoff has a wide margin.

    Finally, note the method is _apply_synapse_boost. An earlier version of
    this docstring referred to "_apply_synapse_recall", which does not
    exist.

    If this gate fails again: first check whether the runner has avx512f,
    then compare the probe digest and per-query hit_modules
    (phase2_synapse.queries vs .off_queries) against a passing job. A
    matching probe with a real delta is this same open bug, not a new
    regression — the embedding path has been bit-stable across every run
    measured so far. A differing probe would be genuinely new.
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
