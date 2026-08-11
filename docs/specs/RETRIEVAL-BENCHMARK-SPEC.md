# N-15 SOTA Retrieval Quality Benchmark Spec

This document describes the N-15 retrieval-quality benchmark framework for NeuralMind. It defines the ground-truth format, metrics, regression floors, and the RAGAS integration path.

## Overview

The existing self-benchmark (`tests/benchmark/run.py`) measures two things:
1. **Reduction ratio** — how many tokens NeuralMind saves vs. loading everything
2. **Binary hit rate** — does the expected module appear in the top-k results?

N-15 adds the missing dimensions:
- **Ranked retrieval quality** — *how well* are results ordered (nDCG, MRR)
- **Graded relevance** — modules are not binary relevant/irrelevant, but exist on a 0-3 scale
- **Faithfulness scoring** — does retrieved context actually support answering the question?
- **Per-query diagnostics** — which queries fail and *why*
- **Per-shape breakdowns** — focused vs. cross-file vs. identity queries

## Ground Truth Format

Ground truth lives in `tests/benchmark/retrieval_queries.json`. Each query has:

```json
{
  "id": "jwt-verify",
  "question": "How does JWT signature verification work?",
  "shape": "focused",
  "relevance_grades": {
    "auth/jwt_utils.py": 3,
    "auth/handlers.py": 1,
    "api/routes.py": 0,
    "billing/stripe_client.py": 0,
    "billing/invoices.py": 0,
    "users/crud.py": 0,
    "db/connection.py": 0
  },
  "gold_facts": [
    "JWT verification uses HMAC-SHA256",
    "decode_token verifies the signature",
    "decode_token checks token expiry",
    "TokenExpiredError is raised when expired"
  ]
}
```

### Relevance Grades

| Grade | Meaning | Example |
|-------|---------|---------|
| 3 | **Essential** — must appear in top results | `auth/jwt_utils.py` for a JWT query |
| 2 | **Relevant** — contributes useful context | `api/routes.py` for an auth-flow query |
| 1 | **Tangential** — tangentially related | `db/connection.py` for a user query |
| 0 | **Irrelevant** — not related | `billing/stripe_client.py` for a JWT query |

Every fixture module must be graded for every query (complete coverage). This is what enables nDCG — the metric needs to know not just which modules are relevant, but their relative importance.

### Gold Facts

Gold facts are verifiable statements derived from fixture source code (not invented). They serve as the ground truth for the RAGAS faithfulness judge. Each query has 2-4 gold facts that a correct answer must include.

## Metrics

All metrics are pure-Python in `tests/benchmark/metrics.py` (stdlib-only, deterministic, CI-safe).

### recall@k

```
recall@k = |actual[:k] ∩ relevant| / |relevant|
```

Fraction of relevant items captured in the top-k results. A query with 3 expected modules where 2 appear in the top-5 has recall@5 = 0.667.

### precision@k

```
precision@k = |actual[:k] ∩ relevant| / k
```

Fraction of the top-k results that are relevant. A query with 2 relevant modules in the top-5 has precision@5 = 0.4.

### MRR (Mean Reciprocal Rank)

```
MRR = 1 / (index of first relevant item, 1-indexed)
```

If the first relevant item appears at position 2, MRR = 0.5. Rewards systems that put relevant items first.

### nDCG@k (Normalized Discounted Cumulative Gain)

```
DCG@k = Σ (2^rel(i) - 1) / log2(i+1)   for i=1..k
nDCG@k = DCG@k / IDCG@k
```

The gold standard for ranked retrieval quality. Unlike binary metrics, nDCG rewards placing grade-3 modules above grade-1 modules. A query where the grade-3 module is at position 5 will score lower than one where it's at position 1, even if both are "hits."

### hit_rate

```
hit_rate = 1.0 if actual ∩ relevant else 0.0
```

Binary: did any relevant item appear? A coarse-grained metric — sensitive to complete misses but blind to ranking quality.

## RAGAS Faithfulness Integration

The framework consumes `neuralmind/ragas.py` (stdlib-only judge) to score retrieval quality end-to-end:

```python
from neuralmind.ragas import score as ragas_score

result = ragas_score(
    query=query,
    retrieved=[context],
    answer=context,  # answer = retrieved context (scoring retrieval, not generation)
    gold_facts=gold_facts,
)
```

This answers: "Does the retrieved context actually support answering the question?" Not just "did the right file appear" but "would the file produce a faithful answer."

### RAGAS Score Components

| Component | Formula | Interpretation |
|-----------|---------|----------------|
| `fact_recall` | fraction of gold facts whose tokens appear in answer | Does the context contain the expected facts? |
| `contradiction` | negation-flip + mutually-exclusive-choice detection | Does the context contradict the gold facts? |
| `faithfulness` | `fact_recall * (1 - contradiction)` | Combined score (0.0 to 1.0) |

