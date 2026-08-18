"""Recall-latency benchmark for the synapse layer.

The marketing surface wanted to say "instant codebase recall" and reached for
a query-latency figure (``0.81s``) that no code in this repo produces. This
module is the fix: it measures the thing the claim is actually about — how
long the associative layer takes to answer "what else matters here?" — so the
number can be quoted with a reproduction command behind it.

What it measures, on a synthetic store built to a fixed shape:

- ``neighbors`` — the one-hop lookup behind ``synaptic_neighbors``, the call an
  agent makes on every prompt to recover what it was working on.
- ``spread`` — multi-hop spreading activation, the expensive path.
- ``reinforce`` — the write side, which runs on every co-activation and must
  stay off the critical path.

It is deliberately **not** an end-to-end query benchmark: a full
``NeuralMind.query`` includes embedding and vector search, whose cost depends
on the backend and the machine. Those belong in a separate benchmark with
their own baseline. This one isolates the synapse layer, which is stdlib-only
and therefore reproducible anywhere, on any machine, with no dependencies.

Run it::

    python -m tests.benchmark.latency            # human-readable
    python -m tests.benchmark.latency --json     # machine-readable
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any

from neuralmind.synapses import SynapseStore

# Store shape. Roughly a mid-size repo's worth of symbols with a realistic
# co-editing history: enough edges that an index actually matters, small
# enough that the benchmark finishes in a couple of seconds in CI.
NODE_COUNT = 4_000
SYMBOLS_PER_FILE = 20
CO_ACTIVATIONS = 3_000
FILES_PER_CO_ACTIVATION = 4
SAMPLES = 200
SEED = 7


def _percentile(values: list[float], fraction: float) -> float:
    """Nearest-rank percentile — no interpolation, no numpy."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(fraction * len(ordered)))
    return ordered[index]


def _summarize(name: str, timings_ms: list[float]) -> dict[str, Any]:
    return {
        "operation": name,
        "samples": len(timings_ms),
        "p50_ms": round(statistics.median(timings_ms), 3),
        "p95_ms": round(_percentile(timings_ms, 0.95), 3),
        "max_ms": round(max(timings_ms), 3),
    }


def _seed_store(
    store: SynapseStore,
    nodes: list[str],
    rng: random.Random,
    co_activations: int,
) -> list[float]:
    """Reinforce a synthetic co-editing history; return per-write timings."""
    timings: list[float] = []
    for _ in range(co_activations):
        group = rng.sample(nodes, FILES_PER_CO_ACTIVATION)
        start = time.perf_counter()
        store.reinforce(group)
        timings.append((time.perf_counter() - start) * 1000.0)
    return timings


def run(
    db_path: Path | None = None,
    *,
    node_count: int = NODE_COUNT,
    co_activations: int = CO_ACTIVATIONS,
    samples: int = SAMPLES,
) -> dict[str, Any]:
    """Measure synapse recall latency. Returns a JSON-shaped report.

    The scale parameters exist so the CI gate can run a smaller store than the
    published benchmark — the regression it is looking for (an index dropped,
    a query turned into a scan) shows up at any size, and a two-second test is
    one people keep.
    """
    rng = random.Random(SEED)
    nodes = [f"module_{i // SYMBOLS_PER_FILE}.py::symbol_{i}" for i in range(node_count)]

    tmp: tempfile.TemporaryDirectory | None = None
    if db_path is None:
        tmp = tempfile.TemporaryDirectory()
        db_path = Path(tmp.name) / "synapses.db"

    try:
        store = SynapseStore(db_path)
        write_ms = _seed_store(store, nodes, rng, co_activations)

        neighbor_ms: list[float] = []
        spread_ms: list[float] = []
        edges_seen = 0
        for _ in range(samples):
            node = nodes[rng.randrange(len(nodes))]

            start = time.perf_counter()
            hits = store.neighbors(node)
            neighbor_ms.append((time.perf_counter() - start) * 1000.0)
            edges_seen += len(hits)

            start = time.perf_counter()
            store.spread([node])
            spread_ms.append((time.perf_counter() - start) * 1000.0)

        return {
            "store": {
                "nodes": node_count,
                "co_activations": co_activations,
                "mean_neighbors_per_node": round(edges_seen / samples, 2),
            },
            "operations": [
                _summarize("neighbors", neighbor_ms),
                _summarize("spread", spread_ms),
                _summarize("reinforce", write_ms),
            ],
        }
    finally:
        if tmp is not None:
            tmp.cleanup()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit the raw report")
    args = parser.parse_args()

    report = run()
    if args.json:
        print(json.dumps(report, indent=2))
        return

    store = report["store"]
    print(
        f"Synapse recall latency — {store['nodes']:,} nodes, "
        f"{store['co_activations']:,} co-activations, "
        f"{store['mean_neighbors_per_node']} neighbors/node\n"
    )
    print(f"{'operation':<12}{'p50 (ms)':>12}{'p95 (ms)':>12}{'max (ms)':>12}")
    for op in report["operations"]:
        print(
            f"{op['operation']:<12}{op['p50_ms']:>12.2f}{op['p95_ms']:>12.2f}{op['max_ms']:>12.2f}"
        )


if __name__ == "__main__":
    main()
