# CMMC 2.0 Query Routing Bridge — NeuralMind ↔ Local LLM Integration
## Business Requirements Document (BRD)

**Date:** 2026-07-29
**Module:** `neuralmind/cmmc20_bridge.py`
**Status:** Draft
**Commit:** pending
**Claim tier:** B+ (compliance Q&A pipeline combining code-graph retrieval + local LLM inference with cloud fallback)

---

## 1. Business Problem

### 1.1 The Gap

NeuralMind knows the *code*. The CMMC RAG prototype knows the *practices*. They do not talk to each other.

| Capability | Existing | Missing |
|-----------|----------|---------|
| Semantic code search | ✅ NeuralMind `embedder.search()` | — |
| CMMC practice retrieval | ✅ CMMC RAG (ChromaDB + Ollama) | — |
| Compliance annotation detection | ✅ `compliance_matcher.py` | — |
| Cross-reference: "Does this code satisfy this practice?" | ❌ | **This bridge** |
| Evidence export of code-to-practice mapping | ✅ `export.py` | ✅ exists, but not LLM-grounded |
| Query routing: simple → local, complex → cloud | ❌ | **This bridge** |

**The core problem:** A developer or GRC analyst who asks "Does our auth service meet AC.L2-3.1.1?" today must manually:
1. Query NeuralMind for relevant code nodes (auth pieces)
2. Look up AC.L2-3.1.1 in the CMMC registry
3. Mentally cross-reference the two
4. Format an answer

This does not scale to 110 practices across a growing codebase.

### 1.2 Why Now

Three preconditions are met simultaneously:

- **NeuralMind G1 + G7:** 110 CMMC practices are already graph nodes (`neuralmind ingest-cmmc`). Compliance annotations in code comments are detected and linked via synapses.
- **CMMC RAG prototype exists:** Proven prompt structure + local LLM integration at `/home/dtfrost5/cmmc_rag_v2.py`. 100% accuracy on domain retrieval.
- **Local LLM is operational:** `qwen2.5:3b-instruct-q4_K_M` running on localhost:11434. Cloud DeepSeek V4 Pro available for fallback.

---

## 2. User Stories

### 2.1 Developer (Primary)

**As a** developer working on a CMMC-scoped codebase,
**I want to** ask "Does this function satisfy AC.L2-3.1.1?" and get a grounded answer citing my actual code,
**so that** I don't need to flip between the CMMC practice document and my IDE.

### 2.2 GRC Analyst (Primary)

**As a** GRC (Governance, Risk, and Compliance) analyst,
**I want to** run a gap analysis across our entire auth codebase against AC domain practices,
**so that** I can produce an evidence checklist for our CMMC Level 2 assessment.

### 2.3 CMMC Consultant (Secondary)

**As a** CMMC consultant reviewing a client's codebase,
**I want to** generate a POA&M (Plan of Actions and Milestones) from code-level findings,
**so that** I can deliver remediation cost estimates with file-level precision.

### 2.4 Engineering Manager (Stakeholder)

**As an** engineering manager,
**I want to** see compliance query costs stay at $0 by using the local LLM for 80%+ of questions,
**so that** we don't burn cloud API budget on routine compliance checks.

---

## 3. Query Flow

