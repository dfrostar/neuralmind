# Wave 3 C3 — Population Tuner Code Review
# Reviewed: neuralmind/tuner.py + neuralmind/fitness.py
# Public repo: dfrostar/neuralmind

---

## Finding 1 — Fitness proxy gameability (CONFIRMED REAL)

retrieval_quality is computed from success_signal on HISTORICAL reasoning_traces
recorded under a PREVIOUS parameter set. _fitness_from_traces never re-runs
retrieval under `params`. A candidate that clamps L0-L3 budgets to their
registered minimums (~50/200/400/500) inflates efficiency by up to ~2.2x
(budget_floor=1150 vs default=2550) while retrieval_quality stays near its
historical value. The weighted-product fitness exp(0.5·log rq + 0.3·log ef +
0.2·log sh) rises monotonically with ef, so the tuner promotes a candidate
that silently retriever-less code in production.

The product form does NOT defend against this: zero-on-any-axis dominance only
activates when a component is *exactly* 0, which rq never is nor could it be.

Patch: cap the efficiency ratio.

--- a/neuralmind/tuner.py
+++ b/neuralmind/tuner.py
@@ -237,1 +237,2 @@
     if candidate_budget <= 0:
         return 1.0
-    return default_budget / candidate_budget
+    # Cap so clamp-minimum budgets cannot push fitness unboundedly high.
+    return min(default_budget / candidate_budget, 10.0)

---

## Finding 2 — Candidate_budget ≠ 0 but near-zero efficiency overflow

In _efficiency_ratio, the `if candidate_budget <= 0` guard prevents division
by zero when budget is exactly 0, but a budget of epsilon (>0, e.g. from
lowering clamp ranges to 1) yields default_budget / epsilon → large.
compute_fitness only clamps efficiency with lo=0.0 and NO upper bound, so
math.log(ef) explodes → math.exp(log_sum) → ±inf. Subsequent
_load_incumbent_fitness() for "inf" gives inf, comparisons degrade to nan.

Patch: hard-cap efficiency in compute_fitness.

--- a/neuralmind/fitness.py
+++ b/neuralmind/fitness.py
@@ -164,1 +164,2 @@
-    ef = _clamp(inputs.efficiency, 0.0)  # no upper bound
+    # Efficiency has no documented upper bound, but clamp to defend against float overflow.
+    ef = min(inputs.efficiency, 10.0)

---

## Finding 3 — Fail-open correctness

Trace with truly empty traces:
 _load_incumbent_fitness → 0.0 (fallback). incumbent_fitness == 0.0 → enter
 re-eval branch → evaluate_candidate(incumbent) → _fitness_from_traces →
 `if not traces: return 0.0` → incumbent_fitness=0.0. _save_incumbent writes
 "0.000000" to meta table. best_fitness=0.0. Population loop: every candidate
 0.0 → `0.0 > 0.0` is False → no promotion. promote_if_better(best_params,
 0.0, 0.0) → `0.0 > 0.0 * 1.05` → False. NO spontaneous promotion. The
 strict `>` in `promote_if_better` is what makes this safe.

 The fragile path: if _load_incumbent_fitness returns 0.0 because of a
 TRANSIENT read error (not empty table), the incumbent's genuine stored
 fitness (say 0.42) is NOT recovered; it gets overwritten with 0.0 via
 _save_incumbent. Next generation, the candidate competes against 0.0 and any
 mediocre candidate trivially promotes. This is silent data loss masquerading
 as fail-open.

Patch: don't persist a 0.0 eval over a potentially valid stored fitness.

--- a/neuralmind/tuner.py
+++ b/neuralmind/tuner.py
@@ -280,3 +280,12 @@
         if incumbent_fitness == 0.0:
             incumbent_fitness = self.evaluate_candidate(incumbent)
-            self._save_incumbent(incumbent, incumbent_fitness)
+            # Only persist when eval produced a non-zero, valid score.
+            # Persisting a 0.0 wipes any previously-stored genuine fitness,
+            # causing spurious promotion on the next run (see Finding 3).
+            if incumbent_fitness > 0.0:
+                self._save_incumbent(incumbent, incumbent_fitness)
+            else:
+                stored = self._load_incumbent_fitness()
+                if stored > 0.0:
+                    incumbent_fitness = stored

---

## Finding 4 — Hysteresis oscillation

promote_if_better promotes iff `fitness > incumbent_fitness * (1 + h)`.
With h=0.05, a 5% gap is required.

Naive flip-flop is prevented: one-sided up-promotion means the incumbent
never moves DOWN. A symmetric ±5% bounce in efficiency alone cannot cause
a down-promotion; the candidate that loses doesn't promote.

However, ORDER-DEPENDENT NEAR-TIE LOTTERY is NOT prevented: candidate A
(ef=1.82) vs incumbent (ef=1.70) → ratio 1.070 → promotes. Incumbent is
now 1.82. Candidate B (ef=1.85) vs new incumbent 1.82 → ratio 1.016 → does
NOT promote. Final parameter set is stochastic, not fitness-ordered.

Minimum stable cycle requires h > 2*sigma where sigma is the inter-gen
fitness noise on near-tie candidates. With historical-only rq and sh, noise
comes entirely from population sampling ef, which has variance ~0.04 per
generation. h=0.05 is borderline; recommend >=0.10. The value is still
strictly better than 0.

---

## Finding 5 — Dead code / factual honesty

5a. CandidateConfig — DEFINED, NEVER INSTANTIATED IN PRODUCTION
     CandidateConfig( search yields zero matches in neuralmind/neuralmind/.
     It is imported in tests/test_tuner.py but never instantiated.
     PopulationTuner uses plain dict internally throughout.

5b. run_generation — DEFINED, NEVER CALLED FROM PRODUCTION
     Called only from tests/test_tuner.py:132 and :140.
     SessionStart hook (hooks.py:339) calls self_improve.tune_selector —
     the OLD single-knob v0.26 tuner, NOT PopulationTuner.
     Not called from cli.py, core.py, server.py, or any daemon path.

5c. self.generations — STORED, NEVER CONSUMED
     Assigned in __init__ (line 109) but never read. run_generation performs
     one pass over population_size once; there is no multi-generation loop.
     NEURALMIND_TUNER_GENERATIONS is a dead config knob.

Summary:
| Component         | Declared      | Consumed            | Effect |
|-------------------|---------------|---------------------|--------|
| CandidateConfig   | tuner.py:49   | nowhere in prod     | dead   |
| run_generation()  | tuner.py:270  | tests only          | dead   |
| self.generations  | tuner.py:109  | nowhere             | dead   |

The wave-3 C3 tuner is fully implemented as a module and FULLY UNWIRED
from daemon, CLI, hooks, and SessionStart.
