# Business Requirements Document: NeuralMind Issue Resolution
**Product**: dfrostar/neuralmind v0.38.0  
**Date**: 2026-06-27  
**Owner**: Engineering / DevEx Team

## 1. Executive Summary
NeuralMind v0.19–v0.38 resolved 10/10 critical adoption blockers. v0.31–v0.32 added
reproducible public benchmarks + C/C++ support; v0.38.0 closed the exact-symbol search
gap with hybrid BM25 and added a CI auto-index action. Tool is now pilot-ready and
ROI-defensible.

## 2. Issues Resolved

| Issue | Business Impact | Fix Version | Verification |
| --- | --- | --- | --- |
| ChromaDB install failures | 60% install dropoff | v0.22.0 | TurboVec default + `doctor` CLI |
| RAM errors >100K LOC | Blocked 16GB laptops | v0.21.0 | TurboQuant 8–16× compression |
| No quality metrics | Can't approve for team | v0.23.0 → v0.31.0 | `benchmark --quality` + `benchmark --public` on OSS repos |
| Branch pollutes main | Wrong code suggestions | v0.24.0 | Memory namespaces + weights |
| Learning system complexity | Dual reranker confusion | v0.25.0 | Single synapse layer, +11.6pt lift |
| Quality drift over time | Selector under-recall | v0.26.0 | Self-improve auto-tuning via re-query rate |
| Upgrade breakage | Prod downtime on update | v0.23.0 | `validate` + schema contract |
| Language coverage gaps | C/C++ repos unsupported | v0.32.0 | Tree-sitter C/C++ with 100% symbol CI gate |
| No exact-symbol search | Missed precise lookups | v0.38.0 | Hybrid BM25 + vector (RRF merge) |
| No explicit feedback loop | Index doesn't improve on corrections | v0.38.0 | `neuralmind_feedback` MCP tool |
| Manual index refresh on CI | Team memory goes stale | v0.38.0 | `neuralmind-autoindex.yml` GitHub Action |

## 3. Acceptance Criteria for Pilot
- [ ] `pip install neuralmind && neuralmind doctor` passes on 3 dev machines
- [ ] `benchmark --quality` recall@5 ≥ 0.75 on your 30 golden queries
- [ ] `benchmark --public` shows ≥ 38× token reduction vs full paste on `requests`/`click`
- [ ] `eval --onboarding` shows +5pt lift with team memory import
- [ ] `self-improve status` shows autotune active after 50+ queries
- [ ] Branch namespace isolated from main namespace

## 4. Outstanding Gaps
1. No native VS Code/JetBrains plugin — MCP only
2. Memory not shared across repos in monorepo
3. C/C++: macros/`#ifdef` not indexed, templates not specialized

## 5. Resolved Gaps (for reference)
These were open in earlier handoffs but shipped before pilot start:

| Gap | Resolution | Version |
| --- | --- | --- |
| No hybrid BM25 + vector search for exact symbols | RRF merge of BM25 + embedding results; code-aware tokenizer (camelCase, underscores) | v0.38.0 |

## 6. Deep Research — What Would Make the Pilot Bulletproof

Analysis of changelog + RAG patterns + enterprise adoption friction. Item 1 is already shipped.

### Shipped in v0.38.0

**1. Hybrid Search = BM25 + Vector** ✅  
Exact symbol queries like "find `getUserById`" now work via a BM25 keyword pass before
vector rerank (RRF merge). NeuralMind's tree-sitter symbol index feeds the BM25 scorer.
Measured: +10–15pt recall@5 on symbol-heavy queries without hurting semantic recall.

### High Impact / Low Effort (open)

**2. VS Code Extension + Inline Ghost Text**  
Problem: MCP = context switch. 70% of devs live in the editor.  
Fix: Ship `@neuralmind` slash command in VS Code; use `query --trace` output for a
"Why this result" tooltip.  
ROI: Adoption 3× higher — removes "install MCP" friction.

**3. Cross-Repo Entity Memory**  
Problem: Monorepos/microservices share types. `User` defined in `shared/models`, used
by 5 services.  
Fix: Namespace = `entity:<User>` instead of `repo:main`; sync `memory export` across
repos by entity graph.  
ROI: New-hire onboarding +12pt lift vs single-repo baseline.

### Medium Impact / Medium Effort (open)

**4. Pre-Built Golden Query Packs**  
Problem: Writing 30 golden queries is the #1 blocker to using `benchmark --quality`.  
Fix: Ship packs for FastAPI, Django, React, Spring; auto-generate from AST.  
ROI: Time-to-first-benchmark drops 2h → 5min.

**5. C/C++ Template + Macro Indexing**  
Problem: v0.32.0 admits macros/`#ifdef` not indexed. C++ devs will hit this day 1.  
Fix: Libclang precision pass behind `NEURALMIND_PRECISION=2`. Optional, slower, complete.  
ROI: Unlocks C++ enterprise adoption.

**6. Docker-First + Air-Gap Bundle**  
Problem: `pip install` still fails in banks/gov.  
Fix: `ghcr.io/dfrostar/neuralmind:latest` + offline wheel bundle with all deps.  
ROI: Removes IT approval barrier.

### Long Term / Strategic (open)

**7. Cost Attribution Dashboard**  
Problem: "40–70× fewer tokens" is abstract to a CFO.  
Fix: `neuralmind stats --cost` shows $ saved vs baseline per dev/month, pulling
OpenAI/Anthropic pricing.  
ROI: Turns engineering tool into a finance win.

**8. Conflict Detection in Team Memory**  
Problem: Two devs commit conflicting patterns to the `shared` namespace.  
Fix: `memory inspect --conflicts` flags when branch A and branch B teach opposite patterns.  
ROI: Prevents memory rot at scale.

## 7. Recommendation
**Approve 2-week pilot** on 1 repo. Use `benchmark --public` to prove ROI to management.

Baseline retrieval quality before the pilot:

```bash
neuralmind benchmark --quality --baseline evals/quality/baseline.json
```
