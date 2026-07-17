# NeuralMind — Next Session Prompt (Wave 4)

**Date:** 2026-07-17
**Previous session:** Built Wave 3 (C2/C3/A3/A4/B4/F1/F2), tagged v0.47.1, all 13 workstreams + DeepSeek QA patched and pushed (`6d945ac`).
**Next session:** Begin Wave 4 — C4 (CI-gated promotion), G3 (modularity), G4 (incremental re-extraction), E1/E2/E3/E4 (team memory), F3 (metrics), F4 (backpressure), D3/D4 (judge populate + fixtures).

---

## THE ASK

Build Wave 4 of the NeuralMind future-proofing plan v2.0. Execute in dependency order:

**C4 — CI-gated tuner promotion.** The tuner (C3) proposes configs. Promotion must be CI-gated against the fixture query set with hysteresis. Runs as a GitHub Actions workflow or a local `neuralmindbenchmark --tuner-ci` command: tuner proposes → fitness eval on fixtures → promote only if fitness beats incumbent by margin. Requires C3 (done) + D (done: fitness.py, quality.py).

**G3 — Modularity clustering.** Replace balanced-per-file communities with real graph modularity (Louvain/Leiden) over the structural edge set. Required for L2 to surface architectural boundaries instead of files. Requires G1 (dynamic import resolution, Wave 1) + G2 (SCIP, Wave 2) — but tree-sitter-only Louvain is acceptable for v1; SCIP edges later augment incrementally.

**G4 — Incremental re-extraction.** Currently only re-embedding is incremental. On each build, re-extract symbols from changed files + their callers/importers (reverse edges already indexed in `structural.py`). Skip full-tree reparse for large repos. Requires G3 (modularity), structural_edges (done).

**E1 — Contribution-quality scoring.** Team memory bundles need quality gates: score each contributor's edges by reinforcement frequency, recency, conflict rate. High-quality edges promote to `shared` namespace; low-quality edges stay in `personal`. Requires C1 fitness (done) + A2 entity resolution (done).

**E2 — Merge semantics.** When two contributors' edges conflict, merge with quality-weighted resolution instead of last-write-wins. Requires E1 (scoring) + A2 (entity resolution, done).

**E3 — Peer review gate.** Team-memory contributions above a quality threshold auto-promote; below the threshold flag for human review before entering `shared`. Requires E1 + E2.

**E4 — Staleness detection (team baseline).** Extend A4 (sleep consolidation, done) to detect stale team edges (no reinforcement in N days) and decay them faster than personal edges. Requires A4.

**F3 — Tool-use metrics pipeline.** Continuous JSONL logging: per-query latency, retrieval reuse rate, tool-call success rate, per-query token cost, synapse activation counts. Bounded retention in `.neuralmind/metrics/`. Feeds C1 fitness + E1 scoring.

**F4 — Backpressure + circuit breakers.** Concurrent build/query/watch on the same project degrades gracefully: bounded queue depth, fail-fast on overload, circuit-breaker state machine (closed → open → half-open). Builds on the existing ProjectRegistry + per-project lock.

**D3 — Populate judge transcripts.** Offline --judge needs real query→answer→expected triples. Populate `bench/public/judge/` with fixture queries and reference answers. Requires D1/D2 (done: quality.py, precision_at_k).

**D4 — Per-language fixtures.** Extend `evals/quality/` runner to cover all 10 languages with real query sets. Requires D1/D2 (done).

---

## WHAT SHIPPED IN WAVE 3 (v0.47.1 + patches)

### C2 — Expanded parameter space
- `neuralmind/contracts.py`: `TuneableParam` frozen dataclass, `TUNABLE_PARAMS` registry (17 params), `register_param`/`get_param`/`clamp_value`, meta keys for A3/C3/A4
- `neuralmind/tuning.py`: `DEFAULT_PARAMS`, `init_registry()`, `load_params`/`save_params` via synapse meta table, `resolve_effective()`, `effective_int`/`effective_float`
- `neuralmind/context_selector.py`: runtime reads from registry via `_resolve_params()` + instance attrs; class constants retained for backward compatibility

### C3 — Population-based evolutionary search
- `neuralmind/tuner.py`: `PopulationTuner` with `CandidateConfig`/`TuneRun`, Gaussian perturbation + uniform exploration (p=0.15), hysteresis-gated promotion (margin 0.05), multi-generation loop, offline schedule gate, `run_generation()`
- Wired into `core.py:_maybe_run_tuner()` (gated on `NEURALMIND_TUNER_ENABLED=1`)
- Fitness proxy: documented limitation (only efficiency axis varies across candidates)

