# Wave 4 — Business Requirements Document (BRD)

**Date:** 2026-07-21
**Repos:** `dfrostar/neuralmind` (public), `dfrostar/neuralmind-autopilot` (PRIVATE)
**Previous waves:** 1-3 (D, B1, G1, A1-A4, B2-B3, C1-C3, F1-F2)
**NeuralMind release:** v1.1.0 → v1.2.0
**Autopilot release:** v0.8.0 → v0.9.0

---

## 1. Business Problem

Wave 3 shipped the self-improvement engine's core: multi-objective fitness (C1), expanded parameter space (C2), and population-based evolutionary search (C3). The tuner runs in the daemon and proposes candidate configs — but **nothing promotes or rolls them back automatically**. The tuner is a brain with no hands: it can evaluate candidates but cannot ship them.

Wave 4 closes the loop. Without it, the tuner's output is advisory — an operator must manually read the proposal, evaluate it, and apply it. The "self-improving product" claim is theater until the promotion path is CI-gated and automated.

Simultaneously, Wave 4 completes the quality harness (D3/D4), wires team-memory merge semantics (E1/E2/E3/E4), adds observability (F3/F4), and raises graph precision (G3/G4).

---

## 2. Business Objectives

| # | Objective | Success Metric | Claim Tier |
|---|-----------|---------------|------------|
| O1 | CI-gated tuner promotion (C4) | Tuner proposes → harness validates → auto-promote or auto-rollback, zero operator intervention | A |
| O2 | Populate judge transcripts (D3) | `bench/public/judge/` has >= 3 project transcripts with real LLM-judged evaluations | C |
| O3 | Per-language fixtures (D4) | TypeScript, Go, Rust, Java fixtures with gold-fact sets | C |
| O4 | Contribution-quality scoring (E1) | Team-memory edges weighted by contributor's measured onboarding lift | B |
| O5 | Merge semantics with decay-on-conflict (E2) | Conflicting edges resolved by quality score, loser decays | B |
| O6 | Peer review gate (E3) | Team-baseline contributions require PR review before commit | C |
| O7 | Staleness detection (E4) | Unreinforced team edges flagged after N days (default 60) | C |
| O8 | Tool-use metrics pipeline (F3) | JSONL stream of latency/reuse/success/cost per query | B |
| O9 | Backpressure + circuit breakers (F4) | Bounded queue depth, fail-fast on overload, auto-recovery | B |
| O10 | Modularity clustering (G3) | Louvain/Leiden communities replace balanced-per-file | B |
| O11 | Incremental re-extraction (G4) | Changed files + dependents re-extracted, not just re-embedded | B |

---

## 3. Stakeholders & Users

| Persona | Need | Pain Today |
|---------|------|------------|
| Operator (dfrostar) | Self-improving product that actually self-improves | Tuner proposals are manual — operator must read, evaluate, apply |
| Tier 2 customer | Team memory that improves with usage | Team brain is a static bundle, not a living merge |
| NeuralMind (product) | Discoverable quality metrics | Judge directory empty, no per-language eval |
| Autopilot (operator) | Observability into daemon health | No metrics stream from daemon to operator |

---

## 4. Workstreams

### A. C4 — CI-Gated Tuner Promotion (**SHIPPED** — `7e7ff98`)

**Files:**
- `neuralmind/quality_harness.py` (NEW — independent validation gate)
- `neuralmind/tuner.py` (EXTENDED — harness injection + promote_with_harness)
- `neuralmind/contracts.py` (EXTENDED — META_TUNER_LAST_DECISION)
- `tests/test_quality_harness_c4.py` (NEW — 13 tests)

**Requirements (all met):**
- ✅ Tuner proposes candidate config → harness evaluates against fixture queries
- ✅ If harness pass AND fitness > incumbent*(1+hysteresis): auto-promote
- ✅ If fitness < incumbent: auto-rollback to incumbent
- ✅ Promotion logged in `self_improve:tuner_last_decision` meta key
- ✅ Failure mode: harness unavailable → fail-open (passed=True, fitness=0.0)
- ✅ Backward compatible: `harness=None` preserves hysteresis-only behavior

### B. D3 — Populate Judge Transcripts (neuralmind)

**Files:**
- `bench/public/judge/` (CREATE — commit LLM-judged transcripts)
- `neuralmind/benchmark.py` (READ — understand `--judge` arm)

**Requirements:**
- Run `neuralmind benchmark --public --judge` on >= 3 projects
- Commit transcripts to `bench/public/judge/`
- Document which projects, which LLM judge, which version

### C. D4 — Per-Language Fixtures (neuralmind)

**Files:**
- `tests/fixtures/` (CREATE — TypeScript, Go, Rust, Java fixtures)
- `neuralmind/eval.py` (READ — understand fixture format)

**Requirements:**
- Mirror Python fixture structure (query + gold-fact sets)
- Each fixture: 10+ queries, gold facts, expected top-k nodes
- CI-gated: `neuralmind eval --language <lang>` passes

### D. E1 — Contribution-Quality Scoring (neuralmind)

**Files:**
- `neuralmind/team_memory.py` (EXTEND — add quality scoring)
- `neuralmind/contribution_scoring.py` (CREATE — new module)

**Requirements:**
- Score each contributor by their bundle's measured onboarding lift
- High contributors' edges get higher initial weight in `shared` namespace
- Low contributors' edges start low, rely on reinforcement to persist

### E. E2 — Merge Semantics with Decay-on-Conflict (neuralmind)

