# Wave 7 + Autopilot Honest Gap Closure — Session Kickoff Prompt

> **START HERE.** Copy this entire document into a new Hermes session to execute Wave 7 + close the honest gaps. All context is inline.

---

## CONTEXT (where we are)

**NeuralMind** (`/home/dtfrost/neuralmind`): **v0.50.0**, CI green, Wave 6 complete (metrics CLI shipped, team memory integration test wired, 1433+ tests).

**Autopilot** (`/home/dtfrost/neuralmind-autopilot/`): **v0.2.0 on disk** (untracked — no `.git`). 13 modules built + tested, engine orchestrator loops in 0.09s. 44 tests pass. Wave 6 DeepSeek QA patches applied (signals, correlator, bandit, engine, promotion_engine, experiment_runner).

> ⚠️ **CRITICAL BLOCKER:** The autopilot repo has NO git history. All work lives only in files. Before any further work: init + commit, or port into `neuralmind/autopilot/`.

---

## HONEST v1.2 GAP ANALYSIS — WHAT'S SOTA vs PLACEHOLDER

| Component | Status | DeepSeek Verdict | What's Missing |
|-----------|--------|------------------|----------------|
| **signals.py** (Page-Hinkley) | ✅ SOTA | Clean — direction logic correct, SQL safe, 0.0 handled | None remaining |
| **correlator.py** (root cause) | ⚠️ PARTIAL | CWD fallback warning added, param_changes time filter fixed | Still defaults `neuralmind_path=Path.cwd()`. Needs explicit path from config. |
| **bandit.py** (Thompson sampling) | ⚠️ PARTIAL | record_outcome now persists (CRITICAL fixed), uncertainty-aware prior | No min-budget floor. Cold-start starvation risk. |
| **self_play.py** (adversarial) | ✅ SOTA | Deterministic hashlib.sha256 IDs | None remaining |
| **engine.py** (orchestrator) | ✅ SOTA | Phase1→Phase2 baseline→drop verified firing, simulation now stochastic | Baseline hardcoded, should be learned from history |
| **experiment_runner.py** | ❌ PLACEHOLDER | _p_value returns 0.03 or 0.5 based on ratio — NOT a statistical test | Proper t-test with historical variance from experiments table |
| **promotion_engine.py** | ❌ PLACEHOLDER | _promote() only sets `proposals.status = 'shipped'` | Actual git tag + push + candidate config shipping |
| **health_dashboard.py** | ⚠️ PARTIAL | Snapshots stored | No statistical trend analysis, raw listing only |
| **war_room.py** | ⚠️ PARTIAL | Telegram credential reading correct | cmd_pause/cmd_resume are no-ops |

**SOTA RUBRIC (post-Wave 6):**

| Layer | Planned | Actual | Gap |
|-------|---------|--------|-----|
| Signal Detection | Continuous + Page-Hinkley ✓ | Fixed PH logic | ✅ None |
| Root-Cause | Automated commit+param+repo join ✓ | Built, CWD TODO | ⚠️ Path default |
| Prioritization | Bayesian bandit ✓ | Built, no min-floor | ⚠️ Starvation |
| Testing | Self-play adversarial ✓ | Fixed hash | ✅ None |
| Promotion | Continuous A/B + auto-rollback ✓ | Built, status-only + dummy p-value | ❌ No shipping |
| Feedback | Real-time query-level ✓ | Engine wired | ⚠️ Historical variance |

---

## WORKSTREAMS (execute in order A→E)

### A. Autopilot Git Init + Baseline Commit
- **Gap:** All work on disk, untracked. Risk of loss.
- **Work:** `cd /home/dtfrost/neuralmind-autopilot && git init && git add -A && git commit -m "feat(v0.2.0): autopilot engine orchestrator + 13 modules, 44 tests"`
- **Files:**
  - `/home/dtfrost/neuralmind-autopilot/` (entire directory)
- **Acceptance:** `git log` shows commit, `git status` clean

### B. experiment_runner.py Real T-Test
- **Gap:** `_p_value()` returns 0.03 or 0.5 — NOT a statistical test. Verdicts driven by noise.
- **Work:** Implement proper t-test using historical variance from experiments table:
  - Query `SELECT baseline_value, candidate_value FROM experiments WHERE proposal_id = ?` for all prior experiments
  - Compute sample mean and sample variance of deltas
  - Use Student's t-distribution (from `statistics` module or manual CDF approximation) to compute actual p-value
  - Replace the `0.03/0.5` constants with real probability
  - Keep honest docstring: "Two-sample Welch's t-test on historical deltas. Assumes approximate normality of deltas."
- **Files:**
  - `autopilot/experiment_runner.py` (replace `_p_value` method)
  - `tests/test_phase3_6.py` (add test: `test_p_value_statistical_properties`)
- **Acceptance:** p-value varies continuously with input, not just two fixed values. Tests pass.

### C. promotion_engine.py Actual Shipping
- **Gap:** `_promote()` only sets `proposals.status = 'shipped'`. No actual code shipping.
- **Work:**
  - Accept `ship_callable: Callable | None` in `__init__` (dependency injection — engine passes a function that does the actual ship)
  - `_promote()` calls `ship_callable(exp)` if provided, else log warning "no ship_callable configured — status-only promotion"
  - Default `ship_callable` is a no-op lambda so existing tests don't break
  - Wire the engine to pass a real ship callable that: (a) updates neuralmind tuner config meta, (b) logs to Telegram if configured
