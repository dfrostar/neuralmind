# Wave 3 — Business Requirements Document (BRD)

**Date:** 2026-07-17
**Author:** Hermes (product strategy)
**Approved by:** <pending> dfrostar review
**Source:** `docs/FUTURE-PROOFING-PLAN.md` §9 sequence

---

## 1. Business Problem

Wave 2 built the fitness function (C1), reasoning traces (A1), entity resolution (A2), learned sparse retrieval (B2), cross-encoder reranking (B3), and SCIP backend (G2). The product can now *measure* retrieval quality and score candidate configs. But it cannot yet *search* the parameter space, *learn* per-edge decay, *consolidate* memory during offline passes, or *serve* multiple MCP clients.

Current state:
- The tuner still only adjusts `l2_recall_k` — the expanded parameter space (C2) is unoccupied
- No population-based search (C3) means the agent hill-climbs one knob instead of exploring a population
- Synapse decay is fixed per-namespace, not learned per-edge (A3)
- No offline consolidation (A4) means redundant edges accumulate and stale team signals never expire
- Layer budgets (L0-L3) are hand-tuned constants, not learned from the user's query distribution
- MCP is stdio-only (F1), blocking multi-client and remote usage
- No shared daemon memory (F2) means cold-start per MCP client

The product can score a candidate. It cannot yet propose, validate, or promote one.

---

## 2. Business Objectives

| # | Objective | Success Metric |
|---|-----------|---------------|
| O1 | Expand the tuner's parameter space from 1 to 8-12 knobs | C2: All candidate parameters are registered with valid bounds, and the tuner can read/write each |
| O2 | Search the parameter space via population-based evolution | C3: Population-based search improves fitness ≥15% over incumbent within 4 weeks of deployment |
| O3 | Learn per-edge decay rates from reinforcement history | A3: Edges with frequent reinforcement decay ≥2x slower than rarely-reinforced edges, measurably reducing retrieval noise |
| O4 | Consolidate memory during an offline daemon pass | A4: Weekly sleep pass prunes ≥10% redundant edges, promotes LTP survivors, flags stale team edges |
| O5 | Replace hand-tuned layer budgets with learned summarization | B4: RAPTOR-style summarization maintains token budgets while improving answer relevance on the fixture set |
| O6 | Serve ≥3 concurrent MCP clients via Streamable HTTP | F1: Transport passes the MCP spec conformance test; stdio retained as fallback |
| O7 | Share warm daemon memory across MCP clients | F2: Second MCP client starts ≤1s after the first (vs. full cold-start); per-client access scoping enforced |

---

## 3. Non-Goals (Confirmed)

- Hosted SaaS / cloud-dependent tuning (violates local-first)
- Full ColBERT multi-vector retrieval
- LLM-judged judge as default
- Cross-repository search
- F3 (tool-use metrics pipeline) and F4 (backpressure + circuit breakers) — deferred to Wave 4
- C4 (CI-gated promotion) — deferred to Wave 4 (depends on C3 + D)

---

## 4. Stakeholders & Users

| Persona | Need | Pain Today |
|---------|------|------------|
| **Individual developer** | Agent that learns their codebase's patterns | Tuner adjusts one knob; retrieval quality doesn't improve with use |
| **Team lead** | Team memory that stays fresh | Stale team edges accumulate; no way to detect decayed contributions |
| **Maker (dfrostar)** | Moat: an agent that evolves its own config | No evolutionary search; can't self-improve beyond hand-tuned constants |
| **MCP client author** | Remote + multi-client agent access | stdio only; no shared warm state |

---

## 5. Wave 3 Workstream Acceptance Criteria

### C2 — Expanded Parameter Space

**Acceptance:**
- `TuneableParams` registry maps name → (min, max, default, description)
- Covers at minimum: SYNAPSE_BOOST_WEIGHT, STRUCTURAL_BOOST_WEIGHT, SPREAD_DEPTH, L0/L1/L2/L3_MAX_TOKENS, STRUCTURAL_HUB_DEGREE, DECAY_RATE_MIN, DECAY_RATE_MAX
- Each parameter's bounds match existing clamp constants
- `context_selector.py` reads from registry for each parameter (no hardcoded overrides)
- Parameters persisted in synapse meta table; tunable per project
- Fails open: unknown parameter names are logged and skipped, never crash

