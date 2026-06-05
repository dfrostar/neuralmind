# NeuralMind v0.15.0 — `pip install neuralmind && neuralmind build .` (no graphify)

**Release Date:** June 2026

## TL;DR

Until now, indexing **your own** repo meant installing a **second, external
tool** (`graphify`) and running `graphify update` before `neuralmind build`
would do anything. That was the #1 onboarding drop-off, a single-maintainer
bus-factor risk, and a big reason Windows install was painful.

**v0.15.0 ships a built-in graph backend.** NeuralMind now parses your code
with a bundled **tree-sitter** backend and generates the graph itself:

```bash
pip install neuralmind
neuralmind build .        # just works — no graphify, no second install
```

A real graphify graph still takes priority where one exists, so nothing
changes for existing setups. And the swap is **proven at parity, not asserted**:
a new CI gate builds the reference fixture with *both* backends and fails the
build if the built-in one drifts outside tolerance of graphify on token
reduction *or* answer faithfulness.

## What the agent actually sees, post-install

The agent sees **the same retrieval surface as before** — same MCP tools, same
graph view, same progressive L0/L1/L2/L3 disclosure, same synapse layer. The
only difference is that on a fresh project with no `graphify-out/graph.json`,
`neuralmind build` now **succeeds on its own** instead of erroring with "run
graphify first." When it auto-generates a graph it prints:

```
[neuralmind] generated code graph via the built-in tree-sitter backend → graphify-out/graph.json
```

**The key architectural property:** everything downstream of `graph.json` —
embedder, context selector, communities, synapses, graph-view server, MCP
tools — is **unchanged**. We only swapped the graph *producer*. That seam
(`graph.json` + a `generated_by` / `schema_version` stamp) is what lets future
backends — more languages, an optional LSP/SCIP precision pass — slot in behind
the same contract.

### Per-agent expectations

| Agent | What changes in v0.15.0 |
|-------|--------------------------|
| **Claude Code** | `neuralmind build` works with no graphify install; hooks, `SYNAPSE_MEMORY.md`, and predictions are unchanged at runtime. |
| **Cursor / Cline** | Same MCP tools, same retrieval; first index no longer needs an external graph step. |
| **Generic MCP client** | `neuralmind_build` succeeds standalone on a fresh repo; no new tool, no contract change. |
| **Contributors / CI** | A new **backend parity gate** (`evals/parity/run.py`) builds the fixture with both backends and gates the built-in one within tolerance. |

## How the built-in backend works

`neuralmind/graphgen.py` is a **pure-Python tree-sitter backend** that parses a
project into a graphify-compatible `graph.json`:

- symbol-level `code` nodes — files, classes, functions/methods, **and
  module-/class-level symbols** (constants like `SESSION_TTL`, dataclass fields
  like `password_hash`) so name-level questions retrieve
- `contains` / `imports_from` / `inherits` / `calls` edges (best-effort name
  resolution)
- a `rationale` layer that keeps the **docstring summary *and* its descriptive
  body** (capped) — the body is where query-relevant facts live
- `document` nodes from **markdown** (each file plus its headings), mirroring
  graphify's document layer
- balanced, **per-file communities** (no networkx) that feed the selector's L1
  summary and L2 "relevant areas"

`tree-sitter` + `tree-sitter-python` are now **core dependencies**, so the
backend is bundled — there is no extra install. On the reference fixture it
**meets or beats graphify on every retrieval metric the parity gate measures**
(fact recall, grounding, token reduction — see below).

### When does it run?

- **No graphify output** → the built-in backend generates `graph.json`.
- **A graphify graph exists** → graphify always wins; the built-in backend
  stays out of the way.
- **`--force`** → only regenerates graphs *we* wrote; it never clobbers a real
  graphify build.
- **Empty / non-code project** → no graph is written, so you still get the
  honest "no graph" guidance instead of a silent 0-node "success."

## The parity gate — the safety net for every backend change

The faithfulness eval and self-benchmark we shipped in v0.13–v0.14 exist
precisely to de-risk swapping the graph backend. v0.15.0 wires them into a
dedicated gate:

```bash
python -m evals.parity.run     # build BOTH backends, eval + benchmark each, gate
```

For each backend it builds the reference fixture's index, runs the
**faithfulness A/B**, and derives the **self-benchmark reduction ratio** from
the same selected contexts. Then it gates that the built-in backend stays:

- within **25%** of graphify's mean token reduction (and above the absolute
  `4.0×` floor the benchmark already uses),
- within **10 points** of graphify's faithfulness delta and fact recall (and
  above the non-negative floor the eval already uses).

Tolerances are overridable via `NEURALMIND_PARITY_*` env vars so the gate can
tighten as the measured distribution stabilises. It runs on every PR
(`.github/workflows/ci-benchmark.yml`) and posts a parity table as a PR comment.

**The result on the reference fixture** (the gate building both backends
end-to-end): the built-in backend doesn't just stay within tolerance — it comes
out **ahead**:

| Metric | graphify | built-in |
|---|---:|---:|
| code nodes | 78 | 79 |
| mean token reduction | 6.08× | **6.66×** |
| faithfulness delta (vs naive) | +0.050 | **+0.143** |
| fact recall | 0.555 | **0.717** |
| grounding | 0.917 | **1.000** |

This is exactly the loop the eval harness was built for: an early cut of the
backend *failed* the gate (it retrieved worse than naive truncation), the gate
caught it pre-merge, and the producer was improved — document nodes, balanced
communities, fuller rationale, symbol extraction — until it cleared the bar on
the merits.

## Honest scope & caveats

- **Python first.** The built-in backend ships with a Python extractor today.
  The `SUPPORTED_SUFFIXES` seam is in place; TypeScript + Go extractors are the
  next increment (fixtures already exist).
- **Heuristic call/inherit edges.** Without type/scope resolution, `calls` and
  `inherits` are best-effort by name. Whether that costs retrieval quality is
  **measured by the parity gate**, not guessed — and an optional LSP/SCIP
  precision pass is on the roadmap for exact edges.
- **graphify is still fully supported** and still takes priority where present;
  this is additive, not a replacement.

## What ships

- **`neuralmind/graphgen.py`** — the built-in tree-sitter graph backend
  (graphify-compatible `graph.json`, `SCHEMA_VERSION` + `SUPPORTED_SUFFIXES`
  seam): code + symbol + `document` nodes, full-body rationale, per-file
  communities. 22 stdlib tests.
- **`core.build()`** auto-generates the graph when no graphify output exists,
  with graphify-always-wins and never-clobber-`--force` guards.
- **`evals/parity/run.py`** — the backend parity gate + a CI job that runs it on
  every PR. 9 stdlib tests for the gate math.
- `tree-sitter` + `tree-sitter-python` added as core dependencies.

## What's next

- **Multi-language** — tree-sitter TypeScript + Go extractors behind the
  `SUPPORTED_SUFFIXES` seam, proven at parity per language.
- **Optional precision pass** — LSP/SCIP-backed exact `calls`/`inherits`,
  off by default, behind the same `graph.json` seam.
- **Incremental updates** — per-file re-parse wired to the watcher.
- **Lean into the moat** — MCP auto-detection across Claude Code / Cursor /
  Cline + the learned-synapse uplift eval (E1.5).

## Upgrade

```bash
pip install --upgrade neuralmind
```

No migration, no config changes. Existing graphify-based setups are unchanged
(graphify still takes priority). On a fresh repo you can now skip graphify
entirely:

```bash
pip install neuralmind
neuralmind build /path/to/your/repo   # built-in tree-sitter backend
neuralmind query "how does auth work?" /path/to/your/repo
```
