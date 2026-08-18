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
# p95 ~61 ms — so these sit roughly 20× above observed.
CEILINGS_MS = {
    "neighbors": 150.0,
    "spread": 750.0,
    "reinforce": 150.0,
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