**Test:**
- `tests/test_tuning.py`: ≥15 tests covering registry lookup, bounds validation, clamp enforcement, persistence round-trip

### C3 — Population-Based Evolutionary Search

**Acceptance:**
- `PopulationTuner` class in `neuralmind/tuner.py`
- Configurable via env: `NEURALMIND_TUNER_POPULATION=15`, `NEURALMIND_TUNER_GENERATIONS=8`, `NEURALMIND_TUNER_HYSTERESIS=0.05`
- Evaluation uses C1 fitness (from `neuralmind/fitness.py`) against real query traces from `reasoning_traces` (A1)
- Gaussian perturbation around current best; uniform exploration probability 0.15
- Promotion requires fitness exceeds incumbent by hysteresis margin
- Runs offline (weekly, configurable via `NEURALMIND_TUNER_INTERVAL`)
- Fail-open: if fitness eval fails, the incumbent stands; no partial promotion
- Local-first: no cloud dependency

**Test:**
- `tests/test_tuner.py`: ≥20 tests covering population sampling, fitness eval, mutation, promotion, hysteresis, fail-open behavior, offline scheduling

### A3 — Learned Per-Edge Decay

**Acceptance:**
- `half_life_days` column added to `synapses` table (schema migration)
- Per-edge rate computed from reinforcement frequency + recency distribution
- Bounded to `[HALF_LIFE_MIN, HALF_LIFE_MAX]` (new constants, defaults [3.0, 120.0])
- Legacy edges without learned rate fall back to namespace default (backward-compatible)
- Decay logic in `synapses.py` updated to use per-edge rate when available
- C3 tuner can propose HALF_LIFE_MIN/MAX bounds

**Test:**
- `tests/test_learned_decay.py`: ≥15 tests covering per-edge rate computation, bounds enforcement, schema migration, fallback behavior, reinforcement-frequency adaptation

### A4 — Sleep Consolidation

**Acceptance:**
- `DaemonSleep` class in `neuralmind/sleep.py`
- Scheduled pass (weekly, configurable via `NEURALMIND_SLEEP_INTERVAL_DAYS`)
- Prunes redundant edges (edges with weight below PRUNE_THRESHOLD and no reinforcement in N days)
- Promotes LTP edges that survived decay
- Emits consolidated team-baseline bundle
- Detects stale team edges (no reinforcement in N days; configurable, default 60)
- Runs offline; never blocks query/build/search
- Fail-open: any error during sleep is logged and skipped

**Test:**
- `tests/test_sleep.py`: ≥15 tests covering pruning, LTP promotion, staleness detection, schedule timing, fail-open behavior, bundle emission

### B4 — Hierarchical Summarization

**Acceptance:**
- RAPTOR-style recursive summarization at each layer (L0-L3)
- Replaces hand-tuned L0_MAX_TOKENS/L1_MAX_TOKENS constants with learned depth selector
- Learned selector operates within IR contract (B1)
- Layer budgets remain byte-compatible (no change to output shape for existing users)
- Gated behind `NEURALMIND_SUMMARIZE=1` initially (opt-in until measured parity)
- Falls back to hand-tuned constants if model unavailable

**Test:**
- `tests/test_summarize.py`: ≥12 tests covering recursive summarization, depth selector, fallback behavior, byte-compatibility of output shape

### F1 — Streamable HTTP MCP Transport

**Acceptance:**
- Implements 2026 MCP spec (Streamable HTTP sessions, OAuth 2.1)
- Stdio retained as fallback for local CLI
- Passes MCP spec conformance test
- Multi-client sessions (≥3 concurrent)
- Existing stdio-only clients continue to work without change
- Token auth preserved

**Test:**
- `tests/test_mcp_http.py`: ≥12 tests covering session management, multi-client concurrency, stdio fallback, OAuth 2.1 flow, auth preservation

### F2 — Shared Daemon Memory

**Acceptance:**
- MCP clients connect to the daemon and share warm NeuralMind instance + synapse store + selector cache
- Per-client access scoping: a client project cannot read another client's synapse data unless explicitly shared
- Second MCP client starts ≤1s after first (vs. full cold-start)
- Existing single-client behavior byte-compatible
- Fail-open: if shared state is unavailable, falls back to cold-start

