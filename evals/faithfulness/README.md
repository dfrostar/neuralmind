# Faithfulness eval harness

Measures whether an agent's answer to a code question gets **better** with
NeuralMind context, not just shorter — the fitness function the v0.13
"Measure" release is built around.

> **Status: E1.1 foundation only.** This directory currently ships the
> query + gold-fact set, the format/scoring spec, and a pure-Python runner
> skeleton with the offline expected-fact-recall scorer. Answer generation,
> the full judge, the report, and the onboarding-lift eval are follow-on
> tasks (see [Roadmap](#roadmap)). Tracking issue:
> [#172](https://github.com/dfrostar/neuralmind/issues/172);
> plan: `docs/NEXT-RELEASE-PLAN.md` §3 Epic E1.

## Why this exists

`docs/HONEST-ASSESSMENT.md` concedes faithfulness is unmeasured: *"Does the
agent's answer get better with NeuralMind context, or just shorter? We have
anecdotes, not measurements."* This harness turns that into a number.

## Design: offline judge is the default and the CI gate

The headline NeuralMind promise is **100% local**. A faithfulness judge
usually wants a strong LLM — which conflicts with that promise. The
resolution, baked into the design:

- **Offline heuristic judge — DEFAULT, and the CI gating signal. Zero
  network.** Scores expected-fact recall, citation/grounding rate, and a
  contradiction check using only the gold facts in `queries.json` and
  string/heuristic matching. This is the judge that gates PRs. It never
  phones home. It is the product.
- **LLM-as-judge — OPT-IN ONLY, and clearly labelled as leaving the
  machine.** Enabled solely via the `NEURALMIND_EVAL_LLM_JUDGE=1` env var
  (the API key comes from the standard provider env var). When enabled the
  runner must print a one-line notice that answers + gold facts are sent to
  a third-party API. It is **never** the default and **never** the CI gate
  — a power-user convenience for nuanced scoring, nothing more.

If neither the env var is set nor a key is present, the harness runs fully
offline. The eval must not quietly phone home; doing so would contradict
the headline claim.

## Files

| File | Purpose |
|---|---|
| `queries.json` | Versioned query + gold-fact set (≥15 queries) derived from `tests/fixtures/sample_project/`. |
| `schema.md` | The `queries.json` format contract + the three scoring dimensions. |
| `runner.py` | Pure-Python skeleton: loads the query set, defines the scoring interface, implements the offline expected-fact-recall scorer. Answerer + API judge are marked TODO. |
| `README.md` | This file. |

`runner.py` imports **standard library only** at module load — no
chromadb / graphify / heavy deps — so it loads and is unit-testable in a
minimal environment. Heavy machinery (the real answerer wired to
`neuralmind.core`) is imported lazily inside the functions that need it,
added in E1.2.

## Running it

```bash
# Offline (default) — once E1.2 lands an answerer this prints the report.
python -m evals.faithfulness.runner

# Today (E1.1): inspect the loaded query set and self-check the scorer.
python evals/faithfulness/runner.py --selfcheck
```

Unit tests (stdlib `unittest`, no pytest required):

```bash
python tests/test_eval_faithfulness.py
```

## Roadmap (issue #172)

| Task | What it adds | Status |
|---|---|---|
| **E1.1** | Query + gold-fact set, schema, runner skeleton + offline recall scorer. | **this PR** |
| E1.2 | A/B answer generation: with-NeuralMind-context vs naive baseline, via a pluggable deterministic answerer. | follow-on |
| E1.3 | Full judges: offline (recall + grounding + contradiction) as default/gate, opt-in LLM-as-judge behind the env var. | follow-on |
| E1.4 | `neuralmind eval` report — faithfulness delta (with vs without), grounding rate, per-query breakdown, `--json`. | follow-on |
| E1.5 | Onboarding-lift eval — cold agent + team baseline vs cold agent alone; gates shared-memory build (#175). | follow-on |

CI gating (Epic E3) consumes the offline judge's output once E1.4 exists,
mirroring how `ci-benchmark.yml` gates token reduction today.
