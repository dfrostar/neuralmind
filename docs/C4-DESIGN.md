# C4 Design — CI-Gated Tuner Promotion via QualityHarness

**Date:** 2026-07-21
**Status:** Proposed — awaiting approval
**Author:** Hermes

---

## 1. Problem

The tuner (`PopulationTuner`) evaluates its own candidates and promotes autonomously if `fitness > incumbent * 1.05`. This is a self-measurement with no independent validation.

Per FUTURE-PROOFING-PLAN §4 C4: *"Tuned configs are validated against the eval harness (D) before promotion. Rollback on regression. The daemon proposes; the harness disposes."*

D1 (`ragas.py`, 353 lines) and D2 (`quality.py`, 338 lines) are built. Nothing connects them as an independent gate.

---

## 2. Architecture

```
PopulationTuner.run_generation()
        │
        ▼
sample_candidate() ──► candidate_params
        │
        ▼
tuner.evaluate_candidate() ──► tuner_fitness (self-measurement)
        │
        ▼
QualityHarness.evaluate(candidate_params) ──► HarnessVerdict (independent gate)
        │
        ▼
┌─────────────────────────────────────────────┐
│  GATE:                                       │
│  verdict.passed AND fitness > incumbent*(1+h) │  → PROMOTE + save incumbent
│  fitness < incumbent                         │  → ROLLBACK to previous incumbent
│  otherwise                                   │  → HOLD
└─────────────────────────────────────────────┘
        │
        ▼
record_promotion_event() ──► operator visibility
```

---

## 3. New Module: `neuralmind/quality_harness.py`

```python
@dataclass
class HarnessVerdict:
    """Result of independent quality validation."""
    fitness: float              # scalar for comparison with incumbent
    ragas_score: float          # mean faithfulness across queries
    retrieval_score: float      # mean of MRR + nDCG + hit_rate
    passed: bool                # all QualityThresholds met
    failures: list[str]         # human-readable threshold failures
    per_query: list[dict]       # per-query breakdown for debugging

@dataclass
class PromotionDecision:
    verdict: str                # "promote" | "rollback" | "hold"
    reason: str                 # human-readable rationale
    candidate_fitness: float
    incumbent_fitness: float
    harness_verdict: HarnessVerdict | None

class QualityHarness:
    """Independent quality validation gate for tuner candidates (C4).
    
    Standalone, stdlib-only at module level. Deps (ragas, quality, 
    embedder) imported lazily.
    """
    
    def __init__(
        self,
        project_path: Path,
        thresholds: QualityThresholds | None = None,
        embed_fn: Callable | None = None,
        incumbent_params: dict | None = None,
    ):
        ...
    
    def evaluate(self, candidate_params: dict) -> HarnessVerdict:
        """Run independent validation of a candidate config.
        
        Steps:
        1. Load fixtures via load_fixture_queries()
        2. Load judge transcripts via load_judge_transcripts()
        3. For each fixture: run embedder.search() with candidate params
        4. Score retrieval with quality.py (MRR, nDCG, hit-rate)
        5. Score answers with ragas.py (faithfulness)
        6. Aggregate + compare against QualityThresholds
        7. Return HarnessVerdict
        """
        ...
    
    def decide(
        self,
        candidate_fitness: float,
        incumbent_fitness: float,
        harness_verdict: HarnessVerdict,
        hysteresis: float = 0.05,
    ) -> PromotionDecision:
        """Decide promote/rollback/hold based on gate logic."""
        ...
```

---

## 4. Tuner Wiring (`tuner.py`)

**Changes to `PopulationTuner.__init__`:**

```python
def __init__(self, ..., harness: QualityHarness | None = None):
    ...
    self.harness = harness  # injected, optional for backward compat
```

**Changes to `run_generation()`:**

