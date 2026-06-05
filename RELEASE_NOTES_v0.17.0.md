# NeuralMind v0.17.0 — optional SCIP precision pass (compiler-accurate edges)

**Release Date:** June 2026

## TL;DR

The built-in backend resolves `calls`/`inherits` edges **heuristically** — by
bare name. When two classes both define `handle()`, a call to `handle()` links
to whichever the heuristic sees first, which can be wrong. That's fine for the
parity gate, but if your repo has been indexed by a **SCIP** tool
(`scip-python`, `scip-typescript`, `scip-go`, …) you have *compiler-accurate*
resolution sitting right there.

v0.17.0 adds an **optional SCIP precision pass** that folds it in:

```bash
scip-python index .                 # produces index.scip (or any SCIP tool)
NEURALMIND_PRECISION=1 neuralmind build .
```

When enabled and a `*.scip` index is present, NeuralMind **replaces** the
heuristic `calls`/`inherits` edges for the files the index covers with
SCIP-resolved ones. **Off by default** — without the flag (or without an index)
the build is byte-for-byte what it was.

## What the agent actually sees, post-install

Nothing changes unless you opt in. With `NEURALMIND_PRECISION=1` and an
`index.scip` present, `neuralmind build` prints what it refined:

```
[neuralmind] SCIP precision pass: +12 calls, +4 inherits (replaced 15 heuristic calls, 3 inherits across 7 document(s))
```

The graph contract is unchanged — same nodes, same edge kinds, same
`graph.json` seam — so the embedder, selector, synapses, graph view, and MCP
tools all consume the refined graph with no changes. The agent just gets
*more accurate* call/inherit structure where a SCIP index exists.

### Per-agent expectations

| Agent | What changes in v0.17.0 |
|-------|--------------------------|
| **Claude Code** | Opt-in precise edges when a SCIP index is present; nothing changes by default. |
| **Cursor / Cline** | Same MCP tools; `calls`/`inherits` are compiler-accurate when precision is on. |
| **Generic MCP client** | No new tool; the refined graph flows through the same contract. |
| **Contributors / CI** | A precision check in the parity gate (heuristic-vs-SCIP on a fixture). |

## How it works

`neuralmind/precision.py` is a self-contained pass:

- **Dependency-free SCIP decoding.** It reads the handful of `scip.proto` fields
  it needs (`Document.relative_path`, `Occurrence.range`/`symbol`/`symbol_roles`/
  `enclosing_range`, `SymbolInformation.relationships`) with a tiny stdlib
  protobuf reader — **no protobuf runtime**, so it can't break on a version
  mismatch and adds no dependency.
- **Class-aware symbol resolution.** A SCIP symbol like `app/A#handle().` is
  mapped to the right graph node using its *enclosing type* (recovered from the
  graph's `contains` edges), so two same-named methods don't collide — which is
  exactly the case the heuristic gets wrong.
- **Scoped + safe.** Only files the index covers are touched; a SCIP symbol that
  doesn't map to a known node is skipped (no dangling edges); when disabled or
  when no index is found, the graph is returned unchanged.

## Proven by the parity gate

The backend parity gate now has a **precision section**. On a dedicated fixture
(`tests/fixtures/scip_precision/` — two classes with a `handle()` method, where
`run()` calls `A.handle`), it asserts:

- the bare-name heuristic links `run() → B.handle` (**wrong**),
- the SCIP pass links `run() → A.handle` (**correct**) and drops the wrong edge,
- the pass is a **strict no-op when disabled**.

The committed `index.scip` is built by `tests/fixtures/scip_precision/build_index.py`
(a faithful subset of what `scip-python` emits), decoded by the *same* reader the
pass uses on real indexes — so the fixture exercises the real code path with no
external indexer required in CI.

## Honest scope & caveats

- **You bring the SCIP index.** NeuralMind consumes a `*.scip` file; producing
  one is the SCIP tool's job (`scip-python`, `scip-typescript`, `scip-go`).
  Without one, nothing changes.
- **`calls`/`inherits` only.** The precision pass refines those two edge kinds
  for covered files; `contains`/`imports_from`/`rationale` and communities are
  untouched.
- **Heuristics remain the default** and still clear the parity gate on their
  own; precision is a strict, opt-in upgrade.

## What ships

- **`neuralmind/precision.py`** — the optional SCIP precision pass (stdlib
  protobuf reader, class-aware symbol resolution, scoped edge replacement).
- **`core.build()`** applies it behind `NEURALMIND_PRECISION` when a `*.scip`
  index is present; a no-op otherwise.
- **`evals/parity/run.py`** — a precision check wired into the CI gate.
- Tests: the decoder + descriptor parser + refine-on-a-real-graph (9 precision
  tests) and the gate logic (16 parity-gate tests); a committed SCIP fixture.

## What's next

- **Incremental updates** — per-file re-parse wired to the watcher so editing
  one file regenerates only its nodes.
- **Lean into the moat** — MCP auto-detection across Claude Code / Cursor /
  Cline + the learned-synapse onboarding-lift eval (E1.5).

## Upgrade

```bash
pip install --upgrade neuralmind
```

No migration, no config changes, no behavior change unless you set
`NEURALMIND_PRECISION=1` with a SCIP index present.
