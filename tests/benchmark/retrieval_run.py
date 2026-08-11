"""N-15 SOTA Retrieval Quality Benchmark runner.

Runs every query from retrieval_queries.json against the NeuralMind index,
extracts ranked modules, computes IR metrics (recall@k, precision@k, MRR,
nDCG@k, hit_rate), runs the RAGAS faithfulness judge, and writes:
    - tests/benchmark/retrieval_results.json  (structured)
    - tests/benchmark/retrieval_report.md     (human-readable)

Design constraints:
- Lazy imports: tiktoken/graphify not required for collection
- Uses real NeuralMind ranking from ctx.top_search_hits (not substring presence)
- Deduplicates preserving rank order
- RAGAS faithfulness via stdlib-only judge (no embed_fn required)

Note: nm.query() writes to .neuralmind/ (synapse store, audit log, recent queries).
This is a side effect of using the real NeuralMind index. For hermetic CI runs,
copy the fixture to tmp_path first.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "sample_project"
QUERIES_PATH = REPO_ROOT / "tests" / "benchmark" / "retrieval_queries.json"
RESULTS_PATH = REPO_ROOT / "tests" / "benchmark" / "retrieval_results.json"
REPORT_PATH = REPO_ROOT / "tests" / "benchmark" / "retrieval_report.md"


# --------------------------------------------------------------------- types


@dataclass
class QueryMetrics:
    """Per-query retrieval quality metrics."""

    id: str
    question: str
    shape: str
    recall_at_1: float = 0.0
    recall_at_3: float = 0.0
    recall_at_5: float = 0.0
    precision_at_5: float = 0.0
    mrr: float = 0.0
    ndcg_at_5: float = 0.0
    hit_rate: float = 0.0
    faithfulness: float = 0.0
    fact_recall: float = 0.0
    contradiction: float = 0.0
    ranked_modules: list[str] = field(default_factory=list)
    expected_modules: list[str] = field(default_factory=list)


@dataclass
class RetrievalResults:
    """Aggregated retrieval benchmark results."""

    version: int = 1
    timestamp: float = 0.0
    config: dict = field(default_factory=dict)
    aggregates: dict = field(default_factory=dict)
    by_shape: dict = field(default_factory=dict)
    queries: list[dict] = field(default_factory=list)


# --------------------------------------------------------------------- helpers


def top_k_modules(context_text: str, ctx: object = None, k: int = 5) -> list[str]:
    """Extract ranked module paths from a NeuralMind context string.

    If ``ctx`` (a ``ContextResult``) is provided, uses the real ranking
    from ``ctx.top_search_hits`` -- preserving NeuralMind's retrieval order.
    Otherwise falls back to the substring-presence heuristic (unordered).

    Deduplicates preserving rank order, maps each hit to its source module
    path, and truncates to ``k`` items.
    """
    # Prefer the real ranking from top_search_hits
    if ctx is not None and hasattr(ctx, "top_search_hits") and ctx.top_search_hits:
        seen: set[str] = set()
        ranked: list[str] = []
        for hit in ctx.top_search_hits:
            meta = hit.get("metadata", {})
            source = meta.get("source_file", "")
            if not source or source in seen:
                continue
            seen.add(source)
            ranked.append(source)
            if len(ranked) >= k:
                break
        return ranked

    # Fallback: substring-presence heuristic (unordered - not a ranking)
    candidates = [
        str(p.relative_to(FIXTURE_DIR)).replace("\\", "/")
        for p in FIXTURE_DIR.rglob("*.py")
        if p.name != "__init__.py"
    ]
    hits = []
    for c in candidates:
        if c in context_text:
            hits.append(c)
    return hits[:k]


def _compute_metrics(
    ranked: list[str],
    relevance: dict[str, int],
    gold_facts: list[str],
    query: str,
    context: str,
) -> dict:
    """Compute all IR metrics + RAGAS faithfulness for a single query."""
    from neuralmind.ragas import contradiction_score as ragas_contradiction_score
    from neuralmind.ragas import fact_recall as ragas_fact_recall
    from tests.benchmark.metrics import (
        hit_rate,
        mrr,
        ndcg_at_k,
        precision_at_k,
        recall_at_k,
    )

    relevant = {k for k, v in relevance.items() if v > 0}

    # RAGAS faithfulness: answer=retrieved context (scoring retrieval, not generation)
    fr = ragas_fact_recall(context, gold_facts)
    con = ragas_contradiction_score(context, gold_facts)
    faith = fr * (1.0 - con)

    return {
        "recall_at_1": recall_at_k(ranked, relevant, 1),
        "recall_at_3": recall_at_k(ranked, relevant, 3),
        "recall_at_5": recall_at_k(ranked, relevant, 5),
        "precision_at_5": precision_at_k(ranked, relevant, 5),
        "mrr": mrr(ranked, relevant),
        "ndcg_at_5": ndcg_at_k(ranked, relevance, 5),
        "hit_rate": hit_rate(ranked, relevant),
        "faithfulness": faith,
        "fact_recall": fr,
        "contradiction": con,
    }


def _aggregate_metrics(all_metrics: list[QueryMetrics]) -> dict:
    """Compute mean across all queries."""
    if not all_metrics:
        return {}

    keys = [
        "recall_at_1",
        "recall_at_3",
        "recall_at_5",
        "precision_at_5",
        "mrr",
        "ndcg_at_5",
        "hit_rate",
        "faithfulness",
        "fact_recall",
        "contradiction",
    ]
    return {k: round(sum(getattr(m, k) for m in all_metrics) / len(all_metrics), 4) for k in keys}


def _aggregate_by_shape(all_metrics: list[QueryMetrics]) -> dict:
    """Compute per-shape breakdowns."""
    shapes: dict[str, list[QueryMetrics]] = {}
    for m in all_metrics:
        shapes.setdefault(m.shape, []).append(m)

    return {shape: _aggregate_metrics(metrics) for shape, metrics in sorted(shapes.items())}


# --------------------------------------------------------------------- runner


def run_benchmark() -> RetrievalResults:
    """Run the full retrieval quality benchmark."""
    from neuralmind import NeuralMind

    if not QUERIES_PATH.exists():
        raise FileNotFoundError(f"Queries file not found: {QUERIES_PATH}")

    queries_data = json.loads(QUERIES_PATH.read_text())
    queries = queries_data["queries"]

    # Build NeuralMind index
    nm = NeuralMind(str(FIXTURE_DIR))
    nm.build()

    all_metrics: list[QueryMetrics] = []

    for q in queries:
        ctx = nm.query(q["question"])
        ranked = top_k_modules(ctx.context, ctx=ctx, k=5)

        metrics = _compute_metrics(
            ranked=ranked,
            relevance=q["relevance_grades"],
            gold_facts=q["gold_facts"],
            query=q["question"],
            context=ctx.context,
        )

        qm = QueryMetrics(
            id=q["id"],
            question=q["question"],
            shape=q["shape"],
            ranked_modules=ranked,
            expected_modules=[k for k, v in q["relevance_grades"].items() if v > 0],
            **metrics,
        )
        all_metrics.append(qm)

    return RetrievalResults(
        version=1,
        timestamp=time.time(),
        config={
            "fixture": str(FIXTURE_DIR),
            "query_count": len(queries),
            "judge": "ragas-stdlib-faithfulness",
        },
        aggregates=_aggregate_metrics(all_metrics),
        by_shape=_aggregate_by_shape(all_metrics),
        queries=[asdict(m) for m in all_metrics],
    )


def write_results(results: RetrievalResults) -> None:
    """Write structured JSON results."""
    RESULTS_PATH.write_text(json.dumps(asdict(results), indent=2))


def write_report(results: RetrievalResults) -> None:
    """Write human-readable Markdown report."""
    lines = [
        "# N-15 SOTA Retrieval Quality Benchmark",
        "",
        f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(results.timestamp))}",
        f"**Fixture:** `{results.config.get('fixture', 'unknown')}`",
        f"**Queries:** {results.config.get('query_count', 0)}",
        f"**Judge:** {results.config.get('judge', 'unknown')}",
        "",
        "## Aggregate Metrics",
        "",
        "| Metric | Value |",
        "|--------|------:|",
    ]

    metric_labels = {
        "recall_at_1": "Recall@1",
        "recall_at_3": "Recall@3",
        "recall_at_5": "Recall@5",
        "precision_at_5": "Precision@5",
        "mrr": "MRR",
        "ndcg_at_5": "nDCG@5",
        "hit_rate": "Hit Rate",
        "faithfulness": "Faithfulness",
        "fact_recall": "Fact Recall",
        "contradiction": "Contradiction",
    }

    for key, label in metric_labels.items():
        value = results.aggregates.get(key, 0.0)
        lines.append(f"| {label} | {value:.4f} |")

    # Per-shape breakdown
    lines += [
        "",
        "## Per-Shape Breakdown",
        "",
        "| Shape | Recall@5 | MRR | nDCG@5 | Hit Rate | Faithfulness |",
        "|-------|---------:|----:|-------:|---------:|-------------:|",
    ]
    for shape, shape_metrics in sorted(results.by_shape.items()):
        lines.append(
            f"| {shape} "
            f"| {shape_metrics.get('recall_at_5', 0):.4f} "
            f"| {shape_metrics.get('mrr', 0):.4f} "
            f"| {shape_metrics.get('ndcg_at_5', 0):.4f} "
            f"| {shape_metrics.get('hit_rate', 0):.4f} "
            f"| {shape_metrics.get('faithfulness', 0):.4f} |"
        )

    # Per-query table
    lines += [
        "",
        "## Per-Query Results",
        "",
        "| # | ID | Shape | R@1 | R@3 | R@5 | P@5 | MRR | nDCG@5 | Hit | Faith |",
        "|---|----|-------|-----|-----|-----|-----|-----|--------|-----|-------|",
    ]
    for i, q in enumerate(results.queries, 1):
        lines.append(
            f"| {i} | `{q['id']}` | {q['shape']} "
            f"| {q['recall_at_1']:.2f} "
            f"| {q['recall_at_3']:.2f} "
            f"| {q['recall_at_5']:.2f} "
            f"| {q['precision_at_5']:.2f} "
            f"| {q['mrr']:.2f} "
            f"| {q['ndcg_at_5']:.2f} "
            f"| {q['hit_rate']:.1f} "
            f"| {q['faithfulness']:.2f} |"
        )

    # Per-query module details
    lines += [
        "",
        "## Per-Query Module Rankings",
        "",
    ]
    for q in results.queries:
        lines += [
            f"### `{q['id']}` — {q['question']}",
            "",
            f"**Expected:** {', '.join(f'`{m}`' for m in q['expected_modules']) or 'none'}",
            f"**Ranked:** {', '.join(f'`{m}`' for m in q['ranked_modules']) or 'none'}",
            "",
        ]

    REPORT_PATH.write_text("\n".join(lines))


def main() -> None:
    """Run the benchmark and write outputs."""
    print("Running N-15 SOTA Retrieval Quality Benchmark...")
    print(f"  Fixture: {FIXTURE_DIR}")
    print(f"  Queries: {QUERIES_PATH}")
    print()

    results = run_benchmark()

    write_results(results)
    write_report(results)

    print(f"Results written to: {RESULTS_PATH}")
    print(f"Report written to: {REPORT_PATH}")
    print()
    print("Aggregate metrics:")
    for key, value in results.aggregates.items():
        print(f"  {key}: {value:.4f}")


if __name__ == "__main__":
    main()