- **Files:**
  - `autopilot/promotion_engine.py` (add ship_callable DI)
  - `autopilot/engine.py` (wire `PromotionEngine(db_path, ship_callable=real_ship_fn)`)
- **Acceptance:** PromotionEngine with a mock ship_callable records the call. Tests pass.

### D. bandit.py Min-Budget Floor
- **Gap:** Proportional allocation starves low-sampled arms to 0 budget. Cold-start arms get 0 trials to disprove low expectations.
- **Work:**
  - Add `MIN_FLOOR_FRACTION = 0.10` class constant (10% of total_budget guaranteed per top-n arm)
  - Modify `allocate()`: each top-n arm gets `floor = MIN_FLOOR_FRACTION * total_budget`, remaining budget distributed proportionally
  - Formula: `budget = floor + (total_budget - floor * len(top_n)) * share`
- **Files:**
  - `autopilot/bandit.py` (modify `allocate()` method)
  - `tests/test_phase2.py` (add test: `test_allocate_min_floor`)
- **Acceptance:** Every top-n arm gets ≥ 10% of total_budget. Tests pass.

### E. engine.py Learned Baseline
- **Gap:** Baseline metrics hardcoded as `{"recall@5": 0.80, "latency_p95": 150.0, "tokens_per_query": 1200.0}`. Real systems drift — baseline should be learned from historical metrics.
- **Work:**
  - Add `_learn_baseline()` method: query `SELECT AVG(value) FROM signals WHERE ts > ? GROUP BY metric_name` from past N days
  - Fall back to hardcoded defaults if no historical signals exist
  - Call once per `run_tick()` to refresh baseline
- **Files:**
  - `autopilot/engine.py` (add `_learn_baseline`, modify `run_tick`)
- **Acceptance:** Baseline reflects actual historical mean after enough data. Tests pass.

### F. DeepSeek QA Gate (parallel dispatch)
- **Policy:** Per-module review of Wave 7 code. Provider pinned to deepseek-v4-pro, inline code, explicit risk checklist.
- **Batches (parallel via delegate_task):**
  - Batch 1: experiment_runner.py (t-test), promotion_engine.py (shipping DI)
  - Batch 2: bandit.py (min-floor), engine.py (learned baseline)
- **Patch workflow:** Apply 🔴 CRITICAL + ⚠️ WARNING immediately after verification, pytest after patching.

---

## CRITICAL PITFALLS

1. **`_p_value()` is the root cause of cosmetic promotion.** The dummy p-value means `promote`/`rollback` verdicts are noise-driven. Fixing this is the single highest-leverage change — without it, the entire loop is decorative.
2. **Status ≠ shipping.** Setting `proposals.status = 'shipped'` is not shipping. The gap between "marked done" and "actually running in production" is where self-improving systems die. Wave 2/4/5 shipped 6 modules with zero integration — same trap.
3. **Starvation kills exploration.** Without min-budget floor, cold-start arms get 0 trials. Bandit becomes a self-fulfilling prophecy — high-impact arms get more trials, low-impact arms never get a chance. The whole system converges prematurely.
4. **Hardcoded baselines rot.** What happens when the codebase grows 3x and latency naturally doubles? The hardcoded `latency_p95: 150.0` fires false alarms forever. Baseline must be a rolling window.
5. **Connection leaks.** `experiment_runner.run_experiment()` has no try/finally around `conn.close()`. One failed INSERT leaks a SQLite handle. In a long-running daemon, this is a slow-motion crash.

---

## ACCEPTANCE GATES

- [ ] A: autopilot repo committed, `git log` shows baseline
- [ ] B: `_p_value()` returns continuous values (not binary 0.03/0.5), test verifies statistical behavior
- [ ] C: `PromotionEngine` accepts `ship_callable`, mock test records the call
- [ ] D: Every top-n arm gets ≥ 10% of total_budget, test verifies min-floor
- [ ] E: Baseline is learned from signals table when data exists, falls back to hardcoded defaults
- [ ] F: DeepSeek QA patches applied, all tests green
- [ ] Final: Full autopilot test suite green (pytest tests/), version bumped to v0.3.0, committed + pushed

---

## FILES TO READ IN NEW SESSION (verify current state)

1. `/home/dtfrost/neuralmind-autopilot/autopilot/experiment_runner.py` — verify _p_value placeholder
2. `/home/dtfrost/neuralmind-autopilot/autopilot/promotion_engine.py` — verify shipping is status-only
3. `/home/dtfrost/neuralmind-autopilot/autopilot/bandit.py` — verify no min-floor in allocate()
4. `/home/dtfrost/neuralmind-autopilot/autopilot/engine.py` — verify hardcoded baseline
5. `/home/dtfrost/neuralmind-autopilot/autopilot/correlator.py` — verify CWD default still present
6. `/home/dtfrost/neuralmind-autopilot/autopilot/signals.py` — verify PH logic
7. `/home/dtfrost/neuralmind-autopilot/tests/test_phase2.py` — bandit + correlator tests
8. `/home/dtfrost/neuralmind-autopilot/tests/test_phase3_6.py` — experiment_runner + promotion tests

---

## FIRST ACTION

1. Read the 8 files above to verify current state.
2. Ask user: "Proceed with Wave 7 A→F as documented?"
3. Start with Workstream A (git init + commit) — protect the work.

---

*Handed off by Hermes. Wave 7 kickoff. 2026-07-18.*
