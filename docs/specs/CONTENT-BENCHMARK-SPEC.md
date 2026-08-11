# N-16 Content Retrieval Quality Benchmark Spec

This document describes the N-16 content retrieval quality benchmark for NeuralMind. It extends N-15's IR metrics to long-form non-code content (books, documentation, compliance frameworks), measuring whether NeuralMind can retrieve the right *paragraph* from a 150K-word book — not just the right *file* from a codebase.

## Why Content Retrieval ≠ Code Retrieval

Code retrieval (N-15) benefits from strong signals:
- Function/class names map cleanly to queries
- Call graphs and imports provide explicit structure
- Queries often reference specific identifiers

Content retrieval is harder:
- Paragraphs lack explicit linkage
- Relevance is topical, not structural
- Queries are natural language, often ambiguous
- Documents have narrative flow, not API boundaries

N-16 measures whether NeuralMind's semantic + BM25 retrieval generalizes to this harder problem.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    N-16 Content QA System                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
│  │   Manifest   │    │   Indexer    │    │   Benchmark  │    │
│  │   v2 JSON    │───▶│  CLI         │───▶│   Runner     │    │
│  │              │    │              │    │              │    │
│  │ 30 queries   │    │ ingest-      │    │ - Ingest     │    │
│  │ × 11 chaps   │    │ content      │    │ - Query      │    │
│  │ × graded     │    │              │    │ - Score      │    │
│  │ relevance    │    │ 150-word     │    │ - Aggregate  │    │
│  └──────────────┘    │ chunks       │    └──────────────┘    │
│                       └──────────────┘                        │
│                              │                                 │
│                       ┌──────────────┐                        │
│                       │   N-15 IR    │                        │
│                       │   Metrics    │                        │
│                       │              │                        │
│                       │ recall@k     │                        │
│                       │ precision@k  │                        │
│                       │ MRR          │                        │
│                       │ nDCG@k       │                        │
│                       │ hit_rate     │                        │
│                       └──────────────┘                        │
│                              │                                 │
│                       ┌──────────────┐                        │
│                       │   RAGAS      │                        │
│                       │              │                        │
│                       │ faithfulness │                        │
│                       │ (stdlib)     │                        │
│                       └──────────────┘                        │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Pipeline

### 1. Ground Truth (`manifest_v2.json`)

30 queries × 11 chapters. Each query has:

```json
{
  "id": "wank-worm-origin",
  "question": "What was the WANK worm and why was it politically significant?",
  "shape": "causal",
  "gold_paragraphs": [
    {"chapter": "chapter_01.md", "chunk_index": 12, "text": "...", "relevance": 3},
    {"chapter": "chapter_01.md", "chunk_index": 45, "text": "...", "relevance": 2}
  ],
  "themes": ["worms", "NASA", "political"]
}
```

Relevance grades:

| Grade | Meaning | Example |
|-------|---------|---------|
| 3 | Essential — directly answers the question | The paragraph containing the definition |
| 2 | Relevant — contributes useful context | Background on related events |
| 1 | Tangential — mentions the topic but not usefully | Passing mention in unrelated context |
| 0 | Irrelevant — not about this query | Not present in top results |

Query shapes:

| Shape | Description | Count |
|-------|-------------|-------|
| precise | Technical details (dates, names, events) | 7 |
| thematic | Cross-chapter themes (motivations, culture) | 1 |
| entity | Character/entity resolution across chapters | 9 |
| temporal | Event sequencing, causation | 2 |
| causal | Why something happened | 11 |

### 2. Indexing

Chapters are chunked into ~150-word overlapping segments (configurable via `--chunk-size` and `--overlap`). Each chunk becomes a `ContentNode` with:

- Unique `doc:` ID based on filename + chunk index
- Full text for embedding
- Metadata: chapter, chunk_index, chunk_count

```bash
neuralmind ingest-content evals/book_retrieval/underground/chapters \
    --chunk-size 500 --overlap 50
```

### 3. Retrieval

For each query:
1. `ctx = nm.query(question)` — NeuralMind progressive disclosure
2. Extract paragraphs from context (split on `\n\n`)
3. Map retrieved paragraphs to gold paragraphs via word-overlap scoring
4. Compute N-15 IR metrics against graded relevance
5. Run RAGAS faithfulness (`fact_recall × (1 - contradiction)`)

### 4. Aggregation

Results are aggregated at two levels:
- **Global**: mean across all queries
- **Per-shape**: mean within each query shape (precise/thematic/entity/temporal/causal)

## CI Regression Gates

7 tests in `tests/test_content_benchmark.py`:

| Test | Floor | Rationale |
|------|-------|-----------|
| `test_recall_at_5_above_floor` | ≥ 0.20 | Honest baseline: content retrieval on 150K words is hard |
| `test_mrr_above_floor` | ≥ 0.30 | First relevant paragraph in top-3 |
| `test_ndcg_at_5_above_floor` | ≥ 0.20 | Ranked quality above random |
| `test_hit_rate_above_floor` | ≥ 0.50 | At most ~15/30 queries completely miss |
| `test_mean_faithfulness_above_floor` | ≥ 0.0 | Stdlib-only judge on compressed output — floor catches complete failures |
| `test_no_query_has_zero_relevant_in_top_5` | zero tolerance | Catches complete misses hidden by averages |
| `test_per_shape_hit_rate` | ≥ 0.30 | No shape below 0.30 hit rate |

## Extending to a New Book

1. Drop Markdown chapters into `evals/book_retrieval/<book>/chapters/`
2. Write a manifest with queries + gold paragraphs + relevance grades
3. Run `python -m evals.book_retrieval.run --manifest <path> --json > results.json`
4. Run CI gates: `python -m pytest tests/test_content_benchmark.py`

No code changes needed.

## Honest Limitations

- **RAGAS without embeddings**: Faithfulness scores use stdlib-only `fact_recall × (1 - contradiction)`. This catches gross failures (fact_recall=0) but misses subtle semantic drift. Embedding-dependent RAGAS columns (context_precision, context_recall, answer_relevance) are `None` until an `embed_fn` is injected.
- **Chunk-level granularity**: 150-word chunks approximate paragraphs. True paragraph-boundary detection requires structural parsing (not always available in Markdown).
- **Word-overlap mapping**: Retrieved-to-gold matching uses word overlap. Works well when gold paragraphs appear verbatim; degrades on paraphrase.

## See Also

- `N-15-PROMPT.md` — N-15 code retrieval benchmark (predecessor)
- `RETRIEVAL-BENCHMARK-SPEC.md` — N-15 spec (code retrieval)
- `evals/book_retrieval/run.py` — N-16 eval runner v2
- `evals/book_retrieval/manifest_v2.json` — 30-query Underground manifest with graded relevance
- `tests/benchmark/metrics.py` — N-15 IR metrics (reused by N-16)
- `tests/test_content_benchmark.py` — N-16 CI regression gates
