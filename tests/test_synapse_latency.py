"""Regression gate for synapse recall latency.

The claim this protects is "instant codebase recall" — the promise that
recovering context after a switch costs a lookup, not a round trip. That claim
needs a number behind it, and a number nobody rechecks is a number that rots,
so the benchmark that produces it runs here on every PR.

The ceilings are deliberately loose. They are not a performance target; they
are a tripwire for the failure that actually happens — an index dropped, a
lookup quietly turned into a table scan — which costs orders of magnitude, not
percent. A tight bound on a shared CI runner would only teach people to ignore
a flaky test.

Stdlib-only, like the rest of the synapse layer's tests.
"""

from __future__ import annotations

from tests.benchmark.latency import run

# Small store: the regressions this catches are algorithmic, and they show at
# any size. Keeps the gate at a couple of seconds.
NODES = 600
CO_ACTIVATIONS = 400
SAMPLES = 40

# Order-of-magnitude tripwires, not targets. Reference run on a 4,000-node
# store (python -m tests.benchmark.latency): neighbors p95 ~6 ms, spread
# p95 ~61 ms, reinforce p95 ~3 ms.
#
# The read and write paths need very different headroom, and calibrating both
# off the same local timings was wrong: `reinforce` commits durably, so its
# p95 is dominated by the host's fsync cost, not by anything this repo
# controls. A Windows CI runner measured 167 ms for the write path while the
# reads stayed fast — a 50× spread on storage alone. Reads never fsync, so
# they keep a tight-ish bound; the write path gets a ceiling that only an
# algorithmic blowup (a scan per write, an unbounded rewrite) can reach.
# The real numbers come from the benchmark, not from these bounds.
CEILINGS_MS = {
    "neighbors": 150.0,
    "spread": 750.0,
    "reinforce": 2_000.0,
}


def _report() -> dict:
    return run(node_count=NODES, co_activations=CO_ACTIVATIONS, samples=SAMPLES)


def test_synapse_recall_stays_within_latency_tripwires() -> None:
    report = _report()
    breaches = [
        f"{op['operation']}: p95 {op['p95_ms']:.1f} ms exceeds {CEILINGS_MS[op['operation']]:.0f} ms"
        for op in report["operations"]
        if op["p95_ms"] > CEILINGS_MS[op["operation"]]
    ]
    assert not breaches, (
        "Synapse recall latency regressed by an order of magnitude — check for a "
        "dropped index or a lookup that became a scan:\n  " + "\n  ".join(breaches)
    )


def test_write_cost_does_not_scale_with_store_size() -> None:
    """The write path's real invariant, stated in a host-independent way.

    An absolute millisecond bound on `reinforce` mostly measures the host's
    fsync cost — which is why a Windows runner can be 50× a local disk without
    anything having regressed. What must hold on *any* host is that the cost of
    one co-activation doesn't grow with the size of the store: reinforcement is
    an indexed upsert of a handful of edges, not a pass over the graph. Compare
    the two on the same machine and the storage cost cancels out.
    """
    small = _report()
    large = run(node_count=NODES * 4, co_activations=CO_ACTIVATIONS * 4, samples=SAMPLES)

    def write_p50(report: dict) -> float:
        return next(op["p50_ms"] for op in report["operations"] if op["operation"] == "reinforce")

    small_ms, large_ms = write_p50(small), write_p50(large)
    # Observed ratio is ~1.1 for a 4× store. Allow 4× to absorb a noisy runner
    # while still catching a write that started scanning what it should index.
    assert large_ms <= max(small_ms * 4.0, 1.0), (
        f"Reinforce cost grew with store size: {small_ms:.2f} ms at {NODES} nodes → "
        f"{large_ms:.2f} ms at {NODES * 4}. A co-activation write should be an indexed "
        "upsert of a few edges, independent of how much the store already holds."
    )


def test_benchmark_reports_every_operation_it_claims_to_measure() -> None:
    # The gate is only as good as its coverage: if an operation silently drops
    # out of the report, the loop above trivially passes on what's left.
    report = _report()
    measured = {op["operation"] for op in report["operations"]}
    assert measured == set(CEILINGS_MS)
    assert all(op["samples"] > 0 for op in report["operations"])


def test_store_actually_has_edges_to_traverse() -> None:
    # A store with no edges would make every lookup trivially fast and the
    # latency gate meaningless.
    report = _report()
    assert report["store"]["mean_neighbors_per_node"] > 0