Embedding-dependent columns (`context_precision`, `context_recall`, `answer_relevance`) return `None` when no `embed_fn` is provided.

## Regression Floors

`tests/test_retrieval_benchmark.py` implements 8 CI gates with conservative floors:

| Test | Floor | Rationale |
|------|-------|-----------|
| `test_recall_at_5_above_floor` | recall@5 ≥ 0.50 | At least half of expected modules in top-5 |
| `test_mrr_above_floor` | MRR ≥ 0.40 | First relevant result typically in top-2.5 |
| `test_ndcg_at_5_above_floor` | nDCG@5 ≥ 0.50 | Ranked quality above random |
| `test_hit_rate_above_floor` | hit_rate ≥ 0.80 | At most ~4/20 queries completely miss |
| `test_mean_faithfulness_above_floor` | faithfulness > 0.0 | Complete failure floor (stdlib-only judge on compressed context) |
| `test_mean_contradiction_below_ceiling` | contradiction ≤ 0.20 | Contradiction rate below 20% |
| `test_no_query_has_zero_relevant_in_top_5` | per-query: recall@5 > 0 | Zero tolerance for complete misses |
| `test_per_shape_hit_rate` | per-shape: hit_rate ≥ 0.70 | No shape broadly missing |

Floors are intentionally conservative — they catch catastrophes (retrieval returning the wrong modules entirely), not marginal regressions.

### Why Conservative Floors?

On a 500-line hermetic fixture, retrieval quality tops out lower than on real repos. The stdlib-only RAGAS judge scores compressed context (not full source), which limits fact recall. Conservative floors:
- Catch genuine regressions (e.g., a change that breaks retrieval for all cross-file queries)
- Avoid false alarms from fixture-size limitations
- Are *floors*, not targets — real repos should substantially exceed them

## Per-Shape Breakdown

Results are broken down by query shape:
- **focused** — targets a single file (e.g., "How does JWT verification work?")
- **cross-file** — spans multiple files (e.g., "How does authentication work?")
- **identity** — asks what something is (e.g., "What database does this project use?")

Per-shape breakdown catches regressions that only hit specific shapes. A change that breaks cross-file queries but preserves focused queries would be invisible in aggregate metrics but obvious in the breakdown.

## Running the Benchmark

```bash
# Build fixture (if not already built)
graphify update tests/fixtures/sample_project
neuralmind build tests/fixtures/sample_project --force

# Run unit tests for metrics
python -m pytest tests/test_benchmark_metrics.py -v

# Run retrieval benchmark (computes metrics + writes results)
python -m tests.benchmark.retrieval_run

# Run CI regression gates
python -m pytest tests/test_retrieval_benchmark.py -v

# Full suite (release gate)
python -m pytest tests/test_benchmark_regression.py tests/test_retrieval_benchmark.py -v
```

## Extending to Real Repos

The framework is designed to extend beyond the hermetic fixture:

1. **Add queries**: Create `benchmark_queries_<project>.json` with the same schema
2. **Add ground truth**: For each query, author `relevance_grades` (all modules) and `gold_facts`
3. **Run on real repo**: Point `FIXTURE_DIR` to the real repo's path
4. **Adjust floors**: Real repos with thousands of modules may need different floors

The metrics themselves are repo-agnostic — they only need a ranked list and ground truth.

## File Layout

```
tests/benchmark/
├── retrieval_queries.json    # Ground truth (19 queries × 7 grades + 2-4 facts)
├── metrics.py                # Pure-Python IR metrics
├── retrieval_run.py          # Runner (queries → metrics → results)
├── retrieval_results.json    # Structured output (generated)
├── retrieval_report.md       # Human-readable report (generated)
├── run.py                    # Existing self-benchmark (untouched)
├── results.json              # Existing self-benchmark results (untouched)
└── report.md                 # Existing self-benchmark report (untouched)

tests/
├── test_benchmark_metrics.py     # Unit tests for metrics (27 tests)
├── test_retrieval_benchmark.py   # CI regression gates (8 tests)
└── test_benchmark_regression.py  # Existing regression gate (untouched)
```

## Adversarial QA

Before shipping, `metrics.py` + `retrieval_run.py` must pass adversarial QA:
- DeepSeek v4 Pro: verify formulas match TREC/BEIR definitions
- GLM-5.2: verify edge cases (empty inputs, zero relevance, NaN handling)

## Version History

- **v1.0** (2026-08-05): Initial implementation. 19 queries, 5 metrics, RAGAS integration, 8 CI gates.
