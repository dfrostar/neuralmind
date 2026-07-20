# Wave 6 — Business Requirements Document (BRD)

**Date:** 2026-07-19
**Source:** `docs/WAVE6-SESSION-KICKOFF.md`, `f31037a feat(v0.50.0): metrics CLI, /api/metrics endpoint, team memory integration test`
**Previous waves:** 1–5 (D/B1/G1, C1/A1/A2/B2/B3/G2, C2/C3/A3/A4/B4/F1/F2, C4/G3/G4/E1-E4/F3/F4, T1/T2 tuner+incremental)
**NeuralMind release:** v0.50.0 → v0.51.x

---

## 1. Business Problem

Wave 5 closed the tuner faithfulness gap and wired incremental extraction — the self-improving loop's brain now works. But three gaps remain:

1. **No observability surface.** The autopilot's signal pipeline (`signals.py`) needs a live metrics feed. Without `neuralmind metrics --summary`, there's no way to verify the index is healthy day-to-day. Drift goes unnoticed.

2. **Team memory is unit-tested but not integration-tested.** E1-E4 (contribution scoring, merge semantics, peer review, staleness) each pass in isolation. The full contributor-A-publishes / contributor-B-imports loop has never been exercised. The handoff doc warned: "integration wiring IS the feature."

3. **Server has no metrics endpoint.** `neuralmind serve` serves queries but exposes no operational telemetry. You can't run a service you can't monitor.

---

## 2. Business Objectives

| # | Objective | Success Metric |
|---|-----------|---------------|
| O1 | `neuralmind metrics --summary` surfaces health in <500ms | Latency_p95, tokens/query, retrieval_reuse_rate, success_rate, synapses_activated |
| O2 | `/api/metrics` HTTP endpoint mirrors CLI output | JSON-identical to `neuralmind metrics --json` |
| O3 | Team memory E1→E2→E3→E4 chain passes in one integration test | Contribution bundle publishes → peer review gate → quality-weighted merge → staleness accelerates decay |

---

## 3. Non-Goals

- Multi-language incremental extraction beyond Python (deferred — tree-sitter-only today)
- Autopilot engine orchestration (deferred to autopilot repo)
- Shadow-eval mode (deferred — live eval sufficient for now)
- WebUI dashboard (Telegram-first for autopilot governance)

---

## 4. Workstreams

### A. Metrics CLI

**Problem:** `MetricsCollector.summarize()` (metrics_pipeline.py:155-228) exists but no CLI reads it.

**Files:**
- `neuralmind/cli.py:2660` — add `metrics` subparser with `--days N`, `--json` flags
- `neuralmind/metrics_pipeline.py` — no changes needed
- `neuralmind/server.py` — add `/api/metrics` GET endpoint

**Acceptance:**
- `neuralmind metrics --summary` prints ASCII table in <500ms
- `curl localhost:PORT/api/metrics` returns JSON matching `--json`

### B. Team Memory Integration Test

**Problem:** E1-E4 modules compose individually but the full contributor lifecycle is untested.

**Files:**
- `tests/test_team_memory_integration.py` (NEW, 10 tests)

**Test matrix:**
1. Contributor A publishes team bundle → stored in `team_memory`
2. Contributor B imports bundle → routed through `PeerReviewGate`
3. Quality-weighted merge resolves conflict (`merge_semantics`)
4. High-quality contributor wins over low-quality
5. Staleness detection accelerates decay after threshold
6. Peer review auto-promotes above threshold
7. Peer review flags for human review below threshold
8. Empty bundle → no-op
9. Malformed bundle → graceful rejection
10. Concurrent imports → no data loss

**Acceptance:** 10/10 pass, no changes to production modules required

---

## 5. Stakeholders & Users

| Persona | Need | Pain Today |
|---------|------|------------|
| Operator (dfrostar) | Know if index is healthy without running benchmark | Manual `neuralmind benchmark` is the only signal |
| Team contributor | Trust that published bundles get fair peer review | No end-to-end test proves the chain works |
| Service consumer | HTTP health endpoint for monitoring | `neuralmind serve` serves queries only |

---

## 6. Release Criteria

- [ ] A: `neuralmind metrics --summary` prints in <500ms
- [ ] A: `curl /api/metrics` returns valid JSON
- [ ] B: 10 integration tests pass
- [ ] All existing tests still pass (regression)
- [ ] `RELEASE_NOTES_v0.50.0.md` drafted

---

Signed-off-by: Hermes (product strategy)
