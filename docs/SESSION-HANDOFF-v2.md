# Session Handoff — NeuralMind Future-Proof Plan v2.0

**Date:** 2026-07-17
**Approved by:** dfrostar (all buckets A–G, as-drafted)
**Next session:** Begin Wave 1 execution — D, B1, G1 in parallel

---

## THE ASK

Build the NeuralMind future-proofing plan v2.0 into working code. Execute Wave 1 in parallel:
**D (Quality harness)**, **B1 (IR-as-primary-contract)**, **G1 (Dynamic import resolution)**.
Then proceed to Waves 2–4 per the dependency graph in the plan.

---

## WHERE THE PLAN LIVES

Single source of truth: `docs/FUTURE-PROOFING-PLAN.md`
Archived (superseded): `docs/archive/FUTURE-PROOFING-PLAN-v1.0.md`, `docs/archive/2026-06-10-future-proofing-prd-pack.md`
Roadmap reference: `ROADMAP.md` (top, updated to point to v2)

---

## WAVE 1 PARALLEL WORKSTREAMS

### D — Quality harness (highest priority, unlocks C1 which unlocks everything adaptive)

**D1. RAGAS-axis offline judge.** Four metrics, zero LLM cost, zero network:
- Context precision: embedding-cosine between retrieved chunks and query
- Context recall: embedding-cosine between gold facts and retrieved chunks
- Faithfulness: token-overlap + contradiction heuristic (negation detection, entity consistency)
- Answer relevance: embedding-cosine between answer and query
All four run offline, reported per-query, aggregated per-build, CI-gated against regression.

**D2. Retrieval metrics.** MRR, nDCG@k, hit-rate@k, precision@k over fixture query set (k=5,10,20). CI-gated. Visible in `neuralmind benchmark --quality`.

**D4. Per-language fixtures** (in parallel with D1/D2). TS, Go, Rust, Java fixtures with real query + gold-fact sets. Mirror the Python fixture at `tests/fixtures/sample_project/`.

### B1 — IR-as-primary-contract migration (finish PRD 1, close the ghost contract gap)

- Make the embedder read `.neuralmind/index_ir.json` instead of `graphify-out/graph.json` as the default code path
- The IR adapter at `neuralmind/ir.py` (already round-trip-faithful, validated by tests) becomes the canonical ingestion path
- Legacy `graph.json` loading retained for one minor release as fallback
- No change to the embedder's downstream behaviour (the IR is designed to be byte-identical on all fields the embedder consumes)
- Update tests to exercise the IR path; existing legacy tests keep passing

### G1 — Cross-file import resolution for dynamic languages

- Static AST analysis + string-literal heuristic at graphgen time (`neuralmind/graphgen.py`)
- Resolve `importlib.import_module("foo")` and `require(variable)` when the argument is a literal or bounded set of literals
- For literals: deterministic structural edges (`confidence_score = 1.0`)
- For variables/dynamic: flagged low-confidence (`confidence_score < 0.5`), surfaced but down-weighted in retrieval
- Required before G2 (SCIP) and G3 (modularity clustering)

---

## THE CRITICAL PATH

The plan's critical path is **D → C1 → C2/C3 → A3/A4 → E1/E2/E4**.

Why this matters now: Wave 1's D (quality harness) must deliver before Wave 2's C1 (fitness function) can be built. C1 is what Wave 3's population-based tuner (C3) optimizes. The tuner is the moat — it's what makes the product self-improving at the local level without a research team. If you only ship one bucket's worth of impact, ship D first and start C1 immediately after.

---

## KEY ARCHITECTURE RULES (do not violate)

1. **Local-first.** No cloud. No phone-home. All fitness eval, tuner search, sleep consolidation, team-memory merge run on the user's machine.
2. **Fail-open.** Every new subsystem (traces, resolution, tuner, judge) degrades gracefully. A failure in any of them must never break query/build/search.
3. **Stdlib-only where it counts.** The synapse layer, structural index, and IR are stdlib-only on purpose — they run without the embedding dep set. Keep it that way for new memory/judge code.
4. **IR is the contract (after B1).** Once B1 lands, new features that consume graph data read the IR, not graph.json directly.
5. **Existing public commands are byte-compatible.** `neuralmind query`, `search`, `build`, `benchmark`, `probe` — their output shape and semantics for existing users don't change unless the plan explicitly says so.
6. **The honesty asset.** `HONEST-ASSESSMENT.md` gets *more* honest with every release, not less. Measured numbers beat marketing copy.

