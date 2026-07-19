# NeuralMind — Next Session Prompt (Wave 3)

**Date:** 2026-07-17
**Previous session:** Built Wave 2 (C1/A1/A2/B2/B3/G2), tagged v0.47.1
**Next session:** Begin Wave 3 — start C2 (expanded parameter space) + C3 (population-based evo), then A3/A4/B4/F1/F2 in parallel

---

## THE ASK

Build Wave 3 of the NeuralMind future-proofing plan v2.0. Execute in dependency order:

**C2 — Expanded parameter space.** Move beyond l2_recall_k. Candidates: SYNAPSE_BOOST_WEIGHT, STRUCTURAL_BOOST_WEIGHT, SPREAD_DEPTH, L0/L1/L2/L3_MAX_TOKENS, STRUCTURAL_HUB_DEGREE, decay rate bounds, community sensitivity. ~8-12 knobs, each bounded per existing clamp constants in `context_selector.py` and `synapses.py`.

**C3 — Population-based evolutionary search.** Local-first, runs in the daemon. Population 10-20, bounded generations (5-10), Gaussian perturbation around current best + uniform-exploration probability 0.15. Evaluation uses C1 fitness against real query traces from `reasoning_traces` (A1). CI-gated promotion with hysteresis margin.

**A3 — Learned per-edge decay.** Replace fixed `HALF_LIFE_DAYS` scalars with per-edge rates adapted from reinforcement frequency + recency. Bounded to [HALF_LIFE_MIN, HALF_LIFE_MAX]. The C3 tuner learns the bounds.

**A4 — Sleep consolidation.** Scheduled daemon pass (weekly, configurable): prune redundant edges, promote LTP edges that survived decay, emit consolidated team-baseline bundle, detect stale team edges (no reinforcement in N days).

**B4 — Hierarchical summarization for L0-L3.** RAPTOR-style recursive summarization at each layer, replacing hand-tuned `L0_MAX_TOKENS`/`L1_MAX_TOKENS` constants with a learned depth selector. Requires B1 + D.

**F1 — Streamable HTTP transport for MCP.** Follow 2026 MCP spec (Streamable HTTP sessions, OAuth 2.1). Stdio retained as fallback.

**F2 — Shared daemon memory model.** MCP clients connect to the daemon, share the warm NeuralMind instance + synapse store + selector cache. Per-client access scoping so one client can't read another's synapses.

---

## WHAT SHIPPED IN WAVE 2 (v0.47.1)

### C1 — Fitness function
- `neuralmind/fitness.py`: `compute_fitness()` — weighted product across retrieval quality, efficiency, session health. Configurable via `NEURALMIND_FITNESS_WEIGHTS="0.5,0.3,0.2"`, persisted to synapse meta table.
- Tests: 13 new in `tests/test_fitness.py`

### A1 — Reasoning trace store
- `neuralmind/traces.py`: `TraceStore` over `synapses.db`, append-only, queryable by session/fingerprint/outcome/time. `ReasoningTrace` dataclass.
- Tests: 12 new in `tests/test_traces.py`

### A2 — Entity resolution layer
- `neuralmind/entity_resolution.py`: `EntityResolver` with cosine-threshold auto-merge (>=0.95) + human-review flag (>0.85). `norm_label()` for scheme-agnostic identity.
- Tests: 16 new in `tests/test_entity_resolution.py`

### B2 — Learned sparse retrieval
- `neuralmind/sparse.py`: `SpladeExpander` with TF-IDF expansion, cosine scoring, `SparseIndex` for retrieval. BM25 fallback. ONNX-compatible interface.
- Tests: 16 new in `tests/test_sparse.py`

### B3 — Cross-encoder reranking
- `neuralmind/rerank.py`: `CrossEncoderReranker` with `HeuristicReranker` baseline, ONNX interface stub, latency budget cap (`NEURALMIND_RERANK_MAX_MS`), self-disables on slow machines.
- Tests: 7 new in `tests/test_rerank.py`

### G2 — SCIP precision backend
- `neuralmind/scip_backend.py`: `ScipBackend` wrapping `precision.py`, opt-in via `NEURALMIND_SCIP=1`, drop-in dispatch for graphgen.py.
- Tests: 7 new in `tests/test_scip_backend.py`

---

## THE CRITICAL PATH

```
D → C1 → C2/C3 → A3/A4 → E1/E2/E4
```

Wave 3's C2 + C3 are the linchpin. Once C2 expands the parameter space and C3 implements population-based search, A3 (learned decay) and A4 (sleep consolidation) become optimizable. The tuner is the moat — it's what makes the product self-improving at the local level without a research team.

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

## FIRST CONCRETE ACTIONS

1. Read `neuralmind/fitness.py`, `neuralmind/traces.py`, `neuralmind/self_improve.py`, `neuralmind/context_selector.py` — confirm C1/C2 integration points
2. Read `tests/test_fitness.py` and `tests/test_traces.py` — confirm test patterns
3. Build C2 (expanded parameter space) + C3 (population-based search) as the critical path
4. Build A3, A4, B4, F1, F2 as parallel workstreams once C2+C3 land
5. Wire `reasoning_traces` (A1) into C3 evaluation loop
6. Run all tests after each workstream

---

## WHAT NOT BUILDING (confirmed by maintainer)

- Hosted SaaS (explicitly out of scope per ROADMAP)
- Cross-repo / org-wide search (Sourcegraph Cody's niche)
- Inline completion (Copilot's niche)
- Full ColBERT multi-vector (storage-prohibited for local-first)
- LLM-judged offline judge as default (opt-in per v0.13 principle)

---

## CROSS-SESSION CONVENTIONS

- **Memory notes:** v2 plan adopted, buckets approved as-drafted, v1.0 archived, Wave 1+2 shipped
- **Deliverable format:** DOCX/XLSX/PPTX for external-facing work, markdown only for internal drafts
- **Honesty rule:** report blockers honestly. Never substitute fabricated results.
- **Don't re-summarize at length** once a bucket is approved. Move to execution.
- **Backup ritual:** after a wave completes successfully, back up to the repo as a celebration.
- **Public-repo standard:** brutally honest, fact-based, no dead code, no overclaims.
- **DeepSeek QA:** methodology-encoding work gets routed through DeepSeek v4 Pro for preliminary review before sign-off.

---

*Handoff prepared by Hermes. Wave 2 → Wave 3 transition. Next session: execute Wave 3.*
