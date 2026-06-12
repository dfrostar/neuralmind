# NeuralMind v0.25.0 — one learning system: the synapse layer

**The headline:** NeuralMind now has a **single** learning signal. The old
`learned_patterns` cooccurrence reranker is **removed**, and `neuralmind learn`
becomes an exit-0 deprecation no-op. The Hebbian **synapse layer** — which
already learns continuously from your queries, edits, and tool calls, and lets
unused edges decay — is now the only thing that adapts retrieval to how you
actually use the codebase. One system instead of two means automatic learning
instead of a manual step, and decay instead of staleness.

This is a removal, not a regression. A 2×2 A/B on the benchmark fixture showed
the reranker added **0.0 points** to top-k hit rate whether synapses were on or
off, while the synapse layer alone adds **+11.6 points**. The reranker was also
runtime-inert on the warm path — the synapse boost re-sort discarded its
ordering anyway — required the manual `neuralmind learn` step to populate, and
went stale between runs. Keeping it added surface area and a manual step for no
measured benefit.

## What the agent actually sees post-install

Nothing changes on the warm path. Recall is synapse-driven exactly as it was in
v0.24.0, so an agent querying through the CLI or MCP gets the same results.

The only visible differences are narrow:

- The L3 search output **no longer prints `(+X.XX boost)` labels** that came
  from the reranker. Synapse-recall labels are unchanged and still appear.
- `.neuralmind/learned_patterns.json` is **no longer read or written**. An
  existing one is simply ignored.
- `neuralmind learn` prints a short deprecation notice and **exits 0**, so any
  script or CI step that calls it keeps working.

## The A/B evidence

A 2×2 on the benchmark fixture, measuring top-k hit rate with the reranker on
vs. off, crossed with synapses on vs. off:

| Configuration | Reranker off | Reranker on | Reranker delta |
|---------------|--------------|-------------|----------------|
| **Synapses off (cold)** | 71.7% | 71.7% | 0.0 points |
| **Synapses on (warm)** | 83.3% | 83.3% | 0.0 points |
| **Synapse delta** | — | — | +11.6 points |

The reranker moved the number by 0.0 points in both rows. The synapse layer
moved it by +11.6 points. The learning that matters is the synapse layer's, and
it is the signal NeuralMind keeps.

## What was removed and what replaces it

- **Removed:** the `learned_patterns` reranker (the cooccurrence-based re-order
  of L3 hits), its `.neuralmind/learned_patterns.json` artifact, and the
  reranking work `neuralmind learn` performed.
- **Replaces it:** the Hebbian synapse layer, already present since v0.4.0 and
  namespace-aware since v0.24.0. It learns automatically and continuously from
  queries, edits, and tool calls; reinforces co-activated nodes; decays unused
  edges so old associations fade instead of going stale; and drives recall via
  spreading activation. No manual step is involved.

## Migration notes

- **Scripts and CI calling `neuralmind learn` keep working.** The command is now
  an exit-0 no-op that prints a deprecation notice pointing at the synapse
  layer. Nothing that invoked it will break; you can drop the call when
  convenient.
- **A stale `.neuralmind/learned_patterns.json` is simply ignored.** It is never
  read or written again and can be deleted at any time. There is no migration
  step and nothing to convert.
- **`NeuralMind(enable_reranking=...)` is accepted and ignored.** The keyword
  argument stays in the constructor signature for backward compatibility, so
  existing Python callers do not break, but it no longer has any effect.

## Per-agent expectations

| Agent | What changes in v0.25.0 |
|-------|--------------------------|
| **Claude Code** | No behavior change. Recall is synapse-driven exactly as before; hooks and `SYNAPSE_MEMORY.md` export are untouched. The L3 output no longer shows reranker `(+X.XX boost)` labels; synapse labels stay. |
| **Cursor / Cline** | No behavior change. The same MCP tools serve the same synapse-driven recall. No tool-surface change. |
| **Generic MCP client** | No behavior change. Recall is synapse-driven as before; no tool added or removed. |
| **Contributors / CI** | The reranker code and its tests are removed. `neuralmind learn` is an exit-0 no-op; `NeuralMind(enable_reranking=...)` is accepted and ignored. `learned_patterns.json` is no longer produced. Inspect learning via `neuralmind stats` / `neuralmind memory inspect`. |

## How to see what's learned

```bash
# What the synapse layer has learned, per namespace
neuralmind memory inspect .
neuralmind stats .            # includes the same breakdown

# `neuralmind learn` still runs (exit 0) but does nothing — drop it when convenient
neuralmind learn .
```

## Why it matters

- **One system, not two.** Two learning mechanisms that nominally do the same
  job is two places for behavior to drift, two things to document, and two
  things to keep honest. The A/B settled which one earns its keep.
- **Automatic beats manual.** The reranker only improved with a `neuralmind
  learn` step you had to remember to run. The synapse layer learns as you work,
  with no manual step.
- **Decay beats staleness.** The reranker's JSON captured a snapshot that aged
  between runs. The synapse layer continuously reinforces what's used and decays
  what isn't, so recall tracks current usage instead of a stale batch.
