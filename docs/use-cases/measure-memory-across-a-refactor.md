# Measure how your AI memory improves across a major refactor

You just rebuilt a subsystem. Did your AI agent's memory keep up — or is it
recalling a codebase that no longer exists? With NeuralMind this is measurable:
snapshot the graph and synapse stats before the refactor, work normally,
snapshot after, and diff.

This page is two things: a **field report** with real numbers from a private
mid-size TypeScript SaaS platform (~9,300 nodes) measured across a major
internal rebuild, and a **recipe** for running the same before/after
measurement on your own repo.

## The field report

**The setting.** A private, mid-size TypeScript SaaS platform (~9,300 indexed
nodes), maintained by NeuralMind's own maintainer — see the honesty notes
below. A major internal rebuild ("Phase 3 → Phase 4") landed a new backend
module, a shared business-logic layer, an admin UI, and end-to-end specs.
NeuralMind ran throughout with lifecycle hooks installed, so the synapse layer
observed the work as it happened. The repo is private, so the numbers are
anonymized; every one of them came from the shipped CLI.

**The numbers.**

| Metric | Before (Phase 3) | After (Phase 4) | Change |
|---|---:|---:|---|
| Total nodes | 9,190 | 9,293 | +103 |
| Communities | — | 810 | new resolution — no comparable before |
| Personal synapse edges | 36 | 135 | **+275%** |
| Shared synapse edges | 10,079 | 10,183 | +104 |
| Shared edge weight | 2,774.73 | 2,924.66 | **+5.4%** |
| Wake-up tokens | — | 455 | |
| Avg query tokens | — | 1,033 | |
| Avg token reduction | — | **48.8×** | vs loading files naively |
| Full `--force` rebuild | — | 326 s (~5.4 min) | incremental rebuilds ~30 s after |

**What the numbers say**

- **48.8× token reduction** — after the rebuild, an average code question cost
  ~1,033 tokens of context instead of the 50K+ a naive "load the relevant
  files" approach would spend. That is one repo's measured ratio from
  `neuralmind benchmark .`, consistent with the
  [40–70× real-repo range](../wiki/Benchmarks.md) — not a universal guarantee.
- **Personal synapse edges tripled (36 → 135)** — the
  [Hebbian synapse layer](../wiki/Learning-Guide.md) learned co-activations
  across the *new* code as it was being written and queried. The memory didn't
  go stale through the rebuild; it grew into the new architecture.
- **Shared edge weight +5.4%** — the static graph's cross-links got denser as
  the new shared business-logic layer connected previously separate areas.
- **Rebuild cost stayed flat** — one full `--force` rebuild at 326 s to pick up
  the new structure, then incremental rebuilds back to ~30 s. Re-indexing is
  not a tax you pay per edit.

## Where each number comes from

Honesty first: the before/after table above is **hand-assembled from the
output of several commands** — there is no single `neuralmind compare-phases`
command.

| Metric | Command |
|---|---|
| Total nodes, communities | `neuralmind stats . --json` (nodes also printed at build time) |
| Personal/shared edges, edge weight | `neuralmind stats .` — the `Memory namespaces` block (per-namespace `edges (weight …)`) |
| Wake-up tokens, avg query tokens, avg reduction | `neuralmind benchmark .` |
| Rebuild time | timed `neuralmind build . --force` (and an untimed incremental `build`) |
| Synapses fired per query, mean tokens | `neuralmind metrics .` |
| Real logged spend | `neuralmind savings .` |

## Run the same measurement on your refactor

### Step 1 — Snapshot before you start

```bash
neuralmind stats . --json > .neuralmind-before.json
neuralmind stats .          # eyeball the Memory namespaces block
neuralmind benchmark .      # baseline reduction number
```

Keep the JSON out of your commit (or don't — it's small and diffs nicely).

### Step 2 — Do the refactor, with the memory watching

The synapse layer only learns from what it observes. Make sure hooks are
installed before the work starts:

```bash
neuralmind install-hooks .
neuralmind watch &   # optional: always-on learning from edits
```

Then work normally — query, edit, run tools. No manual "learn" step exists;
co-activations are recorded as you go (see the
[Learning Guide](../wiki/Learning-Guide.md)).

### Step 3 — Rebuild and snapshot after

```bash
time neuralmind build . --force   # once, to pick up new structure
neuralmind stats . --json > .neuralmind-after.json
neuralmind stats .
```

Diff the two JSON files (or the two `Memory namespaces` blocks). The
interesting deltas: node count (did the graph track the new code?), personal
edges (did the memory learn the new co-activations?), shared edge weight (did
the graph get denser or just bigger?).

### Step 4 — Re-benchmark and price it

```bash
neuralmind benchmark .   # reduction ratio on the post-refactor graph
neuralmind metrics .     # mean tokens/query and synapses fired, from real usage
neuralmind savings .     # what your actual logged queries cost vs naive
```

If the reduction ratio held (or improved) across the rebuild, your agent's
context bill survived the refactor. If personal edges barely moved, the
memory wasn't watching — check that hooks were installed *before* the work.

## Honesty notes

- This is **one repo, one developer, measured by the maintainer on a private
  codebase**. It is an existence proof and a recipe, not an independent
  benchmark. You cannot re-run it on the source repo — but you can run the
  identical method on yours, which is the point.
- 48.8× is a reduction in **retrieval input tokens**, not your total LLM
  bill. For typical end-to-end agent sessions the realistic total-cost saving
  is smaller — see the [Honest assessment](../HONEST-ASSESSMENT.md).
- The CI-gated, reproducible numbers live in
  [Benchmarks & Results](../wiki/Benchmarks.md); this page is deliberately
  labeled a field report.

## Related

- [Shareable single-page version](https://neuralmind.uk/field-reports/measure-memory-across-a-refactor/) — this field report on neuralmind.uk
- [Use case: Does it work on your code? (5-minute benchmark)](./benchmark-your-repo.md) — the first-run version of this measurement
- [Use case: Growing monorepo](./growing-monorepo.md) — keeping the index fresh with minimal effort
- [Wiki: Brain-Like Learning Guide](../wiki/Learning-Guide.md) — how the synapse layer learns what this page measures

---

[← Back to use-case index](./README.md) · [Main README](../../README.md)
