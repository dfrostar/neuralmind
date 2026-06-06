# NeuralMind v0.20.0 — measure the *onboarding lift*: `neuralmind eval --onboarding`

**Release Date:** June 2026

## TL;DR

v0.14.0 measured whether NeuralMind's *graph* gives faithful answers. **v0.20.0
measures the thing that's uniquely NeuralMind** — the **learned synapse memory**
on top of the graph:

> Does an agent that inherits a **committed team memory** retrieve better on its
> *first* queries than a **cold agent with no memory** — and by how much?

```bash
neuralmind eval --onboarding             # markdown report: the onboarding lift
neuralmind eval --onboarding --json      # machine-readable
neuralmind eval --onboarding --selfcheck # validate the baseline + scorer (no heavy deps)
```

That **onboarding lift** is NeuralMind's headline differentiator. As 2026's
research shows, static tree-sitter code graphs are commoditizing fast — the
defensible edge is the usage-memory layer that learns what your team edits
together. This release turns that edge into a number you can track in CI.

## The metric, stated honestly

A **cold-vs-onboarded A/B** over the same gold queries the faithfulness eval
uses, sharing **one** built index and differing in exactly one switch
(`NEURALMIND_SYNAPSE_INJECT`):

| Arm | Synapse memory | Recall |
|-----|----------------|--------|
| **cold** | committed baseline present but never consulted | **off** |
| **onboarded** | committed team baseline replayed in | **on** |

Both arms are scored by the same offline `OfflineJudge`. **Onboarding lift =
onboarded − cold top-k module hit-rate** — the share of a query's expected
modules that land in the ranked top-k retrieval the agent actually sees. That is
exactly the slice associative recall re-ranks and displaces within, so it is
where the learned layer earns its keep. Because recall *displaces* the weakest
hits rather than adding tokens, the lift is **budget-neutral by design** — same
token cost, better-ranked modules.

Two further dimensions ride along as **honest secondaries** (reported, not
gated): **fact-recall** over the full window — which at a fixed budget is
*budget-traded* (surfacing co-edited hubs displaces some fact text, so on the
tiny fixture it dips slightly even as hit-rate rises), and **grounding**, which
*saturates* (≈100% both arms) once every expected module already fits the
window. The lift only becomes visible in the ranked top-k — which is why that is
the headline and the gate.

This formalises the self-benchmark's long-standing Phase-3 synapse A/B (top-k
hit rate 71.7% → 83.3% with recall on) into a committed-baseline eval with a CI
gate — scored on the *same* top-k hit-rate metric.

### The committed team baseline

`evals/onboarding/seed_history.json` is a **transparent, regenerable** record of
co-edit sessions — groups of files a teammate edited together. The harness
replays them through the *real* reinforcement path (`activate_files`, the same
one the file watcher uses), teaching the synapse graph cross-cutting
associations a textual search can't recover (e.g. `users/crud.py` and
`db/connection.py` are hubs touched alongside almost every feature even though
the words "authentication" or "billing" never appear in them). No binary
`synapses.db` is committed — the history *is* the source of truth.

## What the agent actually sees, post-install

A new **`neuralmind eval --onboarding`** mode on the CLI. Like `neuralmind
eval`, it's a **contributor/CI quality self-test** that runs against the gold
set + committed baseline shipped with the **source repository** (the `evals/`
package), *not* the installed wheel — from a `pip install`, it prints an
actionable message pointing at a source checkout. It does **not** change runtime
behaviour of the synapse layer, graph view, MCP tools, or hooks.

### Per-agent expectations

| Agent | What changes in v0.20.0 |
|-------|--------------------------|
| **Claude Code** | A new CLI/quality command; no runtime change. |
| **Cursor / Cline** | Same MCP tools, same retrieval; the eval is CLI/CI only. |
| **Generic MCP client** | No new MCP tool; it's a CLI/CI quality gate. |
| **Contributors / CI** | A runnable onboarding-lift gate: `--selfcheck` (no deps) and the full A/B (`--run`) with chromadb + a built index; gated in `ci-benchmark.yml` at top-k hit-rate lift ≥ 0. |

## What ships

- **`evals/onboarding/`** — `seed_history.json` (committed team baseline),
  `harness.py` (cold-vs-onboarded A/B + lift report), `runner.py`
  (`--selfcheck` / `--run [--json]`), mirroring `evals/faithfulness/`.
- **`neuralmind eval --onboarding`** CLI mode.
- **CI gate** — the benchmark job averages a few runs (to absorb ChromaDB HNSW
  query-time jitter) and fails if inheriting committed team memory ever *lowers*
  the top-k module hit-rate (mean lift ≥ 0); fact-recall + grounding print
  alongside as ungated secondaries.
- 13 stdlib unit tests (seed-history validation, A/B math incl. the headline
  hit-rate + secondary recall, report render); the `--selfcheck` gate runs with
  no heavy deps.

## Honest scope & caveats

- It self-evaluates the committed reference fixture + baseline — a
  credibility/quality gate, not yet a "point it at your repo" onboarding eval
  (that needs per-project baselines, a future increment).
- The full A/B needs the retrieval stack (chromadb) + a built index;
  `--selfcheck` needs neither. From an installed wheel, run it from a source
  checkout: `python -m evals.onboarding.runner --run`.
- The lift is measured on a deliberately tiny fixture, so the CI floor is a
  conservative `≥ 0` (catch regressions in the recall mechanism, don't chase a
  number). On the reference fixture the headline top-k hit-rate lift is a
  deterministic **+6.5 points** (75.9% → 82.4%); on real repos it is larger.

## Upgrade

```bash
pip install --upgrade neuralmind
```

No migration, no config changes, no runtime behaviour change for existing
installs. To run the onboarding self-test, use a **source checkout** (the gold
set + baseline aren't in the wheel):

```bash
git clone https://github.com/dfrostar/neuralmind && cd neuralmind
python -m evals.onboarding.runner --selfcheck   # baseline + scorer, no heavy deps
python -m evals.onboarding.runner --run          # full A/B (needs chromadb + a built index)
```