```python
# After evaluating candidate fitness:
if self.harness is not None:
    harness_verdict = self.harness.evaluate(gen_best_params)
    effective_fitness = harness_verdict.fitness
else:
    harness_verdict = None
    effective_fitness = gen_best_fitness

# Gate decision
decision = self.promote_if_better(gen_best_params, effective_fitness, incumbent_fitness)
if decision and (harness_verdict is None or harness_verdict.passed):
    self._save_incumbent(gen_best_params, effective_fitness)
    promoted = True
elif harness_verdict and effective_fitness < incumbent_fitness:
    # Rollback: keep incumbent, log rollback
    log.warning("Candidate rolled back: %s", harness_verdict.failures)
else:
    # Hold: no promotion, no rollback
    pass
```

**New method on `PopulationTuner`:**

```python
def promote_with_harness(
    self,
    candidate_params: dict,
    candidate_fitness: float,
    incumbent_fitness: float,
) -> PromotionDecision:
    """Validate candidate with harness before promoting.
    
    Returns PromotionDecision with verdict + rationale.
    Thread-safe: assumes caller holds no locks (this method
    does not touch shared state beyond the tuner's own persistence).
    """
    if self.harness is None:
        # Fallback to hysteresis-only promotion
        if self.promote_if_better(candidate_params, candidate_fitness, incumbent_fitness):
            self._save_incumbent(candidate_params, candidate_fitness)
            return PromotionDecision("promote", "harness disabled, hysteresis only", ...)
        return PromotionDecision("hold", "below hysteresis", ...)
    
    verdict = self.harness.evaluate(candidate_params)
    decision = self.harness.decide(candidate_fitness, incumbent_fitness, verdict, self.hysteresis)
    
    if decision.verdict == "promote":
        self._save_incumbent(candidate_params, verdict.fitness)
    elif decision.verdict == "rollback":
        pass  # incumbent stands
    # hold: nothing
    
    return decision
```

---

## 5. Operator Visibility

Every promotion/rollback event gets a structured log line + synapse meta record:

```python
# In tuner.py _save_incumbent, after successful promotion:
store.set_meta("self_improve:last_decision", json.dumps({
    "verdict": decision.verdict,
    "reason": decision.reason,
    "candidate_fitness": decision.candidate_fitness,
    "incumbent_fitness": decision.incumbent_fitness,
    "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
}))
```

A future `neuralmind self-improve history` CLI command can dump this log.

---

## 6. Backward Compatibility

- `harness=None` (default): tuner behaves exactly as today (hysteresis-only promotion). No regression.
- `harness=QualityHarness(...)`: enables independent gating.
- All new params are `Optional[..., None]` default.
- No new required env vars.

---

## 7. Test Plan

| Test | File | Covers |
|------|------|--------|
| test_harness_passes_good_candidate | test_quality_harness.py | Harness promotes when thresholds met |
| test_harness_fails_bad_candidate | test_quality_harness.py | Harness blocks when thresholds fail |
| test_harness_rollback_on_regression | test_quality_harness.py | Rollback when fitness < incumbent |
| test_tuner_promotes_with_harness | test_tuner.py | Tuner uses harness gate |
| test_tuner_falls_back_without_harness | test_tuner.py | Backward compat: no harness = hysteresis only |
| test_promotion_decision_logging | test_tuner.py | Decision recorded in meta table |
| test_harness_with_no_fixtures | test_quality_harness.py | Fail-open: no fixtures = no crash |

---

## 8. Files Changed

| File | Change |
|------|--------|
| `neuralmind/quality_harness.py` | NEW — QualityHarness + HarnessVerdict + PromotionDecision |
| `neuralmind/tuner.py` | EXTEND — harness injection, gate logic, decision logging |
| `tests/test_quality_harness.py` | NEW — 7 tests |
| `tests/test_tuner.py` | EXTEND — 3 new tests |

---

## 9. Acceptance

- [ ] QualityHarness evaluates candidate independently of tuner's self-measurement
- [ ] Promotion requires BOTH harness pass AND hysteresis beat
- [ ] Rollback on fitness regression (harness verdict < incumbent)
- [ ] Decision logged in synapse meta table for operator visibility
- [ ] Backward compatible: harness=None preserves current behavior
- [ ] All existing tuner tests pass (no regression)
- [ ] All new tests pass
- [ ] ruff clean

---

*Design v1.0. Awaiting approval to implement.*