**Test:**
- `tests/test_daemon_memory.py`: ≥12 tests covering shared instance, access scoping, cold-start fallback, cache invalidation on switch

---

## 6. Shared Contracts

These interfaces must be established before parallel workstreams run:

```python
# contracts.py — shared definitions (Wave 3a spike)
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class TuneableParam:
    name: str
    min_value: float
    max_value: float
    default: float
    description: str

# Registry of all tuneable parameters (populated by C2)
TUNABLE_PARAMS: dict[str, TuneableParam] = {}

# Synapse meta table keys (A3, C3)
META_DECAY_RATE_MIN = "self_improve:decay_rate_min"
META_DECAY_RATE_MAX = "self_improve:decay_rate_max"
```

| Contract | Modules Need It | Location |
|---|---|---|
| `TuneableParams` registry | C2, C3 | new `neuralmind/tuning.py` + `contracts.py` |
| `half_life_days` column migration | A3 | `synapses.py` |
| Daemon sleep scheduler hook | A4 | `core.py` / `server.py` |
| Layer summary generation hook | B4 | `context_selector.py` |
| Shared daemon state model | F1, F2 | `core.py` / `server.py` |
| C1 fitness interface | C3 | `fitness.py` |
| `reasoning_traces` query API | C3, A4 | `traces.py` |

---

## 7. Dependency-Ordered Execution

```
Shared Contracts (Wave 3a)  →  C2 (parameter space)  →  C3 (population search)
                                ↓
                    A3 (learned decay)  ←  C2 complete
                                ↓
                    A4 (sleep consolidation)  ←  A3 complete
                                ↓
                    B4 (hierarchical summarization)  ←  B1 + D complete (already true)
                                ↓
                    F1 (Streamable HTTP)  ─┐
                    F2 (shared daemon)    ─┴─ parallel, no dependency between them
```

Critical path: `Shared Contracts → C2 → C3 → A3 → A4 → B4`. F1 + F2 run in parallel with the critical path once shared contracts land.

---

## 8. Release Criteria

- [ ] C2: All parameters registered with valid bounds; tuner reads/writes each; persistence works
- [ ] C3: Population search improves fitness ≥15% over incumbent on fixture query set
- [ ] A3: Per-edge decay measurably reduces retrieval noise on long-running test fixtures
- [ ] A4: Sleep pass prunes ≥10% redundant edges on a test graph with known staleness
- [ ] B4: RAPTOR summarization maintains token budgets while improving answer relevance ≥3pts
- [ ] F1: Streamable HTTP serves ≥3 concurrent clients; stdio fallback preserved
- [ ] F2: Shared daemon memory cuts cold-start time by ≥50% for second client; access scoping enforced
- [ ] All existing tests still pass (no regressions)
- [ ] `neuralmind benchmark --quality` reports tuner-evolved fitness score
- [ ] All new tests pass (≥107 new tests across 7 test files)
- [ ] DeepSeek QA completed on Wave 3 code (post-implementation)

---

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| C3 exploits fitness proxy (optimizes metric, degrades real quality) | Medium | High | CI-gated promotion (C4 in Wave 4); uses real query traces from A1 |
| Population search too slow on consumer hardware | Medium | Medium | Bounded population (10-20), bounded generations (5-10), runs offline weekly |
| Schema migration breaks existing synapses.db files | Low | High | Migration tested on backup copies; rollback semantics; version-stamped |
| Shared daemon state leaks data across clients | Low | Critical | Per-client access scoping enforced at query layer; unittested |
| RAPTOR summarization regresses on small codebases | Medium | Low | Gated behind `NEURALMIND_SUMMARIZE=1`; falls back to constants |
| Streamable HTTP spec non-compliance blocks ecosystem integrations | Medium | High | MCP spec conformance test in CI |

---

## 10. Timeline

Estimated sequence for Wave 3:
- **Shared contracts** first (spike, ~1 day)
- **C2** next (critical path, ~2 days)
- **C3** next (critical path, ~3 days) — feeds A3
- **A3** next (critical path, ~2 days) — feeds A4
- **A4** next (critical path, ~2 days)
- **B4** parallel with F1/F2 (~3 days each, all parallelizable once contracts land)
- **F1 + F2** in parallel with critical path (~3 days)

Total estimated: ~10-12 working days with optimal parallelization.

---

*Prepared by Hermes. Pending maintainer approval before build begins.*