**Files:**
- `neuralmind/merge_semantics.py` (EXTEND — add conflict resolution)
- `neuralmind/entity_resolution.py` (READ — A2 already shipped)

**Requirements:**
- When two bundles disagree on same edge: weight by contribution-quality score
- Loser edge decays at accelerated rate
- Requires entity resolution (A2) to recognize same edge across ID schemes

### F. E3 — Peer Review Gate (neuralmind)

**Files:**
- `neuralmind/team_memory.py` (EXTEND — add review flag)

**Requirements:**
- Team-baseline contributions require human review before commit
- Mechanism: GitHub PR on bundle file with E1.5 eval delta in PR comment
- Not a new tool — existing GitHub workflow

### G. E4 — Staleness Detection (neuralmind)

**Files:**
- `neuralmind/team_staleness.py` (EXTEND — add flagging)
- `neuralmind/sleep.py` (READ — A4 already shipped)

**Requirements:**
- Flag team-baseline edges with no reinforcement in N days (default 60)
- Couples with A4 sleep consolidation (prunes flagged edges)
- Configurable: `NEURALMIND_STALENESS_DAYS`

### H. F3 — Tool-Use Metrics Pipeline (neuralmind)

**Files:**
- `neuralmind/metrics_pipeline.py` (EXTEND — add continuous logging)
- `neuralmind/daemon.py` (READ — understand daemon loop)

**Requirements:**
- Log per-query: latency, retrieval reuse rate, tool-call success, token cost
- Structured JSONL to `.neuralmind/metrics/`
- Bounded retention (default 30 days)
- Feeds fitness function (C1) and team-memory quality scoring (E1)

### I. F4 — Backpressure + Circuit Breakers (neuralmind)

**Files:**
- `neuralmind/daemon.py` (EXTEND — add queue depth + circuit state machine)

**Requirements:**
- Bounded queue depth for concurrent build/query/watch
- Circuit breaker: closed → open → half-open state machine
- Fail-fast on overload, auto-recovery after timeout

### J. G3 — Modularity Clustering (SHIPPED — v1.4.0)

**Files:**
- `neuralmind/modularity.py` (NEW — pure Python Louvain)
- `neuralmind/graphgen.py` (`_assign_communities` wiring)

**Requirements (all met):**
- [x] Louvain algorithm over structural edge set (O(n·k) Phase 1)
- [x] Resolution parameter applied in ΔQ gain formula
- [x] Communities match architectural boundaries (measured on test project)
- [x] Requires G1+G2 (dynamic import resolution + SCIP precision)
- [x] Deterministic output (sorted node iteration, no hash/random)
- [x] Incremental stability (unchanged files carry community ID byte-for-byte)
- [x] Fail-open (collapses to per-file grouping on ≤1 community output)
- [x] All existing tests pass (1582+)
- [x] ruff clean
- [x] DeepSeek QA: CLEAN (0 CRITICAL, 3 WARNINGs patched)

### K. G4 — Incremental Re-extraction (neuralmind)

**Files:**
- `neuralmind/graphgen.py` (EXTEND — add re-extraction for changed files)
- `neuralmind/incremental_extract.py` (READ — understand current incremental path)

**Requirements:**
- Re-extract symbols from changed files + their dependents
- Uses structural index's reverse edges (`callers`/`importers`)
- Skips full-tree reparse for large repos

---

## 5. Non-Goals

- Hosted SaaS (out of scope per ROADMAP)
- Cross-repo / org-wide search (Sourcegraph Cody's niche)
- Inline completion (Copilot's niche)
- Full ColBERT multi-vector (storage-prohibitive)
- LLM-judged offline judge as default (opt-in only)

---

## 6. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Tuner promotion degrades real quality | Low | High | CI gate (D1/D2) blocks promotion on regression |
| Louvain/Leiden produces unstable communities | Medium | Medium | Seed with current balanced-per-file as baseline |
| Merge semantics create conflict loops | Low | Medium | Decay-on-conflict is one-directional (loser decays) |
| Metrics pipeline adds latency | Low | Low | Async write, bounded retention |
| Incremental re-extraction misses edges | Medium | High | Integration test: rename symbol, verify re-extraction |

---

## 7. Release Criteria

- [ ] A: C4 — Tuner promotion auto-ships or auto-rolls-back based on harness verdict
- [ ] B: D3 — `bench/public/judge/` has >= 3 project transcripts
- [ ] C: D4 — TypeScript, Go, Rust, Java fixtures pass `neuralmind eval`
- [ ] D: E1 — Contribution-quality scoring weights edges by onboarding lift
- [ ] E: E2 — Merge semantics resolve conflicts by quality score
- [ ] F: E3 — Peer review gate flags team-baseline contributions
- [ ] G: E4 — Staleness detection flags unreinforced edges after N days
- [ ] H: F3 — Metrics pipeline logs JSONL to `.neuralmind/metrics/`
- [ ] I: F4 — Backpressure + circuit breakers prevent overload
- [x] J: G3 — Louvain communities replace balanced-per-file (`f49b535`, v1.4.0)
- [ ] K: G4 — Incremental re-extraction skips unchanged files
- [ ] L: All existing tests pass (130+ autopilot, 1500+ neuralmind)
- [ ] M: ruff clean
- [ ] N: Docs synced (BRD, TRD, Test Plan, Decisions)
- [ ] O: ROADMAP.md updated

---

*BRD v1.0. Wave 4 — Close the Loop.*