```
User Query
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  CMMC20 Bridge                                                │
│                                                              │
│  1. PARSE: Extract practice IDs, domain hints from query      │
│                                                              │
│  2. RETRIEVE from NeuralMind:                                 │
│     ├─ embedder.search(query) → relevant code nodes          │
│     ├─ compliance_matcher → annotation matches               │
│     └─ CMMC content nodes → practice details                 │
│                                                              │
│  3. ROUTE:                                                    │
│     ├─ Single practice + single file → LOCAL (qwen2.5:3b)   │
│     ├─ Multiple practices + multiple files → LOCAL (batch)   │
│     └─ Complex / cross-domain / POA&M → CLOUD (DeepSeek V4) │
│                                                              │
│  4. GENERATE: Build structured prompt → LLM → answer         │
│                                                              │
│  5. EXPORT: Evidence bundle → CSV/PDF via export.py          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 3.1 Route Decision Criteria

| Query Type | Router Decision | Expected % | Latency Budget |
|-----------|----------------|------------|---------------|
| Single practice lookup ("What is AC.L2-3.1.1?") | Local | ~40% | <5s |
| Code-compliance gap ("Does auth.py meet AC.L2-3.1.1?") | Local | ~35% | <10s |
| Multi-practice analysis ("Which AC practices does auth cover?") | Local | ~10% | <15s |
| Cross-domain POA&M ("Build a remediation plan for all AC gaps") | Cloud | ~10% | <30s |
| Evidence checklist generation | Local | ~5% | <10s |

**Target: 85%+ local, 15% or fewer routed to cloud.**

---

## 4. Success Criteria

### 4.1 Query Accuracy

| Metric | Target | Measurement |
|--------|--------|-------------|
| Practice ID recall | 100% | Practice ID present in answer |
| Code reference accuracy | ≥95% | Retrieved code node is relevant to the practice |
| Answer grounded in context | ≥95% | Answer cites specific code lines or practice text |
| Hallucination rate (false compliance claims) | <5% | Manual review of edge cases |

### 4.2 Latency

| Metric | Target |
|--------|--------|
| Local P50 | <5s |
| Local P95 | <12s |
| Cloud P50 | <8s (DeepSeek API latency) |
| Cloud P95 | <20s |

### 4.3 Cost

| Metric | Target |
|--------|--------|
| Local queries | $0 (Ollama on local hardware) |
| Cloud queries per 1K | ~$0.03 (DeepSeek V4 Pro) |
| Monthly cloud budget at 500 queries | <$2.25 |

### 4.4 Coverage

| Metric | Target |
|--------|--------|
| CMMC practices supported | 110/110 (all Level 2) |
| Query patterns supported | 5 (see §Prompt Templates in TRD) |
| Export formats | 2 (CSV, PDF) |

---

## 5. Constraints & Non-Goals

### 5.1 Constraints

- **No cloud dependency for core flow:** The bridge must function fully offline for single-practice + single-file queries.
- **No modification to existing NeuralMind modules:** `core.py`, `embedder.py`, `export.py`, `compliance_matcher.py` remain unchanged. The bridge is additive.
- **Local model ceiling:** qwen2.5:3b has a 32K token context window. Practice + code snippets must fit within this. Complex multi-codebase queries must route to cloud.

### 5.2 Non-Goals (v1)

- **No fine-tuned model:** The `cmmc-expert-v2` fine-tune is not production-usable (training loss 0.1695, output not coherent). v1 uses zero-shot prompting only. A future cmmc-expert-v3 is a roadmap item.
- **No real-time code watcher:** The bridge queries the *indexed* code graph. It does not watch files for live changes.
- **No authentication/authorization on the bridge API:** v1 is a CLI + library module. API server is future scope.
- **No 3rd-party tool integration:** No Jira, ServiceNow, or GRC platform connectors. Exports are CSV/PDF only.

---

## 6. Alternatives Considered

### 6.1 Full cloud (DeepSeek-only)

**Rejected** because:
- Every query costs money
- Requires internet connectivity
- Latency is worse for simple lookups (cloud round-trip vs local)
- CUI data must not leave the network for Level 2 compliance

### 6.2 Full local (Ollama-only)

**Rejected** because:
- 3B parameter model cannot reliably reason across 5+ practices and 10+ code files
- Multi-practice synthesis (POA&M generation) requires stronger reasoning
- Context window limits make large codebase analysis impossible locally

### 6.3 Separate RAG service (standalone FastAPI)

**Deferred** because:
- Would duplicate NeuralMind's existing graph retrieval
- Bridge-as-library has zero operational overhead
- Can be wrapped by a server later if needed

---

## 7. Future Considerations

- **cmmc-expert-v3 fine-tune:** Once 64GB RAM upgrade completes, train a 3B parameter model on 110 practices + synthetic Q&A pairs. Target: match cloud quality on local hardware.
- **Multi-framework analysis:** Extend bridge to SOX, NIST, HIPAA, ISO 27001 using the same architecture — the compliance_matcher already supports all of them.
- **Automated POA&M ingestion:** Feed bridge output into Jira/ServiceNow via pluggable connectors.
- **Continuous gap monitoring:** Cron-driven daily bridge runs that alert on new code-vs-practice gaps.

---

## 8. Open Questions

| # | Question | Owner | Status |
|---|----------|-------|--------|
| Q1 | What is the actual token consumption per avg query (practice + code snippet)? | TBD | Needs benchmark |
| Q2 | Should the cloud router use DeepSeek V4 Pro or could GPT-4o-mini be cheaper? | TBD | Cost comparison needed |
| Q3 | How many code nodes does `embedder.search()` return for "auth AC.L2-3.1.1"? | TBD | Needs query profiling |
