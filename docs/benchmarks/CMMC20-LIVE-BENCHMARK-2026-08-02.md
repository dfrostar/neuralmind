# CMMC 2.0 Live Benchmark Report

**Date:** 2026-08-02
**Repo:** `/home/dtfrost5/cmmc20` (Level2Logic CMMC SaaS)
**NeuralMind version:** v1.13.1
**Index:** 1,486 nodes, 89 communities, 129 document chunks from `complete-cmmc-spec.md`

---

## Summary

| Metric | Value |
|--------|-------|
| **Avg token reduction** | **68.1×** |
| **Avg query tokens** | 740 (vs ~50K naive) |
| **Avg latency** | 8.4s/query |
| **Synapse edges** | 4,121 |
| **Document ingestion** | 129 nodes from CMMC spec |

---

## Query-Level Results

| # | Query | Tokens | Reduction | Latency |
|---|-------|--------|-----------|---------|
| 1 | CMMC 2.0 gap assessment methodology | 884 | 56.6× | 8.4s |
| 2 | authentication middleware JWT token validation | 708 | 70.6× | 8.6s |
| 3 | stripe payment integration webhook | 687 | 72.8× | 8.5s |
| 4 | database schema migration compliance | 816 | 61.3× | 8.4s |
| 5 | assessment report generation flow | 690 | 72.5× | 8.2s |
| 6 | multi-tenant organization scoping | 775 | 64.5× | 8.7s |
| 7 | evidence upload S3 storage | 785 | 63.7× | 8.5s |
| 8 | practice assessment scoring algorithm | 683 | 73.2× | 8.3s |
| 9 | client dashboard analytics | 683 | 73.2× | 8.3s |
| 10 | user role permissions RBAC | 686 | 72.9× | 8.1s |

---

## Comparison: Self-Benchmark vs Live CMMC 2.0

| Metric | Self-Benchmark (fixture) | Live CMMC 2.0 | Δ |
|--------|-------------------------|---------------|---|
| Avg reduction | 8.3× | 68.1× | +59.8× |
| Avg tokens | 11,025 | 740 | -93% |
| Top-k hit rate | 71.9% | N/A (quality eval timed out) | — |
| Synapse hit rate Δ | +14.0pts | Not measured | — |
| Latency | ~1s | 8.4s | +7.4s |

**Key insight:** The live CMMC 2.0 repo (1,486 nodes, 2.8MB code+docs) shows **68.1× reduction** — dramatically higher than the 8.3× fixture benchmark. This is expected: the fixture is a small sample project where naive token counts are already low. The larger the codebase, the more NeuralMind's graph structure amortizes the naive cost.

---

## Document Ingestion Verification

```bash
$ python3 -m neuralmind learn complete-cmmc-spec.md --json
{
  "success": true,
  "node_count": 129,
  "embed_stats": {"added": 0, "updated": 0, "skipped": 129},
  "synapse_doc_edges": 0
}
```

- 129 document chunks ingested from 58KB CMMC spec
- 0 new nodes on re-ingestion (dedup via `content_hash` confirmed)
- 0 synapse doc edges (expected: `NEURALMIND_LLM_SEED` not set — fail-open)

---

## Known Gaps

1. **Quality eval timed out** at 120s — the `--quality` flag runs a full precision@k/recall@k over golden queries. Need to either optimize or run offline.
2. **Latency 8.4s/query** — acceptable for interactive use but not for batch. TurboVec backend should reduce this; current build uses default ChromaDB.
3. **No synapse doc edges** — LLM seeding gated off. With `NEURALMIND_LLM_SEED=1` + `ANTHROPIC_API_KEY`, the 129 document chunks would create co-activation edges to code nodes, potentially improving recall further.

---

## Reproduce

```bash
cd /home/dtfrost5/cmmc20
python3 -m neuralmind build .
python3 -m neuralmind learn complete-cmmc-spec.md
python3 -m neuralmind benchmark .
python3 -m neuralmind query . "CMMC 2.0 gap assessment methodology"
```
