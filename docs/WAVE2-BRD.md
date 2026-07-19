# Wave 2 — Business Requirements Document (BRD)

**Date:** 2026-07-17
**Author:** Hermes (product strategy)
**Approved by:** dfrostar (v2.0 plan, all buckets)
**Source:** `docs/FUTURE-PROOFING-PLAN.md` §9 sequence

---

## 1. Business Problem

NeuralMind v0.47.1 shipped the quality harness (D), IR migration (B1), and dynamic import resolution (G1). The product can now *measure* retrieval quality. It cannot yet *optimize* itself against that measurement.

Current state:
- The self-improvement engine (`self_improve.py`) tunes one parameter (`l2_recall_k`) using a weak signal (`re_query_rate`)
- No fitness function exists — the tuner cannot evaluate whether a change actually improved anything
- Team memory is a static bundle with no merge quality signal
- Retrieval uses single-vector + BM25 (2024 state of the art, not 2026)
- Dynamic imports are resolved (G1), but SCIP-accurate edges and real modularity are missing

The product is measurable. It is not yet adaptive.

---

## 2. Business Objectives

| # | Objective | Success Metric |
|---|-----------|---------------|
| O1 | Replace the single-parameter tuner with a multi-objective fitness function | Fitness score improves ≥15% over default within 4 weeks of deployment |
| O2 | Enable reasoning-trace memory so retrieval can favor successful past strategies | Faithfulness delta ≥ +10pts on fixture query set |
| O3 | Lay groundwork for team-memory merge semantics via entity resolution | Two contributors with different ID schemes resolve to same node with ≥0.95 cosine |
| O4 | Close the retrieval gap vs. 2026 state of the practice | Learned sparse (B2) + cross-encoder (B3) lift precision@5 by ≥5pts on public benchmark |
| O5 | Enable compiler-accurate graph edges for SCIP-supported languages | Structural edge recall +≥20% on Go/Rust/Java/C++ fixtures |

---

## 3. Non-Goals (Confirmed)

- Hosted SaaS / cloud-dependent tuning (violates local-first architecture)
- Full ColBERT multi-vector retrieval (storage-prohibitive)
- LLM-judged judge as default (violates v0.13 principle)
- Inline completion or general agent UX (out of scope)
- Cross-repository / org-wide search (Sourcegraph's niche)

---

## 4. Stakeholders & Users

| Persona | Need | Pain Today |
|---------|------|------------|
| **Individual developer** (primary) | Local-first memory that learns their codebase | Retrieval quality degrades over time; tuner doesn't catch regressions |
| **Team lead** | Onboard new team members with earned intuition | Static team-memory bundle has no quality signal; no merge when contributors disagree |
| **Maker (dfrostar)** | Moat against commodity RAG | Retrieval is replaceable; the learning loop is the product |

---

## 5. Market Context

The codebase-memory space (CodeGraph, Continue, Mem0, Cognee, codebase-memory-mcp) competes on retrieval. The 2026 differentiator is **adaptive learning**: products that improve with use, not products that degrade until re-indexed.

Competitor analysis:
- **Mem0 v3** — cloud-hosted, reasoning traces, multi-agent. Privacy cost.
- **Cognee** — graph-native memory, graph Laplacian signals. No local-first deployment.
- **Claude Code auto-memory** — append-only markdown. No structured learning.
- **Sourcegraph Cody** — cross-repo search. Enterprise-only, no offline mode.

NeuralMind's differentiator: **local-first + adaptive synapse layer + evolutionary tuner**. Wave 2 builds the fitness function that makes the tuner real.

---

## 6. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Fitness function exploits proxy (optimizes metric, degrades real quality) | Medium | High | CI-gated promotion (C4); employs real query traces from reasoning_traces table |
| Population-based tuner too slow on consumer hardware | Low | Medium | Bounded population (10-20), bounded generations (5-10), runs offline weekly |
| Entity resolution corrupts graph with false positives | Low | High | ≥0.95 cosine threshold; fail-open (unresolved stays separate) |
| Learned sparse retrieval regresses on small codebases | Medium | Low | Gated behind `NEURALMIND_SPARSE=1`; falls back to BM25 |
| Wave 2 scope creep delays Wave 3 (the moat) | Medium | High | C1 (fitness function) is the priority; B2/B3/G2 are parallelizable but lower priority |

---

## 7. Release Criteria

- [ ] C1: Fitness function module passes unit tests, integrates with `self_improve.py`
- [ ] A1: Reasoning traces recorded on query/build, queryable by recall path
- [ ] A2: Entity resolution merges same-entity nodes across ID schemes in test fixtures
- [ ] B2: Learned sparse retrieval lifts precision@5 by ≥3pts on Python fixture
- [ ] B3: Cross-encoder reranking lifts precision@5 by ≥2pts (additive to B2)
- [ ] G2: SCIP edges measured on Rust/Go fixtures with recall improvement
- [ ] All existing tests still pass (no regressions)
- [ ] `neuralmind benchmark --quality` reports fitness score

---

## 8. Timeline

Wave 2 is the second of four waves in the v2.0 plan. Estimated sequence:

- **C1** first (on critical path, unlocks C2+C3 in Wave 3)
- **A1, A2, B2, B3, G2** in parallel after C1 lands
- **Wave 3** (C2/C3/A3/A4/B4/F1/F2) follows once C1+A1 are live
- **Wave 4** (C4/E1-G4/F3/F4/D3/D4) closes the loop

Parallelizable workstreams: C1 → {A1, A2, B2, B3, G2} → Wave 3
