# Business Requirements Document: NeuralMind Issue Resolution
**Product**: dfrostar/neuralmind v0.38.0  
**Date**: 2026-06-27  
**Owner**: Engineering / DevEx Team

## 1. Executive Summary
NeuralMind v0.19–v0.38 resolved 10/10 critical adoption blockers from the v0.15 baseline.
Tool is now pilot-ready. Remaining gaps are workflow polish, not core reliability.

## 2. Issues Resolved

| Issue | Business Impact | Fix Version | Verification |
| --- | --- | --- | --- |
| ChromaDB install failures | 60% install dropoff | v0.22.0 | TurboVec default + `doctor` CLI |
| RAM errors >100K LOC | Blocked 16GB laptops | v0.21.0 | TurboQuant 8–16× compression |
| No quality metrics | Can't approve for team | v0.23.0 | `benchmark --quality` CI-gated |
| Branch pollutes main | Wrong code suggestions | v0.24.0 | Memory namespaces + weights |
| Upgrade breakage | Prod downtime on update | v0.23.0 | `validate` + schema contract |
| No exact-symbol search | Missed precise lookups | v0.38.0 | Hybrid BM25 + vector (RRF merge) |
| No explicit feedback loop | Index doesn't improve on corrections | v0.38.0 | `neuralmind_feedback` MCP tool |
| Manual index refresh on CI | Team memory goes stale | v0.38.0 | `neuralmind-autoindex.yml` GitHub Action |

## 3. Acceptance Criteria for Pilot
- [ ] `pip install neuralmind && neuralmind doctor` passes on 3 dev machines
- [ ] `benchmark --quality` recall@5 ≥ 0.75 on your golden queries
- [ ] `eval --onboarding` shows +5pt lift with team memory import
- [ ] Branch namespace isolated from main namespace

## 4. Outstanding Gaps
1. No native VS Code/JetBrains plugin — MCP only
2. Memory not shared across repos in monorepo

## 5. Resolved Gaps (for reference)
These were listed as open in earlier handoffs but shipped before pilot start:

| Gap | Resolution | Version |
| --- | --- | --- |
| No hybrid BM25 + vector search for exact symbols | RRF merge of BM25 + embedding results; code-aware tokenizer (camelCase, underscores) | v0.38.0 |

## 6. Recommendation
**Approve 2-week pilot** on 1 repo. Measure: tokens/query, recall@5, new hire onboarding time.

To baseline retrieval quality before the pilot, run:

```bash
neuralmind benchmark --quality --baseline evals/quality/baseline.json
```

This produces per-suite MRR, recall@5, and answerability scores against the golden query set
and flags any regression from the committed baseline.
