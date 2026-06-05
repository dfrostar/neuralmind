# NeuralMind v0.14.0 — measure faithfulness: the `neuralmind eval` command

**Release Date:** June 2026

## TL;DR

v0.13.x built the measurement *foundation*. **v0.14.0 turns it into a
command you can run.** `neuralmind eval` produces a **faithfulness number**:
does NeuralMind's selected context contain more of the facts a correct answer
needs than a naive baseline given the *same token budget*?

```bash
neuralmind eval            # markdown report: faithfulness delta + per-query table
neuralmind eval --json     # machine-readable
neuralmind eval --selfcheck  # validate the gold set + offline scorer (no heavy deps)
```

It's the first release where you can **measure answer quality, not just token
reduction** — and, like everything in NeuralMind, the default judge is **100%
local**.

## The metric, stated honestly

Faithfulness = **expected-fact recall of the answer**, compared **at a matched
token budget**:

- The default answerer is deterministic and offline — the "answer" *is* the
  context handed to the model (retrieval-as-answer), so recall measures whether
  the *selected context* actually contains each gold fact. No LLM, no network.
- The baseline is naive truncation of the repo to the **same per-query token
  budget** as NeuralMind's context. So a positive delta means smart selection
  beats dumb truncation **at equal cost** — not the dishonest "small context vs
  the whole 50k-token repo" (which trivially wins recall at 40–70× the tokens).

`faithfulness_delta = mean(nm_recall) − mean(naive_recall)`. The report also
carries a **grounding rate** (are the right modules cited?) and a
**contradiction rate** (does the answer assert a choice that conflicts with the
gold facts, e.g. PostgreSQL when the fixture is SQLite?).

The opt-in LLM-as-judge stays behind `NEURALMIND_EVAL_LLM_JUDGE` and is
**never** the default or the CI gate — the only path that would leave the
machine, and it says so loudly when enabled.

## What the agent actually sees, post-install

A new **`neuralmind eval`** command (and the module form `python -m
evals.faithfulness.runner --run`). It is a **quality self-test against the
bundled reference fixture** — the faithfulness analogue of `neuralmind
benchmark`, which measures token reduction. It does **not** change how the
synapse layer, graph view, MCP tools, or hooks behave at runtime.

### Per-agent expectations

| Agent | What changes in v0.14.0 |
|-------|--------------------------|
| **Claude Code** | A new CLI/quality command; no change to hooks, `SYNAPSE_MEMORY.md`, or predictions at runtime. |
| **Cursor / Cline** | Same MCP tools, same retrieval; `neuralmind eval` available from the CLI. |
| **Generic MCP client** | No new MCP tool; the eval is a CLI/CI quality gate. |
| **Contributors / CI** | A runnable faithfulness gate: `--selfcheck` (no deps) and the full A/B (`--run`) when chromadb + a built index are present. |

## Honest scope & caveats

- **It self-evaluates the committed reference fixture + gold set**, which ship
  with the *source* repository. So today it's a credibility/quality gate, not
  yet a "point it at your repo" eval — that needs per-project gold sets (a
  future increment).
- **The A/B needs the retrieval stack** (chromadb) **and a built index**;
  without them `neuralmind eval` / `--run` degrade with an actionable message.
  `--selfcheck` needs neither.
- From an installed wheel (where the `evals/` package isn't bundled), run it
  from a source checkout: `python -m evals.faithfulness.runner --run`.

## Platform support — Windows is now ⚠️ experimental

v0.14.0 adds **macOS to the CI gate** (verified on every PR alongside Linux
3.10–3.12). Running the full suite on **Windows** for the first time surfaced
genuine issues — ChromaDB holds open file handles so temp-dir teardown fails
(`WinError 32`), event-log rotation relies on POSIX rename-over-open, and a
concurrent-append path loses writes. Rather than claim support we can't back,
**Windows is reclassified from "Full" to ⚠️ Experimental**: it still installs
and runs (the Task Scheduler walkthrough applies), but it's dropped from the
gating matrix and the `schema.org`/compatibility claims are narrowed to Linux +
macOS until the issues are fixed. Tracking: **#186**.

## What ships (Epic E1, tasks E1.2–E1.4)

- **`evals/faithfulness/harness.py`** — the deterministic answerer, the
  matched-budget naive baseline, the (lazily-imported) NeuralMind context
  provider, the A/B run, and the report (Markdown + `--json`).
- **`OfflineJudge`** now scores all three dimensions offline — expected-fact
  recall, grounding, and contradiction.
- **`neuralmind eval`** CLI + `python -m evals.faithfulness.runner --run`.
- 28 stdlib unit tests covering the judge and the harness (no chromadb needed).
- **Now gated in CI.** `ci-benchmark.yml` builds the reference fixture index
  and runs the A/B on every PR, failing the build if NeuralMind's selected
  context ever carries fewer gold facts than a matched-budget naive
  truncation. First measured result on the reference fixture: **fact-recall
  `1.0` vs `~0.4` naive, grounding `1.0` vs `0.0`** at an equal per-query token
  budget — smart selection keeps every gold fact and cites the right modules
  where dumb truncation keeps about half and cites none.

## What's next

- **E1.5** — onboarding-lift eval (cold agent + a committed team baseline vs a
  cold agent alone); gates the shared-memory build.
- **v0.14 roadmap** — decouple the graph backend (tree-sitter / LSP / SCIP),
  proven at parity by *this* harness; then host-API hardening and portable
  cross-agent memory.

## Upgrade

```bash
pip install --upgrade neuralmind
neuralmind eval --selfcheck   # confirms the gold set + offline scorer
```

No migration, no config changes, no runtime behavior change for existing
installs.
