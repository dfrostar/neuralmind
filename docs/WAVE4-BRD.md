# Wave 4 — Business Requirements Document (BRD)

**Date:** 2026-07-17
**Source:** `docs/FUTURE-PROOFING-PLAN.md` §9 sequence
**Previous waves:** 1 (D/B1/G1), 2 (C1/A1/A2/B2/B3/G2), 3 (C2/C3/A3/A4/B4/F1/F2)

---

## 1. Business Problem

Wave 3 completed the self-improvement engine (C2+C3), memory deepening (A3+A4), hierarchical summarization (B4), and daemon hardening (F1+F2). The tuner exists, but promotion is manual. Team memory exists, but merge is last-write-wins. Graph communities are file-based, not architecture-based. Re-extraction is full-tree.

v2.0 is **working but loosely coupled**. Wave 4 tightens every coupling point:

- Tuner proposes → promotes automatically with CI hysteresis (C4)
- Structural edges drive real graph modularity (G3)
- Re-extraction is incremental (G4)
- Team contributions are quality-scored, merged, peer-reviewed, and staled (E1–E4)
- Telemetry is continuous (F3)
- Concurrency degrades gracefully (F4)

## 2. Business Objectives

| # | Objective | Success Metric |
|---|-----------|---------------|
| O1 | Tuner promotion is CI-gated | Candidate must beat incumbent by ≥5% hysteresis on fixture set |
| O2 | Communities reflect architecture | Louvain modularity over structural edges, not per-file |
| O3 | Large-repo builds are incremental | Only changed files + importers re-extracted |
| O4 | Team-memory quality signal exists | Edge quality scores predict retrieval usefulness |
| O5 | Conflicting edges merge rationally | Quality-weighted merge beats last-write-wins |
| O6 | Stale team edges decay faster | 30-day threshold = ~1/32 weight (5× fast decay) |
| O7 | Query latency is measurable | JSONL metrics with bounded retention |
| O8 | Concurrent access degrades gracefully | Bounded queue depth + circuit breaker fail-fast |
| O9 | Offline judge has real transcripts | bench/public/judge/ populated |

## 3. Non-Goals

- Hosted SaaS / cloud-dependent tuning
- Full ColBERT multi-vector retrieval
- LLM-judged judge as default
- Inline completion or general agent UX
- Cross-repository / org-wide search

## 4. Workstreams

### C4 — CI-gated tuner promotion
- Wraps `PopulationTuner` (C3) with fixture-evaluated promotion gate
- `neuralmind benchmark --tuner-ci` CLI command
- Hysteresis: candidate must beat incumbent by configurable margin (default 5%)
- Fail-open: if eval fails, incumbent stands

### G3 — Modularity clustering
- Louvain method over structural edges (calls/imports/inherits)
- Replaces balanced-per-file communities with architectural boundaries
- Phase 1 (greedy) + Phase 2 (simplified aggregation)
- Stdlib-only, deterministic output

### G4 — Incremental re-extraction
- Content-hash cache under `.neuralmind/extraction_cache.json`
- Detects added/modified/deleted files via mtime + SHA-256
- Resolves reverse edges (importers/callers) for transitive invalidation

### E1 — Contribution-quality scoring
- Three-axis scoring: reinforcement frequency (0.4), recency (0.35), conflict penalty (−0.25)
- Edges above 0.70 promote; below 0.30 decay-fast
- History-independent (scorable at any edge)

### E2 — Merge semantics
- Quality-weighted conflict resolution (replaces last-write-wins)
- Tiebreaker: higher activation count
- Fail-open: unresolved edges stay separate

### E3 — Peer review gate
- Three outcomes: auto-promote (≥0.75), review-required (0.15–0.75), reject (<0.15)
- Actionable reviewer hints (which axis dragged the score down)
- Fail-open: malformed edges skip

### E4 — Staleness detection
- Team-shared edges: 30-day stale threshold
- Team-branch edges: 14-day stale threshold
- Fast decay: weight × 2⁻⁵ (≈ 1/32)

### F3 — Tool-use metrics pipeline
- JSONL files under `.neuralmind/metrics/` (one per UTC day)
- Per-query: latency, retrieval reuse rate, tool success, tokens, synapse activations
- 30-day retention, 10 MB cap, truncate-to-half on overflow

### F4 — Backpressure + circuit breakers
- `CircuitBreaker`: closed → open → half-open state machine
- `ProjectBackpressure`: bounded concurrent operations per project
- `ProjectLock`: threading.Lock + backpressure slot acquisition

### D3 — Judge transcripts
- Populated `bench/public/judge/` with fixture query→answer→expected triples
- Manifest-driven loading

### D4 — Per-language fixtures
- Registered C#, Ruby, PHP suites in `evals/quality/runner.py`
- 10-language coverage, 128 golden queries total

## 5. Stakeholders & Users

| Persona | Need | Pain Today |
|---------|------|------------|
| Individual developer | Local-first memory that learns | Tuner results are approximate, not promoted |
| Team lead | Quality-gated shared memory | Last-write-wins creates noise |
| Engineer scaling the system | Graceful degradation under load | Concurrent ops degrade ungracefully |

## 6. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Louvain labeling non-deterministic | Low | Medium | Contiguous-integer relabeling at end |
| Fast-decay over-aggressive | Low | Medium | Multiplier is reversible over multiple sleep passes |
| Metrics directory disk growth | Low | Low | Bounded retention + rotation |
| Backpressure deadlock | Very Low | High | Non-blocking acquire with timeout |

## 7. Release Criteria

- [x] C4: CI-gated promotion wired
- [x] G3: Louvain modularity unit-tested (triangle, line, singleton)
- [x] G4: Incremental extraction cache correctly skips unchanged files
- [x] E1–E4: Coherent chain (score → merge → gate → staleness)
- [x] F3: Metrics JSONL rotation + summarization
- [x] F4: Circuit breaker state machine + backpressure bounds
- [x] D3: Judge transcripts written
- [x] D4: 10-language golden-suite coverage
- [x] All tests pass (1374/1374)

---

Signed-off-by: Hermes, from the v2.0 plan (BRD)
