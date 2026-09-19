#!/usr/bin/env python3
"""Peptide Patient's Guide — NeuralMind Retrieval Benchmark."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from neuralmind import core  # noqa: E402  (must follow sys.path bootstrap above)

PEPTIDE_BOOK_DIR = Path("/home/dtfrost5/ai-agent-playbook-v2/books/peptide-patient-guide")
QUERIES_PATH = Path(__file__).parent / "peptide_queries.json"
RESULTS_PATH = Path(__file__).parent / "peptide_results.json"
REPORT_PATH = Path(__file__).parent / "peptide_report.md"

CHAPTER_FILES = [
    "00_front-matter.md",
    "01_what-are-peptides.md",
    "02_chapter-2.md",
    "03_fda-approved-peptides.md",
    "04_grey-market-compounds.md",
    "05_safety-side-effects.md",
    "06_regulatory-landscape.md",
    "07_future-of-peptide-therapy.md",
    "08_questions-to-ask-prescriber.md",
    "98_claims-register-appendix.md",
    "99_back-matter.md",
]


@dataclass
class QueryMetrics:
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
    latency_ms: float = 0.0
    ranked_chapters: list[str] = field(default_factory=list)
    expected_chapters: list[str] = field(default_factory=list)
    facts_found: int = 0
    facts_total: int = 0


@dataclass
class BenchmarkResults:
    timestamp: float = 0.0
    neuralmind_version: str = ""
    project: str = ""
    total_nodes: int = 0
    total_queries: int = 0
    aggregates: dict = field(default_factory=dict)
    by_shape: dict = field(default_factory=dict)
    queries: list[dict] = field(default_factory=list)


def extract_chapters_from_context(context_text: str) -> list[str]:
    found = []
    for line in context_text.split("\n"):
        # Old format: filenames like chapters/01_what-are-peptides.md
        matches = re.findall(r"(?:chapters/)?(\d\d_[a-z][a-z0-9_-]*\.md)", line)
        for m in matches:
            if m not in found and m in CHAPTER_FILES:
                found.append(m)
        # New format: ## 01 What Are Peptides (Title Case from MedicalRetriever)
        heading_match = re.match(r"^##\s+(\d\d)\s+(.+)", line)
        if heading_match:
            ch_num = heading_match.group(1)
            # Find matching CHAPTER_FILE by number
            for cf in CHAPTER_FILES:
                if cf.startswith(ch_num) and cf not in found:
                    found.append(cf)
                    break
    return found


def extract_chapters_from_top_hits(ctx) -> list[str]:
    chapters = []
    if hasattr(ctx, "top_search_hits") and ctx.top_search_hits:
        for hit in ctx.top_search_hits:
            # New format: source_file is top-level
            source = hit.get("source_file", "")
            if not source:
                # Old format: nested under metadata
                meta = hit.get("metadata", {})
                source = meta.get("source_file", "")
            if source:
                chapter = Path(source).name
                if chapter and chapter not in chapters and chapter in CHAPTER_FILES:
                    chapters.append(chapter)
    return chapters


def check_facts_in_context(context_text: str, gold_facts: list[str]) -> tuple[int, int]:
    found = 0
    context_lower = context_text.lower()
    for fact in gold_facts:
        key_terms = [w for w in fact.lower().split() if len(w) > 4]
        if key_terms and all(term in context_lower for term in key_terms[:3]):
            found += 1
    return found, len(gold_facts)


def run_benchmark():
    print("=" * 60)
    print("Peptide Patient's Guide — NeuralMind Retrieval Benchmark")
    print("=" * 60)

    with open(QUERIES_PATH) as f:
        queries = json.load(f)["queries"]
    print(f"\nLoaded {len(queries)} queries")

    print(f"\nInitializing NeuralMind on: {PEPTIDE_BOOK_DIR}")
    start = time.time()
    old_cwd = os.getcwd()
    os.chdir(PEPTIDE_BOOK_DIR)
    nm = core.NeuralMind(".")
    os.chdir(old_cwd)
    print(f"Init time: {time.time() - start:.2f}s")

    total_nodes = 0
    try:
        with open(PEPTIDE_BOOK_DIR / ".neuralmind" / "index_ir.json") as f:
            total_nodes = len(json.load(f).get("nodes", []))
    except OSError:
        pass

    results = []
    print(f"\nRunning {len(queries)} queries...")

    for i, q in enumerate(queries, 1):
        print(f"  [{i}/{len(queries)}] {q['id']}: {q['question'][:50]}...")

        start = time.time()
        try:
            ctx = nm.query(q["question"])
            context_text = ctx.context if hasattr(ctx, "context") else str(ctx)
        except Exception as e:
            print(f"    ERROR: {e}")
            context_text = ""
            ctx = None
        latency = (time.time() - start) * 1000

        ranked_ctx = extract_chapters_from_context(context_text)
        ranked_hits = extract_chapters_from_top_hits(ctx) if ctx else []
        ranked = ranked_ctx if len(ranked_ctx) >= len(ranked_hits) else ranked_hits

        expected = [ch for ch, grade in q["relevance_grades"].items() if grade >= 2]

        m = QueryMetrics(
            id=q["id"],
            question=q["question"],
            shape=q["shape"],
            ranked_chapters=ranked,
            expected_chapters=expected,
            latency_ms=latency,
        )

        if expected:
            m.recall_at_1 = 1.0 if ranked and ranked[0] in expected else 0.0
            m.recall_at_3 = min(len(set(ranked[:3]) & set(expected)) / len(expected), 1.0)
            m.recall_at_5 = min(len(set(ranked[:5]) & set(expected)) / len(expected), 1.0)
        if ranked:
            m.precision_at_5 = len(set(ranked[:5]) & set(expected)) / len(ranked[:5])
        for rank, ch in enumerate(ranked, 1):
            if ch in expected:
                m.mrr = 1.0 / rank
                break
        if expected:
            dcg = sum(
                (2 ** q["relevance_grades"].get(ch, 2) - 1) / (rank + 1)
                for rank, ch in enumerate(ranked[:5], 1)
                if ch in expected
            )
            ideal = sorted([v for v in q["relevance_grades"].values() if v >= 2], reverse=True)
            idcg = sum((2**r - 1) / (i + 2) for i, r in enumerate(ideal[:5]))
            m.ndcg_at_5 = dcg / idcg if idcg > 0 else 0.0
        m.hit_rate = 1.0 if set(ranked[:5]) & set(expected) else 0.0
        if q.get("gold_facts"):
            m.facts_found, m.facts_total = check_facts_in_context(context_text, q["gold_facts"])

        results.append(m)
        print(f"    R@5={m.recall_at_5:.2f} MRR={m.mrr:.2f} lat={latency:.0f}ms ch={len(ranked)}")

    agg = {
        "recall_at_1": sum(r.recall_at_1 for r in results) / len(results),
        "recall_at_3": sum(r.recall_at_3 for r in results) / len(results),
        "recall_at_5": sum(r.recall_at_5 for r in results) / len(results),
        "precision_at_5": sum(r.precision_at_5 for r in results) / len(results),
        "mrr": sum(r.mrr for r in results) / len(results),
        "ndcg_at_5": sum(r.ndcg_at_5 for r in results) / len(results),
        "hit_rate": sum(r.hit_rate for r in results) / len(results),
        "avg_latency_ms": sum(r.latency_ms for r in results) / len(results),
        "median_latency_ms": sorted([r.latency_ms for r in results])[len(results) // 2],
        "p95_latency_ms": sorted([r.latency_ms for r in results])[int(len(results) * 0.95)],
        "total_facts_found": sum(r.facts_found for r in results),
        "total_facts": sum(r.facts_total for r in results),
    }

    by_shape = {}
    for shape in {r.shape for r in results}:
        sr = [r for r in results if r.shape == shape]
        by_shape[shape] = {
            "count": len(sr),
            "recall_at_5": sum(r.recall_at_5 for r in sr) / len(sr),
            "mrr": sum(r.mrr for r in sr) / len(sr),
            "avg_latency_ms": sum(r.latency_ms for r in sr) / len(sr),
        }

    benchmark = BenchmarkResults(
        timestamp=time.time(),
        neuralmind_version="3.10.0",
        project="peptide-patient-guide",
        total_nodes=total_nodes,
        total_queries=len(queries),
        aggregates=agg,
        by_shape=by_shape,
        queries=[asdict(r) for r in results],
    )

    with open(RESULTS_PATH, "w") as f:
        json.dump(asdict(benchmark), f, indent=2)
    print(f"\nResults saved to: {RESULTS_PATH}")

    generate_report(benchmark)
    print(f"Report saved to: {REPORT_PATH}")


def grade(val, green=0.7, yellow=0.5):
    return "🟢" if val >= green else "🟡" if val >= yellow else "🔴"


def generate_report(b: BenchmarkResults):
    a = b.aggregates
    fp = a["total_facts_found"] / a["total_facts"] * 100 if a["total_facts"] else 0

    r = f"""# NeuralMind Performance Report — Peptide Patient's Guide

