# NeuralMind — Next Session Prompt (Wave 2)

**Date:** 2026-07-17
**Approved by:** dfrostar (all buckets A–G, as-drafted)
**Previous session:** Built Wave 1 (D/B1/G1), tagged v0.47.1
**Next session:** Begin Wave 2 — start C1 (fitness function), then A1/A2/B2/B3/G2 in parallel

---

## THE ASK

Build Wave 2 of the NeuralMind future-proofing plan v2.0. Execute C1 first (it's on the critical path), then A1, A2, B2, B3, G2 in parallel once C1 lands. Then proceed to Waves 3–4 per the dependency graph.

---

## WHERE THE PLAN LIVES

Single source of truth: `docs/FUTURE-PROOFING-PLAN.md` (v2.0, 567 lines)
Archived (superseded): `docs/archive/FUTURE-PROOFING-PLAN-v1.0.md`, `docs/archive/2026-06-10-future-proofing-prd-pack.md`
Roadmap reference: `ROADMAP.md` (top, updated to v0.47.0)
Handoff from v1→v2: `docs/SESSION-HANDOFF-v2.md`

---

## WHAT SHIPPED IN WAVE 1 (v0.47.1)

### D — Quality harness
- `neuralmind/ragas.py`: RAGAS-axis offline judge (faithfulness, context precision/recall, answer relevance)
  - Faithfulness = stdlib-only (token-overlap + contradiction heuristic)
  - Cosine columns use injectable `embed_fn` for model-free CI
  - `faithfulness = fact_recall * (1 - contradiction)` — multiplicative, not additive
- `neuralmind/quality.py`: nDCG@k, hit-rate@k added; DEFAULT_KS extended to (1, 3, 5, 10)
- `evals/quality/runner.py`: 7 language suites registered (python, typescript, go, rust, java, c, cpp)
- `evals/quality/harness.py`: SEARCH_K bumped 10→20
- Tests: 11 new in `tests/test_quality_harness.py`

### B1 — IR-as-primary-contract
- `embedding_backend.py`: `ir_path` property on base class
- `embedder.py`, `turbovec_backend.py`, `in_memory_backend.py`: IR-first `load_graph()` with mtime fallback
- `core.py`, `server.py`: Updated error messages and existence checks
- Tests: 14 new in `tests/test_ir_load.py`

### G1 — Dynamic import resolution
- `add_edge()` gains `confidence_score: float = 1.0` kwarg (backward-compatible)
- `_py_resolve_dynamic_imports()`, `_ts_resolve_dynamic_imports()`, Ruby dynamic require extension
- `file_constants` table for const-variable resolution
- `_ensure_ext_node()` helper
- SCHEMA_VERSION 1→2
- Tests: 12 new in `tests/test_graphgen.py`; 2 new fixtures

---

## WAVE 2 PARALLEL WORKSTREAMS

### C1 — Multi-objective fitness function (highest priority, unlocks C2+C3)

**What:** The tuner's North Star. Three axes combined via weighted product:
- *Retrieval quality*: faithfulness delta from D (the "does the agent answer better" signal)
- *Efficiency*: token-cost reduction (the "does it cost less" signal)
- *Session health*: re-query-rate + transition-margin (the "does the agent stop repeating itself" signal)

**Design rules:**
- Weights are operator-configurable: `NEURALMIND_FITNESS_WEIGHTS="0.5,0.3,0.2"`
- Persisted in synapse meta table, tunable per project
- Weighted product (not sum): zero on any axis dominates
- Imports `neuralmind.ragas` and `neuralmind.quality` directly
- CI-gated: fails on regression (not just absolute floor)

**Files to create/modify:**
- `neuralmind/fitness.py` (NEW)
- `tests/test_fitness.py` (NEW)
- Modify `neuralmind/self_improve.py` to use fitness (replaces `re_query_rate` signal)
- Modify `evals/quality/harness.py` to expose fitness output

### A1 — Reasoning trace store

**What:** Immutable `reasoning_traces` table in `synapses.db`:
- (session_id, timestamp, query_fingerprint, strategy, tools_used, outcome, success_signal)
- Queryable by synapse recall path
- Schema-versioned alongside existing meta table
- **Fail-open**: traces are observational, never load-bearing

**Design rules:**
- Observational only — never load-bearing
- Schema-versioned (use existing `meta` table pattern)
- Powers C3 (population search needs real query traces from last N sessions)

**Files to create/modify:**
- `neuralmind/traces.py` (NEW)
- `tests/test_traces.py` (NEW)
- Modify `neuralmind/synapses.py` for table creation
- Modify `neuralmind/core.py` to record traces on query/build

### A2 — Entity resolution layer

**What:** Resolve synapse node identity by structural-anchor + normalized-label, not exact ID match
- Uses existing `normalize_namespace` + `norm_label` seam
- Thresholds: >=0.95 cosine auto-merge, >0.85 human-review flag
- Required for any real team-memory merge semantics (E2 depends on this)

**Design rules:**
- Cosine threshold-based auto-merge (>=0.95) with human-review flag (>0.85)
- Works across ID schemes (different backends mint different IDs)
- Fail-open: unresolved entities stay separate (never corrupt the graph)

**Files to create/modify:**
- `neuralmind/entity_resolution.py` (NEW)
- `tests/test_entity_resolution.py` (NEW)
- Modify `neuralmind/team_memory.py` to use resolution on import/merge

### B2 — Learned sparse retrieval (SPLADE-style)

**What:** SPLADE-style expansion over existing BM25 index
- Lightweight expansion model (distilled from MiniLM, ONNX-compatible)
- Maps each chunk to sparse weighted token vector
- Queried via same RRF path
- ~5% storage uplift, one extra forward pass per chunk at index time
- **Skip full ColBERT** (storage-prohibitive for local-first)

**Design rules:**
- Must wait for B1 (IR is the contract for stored vectors)
- ONNX-compatible (no PyTorch required)
- Operates in `neuralmind/backend_manager.py` search path
- Falls back to BM25 if model unavailable
- Gated behind `NEURALMIND_SPARSE=1` initially

**Files to create/modify:**
- `neuralmind/sparse.py` (NEW)
- `tests/test_sparse.py` (NEW)
- Modify `neuralmind/backend_manager.py` to wire sparse into RRF

### B3 — Cross-encoder reranking

**What:** Distilled cross-encoder (ms-marco-MiniLM, ONNX) reranks top-20 from first stage
- Typically 5-15% precision lift
- Optional: `NEURALMIND_RERANK=1`
- Latency budget cap: `NEURALMIND_RERANK_MAX_MS`
- Off hot path on slow machines

**Files to create/modify:**
- `neuralmind/rerank.py` (NEW)
- `tests/test_rerank.py` (NEW)
- Modify `neuralmind/backend_manager.py` search path

### G2 — SCIP precision pass

**What:** For languages with SCIP support (Go, Rust, Java, C/C++), use `scip-index` at build time for compiler-accurate edges
- Falls back to tree-sitter where SCIP unavailable
- Gated behind `NEURALMIND_SCIP=1` (opt-in until measured parity)

**Files to create/modify:**
- `neuralmind/scip_backend.py` (NEW)
- `tests/test_scip.py` (NEW)
- Modify `neuralmind/graphgen.py` to dispatch to SCIP

---

## THE CRITICAL PATH

```
D → C1 → C2/C3 → A3/A4 → E1/E2/E4
```

Wave 2's C1 (fitness function) is the linchpin. Once C1 is live, C2 (expanded parameter space) and C3 (population-based search) can follow. The tuner is the moat — it's what makes the product self-improving at the local level without a research team.

---

## KEY ARCHITECTURE RULES (do not violate)

1. **Local-first.** No cloud. No phone-home. All fitness eval, tuner search, sleep consolidation, team-memory merge run on the user's machine.
2. **Fail-open.** Every new subsystem degrades gracefully. A failure in any of them must never break query/build/search.
3. **Stdlib-only where it counts.** The synapse layer, structural index, and IR are stdlib-only on purpose. Keep new code stdlib-only unless a real model dep is unavoidable.
4. **IR is the contract (after B1).** New features that consume graph data read the IR, not graph.json.
5. **Existing public commands are byte-compatible.** `neuralmind query`, `search`, `build`, `benchmark`, `probe` — output shape and semantics for existing users don't change unless explicitly stated.
6. **The honesty asset.** `HONEST-ASSESSMENT.md` gets *more* honest with every release. Measured numbers beat marketing copy.

---

## DECISIONS MAINTAINER APPROVED (non-negotiable without re-discussion)

- **C is deep, not narrow.** Population-based evolutionary optimization, not fixed-point tuner. Bounded population (10-20), bounded generations (5-10), CI-gated promotion.
- **B uses learned sparse + cross-encoder, not full ColBERT.** Storage-prohibited for local-first.
- **G uses Louvain/Leiden modularity** over the structural edge set.
- **F adopts Streamable HTTP** (2026 MCP standard).
- **MOAT is the learning loop.** Retrieval is commodity. The synapse layer + tuner = product.

---

## SUCCESS CRITERIA

| Criterion | Target |
|---|---|
| Retrieval quality (synapse vs no-synapse) | Faithfulness delta ≥ +10pts |
| Retrieval discrimination | MRR ≥ 0.65 on fixture query set |
| Token cost | Maintain ≤ current reduction ratio |
| Self-improvement efficacy | Tuner improves fitness ≥ 15% over default in 4 weeks |
| Team onboarding lift | New-agent faithfulness + ≥ 15% with team baseline |
| Graph precision | Structural edge recall + ≥ 20% with SCIP (G languages) |
| MCP transport | Streamable HTTP serves ≥ 3 concurrent clients |

---

## THE 7 BUCKETS AT A GLANCE

| Bucket | What | Wave | Status |
|---|---|---|---|
| A | Memory deepening (traces, entity resolution, learned decay, sleep) | 2-3 | Plan ready |
| B | Retrieval upgrade (IR migration, learned sparse, cross-encoder) | 1-3 | B1 done |
| C | Self-improvement v2 (multi-objective fitness + population-based evo) | 2-4 | Plan ready |
| D | Quality harness (RAGAS + nDCG/MRR + per-language) | 1 | DONE |
| E | Team memory (quality scoring, merge semantics, peer review) | 4 | Plan ready |
| F | Daemon + MCP hardening (Streamable HTTP, shared memory, metrics, backpressure) | 3-4 | Plan ready |
| G | Graph precision (dynamic imports, SCIP, modularity clustering) | 1-4 | G1 done |

---

## FIRST CONCRETE ACTIONS

1. Read `neuralmind/ragas.py`, `neuralmind/quality.py`, `neuralmind/self_improve.py`, `neuralmind/core.py` — confirm current state matches the plan's "current state" description
2. Read `tests/test_quality_harness.py` and `tests/test_fitness.py` (exists?)
3. **C1 (fitness function):** Build new module `neuralmind/fitness.py`
   - Imports from `neuralmind.ragas` (RAGAS-axis scores) and `neuralmind.quality` (retrieval metrics)
   - Three-axis weighted product
   - Configurable weights via env var
   - CI-gated regression test
4. **A1 (reasoning traces):** Build new module `neuralmind/traces.py`
   - New table in `synapses.db`
   - Record on query/build
   - Queryable by recall path
5. **A2 (entity resolution):** Build new module `neuralmind/entity_resolution.py`
   - Cosine threshold-based auto-merge
   - Works across ID schemes
6. **B2 (learned sparse):** Build new module `neuralmind/sparse.py`
   - ONNX-compatible SPLADE-style expansion
   - Integrates with existing RRF path
7. **B3 (cross-encoder):** Build new module `neuralmind/rerank.py`
   - Distilled cross-encoder reranking
   - Latency budget cap
8. **G2 (SCIP):** Build new module `neuralmind/scip_backend.py`
   - For Go/Rust/Java/C/C++
   - Falls back to tree-sitter

---

## WHAT NOT BUILDING (confirmed by maintainer)

- Hosted SaaS (explicitly out of scope per ROADMAP)
- Cross-repo / org-wide search (Sourcegraph Cody's niche)
- Inline completion (Copilot's niche)
- Full ColBERT multi-vector (storage-prohibited for local-first)
- LLM-judged offline judge as default (opt-in per v0.13 principle)

---

## CROSS-SESSION CONVENTIONS

- **Memory notes:** v2 plan adopted, buckets approved as-drafted, v1.0 archived, Wave 1 shipped
- **Deliverable format:** DOCX/XLSX/PPTX for external-facing work, markdown only for internal drafts
- **Honesty rule:** report blockers honestly. Never substitute fabricated results.
- **Don't re-summarize at length** once a bucket is approved. Move to execution.
- **Backup ritual:** after a wave completes successfully, back up to the repo as a celebration.
- **Public-repo standard:** brutally honest, fact-based, no dead code, no overclaims.

---

*Handoff prepared by Hermes. Wave 1 → Wave 2 transition. Next session: execute Wave 2.*
