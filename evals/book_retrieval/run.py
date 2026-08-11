"""Document retrieval eval runner v2 — N-15 IR metrics + graded relevance + RAGAS.

Usage:
    python -m evals.book_retrieval.run
    python -m evals.book_retrieval.run --json
    python -m evals.book_retrieval.run --query wank-worm-origin
    python -m evals.book_retrieval.run --manifest evals/book_retrieval/manifest_v2.json
    python -m evals.book_retrieval.run --output results.json --report report.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

MANIFEST_PATH = Path(__file__).parent / "manifest.json"
# N-15 IR metrics (stdlib-only)
sys.path.insert(0, str(PROJECT_ROOT / "tests"))
from benchmark.metrics import hit_rate, mrr, ndcg_at_k, precision_at_k, recall_at_k


def load_manifest(manifest_path: Path | None = None) -> dict[str, Any]:
    path = manifest_path or MANIFEST_PATH
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return re.sub(r"[^a-z0-9 ]", "", text)


def overlap_score(retrieved: str, gold: str) -> float:
    retrieved_words = set(normalize(retrieved).split())
    gold_words = set(normalize(gold).split())
    if not gold_words:
        return 0.0
    return len(retrieved_words & gold_words) / len(gold_words)


def extract_paragraphs_from_context(context: str) -> list[str]:
    """Extract paragraphs from NeuralMind context output.

    Splits on double newlines and filters out empty/short segments.
    """
    paragraphs = []
    for para in context.split("\n\n"):
        para = para.strip()
        if len(para) > 20:  # Filter out very short fragments
            paragraphs.append(para)
    return paragraphs


def compute_ir_metrics(
    retrieved_paragraphs: list[str],
    gold_paragraphs: list[dict],
) -> dict[str, float]:
    """Compute N-15 IR metrics for a single query.

    Args:
        retrieved_paragraphs: Ranked list of paragraph strings from retrieval.
        gold_paragraphs: List of dicts with 'text' and 'relevance' (0-3) keys.

    Returns:
        Dict with recall@1, recall@3, recall@5, precision@5, mrr, ndcg@5, hit_rate.
    """
    # Build relevance dict: paragraph text → relevance grade
    relevance_dict: dict[str, int] = {}
    relevant_set: set[str] = set()
    for gp in gold_paragraphs:
        text = gp.get("text", "")
        rel = gp.get("relevance", 3)  # Default to 3 if not specified
        if text:
            relevance_dict[text] = rel
            if rel > 0:
                relevant_set.add(text)

    # Map retrieved paragraphs to gold paragraphs by best overlap
    # DEDUP: track which gold paragraphs have already been matched to prevent
    # multiple retrieved paragraphs from mapping to the same gold (which would
    # inflate recall/precision/nDCG beyond 1.0).
    #
    # POSITION PRESERVATION: a retrieved paragraph with no gold match is still
    # appended (as the sentinel `None`), NOT dropped. Dropping non-matches
    # collapses `actual_ranked` to a list of only-relevant items, which makes
    # MRR trivially 1.0 (the first element is always relevant) and overstates
    # recall@5 / nDCG@5 because a match that actually sits past rank 5 is scored
    # as though it were at a top position. Keeping a placeholder row preserves
    # the true rank so the standard IR metrics are honest.
    actual_ranked: list[str | None] = []
    matched_golds: set[str] = set()
    for ret_para in retrieved_paragraphs:
        best_match = None
        best_score = 0.0
        for gold_para in relevance_dict:
            if gold_para in matched_golds:
                continue  # Already matched — skip to prevent duplicate counting
            score = overlap_score(ret_para, gold_para)
            if score > best_score:
                best_score = score
                best_match = gold_para
        if best_match and best_score >= 0.15:  # Minimum overlap threshold
            actual_ranked.append(best_match)
            matched_golds.add(best_match)
        else:
            # Irrelevant retrieved paragraph — keep its slot so downstream
            # metrics (recall@k / precision@k / nDCG) weight it by its true
            # rank instead of compressing it away.
            actual_ranked.append(None)

    # NOTE: `None` sentinels are never in `relevant_set` and never key a
    # relevance grade in `relevance_dict` (defaults to 0 for nDCG), so the
    # stdlib metric helpers (`benchmark/metrics.py`) treat them as irrelevant
    # rows without modification.

    # Compute metrics
    return {
        "recall_at_1": recall_at_k(actual_ranked, relevant_set, 1),
        "recall_at_3": recall_at_k(actual_ranked, relevant_set, 3),
        "recall_at_5": recall_at_k(actual_ranked, relevant_set, 5),
        "precision_at_5": precision_at_k(actual_ranked, relevant_set, 5),
        "mrr": mrr(actual_ranked, relevant_set),
        "ndcg_at_5": ndcg_at_k(actual_ranked, relevance_dict, 5),
        "hit_rate": hit_rate(actual_ranked, relevant_set),
    }


def compute_faithfulness(
    query: str,
    retrieved_paragraphs: list[str],
    gold_paragraphs: list[dict],
) -> dict[str, Any]:
    """Compute RAGAS faithfulness score for retrieved context."""
    from neuralmind.ragas import score as ragas_score

    # Build gold facts from gold paragraphs
    gold_facts = [gp.get("text", "") for gp in gold_paragraphs if gp.get("text")]

    # Use retrieved paragraphs as the "answer" for faithfulness scoring
    answer = "\n\n".join(retrieved_paragraphs) if retrieved_paragraphs else ""

    # Retrieved docs for context precision/recall
    retrieved_docs = retrieved_paragraphs if retrieved_paragraphs else []

    result = ragas_score(
        query=query,
        retrieved=retrieved_docs,
        answer=answer,
        gold_facts=gold_facts,
    )
    return result.to_dict()


def run_eval(
    query_filter: str | None = None,
    verbose: bool = False,
    manifest_path: Path | None = None,
    book_dir: Path | None = None,
) -> dict[str, Any]:
    """Run the book retrieval eval v2 with N-15 IR metrics + RAGAS.

    Args:
        query_filter: Run only queries matching this substring.
        verbose: Print progress per query.
        manifest_path: Path to manifest_v2.json. Defaults to manifest.json.
        book_dir: Path to book directory. Defaults to manifest parent or 'underground'.
    """
    import neuralmind

    # Load manifest with error handling
    try:
        manifest = load_manifest(manifest_path)
        queries = manifest["queries"]
    except (OSError, ValueError, KeyError) as exc:
        return {"error": f"Failed to load manifest: {exc}"}

    if query_filter:
        queries = [q for q in queries if query_filter in q["id"]]

    # Resolve book directory: explicit > manifest parent > default Underground
    if book_dir is None:
        if manifest_path is not None:
            candidate = Path(manifest_path).parent
            if (candidate / "chapters").exists():
                book_dir = candidate
            else:
                book_dir = Path(__file__).parent / "underground"
        else:
            book_dir = Path(__file__).parent / "underground"
    chapters_dir = book_dir / "chapters"

    if not chapters_dir.exists():
        return {"error": f"Chapters not found at {chapters_dir}"}

    # Create a temp project directory with the book chapters + a seed Python file
    tmp_dir = Path(tempfile.mkdtemp(prefix="nm_book_eval_"))
    try:
        proj_dir = tmp_dir / "book"
        proj_dir.mkdir()

        # Copy chapters
        import shutil

        shutil.copytree(chapters_dir, proj_dir / "chapters")

        # Create a seed Python file so tree-sitter generates a minimal graph
        seed_file = proj_dir / "_seed.py"
        seed_file.write_text("# Seed file for document eval\ndef seed_function():\n    pass\n")

        print(f"Initializing NeuralMind on book ({proj_dir})...")
        mind = neuralmind.NeuralMind(str(proj_dir))

        print("Building index...")
        build_result = mind.build()
        if not build_result.get("success"):
            return {"error": f"Build failed: {build_result.get('error')}"}

        print(f"Ingesting {len(list((proj_dir / 'chapters').glob('*.md')))} chapters...")
        for chapter in sorted((proj_dir / "chapters").glob("*.md")):
            result = mind.ingest_document(chapter)
            if verbose:
                nodes = result.get("node_count", 0)
                print(f"  {chapter.name}: {nodes} nodes")

        # Run queries
        results = []
        total_tokens_naive = 0
        total_tokens_nm = 0

        full_text = ""
        for chapter in sorted((proj_dir / "chapters").glob("*.md")):
            full_text += chapter.read_text(encoding="utf-8")

        print(f"\nRunning {len(queries)} queries...")

        for i, query in enumerate(queries, 1):
            q_text = query["question"]
            gold_paras = query["gold_paragraphs"]

            # Handle both old format (list of strings) and new format (list of dicts)
            gold_paragraphs_normalized = []
            for gp in gold_paras:
                if isinstance(gp, str):
                    gold_paragraphs_normalized.append({"text": gp, "relevance": 3})
                else:
                    gold_paragraphs_normalized.append(gp)

            try:
                nm_result = mind.query(q_text)
                nm_context = nm_result.context if hasattr(nm_result, "context") else str(nm_result)
                nm_tokens = (
                    nm_result.budget.total
                    if hasattr(nm_result, "budget")
                    else len(nm_context.split())
                )
                # Use L3 search hits (relevance-ranked) for IR metrics.
                # The assembled context (nm_context) is a layered disclosure
                # document (L0→L3), NOT a ranked list — using it for recall@5/
                # MRR/nDCG measures disclosure-layer position, not retrieval
                # quality. top_search_hits are the actual retrieval results
                # in descending relevance order.
                search_hits = getattr(nm_result, "top_search_hits", None)
            except Exception as e:
                nm_context = ""
                nm_tokens = 0
                search_hits = None
                if verbose:
                    print(f"  Query {query['id']} failed: {e}")

            # Extract ranked paragraphs from L3 search hits (relevance order)
            # Fall back to legacy context splitting if unavailable
            if search_hits:
                retrieved_paragraphs = [
                    hit.get("document", "") for hit in search_hits if hit.get("document")
                ]
            else:
                retrieved_paragraphs = extract_paragraphs_from_context(nm_context)

            # Compute N-15 IR metrics
            ir_metrics = compute_ir_metrics(retrieved_paragraphs, gold_paragraphs_normalized)

            # Compute RAGAS faithfulness
            ragas_result = compute_faithfulness(
                q_text, retrieved_paragraphs, gold_paragraphs_normalized
            )

            naive_tokens = len(full_text.split())
            total_tokens_naive += naive_tokens
            total_tokens_nm += nm_tokens

            # Determine query shape (from manifest or default)
            query_shape = query.get("shape", "precise")

            result_entry = {
                "id": query["id"],
                "question": q_text,
                "shape": query_shape,
                "nm_tokens": nm_tokens,
                "naive_tokens": naive_tokens,
                "reduction": naive_tokens / nm_tokens if nm_tokens > 0 else 0,
                "ir_metrics": ir_metrics,
                "ragas": ragas_result,
                "themes": query.get("themes", []),
            }
            results.append(result_entry)

            if verbose or (i % 5 == 0):
                status = "✓" if ir_metrics["hit_rate"] > 0 else "✗"
                print(
                    f"  [{status}] {query['id']}: "
                    f"recall@5={ir_metrics['recall_at_5']:.2f}, "
                    f"mrr={ir_metrics['mrr']:.2f}, "
                    f"faithfulness={ragas_result['faithfulness']:.2f}"
                )

        # Aggregate
        hits = sum(1 for r in results if r["ir_metrics"]["hit_rate"] > 0)
        avg_recall_5 = (
            sum(r["ir_metrics"]["recall_at_5"] for r in results) / len(results) if results else 0
        )
        avg_mrr = sum(r["ir_metrics"]["mrr"] for r in results) / len(results) if results else 0
        avg_ndcg_5 = (
            sum(r["ir_metrics"]["ndcg_at_5"] for r in results) / len(results) if results else 0
        )
        avg_faithfulness = (
            sum(r["ragas"]["faithfulness"] for r in results) / len(results) if results else 0
        )
        avg_reduction = sum(r["reduction"] for r in results) / len(results) if results else 0

        # Per-shape breakdown
        by_shape: dict[str, list[dict]] = {}
        for r in results:
            shape = r.get("shape", "precise")
            if shape not in by_shape:
                by_shape[shape] = []
            by_shape[shape].append(r)

        shape_aggregates = {}
        for shape, shape_results in by_shape.items():
            shape_aggregates[shape] = {
                "count": len(shape_results),
                "recall_at_5": sum(r["ir_metrics"]["recall_at_5"] for r in shape_results)
                / len(shape_results),
                "mrr": sum(r["ir_metrics"]["mrr"] for r in shape_results) / len(shape_results),
                "ndcg_at_5": sum(r["ir_metrics"]["ndcg_at_5"] for r in shape_results)
                / len(shape_results),
                "hit_rate": sum(r["ir_metrics"]["hit_rate"] for r in shape_results)
                / len(shape_results),
                "mean_faithfulness": sum(r["ragas"]["faithfulness"] for r in shape_results)
                / len(shape_results),
            }

        return {
            "version": 2,
            "book": "Underground",
            "query_count": len(queries),
            "aggregates": {
                "recall_at_5": avg_recall_5,
                "mrr": avg_mrr,
                "ndcg_at_5": avg_ndcg_5,
                "hit_rate": hits / len(queries) if queries else 0,
                "mean_faithfulness": avg_faithfulness,
                "avg_token_reduction": avg_reduction,
            },
            "by_shape": shape_aggregates,
            "queries": results,
        }

    finally:
        # Always clean up temp directory (M3 fix: was leaking on early returns)
        shutil.rmtree(tmp_dir, ignore_errors=True)


def print_report(report: dict[str, Any]) -> None:
    print("\n" + "=" * 70)
    print("BOOK RETRIEVAL EVAL REPORT v2 — N-15 IR Metrics + RAGAS")
    print("=" * 70)
    print(f"Book: {report['book']}")
    print(f"Queries: {report['query_count']}")
    print()

    agg = report["aggregates"]
    print("AGGREGATES:")
    print(f"  recall@5        : {agg['recall_at_5']:.3f}")
    print(f"  MRR             : {agg['mrr']:.3f}")
    print(f"  nDCG@5          : {agg['ndcg_at_5']:.3f}")
    print(f"  hit_rate        : {agg['hit_rate']:.3f}")
    print(f"  mean_faithfulness: {agg['mean_faithfulness']:.3f}")
    print(f"  avg_token_reduction: {agg['avg_token_reduction']:.1f}x")
    print()

    if report.get("by_shape"):
        print("PER-SHAPE BREAKDOWN:")
        for shape, shape_agg in report["by_shape"].items():
            print(f"  {shape} ({shape_agg['count']} queries):")
            print(f"    recall@5  : {shape_agg['recall_at_5']:.3f}")
            print(f"    MRR       : {shape_agg['mrr']:.3f}")
            print(f"    hit_rate  : {shape_agg['hit_rate']:.3f}")
            print(f"    faithfulness: {shape_agg['mean_faithfulness']:.3f}")
        print()

    print("PER-QUERY BREAKDOWN:")
    print("-" * 70)
    for r in report["queries"]:
        status = "✓" if r["ir_metrics"]["hit_rate"] > 0 else "✗"
        print(
            f"  [{status}] {r['id'][:40]:40s} "
            f"recall@5={r['ir_metrics']['recall_at_5']:.2f} "
            f"mrr={r['ir_metrics']['mrr']:.2f} "
            f"faith={r['ragas']['faithfulness']:.2f}"
        )

    misses = [r for r in report["queries"] if r["ir_metrics"]["hit_rate"] == 0]
    if misses:
        print(f"\nMISSES ({len(misses)}):")
        for r in misses:
            print(f"  - {r['id']}: {r['question'][:60]}...")

    print("=" * 70)


def _format_report_md(report: dict[str, Any]) -> str:
    """Format the eval report as Markdown for writing to a file."""
    lines = []
    lines.append("# Book Retrieval Eval Report v2 — N-15 IR Metrics + RAGAS\n")
    lines.append(f"**Book:** {report['book']}  ")
    lines.append(f"**Queries:** {report['query_count']}  ")
    lines.append("")

    agg = report["aggregates"]
    lines.append("## Aggregates\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| recall@5 | {agg['recall_at_5']:.3f} |")
    lines.append(f"| MRR | {agg['mrr']:.3f} |")
    lines.append(f"| nDCG@5 | {agg['ndcg_at_5']:.3f} |")
    lines.append(f"| hit_rate | {agg['hit_rate']:.3f} |")
    lines.append(f"| mean_faithfulness | {agg['mean_faithfulness']:.3f} |")
    lines.append(f"| avg_token_reduction | {agg['avg_token_reduction']:.1f}x |")
    lines.append("")

    if report.get("by_shape"):
        lines.append("## Per-Shape Breakdown\n")
        for shape, shape_agg in report["by_shape"].items():
            lines.append(f"### {shape} ({shape_agg['count']} queries)\n")
            lines.append(f"- recall@5: {shape_agg['recall_at_5']:.3f}")
            lines.append(f"- MRR: {shape_agg['mrr']:.3f}")
            lines.append(f"- hit_rate: {shape_agg['hit_rate']:.3f}")
            lines.append(f"- faithfulness: {shape_agg['mean_faithfulness']:.3f}")
            lines.append("")

    lines.append("## Per-Query Breakdown\n")
    for r in report["queries"]:
        status = "✓" if r["ir_metrics"]["hit_rate"] > 0 else "✗"
        lines.append(
            f"- [{status}] **{r['id']}** — "
            f"recall@5={r['ir_metrics']['recall_at_5']:.2f}, "
            f"mrr={r['ir_metrics']['mrr']:.2f}, "
            f"faith={r['ragas']['faithfulness']:.2f}"
        )

    misses = [r for r in report["queries"] if r["ir_metrics"]["hit_rate"] == 0]
    if misses:
        lines.append("")
        lines.append(f"## Misses ({len(misses)})\n")
        for r in misses:
            lines.append(f"- {r['id']}: {r['question'][:80]}...")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Book retrieval eval v2 (N-15 IR + RAGAS)")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--query", help="Run single query by ID substring")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--manifest", type=Path, help="Path to manifest JSON")
    parser.add_argument("--output", "-o", type=Path, help="Write results JSON to this path")
    parser.add_argument("--report", type=Path, help="Write Markdown report to this path")
    args = parser.parse_args()

    report = run_eval(
        query_filter=args.query,
        verbose=args.verbose,
        manifest_path=args.manifest,
    )

    if "error" in report:
        print(f"Error: {report['error']}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if not args.json:
            print(f"Wrote results: {args.output}")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(_format_report_md(report), encoding="utf-8")
        if not args.json:
            print(f"Wrote report: {args.report}")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)


if __name__ == "__main__":
    main()