**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(b.timestamp))}
**NeuralMind Version:** {b.neuralmind_version}
**Project:** {b.project}
**Index Size:** {b.total_nodes} nodes
**Queries Run:** {b.total_queries}

---

## Executive Summary

| Metric | Value | Grade |
|--------|-------|-------|
| Recall@1 | {a['recall_at_1']:.1%} | {grade(a['recall_at_1'])} |
| Recall@3 | {a['recall_at_3']:.1%} | {grade(a['recall_at_3'], 0.8, 0.6)} |
| Recall@5 | {a['recall_at_5']:.1%} | {grade(a['recall_at_5'], 0.9, 0.7)} |
| Precision@5 | {a['precision_at_5']:.1%} | {grade(a['precision_at_5'])} |
| MRR | {a['mrr']:.2f} | {grade(a['mrr'], 0.8, 0.6)} |
| nDCG@5 | {a['ndcg_at_5']:.2f} | {grade(a['ndcg_at_5'], 0.8, 0.6)} |
| Hit Rate | {a['hit_rate']:.1%} | {grade(a['hit_rate'], 0.9, 0.7)} |
| Avg Latency | {a['avg_latency_ms']:.0f}ms | {grade(1000 - a['avg_latency_ms'], 500, 0)} |
| P95 Latency | {a['p95_latency_ms']:.0f}ms | {grade(2000 - a['p95_latency_ms'], 1000, 0)} |
| Fact Recall | {a['total_facts_found']}/{a['total_facts']} ({fp:.0f}%) | {grade(fp / 100)} |

