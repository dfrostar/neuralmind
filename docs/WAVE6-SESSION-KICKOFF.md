# Wave 6 + Autopilot Engine — Session Kickoff Prompt

> **START HERE.** Copy this entire document into a new Hermes session to execute Wave 6 + autopilot orchestration. All context is inline — no need to re-read old sessions.

---

## CONTEXT (where we are)

**NeuralMind** (`/home/dtfrost/neuralmind`): v0.49.4, CI green, Wave 5 complete (tuner faithfulness gap closed, incremental extraction wired). 1374 tests.

**Autopilot** (`/home/dtfrost/neuralmind-autopilot/`): 12 modules built + tested. No orchestration — the loop signals→correlator→bandit→experiment→promotion is unplugged. 3 test files, 44 tests.

**Skills loaded this session:**
- `neuralmind` (devops/neuralmind) — operations, FUTURE-PROOFING-PLAN.md, Phase 3 plan
- `neuralmind-product-ops` (meta/neuralmind-product-ops) — self-improving loop architecture, product-ops-architecture.md
- `self-improving-product-ops` (meta/self-improving-product-ops) — SOTA rubric, honesty gate
- `neuralmind-release` (neuralmind-release) — version bump + tag ritual
- `deepseek-qa` (deepseek-qa) — per-module QA dispatch, risk database
- `autonomous-agent-decision-boundaries` (autonomous-agent) — reliability patterns

---

## CLARIFYING DECISIONS (already made)

1. **Cut release at end:** Yes. v0.49.4 → v0.50.0 for NeuralMind, autopilot v0.2.0.
2. **Autopilot metrics source:** `neuralmind benchmark --json` (full eval), NOT stale JSONL. Each tick runs a fresh benchmark to populate metrics.

---

## WORKSTREAMS (execute in order A→E)

### A. NeuralMind: Metrics Dashboard CLI
- **Gap:** `MetricsCollector.summarize()` exists (metrics_pipeline.py:155-228) but no CLI command reads it.
- **Work:** Wire `neuralmind metrics --summary` to `MetricsCollector.summarize()`.
  - ASCII table output: latency_p95, tokens/query, retrieval_reuse_rate, success_rate, synapses_activated
  - `--days N` window (default 7)
  - `--json` flag for machine-readable export
  - Wire into `neuralmind serve` dashboard endpoint
- **Files:**
  - `neuralmind/cli.py` (~line 2484 — add `metrics_p = subparsers.add_parser("metrics")`)
  - `neuralmind/metrics_pipeline.py` (already has summarize(), no changes needed)
  - `neuralmind/server.py` (add `/api/metrics` GET endpoint)
- **Acceptance:** `neuralmind metrics --summary` prints project health table in <500ms

### B. NeuralMind: Team Memory Integration Test
- **Gap:** E1-E4 modules all built + unit-tested. No end-to-end test exercises the full lifecycle.
- **Work:** `tests/test_team_memory_integration.py`
  - Spin up two SynapseStores (simulated contributors)
  - Contributor A publishes team bundle
  - Contributor B imports it → routes through PeerReviewGate
  - Verify quality-weighted merge wins (contribution_scoring.py)
  - Verify merge semantics handle conflict (merge_semantics.py)
  - Verify staleness accelerates decay after threshold (team_staleness.py:181-193 `run_staleness_pass`)
