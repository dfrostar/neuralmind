# Faithfulness eval harness

Measures whether an agent's answer to a code question gets **better** with
NeuralMind context, not just shorter — the fitness function the v0.13
"Measure" release is built around.

> **Status: E1.2–E1.4 implemented.** This directory ships the query +
> gold-fact set, the three-dimension offline judge (expected-fact recall,
> grounding, contradiction), and the A/B harness + report that turns it into
> a number: NeuralMind's selected context vs a matched-budget naive baseline.
> The onboarding-lift eval (E1.5) is the remaining follow-on. Tracking issue:
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

## The number: faithfulness delta at a matched token budget

The headline metric is **expected-fact recall of the answer**, compared
**at the same token budget**:

- The default answerer is deterministic and offline — the "answer" *is* the
  context handed to the model (retrieval-as-answer), so recall measures
  whether the *selected context* actually contains each gold fact.
- The baseline is naive truncation of the repo to the **same per-query token
  budget** as NeuralMind's context. So a positive delta means smart selection
  beats dumb truncation **at equal cost** — not the dishonest "small context
  vs the whole 50k-token repo" comparison (the whole repo trivially contains
  every fact at ~1.0 recall while costing 40–70× the tokens).

`faithfulness_delta = mean(nm_recall) − mean(naive_recall)`. The report also
carries grounding rate (are the right modules cited?) and contradiction rate
(does the answer assert a choice that conflicts with the gold facts?).

## Files

| File | Purpose |
|---|---|
| `queries.json` | Versioned query + gold-fact set (≥15 queries) derived from `tests/fixtures/sample_project/`. |
| `schema.md` | The `queries.json` format contract + the three scoring dimensions. |
| `runner.py` | Stdlib-only: loads the query set and implements the three-dimension offline judge (recall + grounding + contradiction). Also the `--selfcheck` / `--run` CLI. |
| `harness.py` | The A/B harness: the deterministic answerer, the matched-budget naive baseline, the NeuralMind context provider (lazy-imported), and the report (`--json` / Markdown). |
| `README.md` | This file. |

`runner.py` imports **standard library only** at module load — no
chromadb / graphify / heavy deps — so it loads and is unit-testable in a
minimal environment. `harness.py` lazy-imports `tiktoken` and
`neuralmind.core` only inside the functions that need them, so the offline
judge and its tests still run without the retrieval stack.

## Running it

```bash
# Dependency-free: validate the gold set + offline scorer (the CI gate).
python -m evals.faithfulness.runner --selfcheck

# The real A/B + report (needs the retrieval stack + a built index):
graphify update tests/fixtures/sample_project
neuralmind build tests/fixtures/sample_project --force
python -m evals.faithfulness.runner --run          # Markdown report
python -m evals.faithfulness.runner --run --json   # machine-readable

# Same thing through the CLI (from a source checkout):
neuralmind eval            # report
neuralmind eval --json     # JSON
neuralmind eval --selfcheck
```

When the retrieval deps or a built graph are missing, `--run` / `neuralmind
eval` degrade with an actionable message and point you at `--selfcheck`,
which never needs them.

Unit tests (stdlib `unittest`, no pytest required):

```bash
python tests/test_eval_faithfulness.py
```

## Roadmap (issue #172)

| Task | What it adds | Status |
|---|---|---|
| **E1.1** | Query + gold-fact set, schema, runner skeleton + offline recall scorer. | ✅ done |
| **E1.2** | A/B answer generation: with-NeuralMind-context vs matched-budget naive baseline, via a deterministic answerer. | ✅ done |
| **E1.3** | Full offline judge: recall + grounding + contradiction (default/gate); opt-in LLM-as-judge behind the env var. | ✅ done |
| **E1.4** | `neuralmind eval` report — faithfulness delta, grounding rate, per-query breakdown, `--json`. | ✅ done |
| E1.5 | Onboarding-lift eval — cold agent + team baseline vs cold agent alone; gates shared-memory build (#175). | follow-on |

CI gating (Epic E3) consumes the offline judge's output once E1.4 exists,
mirroring how `ci-benchmark.yml` gates token reduction today.