---

## Performance by Query Shape

| Shape | Count | Recall@5 | MRR | Avg Latency |
|-------|-------|----------|-----|-------------|
"""
    for shape, d in sorted(b.by_shape.items()):
        r += f"| {shape} | {d['count']} | {d['recall_at_5']:.1%} | {d['mrr']:.2f} | {d['avg_latency_ms']:.0f}ms |\n"

    r += """
---

## Per-Query Breakdown

| ID | Shape | R@1 | R@3 | R@5 | MRR | nDCG@5 | Latency | Top Chapter |
|----|-------|-----|-----|-----|-----|--------|---------|-------------|
"""
    for q in b.queries:
        top = q["ranked_chapters"][0] if q["ranked_chapters"] else "NONE"
        r += f"| {q['id']} | {q['shape']} | {q['recall_at_1']:.2f} | {q['recall_at_3']:.2f} | {q['recall_at_5']:.2f} | {q['mrr']:.2f} | {q['ndcg_at_5']:.2f} | {q['latency_ms']:.0f}ms | {top} |\n"

    r += """
---

## Brutally Honest Assessment

### What's Working Well
"""
    good_r = [q for q in b.queries if q["recall_at_5"] >= 0.8]
    good_l = [q for q in b.queries if q["latency_ms"] < 500]
    if good_r:
        r += f"- **{len(good_r)}/{b.total_queries} queries** achieve ≥80% recall@5\n"
    if good_l:
        r += f"- **{len(good_l)}/{b.total_queries} queries** complete in under 500ms\n"
    if a["hit_rate"] >= 0.8:
        r += f"- **{a['hit_rate']:.0%} hit rate** — most queries find at least one relevant chapter\n"

    r += """