### A3 — Learned per-edge decay
- `neuralmind/learned_decay.py`: `compute_edge_half_life()` with recency damping + `min_floor` param for shared namespace stickiness, `update_learned_half_life()` with optional `conn` reuse
- `neuralmind/synapses.py`: `half_life_days` + `learned_at` columns (nullable, backfilled), `decay()` branches on `IS NULL`/`IS NOT NULL` for ephemeral/shared/default namespaces, `reinforce()` recomputes half-life in the same transaction, composite index `idx_syn_ns_hl`

### A4 — Sleep consolidation
- `neuralmind/sleep.py`: `DaemonSleep` with `prune_redundant_edges`, `promote_ltp_edges`, `emit_team_bundle`, `detect_stale_edges` (all namespaces), schedule gate
- Emits consolidated team-baseline bundle to `self_improve:team_bundle` meta key

### B4 — Hierarchical summarization
- `neuralmind/summarize.py`: `RaptorSummarizer` with recursive chunking + heuristic/semantic scoring, `get_l2_summary()` reads IR contract (`index_ir.json`)
- Gated on `NEURALMIND_SUMMARIZE=1`

### F1 — Streamable HTTP MCP transport
- `neuralmind/mcp_http.py`: `StreamableHTTPMCP` skeleton (session lifecycle + Starlette app factory), `select_transport()`
- `neuralmind/mcp_server.py`: transport selection in `main()` (gated on `NEURALMIND_MCP_TRANSPORT=streamable_http`), falls back to stdio

### F2 — Shared daemon memory
- `neuralmind/daemon_memory.py`: `SharedDaemonMemory` with warm instance cache, per-client access scoping, explicit share grants, thread safety, selector cache

---

## THE CRITICAL PATH

```
D → C1 → C2/C3 → A3/A4 → E1/E2/E4
```

Wave 4's E1/E2/E4 are the linchpin. Once contribution-quality scoring (E1) is live, merge semantics (E2), peer review gates (E3), and team-edge staleness (E4) unlock the team-memory flywheel. This is where product becomes platform.

---

## KEY ARCHITECTURE RULES (do not violate)

1. **Local-first.** No cloud. No phone-home.
2. **Fail-open.** Every new subsystem degrades gracefully.
3. **Stdlib-only where it counts.** Heavy deps imported lazily.
4. **IR is the contract (after B1).** Read `index_ir.json`, not `graph.json`.
5. **Existing public commands are byte-compatible.**
6. **The honesty asset.** `HONEST-ASSESSMENT.md` gets *more* honest.
7. **Per-module DeepSeek QA (new rule, Wave 3 lesson).** One DeepSeek subagent per module, model-pinned, inline code, explicit risk checklist, patch diffs requested. See `deepseek-qa` skill.

---

## FIRST CONCRETE ACTIONS

1. Read `neuralmind/fitness.py`, `neuralmind/quality.py`, `neuralmind/structural.py`, `neuralmind/team_memory.py`, `neuralmind/memory.py`, `neuralmind/synapses.py` — confirm Wave 4 integration points
2. Read `evals/quality/runner.py`, `tests/test_quality_harness.py` — confirm D3/D4 test patterns
3. Build C4 (CI-gated promotion) — closest to completion since C3 + D are done
4. Build G3 + G4 in parallel (graph precision)
5. Build E1/E2/E3/E4 as a chain (team memory)
6. Build F3 + F4 in parallel (infrastructure)
7. Build D3 + D4 (quality harness populate)
8. Per-module DeepSeek review after each workstream (pinned, inlined, patched immediately)
9. Run all tests after each workstream
10. Back up to the repo as a celebration when Wave 4 ships

## WHAT NOT BUILDING (confirmed by maintainer)

- Hosted SaaS
- Cross-repo / org-wide search
- Inline completion
- Full ColBERT multi-vector
- LLM-judged offline judge as default

---

## CROSS-SESSION CONVENTIONS

- **Memory notes:** v2 plan adopted, buckets A-G approved, Waves 1-3 shipped + patched
- **Deliverable format:** DOCX/XLSX/PPTX for external-facing work, markdown only for internal drafts
- **Honesty rule:** report blockers honestly. Never substitute fabricated results.
- **Backup ritual:** after a wave completes successfully, back up to the repo as a celebration.
- **DeepSeek QA:** methodology-encoding work gets routed through DeepSeek v4 Pro for preliminary review before sign-off.
- **Public-repo standard:** brutally honest, fact-based, no dead code, no overclaims.
- **DeepSeek dispatch pattern (Wave 3 lesson):** use the `deepseek-qa` skill. Per-module dispatch, model pin `{"provider": "deepseek", "model": "deepseek-v4-pro"}`, inline code, explicit risk checklist, patch diffs.

---

*Handoff prepared by Hermes. Wave 3 → Wave 4 transition. Next session: execute Wave 4.*