- **Files:**
  - `tests/test_team_memory_integration.py` (NEW)
  - No changes to neuralmind/*.py — pure integration test of existing modules
- **Acceptance:** E1→E2→E3→E4 chain passes in one test file

### C. Autopilot: Engine Orchestrator + Bug Fixes
- **Gap:** `signals.py::process_metrics()` takes a dict but nothing feeds it. metrics_reader reads JSONL but is dead. The loop is unplugged.
- **Work:**
  1. New `engine.py`: engine loop that:
     - Runs `neuralmind benchmark --json` via NeuralMindClient → gets recall@5, latency_p95, etc.
     - Feeds to `SignalDetector.process_metrics()`
     - On signal fire, dispatches `RootCauseCorrelator.correlate()`
     - On insight, dispatches `BanditAllocator.create_proposal()` → `allocate()`
     - On proposal approval, dispatches `ExperimentRunner.run_experiment()`
     - On experiment complete, dispatches `PromotionEngine.evaluate()`
  2. Fix signals.py down-direction PH logic:
     - Current: `max_sum_dev - sum_dev` then resets `max_sum_dev` inside update()
     - Fix: proper Page-Hinkley — track cumulative sum of deviations from running mean, alarm when cumulative deviation exceeds lambda * n (number of observations)
  3. Fix self_play.py non-deterministic IDs:
     - Replace `hash(q["query"])[:16]` with `hashlib.sha255(q["query"].encode()).hexdigest()[:16]`
  4. Honest docstring on `ExperimentRunner._p_value()`: "Heuristic placeholder. Replace with proper t-test using historical variance before production use."
- **Files:**
  - `autopilot/engine.py` (NEW)
  - `autopilot/signals.py` (fix down-direction logic)
  - `autopilot/self_play.py` (deterministic IDs)
  - `autopilot/experiment_runner.py` (docstring only)
- **Acceptance:** Synthetic recall drop → signal → insight → proposal → experiment → promote/rollback, full loop in <30s

### D. neuralmind-product-ops Skill v1.1
- **Gap:** v1.0 describes planned architecture. Reality: 8 modules built, but engine orchestration missing, p-value is dummy, metrics feed unplugged.
- **Work:** Update skill to honestly reflect what's SOTA-compliant vs placeholder.
  - SOTA: signal layer (continuous + Page-Hinkley ✓, but down-direction bug), correlator (commit+param+repo join ✓), bandit (Thompson sampling ✓), self-play (adversarial generation ✓), promotion (auto promote/rollback ✓)
  - Placeholder: p-value (heuristic ✗), engine orchestration (partial ✗), metrics feed (partial ✗)
  - Document what needs upgrading to cross the honesty gate
- **Files:**
  - `~/.hermes/skills/meta/neuralmind-product-ops/SKILL.md` (patch to v1.1)
- **Acceptance:** SOTA rubric table updated with honest self-assessment

### E. DeepSeek QA Gate (parallel dispatch)
- **Policy:** Per-module review of engine.py + Wave 6 code. Provider pinned to deepseek-v4-pro, inline code, explicit risk checklist.
- **Batches (parallel via delegate_task):**
  - Batch 1 (HIGH risk — 1 module each): signals.py, correlator.py, bandit.py
  - Batch 2: engine.py, experiment_runner.py, promotion_engine.py
  - Batch 3 (LOW risk): metrics CLI, team memory integration test
- **Patch workflow:** Apply 🔴 CRITICAL + ⚠️ WARNING immediately after verification, pytest after patching, report what was patched + tests pass.

---

## CRITICAL PITFALLS (from prior waves)

1. **Integration wiring IS the feature.** Standalone modules that don't compose are incomplete. Wave 2 shipped 6 modules with zero integration points — CRITICAL finding.
2. **DeepSeek QA against stale code is wasted.** Only dispatch after code is written. The validated dispatch template: per-module, pinned provider/model, inline critical code sections, explicit risk checklist, leaf role, patch diffs.
3. **Version triple-alignment.** pyproject.toml + __init__.py __version__ + .release-please-manifest.json must all match the tag. neuralmind --version must confirm.
4. **Tag → DeepSeek review → patch → retag is the ritual.** Tag v0.50.0 at wave ship. Run DeepSeek QA. Patch CRITICAL + WARNING. If patches landed, retag v0.50.1.
5. **Public-repo standard.** Brutal honesty, no overclaims, no praise. Document what's placeholder vs production-grade.

---

## ACCEPTANCE GATES (before moving to next workstream)

- [ ] A: `neuralmind metrics --summary` prints table in <500ms
- [ ] B: `pytest tests/test_team_memory_integration.py` passes
- [ ] C: Full autopilot loop (synthetic drop → promote/rollback) in <30s
- [ ] D: Skill v1.1 documented with honest SOTA rubric
- [ ] E: DeepSeek QA patches applied, all tests green
- [ ] Final: Full test suite green (pytest tests/), version triple-aligned, tagged v0.50.0

---

## FILES TO READ IN NEW SESSION (to verify current state before editing)

1. `/home/dtfrost/neuralmind/neuralmind/metrics_pipeline.py` — verify summarize() exists
2. `/home/dtfrost/neuralmind/neuralmind/team_memory.py` — verify E1-E4 interfaces
3. `/home/dtfrost/neuralmind/neuralmind/contribution_scoring.py` — verify scoring interface
4. `/home/dtfrost/neuralmind/neuralmind/peer_review.py` — verify gate interface
5. `/home/dtfrost/neuralmind/neuralmind/merge_semantics.py` — verify merge interface
6. `/home/dtfrost/neuralmind-autopilot/autopilot/signals.py` — fix down-direction bug
7. `/home/dtfrost/neuralmind-autopilot/autopilot/self_play.py` — fix non-deterministic IDs
8. `/home/dtfrost/neuralmind-autopilot/autopilot/experiment_runner.py` — update p-value docstring
9. `/home/dtfrost/neuralmind/neuralmind/cli.py` — add metrics subparser (around line 2484)
10. `/home/dtfrost/neuralmind/neuralmind/server.py` — add /api/metrics endpoint

---

## FIRST ACTION

1. Read the 10 files above to verify current state hasn't drifted from this doc.
2. Confirm with user: "Proceed with Wave 6 A→E as documented?"
3. Start with Workstream A (metrics CLI) — lowest risk, highest visibility.

---

*Handoff by Hermes. Wave 6 kickoff. 2026-07-18.*