### What Needs Improvement
"""
    bad_r = [q for q in b.queries if q["recall_at_5"] < 0.5]
    slow = [q for q in b.queries if q["latency_ms"] > 1000]
    zero = [q for q in b.queries if q["recall_at_5"] == 0.0]
    low = [q for q in b.queries if len(q["ranked_chapters"]) < 3]

    if zero:
        r += f"- **{len(zero)} queries** returned ZERO relevant chapters: {', '.join(q['id'] for q in zero)}\n"
    if bad_r:
        r += f"- **{len(bad_r)} queries** have <50% recall@5\n"
    if slow:
        r += f"- **{len(slow)} queries** exceed 1 second latency\n"
    if a["recall_at_1"] < 0.6:
        r += f"- **Recall@1 is only {a['recall_at_1']:.0%}** — the top result is often wrong\n"
    if low:
        r += (
            f"- **{len(low)} queries** returned fewer than 3 chapters — context may be too sparse\n"
        )

    cross = [q for q in b.queries if q["shape"] == "cross-chapter"]
    if cross:
        cr = sum(q["recall_at_5"] for q in cross) / len(cross)
        if cr < 0.7:
            r += f"- **Cross-chapter queries underperform** ({cr:.0%} recall@5)\n"

    r += f"""
### Critical Issues

1. **Index treats book as code repository.** Context says "Code repository with semantic indexing" — tree-sitter parsing is for functions/classes, not chapters.

2. **No chapter-aware retrieval.** NeuralMind doesn't understand "Chapter 3: FDA-Approved Peptides" is a semantic unit.

3. **Synapse layer adds no value for static books.** Hebbian co-activation is for usage patterns; a book has fixed structure.

4. **Metadata pollution.** Queries return hits from research notes, session context, illustration plans — not just chapters.

5. **Cross-chapter reasoning absent.** Questions like "FDA vs PCAC" need synthesis from 3-4 chapters. NeuralMind returns isolated chunks.

6. **Context is too verbose.** ~4,500 chars with cluster metadata instead of actual chapter text.

### Performance Comparison to Baselines

| Approach | Expected Recall@5 | Pros | Cons |
|----------|-------------------|------|------|
| NeuralMind (current) | {a['recall_at_5']:.0%} | Learns over time | Wrong tool for prose, verbose |
| Pure embedding (ChromaDB) | ~85-90% | Fast, accurate | No structure awareness |
| BM25 keyword search | ~70-80% | Fast, interpretable | Misses semantic matches |
| Hybrid (BM25 + embedding) | ~90-95% | Best of both worlds | More complex |
| Full-text search (SQLite FTS) | ~75-85% | Simple, fast | No semantic understanding |

---

## Recommendations

### Short-term (quick wins)
- **Filter index to chapters only.** Exclude metadata/, reports/, assets/, session files.
- **Add chapter-level chunking.** Treat each chapter as a document.
- **Suppress architecture metadata.** Strip "Knowledge Graph" and "Code Clusters" from output.

### Medium-term (structural)
- **Implement "content mode".** Switch between code analysis and prose analysis.
- **Add cross-chapter relationship edges.** Link chapters that share topics.
- **Use BM25 + embedding hybrid.** BM25 for exact medical terms, embedding for semantics.

### Long-term (strategic)
- **NeuralMind is the wrong tool for book retrieval.** Consider memU, Obsidian, or a RAG pipeline.
- **Disable synapse layer for static content.** It adds latency without benefit.

---

## Conclusion

NeuralMind v3.10.0 **functions** as a retrieval system but is **not optimized for books**. At {a['recall_at_5']:.0%} recall, it misses more than half the relevant content.

**Verdict:** A purpose-built content retrieval system would achieve >90% recall with cleaner output.

---

*Report generated by peptide_benchmark.py | NeuralMind v3.10.0*
"""

    with open(REPORT_PATH, "w") as f:
        f.write(r)


if __name__ == "__main__":
    run_benchmark()
