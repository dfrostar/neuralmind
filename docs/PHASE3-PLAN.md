# NeuralMind v2.1 — Phase 3 Plan: Tighten the Moat

**Date:** 2026-07-17
**Prerequisite:** v2.0 complete (4 waves, 1374 tests, all public-facing pages updated)

## Why Phase 3?

v2.0 closed the gap to 2026 state-of-practice. The moat — the learning loop — has known sharp edges. DeepSeek QA on Wave 4 surfaced two recurring failure patterns:

1. **Assumptions that held in isolation broke at wiring time** (auto-promote threshold was correct in code but unreachable against real output; fast-decay compounded daily because it wasn't time-proportional).
2. **Components built independently aren't integrated end-to-end** (tuner fitness is single-variable but claims multi-objective; incremental extraction is built but not wired into the build loop; metrics are produced but not surfaced).

Phase 3 targets integration debt, not just feature additions.

---

## Candidate workstreams (ranked by leverage)

### 🔴 HIGH — Close the tuner faithfulness gap

**Problem:** `PopulationTuner._fitness_from_traces()` derives retrieval_quality and session_health from *historical* traces that are fixed across candidates. Only efficiency (L0-L3 token budget) actually varies. Documented as a limitation in TRD §4.2.

This is the single biggest credibility risk. The tuner claims to be "the moat" but is effectively a single-variable budget optimizer.

**Fix candidates:**
1. **A/B candidate eval against live retrieval.** For each candidate, temporarily configure the embedder, run N fixture queries, measure real retrieval_quality (nDCG@5) and session_health (re-query-rate over the N queries). Expensive but faithful.
2. **Shadow-eval mode.** Run candidates in shadow: apply each candidate to a temporary query set without promoting, measure real outcomes. Promote after M successful shadow rounds.
3. **Extend efficient proxy.** Instead of historical traces, measure retrieval_quality proxy as a direct function of candidate params (e.g., higher L2 recall K → higher discrimination; synapse boost weight → higher recall). Build a learned proxy from historical runs.

**Deliverable:** `PopulationTuner.evaluate_candidate` varies at least two fitness axes. Integration test: tuner should differ from random search on the Python fixture within 5 generations.

### 🔴 HIGH — Wire incremental extraction into the build pipeline

**Problem:** G4's `IncrementalExtractor` is built but not wired into `graphgen.py`'s build loop. Every `neuralmind build` still re-extracts all symbols for all files.

**Fix:** Detect unchanged files (mtime + SHA-256), skip re-extraction, invalidate importers via reverse-edge traversal from structural_edges.

**Deliverable:** `neuralmind build` on a 10K-line repo with 1 file changed completes in <10% of full-rebuild time. Test: touch one file, verify only that file's symbols + its importers are updated.

### 🟠 MEDIUM — Wire metrics to a dashboard command

**Problem:** F3's `MetricsCollector` produces JSONL files, but no human-readable surface exists. `neuralmind metrics --summary` doesn't exist.

**Fix:** New CLI command reads from JSONL, prints ASCII table of latency/p95/token-savings, optional `--json` for export. Wire into `neuralmind serve` dashboard.

**Deliverable:** `neuralmind metrics --summary` prints project health in <500ms.

### 🟠 MEDIUM — Team memory production round-trip test

**Problem:** E1-E4 logic is unit-tested in isolation, but the full lifecycle (publish → bundle → import → score → gate → merge → decay) has never been exercised as a pipeline with simulated concurrent contributors.

**Fix:** Integration test that spins up two "contributors" (two synapse stores), publishes bundles, imports each other's, routes through PeerReviewGate, verifies quality-weighted merge wins, verifies staleness accelerates decay after threshold.

**Deliverable:** One test file (`test_team_memory_integration.py`) exercises the full E1→E2→E3→E4 chain end-to-end.

### 🟡 LOW — Concurrency load test for F4 backpressure

**Problem:** F4's `ProjectBackpressure` and `CircuitBreaker` are tested in isolation but not under concurrent daemon + CLI + MCP patterns.

**Fix:** Stress test: N threads hammer `ProjectBackpressure.acquire(timeout=0.1)` simultaneously, verify queue depth never exceeds max_concurrent, verify circuit opens on sustained failures, verify recovery after timeout.

**Deliverable:** `test_backpressure_stress.py` runs 1000 concurrent acquires in <5s without exceeding bound.

### 🟡 LOW — ColBERT multi-vector (deferred from v2.0)

**Problem:** Learned sparse approximates late-interaction. Need to quantify "80%" claim.

**Fix:** Build a ColBERT mini-BERT evaluation on the Python fixture, compare nDCG@5 against learned sparse. Document storage/performance tradeoff.

**Deliverable:** One benchmark comparison in `bench/public/`, honest storage/latency/quality table.

---

## Recommended sequence

```
Wave 5: Tuner faithfulness gap  ← HIGHEST LEVERAGE, moat-defining
         Wiring incremental extraction into build pipeline
Wave 6: Metrics dashboard
         Team memory integration test
Wave 7: Concurrency load test
         ColBERT quantification
```

## Cross-cutting lessons encoded

**From Wave 4:**
- Unit tests that pass but don't exercise real output are insufficient. Add "outcome assertions" (e.g., auto-promote must be reachable, not just a code path that compiles).
- DeepSeek per-module review caught 7+ real bugs. Continue dispatching one subagent per new module in Phase 3.
- Document simplified modules as simplified (Phase 2 Louvain).

**From Wave 3:**
- Parallel delegation for independent modules; direct build for tightly integrated ones.
- Handoff doc for session continuity.

## First concrete action (if approved)

1. Read `tuner.py:166-236` (`_fitness_from_traces` + `evaluate_candidate`) and trace fixtures to build a real multi-objective eval harness.
2. Read `graphgen.py:580-664` (`build_graph`) to find the integration point for `IncrementalExtractor.scan_files()`.
3. Dispatch two parallel DeepSeek reviews: one on the tuner fix, one on the incremental extraction wiring.
4. Write the Wave 5 BRD/TRD.

---

*Plan by Hermes. Approved by dfrostar to proceed.*
