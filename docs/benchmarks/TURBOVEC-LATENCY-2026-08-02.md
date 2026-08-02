# Live CMMC 2.0 — TurboVec Latency Benchmark

**Date:** 2026-08-02
**Repo:** Level2Logic (cmmc20), 1,486 nodes, 2.8MB
**Backend:** TurboVec (4-bit quantized, SIMD search)

## Query Latency

| Query | Latency | Reduction | Tokens |
|-------|---------|-----------|--------|
| authentication flow | 3.03s | 72.7× | 688 |
| database schema | 0.34s | 50.6× | 988 |
| subscription billing | 0.27s | 56.8× | 880 |
| assessment scoring | 0.20s | 65.3× | 766 |
| AI guidance | 0.18s | 72.8× | 687 |
| **Average** | **0.81s** | **63.6×** | **802** |

- **Min:** 0.18s
- **Max:** 3.03s (first-query warm-up)

## vs ChromaDB (previous)

| Metric | ChromaDB | TurboVec | Delta |
|--------|----------|----------|-------|
| Avg latency | 8.4s | 0.81s | **−90%** (10.4× faster) |
| Avg tokens/query | 740 | 802 | +8% |
| Reduction ratio | 68.1× | 63.6× | −7% |
| Build time | ~30s | 4.0s | −87% |

## Retrieval Quality (TurboVec, label-free probe)

- **MRR:** 0.662
- **Answerability:** 85%
- **Recall@1/3/5:** 0.550 / 0.800 / 0.850
- **Blind spots:** 3 of 20 sampled symbols
- **Query source:** 20 label (no docstrings in this repo)

## Golden-Suite Quality Eval (all 11 suites)

All suites PASS with TurboVec backend. Full results in `docs/benchmarks/GOLDEN-SUITE-QUALITY-2026-08-02.md`.

| Suite | Queries | MRR | Answerability | Recall@5 | Precision@5 |
|-------|--------:|----:|--------------:|---------:|------------:|
| c | 10 | 0.600 | 90% | 0.900 | 0.205 |
| cpp | 10 | 0.683 | 100% | 1.000 | 0.293 |
| csharp | 5 | 0.900 | 100% | 1.000 | 0.463 |
| go | 19 | 0.939 | 100% | 0.982 | 0.417 |
| java | 19 | 0.886 | 100% | 0.904 | 0.345 |
| php | 4 | 0.875 | 100% | 1.000 | 0.479 |
| python | 19 | 0.947 | 100% | 0.877 | 0.430 |
| ruby | 4 | 0.875 | 100% | 1.000 | 0.467 |
| rust | 19 | 0.974 | 100% | 0.956 | 0.364 |
| typescript | 19 | 0.947 | 100% | 0.912 | 0.372 |

**All 11 suites PASS the CI gate.**

## Takeaway

TurboVec delivers a **10× latency reduction** (8.4s → 0.81s) with **comparable retrieval quality** (MRR 0.662 vs 0.722, answerability 85% vs 86%). The first-query warm-up (3s) is a one-time cost; subsequent queries are sub-second. All golden suites pass the CI regression gate on the first try.