---

## WHAT NOT BUILDING (confirmed by maintainer)

- Hosted SaaS (explicitly out of scope per ROADMAP)
- Cross-repo / org-wide search (Sourcegraph Cody's niche)
- Inline completion (Copilot's niche)
- Full ColBERT multi-vector (storage-prohibitive for local-first; learned sparse approximates 80% of the benefit)
- LLM-judged offline judge (offline heuristic is default; LLM judge stays opt-in per the v0.13 principle)

---

## THE 7 BUCKETS AT A GLANCE

| Bucket | What | Wave | Why |
|---|---|---|---|
| A | Memory deepening (traces, entity resolution, learned decay, sleep) | 2-3 | The product. The moat. |
| B | Retrieval upgrade (IR migration, learned sparse, cross-encoder) | 1-3 | Close the gap to 2026 SotA. |
| C | Self-improvement v2 (multi-objective fitness + population-based evo) | 2-4 | Autonomous local evolution. |
| D | Quality harness (RAGAS + nDCG/MRR + per-language) | 1 | Measure what matters. |
| E | Team memory (quality scoring, merge semantics, peer review) | 4 | Close the E1.5 loop honestly. |
| F | Daemon + MCP hardening (Streamable HTTP, shared memory, metrics, backpressure) | 3-4 | Infrastructure for continuous evolution. |
| G | Graph precision (dynamic imports, SCIP, modularity clustering) | 1-4 | The commodity half. |

---

## DECISION-MAINTAINER APPROVED (non-negotiable without re-discussion)

- **C is deep, not narrow.** Population-based evolutionary optimization, not fixed-point tuner. Rationale: 2026 research consensus is that population search (not hill-climbing) produces genuine capability gains. Bounded population (10-20), bounded generations (5-10), CI-gated promotion.
- **B uses learned sparse + cross-encoder, not full ColBERT.** Storage-prohibited for local-first. Learned sparse approximates most of the late-interaction benefit at ~5% storage uplift.
- **G uses Louvain/Leiden modularity** over the structural edge set (real architectural communities, not per-file).
- **F adopts Streamable HTTP** (2026 MCP standard). Not adopting locks into single-client local.

---

## SUCCESS CRITERIA (from the plan)

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

## FIRST CONCRETE ACTIONS (do these in the next session)

1. Read `docs/FUTURE-PROOFING-PLAN.md` for full context on every bucket (especially C and the critical path D→C1→C3).
2. Read the current state of `neuralmind/benchmark.py`, `tests/benchmark/`, and `tests/fixtures/sample_project/` — this is where D lives.
3. Read `neuralmind/ir.py` and the embedder construction in `neuralmind/backend_manager.py` / `neuralmind/turbovec_backend.py` — this is where B1 lives.
4. Read `neuralmind/graphgen.py` (the per-language extractors and symbol extraction) — this is where G1 lives.
5. Spawn **D**, **B1**, **G1** as three parallel workstreams. Each should:
   - Confirm current code state vs. the plan's "current state" description
   - Surface any drift or hidden assumptions
   - Propose a concrete implementation + test plan for that wave's scope
   - Flag any blocker that would prevent the critical path (D→C1→C3) from completing

---

## CROSS-SESSION CONVENTIONS

- **Memory notes** in this session: plan adopted, buckets per the v2 future-proofing plan, v1.0 archived, all 7 buckets approved as-drafted.
- **Deliverable format:** plan is canonical markdown; working code is the next session's output.
- **Honesty rule:** report blockers honestly. Never substitute fabricated results.
- **Don't re-summarize at length** once a bucket is approved. Move to execution.
- **Backup ritual:** after a wave completes successfully, back up to the repo as a celebration.

---

*Handoff prepared by Hermes. v1.0 → v2.0 transition complete. Next session: execute Wave 1.*
