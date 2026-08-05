"""Document retrieval eval runner for long-form books.

Usage:
    python -m evals.book_retrieval.run
    python -m evals.book_retrieval.run --json
    python -m evals.book_retrieval.run --query wank-worm-origin
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


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


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


def score_retrieval(retrieved_text: str, gold_paragraphs: list[str]) -> dict[str, float]:
    scores = [overlap_score(retrieved_text, gold) for gold in gold_paragraphs]
    return {
        "max_overlap": max(scores) if scores else 0.0,
        "avg_overlap": sum(scores) / len(scores) if scores else 0.0,
        "any_hit": max(scores) >= 0.3 if scores else False,
    }


def run_eval(query_filter: str | None = None, verbose: bool = False) -> dict[str, Any]:
    import neuralmind

    manifest = load_manifest()
    queries = manifest["queries"]

    if query_filter:
        queries = [q for q in queries if query_filter in q["id"]]

    # Create a temp project directory with the book chapters + a seed Python file
    book_dir = Path(__file__).parent / "underground"
    chapters_dir = book_dir / "chapters"

    if not chapters_dir.exists():
        return {"error": f"Chapters not found at {chapters_dir}"}

    # Create temp project
    tmp_dir = Path(tempfile.mkdtemp(prefix="nm_book_eval_"))
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

        try:
            nm_result = mind.query(q_text)
            nm_context = nm_result.context if hasattr(nm_result, "context") else str(nm_result)
            nm_tokens = (
                nm_result.budget.total if hasattr(nm_result, "budget") else len(nm_context.split())
            )
        except Exception as e:
            nm_context = ""
            nm_tokens = 0
            if verbose:
                print(f"  Query {query['id']} failed: {e}")

        scoring = score_retrieval(nm_context, gold_paras)
        naive_tokens = len(full_text.split())

        total_tokens_naive += naive_tokens
        total_tokens_nm += nm_tokens

        results.append(
            {
                "id": query["id"],
                "question": q_text,
                "nm_tokens": nm_tokens,
                "naive_tokens": naive_tokens,
                "reduction": naive_tokens / nm_tokens if nm_tokens > 0 else 0,
                "max_overlap": scoring["max_overlap"],
                "any_hit": scoring["any_hit"],
                "themes": query.get("themes", []),
            }
        )

        if verbose or (i % 5 == 0):
            status = "✓" if scoring["any_hit"] else "✗"
            print(
                f"  [{status}] {query['id']}: overlap={scoring['max_overlap']:.2f}, tokens={nm_tokens}"
            )

    # Aggregate
    hits = sum(1 for r in results if r["any_hit"])
    avg_overlap = sum(r["max_overlap"] for r in results) / len(results) if results else 0
    avg_reduction = sum(r["reduction"] for r in results) / len(results) if results else 0

    # Cleanup
    shutil.rmtree(tmp_dir, ignore_errors=True)

    return {
        "book": "underground",
        "total_queries": len(queries),
        "hits": hits,
        "misses": len(queries) - hits,
        "recall_any_hit": hits / len(queries) if queries else 0,
        "avg_max_overlap": avg_overlap,
        "avg_token_reduction": avg_reduction,
        "total_tokens_naive": total_tokens_naive,
        "total_tokens_nm": total_tokens_nm,
        "per_query": results,
    }


def print_report(report: dict[str, Any]) -> None:
    print("\n" + "=" * 60)
    print("BOOK RETRIEVAL EVAL REPORT")
    print("=" * 60)
    print(f"Book: {report['book']}")
    print(f"Queries: {report['total_queries']}")
    print(
        f"Hits (overlap >= 0.3): {report['hits']}/{report['total_queries']} ({report['recall_any_hit']:.1%})"
    )
    print(f"Avg max overlap: {report['avg_max_overlap']:.3f}")
    print(f"Avg token reduction vs full-text: {report['avg_token_reduction']:.1f}×")
    print(
        f"Total tokens — Naive: {report['total_tokens_naive']:,} | NeuralMind: {report['total_tokens_nm']:,}"
    )

    print("\nPer-query breakdown:")
    print("-" * 60)
    for r in report["per_query"]:
        status = "✓" if r["any_hit"] else "✗"
        print(
            f"  [{status}] {r['id'][:40]:40s} overlap={r['max_overlap']:.2f} reduction={r['reduction']:.1f}×"
        )

    misses = [r for r in report["per_query"] if not r["any_hit"]]
    if misses:
        print(f"\nMISSES ({len(misses)}):")
        for r in misses:
            print(f"  - {r['id']}: {r['question'][:60]}...")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Book retrieval eval")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--query", help="Run single query by ID substring")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    report = run_eval(query_filter=args.query, verbose=args.verbose)

    if "error" in report:
        print(f"Error: {report['error']}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)


if __name__ == "__main__":
    main()
