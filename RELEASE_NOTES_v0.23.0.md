# NeuralMind v0.23.0 — versioned IR, retrieval-quality harness, and a local daemon

**The headline:** three foundations from the future-proofing roadmap land
together — a **versioned internal index contract (IR)** that decouples the
stack from any one graph producer (**PRD 1**), a **retrieval-quality harness**
that proves NeuralMind retrieves the *right* code, not just *less* of it
(**PRD 2**), and an experimental **local daemon** that holds project state warm
so repeat queries skip cold backend init (**PRD 5**). The IR is the contract
everything reads, the quality harness is the fitness function that keeps
retrieval honest, and the daemon is the stable runtime boundary the rest of the
roadmap builds on.

## PRD 1 — versioned internal index contract (IR)

NeuralMind now builds a canonical, **versioned intermediate representation
(IR)** of your code graph and validates it on every build. A new command —
**`neuralmind validate`** — checks that contract and reports schema problems
(dangling edges, orphaned nodes, unknown kinds, unsupported versions). This
decouples retrieval, memory, compression, benchmarking, the UI, and MCP from
any one graph producer's field names by putting a stable, schema-versioned
contract in the middle.

It's deliberately conservative — a **Phase-1, hidden-adapter** rollout. The
embedder still reads `graph.json` exactly as before; the IR is materialized
*alongside* it and proven to round-trip back to a graph the rest of the stack
sees as identical. Nothing about retrieval, token reduction, or your existing
index changes. You gain a versioned contract, validation tooling, and a
migration seam — without a rebuild.

## What's new

- **A canonical, versioned IR (`neuralmind/ir.py`).** Every build now adapts
  the loaded `graph.json` into an `IndexIR` — canonical `IRNode` / `IREdge` /
  `IRCluster` / `IRSynapse` entities stamped with an `ir_version`, the source
  backend, the producer's schema version, language inference, and a per-build
  **coverage** signal (`coarse` for the tree-sitter/graphify extractors; a
  future SCIP/LSP backend reports `precise`). Written to
  `<project>/.neuralmind/index_ir.json`.

- **`neuralmind validate`.** Validates the IR without standing up a vector
  backend (the decoupling is the point — it needs no ChromaDB/turbovec). It
  reports the contract version, adapter metadata, node-kind and language
  breakdowns, learned-synapse count, and any issues:
  - **errors** — dangling edge endpoints, missing endpoints, duplicate node
    ids, malformed synapse endpoints, unsupported IR version;
  - **warnings** — orphaned (edgeless) nodes, unknown node kinds, unknown edge
    relations, and **stale synapses** (learned memory pointing at nodes a
    rebuild removed — harmless but prunable).

  `neuralmind validate --write` (re)materializes the IR to `.neuralmind/` — the
  **in-place migration** path for a project that predates the IR, no rebuild
  required. `--json` emits a machine-readable summary for dashboards/CI.

- **A round-trip-faithful graphify⇄IR adapter.** `from_graph_json` /
  `to_graph_json` round-trip any `graph.json` back to a dict equal on every
  field the stack consumes (node id / label / file_type / source_file /
  source_location / community / norm_label; edge relation / source / target /
  weight / confidence). Non-standard producer fields are preserved verbatim, so
  upgrades don't silently drop information. A test exercises this on a real
  graphify fixture.

- **Learned synapses are first-class IR entities.** The IR folds in the
  Hebbian co-activation layer from the SQLite synapse store as canonical
  `IRSynapse` records — on `build` (from the live store) and in `validate`
  (read backend-free, since the store is stdlib `sqlite3`). So the learned
  memory travels with the index, validated alongside it, ready for the
  portable team-memory bundles of PRD 8.

- **Coarse-but-honest kinds.** The `graph.json` schema is deliberately locked
  to graphify's shape (a parity test enforces it), so the adapter infers kind
  from the only signals it has: `file_type` plus the label convention the
  built-in backend emits — a call-form label (`name()`) maps to `function`,
  file anchors to `file`, docs/rationale to `document`, everything else to the
  generic `symbol`. It never *guesses* a class, so coverage stays `coarse`; a
  precise backend that carries real kind metadata is the path to `precise`.

- **IR metadata in `build` and `stats`.** `neuralmind build` prints an
  `IR: v1 (valid)` line; `neuralmind stats` (and the `build_stats`) now carry an
  `ir` block with the contract version, counts, coverage, and the last
  validation result. The IR is also exposed as public API:
  `from neuralmind import IndexIR, from_graph_json, validate_ir,
  validate_project`.

- **Version safety.** Loading an IR whose `ir_version` is newer than this build
  understands fails with an actionable error (`pip install -U neuralmind`)
  rather than a silent mis-read. The migration seam (`migrate_payload`) is in
  place for the day IR v2 lands.

## Why it matters

- **Less coupling, safer evolution.** Retrieval no longer has to assume one
  producer's exact JSON shape. The IR is the single contract; the
  graphify/tree-sitter reader is just the first adapter behind it (PRD 7's
  pluggable ingestion plugs in here later).
- **Catch a broken index before it costs a query.** `validate` turns "why is
  retrieval weird?" debugging into a one-line schema check — dangling edges and
  orphaned nodes are exactly the kind of resolution bug that used to surface
  only as bad results.
- **Upgrades stop meaning rebuilds.** A versioned contract plus an in-place
  `--write` migration means a schema bump can migrate state instead of forcing
  `build --force`.

## Per-agent expectations

| Agent | What changes in v0.23.0 |
|-------|--------------------------|
| **Claude Code** | No workflow change. Builds now also write `.neuralmind/index_ir.json` and show an `IR: v1 (valid)` line; `neuralmind validate` is available for a schema check. Optional: `neuralmind daemon start` makes repeat `query`/`stats` warm. |
| **Cursor / Cline** | Same MCP tools, same retrieval. The IR is internal and the daemon is opt-in; nothing about the tool surface changes. |
| **Generic MCP client** | No new tool in this release. The IR is the internal contract MCP responses are built on; the daemon's shared `dispatch()` API is the boundary MCP moves onto next (PRD 5 Phase 3), and trace/attribution (PRD 3) builds on the IR. |
| **Contributors / CI** | New `neuralmind/ir.py` contract + `neuralmind validate` (backend-free, `--json`); `validate_project()` / `from_graph_json()` / `validate_ir()` seams; IR metadata in `stats`/`build_stats`. New `neuralmind/quality.py` + `neuralmind benchmark --quality` (precision@k / recall@k / MRR / answerability, gated). New `neuralmind/daemon.py` + `daemon_client.py`: a `ProjectRegistry` (warm cache), `JobManager`, and a transport-agnostic `dispatch()` the CLI client speaks. |

## How to use it

```bash
# Validate the canonical IR for a project (no rebuild, no vector backend needed)
neuralmind validate .

# Machine-readable summary for CI/dashboards
neuralmind validate . --json

# Migrate a legacy project's state to the IR in place (no rebuild)
neuralmind validate . --write
```

```python
from neuralmind import from_graph_json, validate_ir, IndexIR
import json

graph = json.load(open("graphify-out/graph.json"))
ir = from_graph_json(graph)          # canonical, versioned IR
issues = validate_ir(ir)             # list[ValidationIssue]
ir.write(".neuralmind/index_ir.json")
```

## PRD 2 — retrieval-quality harness

Token-reduction benchmarking proves NeuralMind is *cheap*; it never proved the
context it selects is *relevant*. As ranking, clustering, and synapse recall
evolve, a change can look great on cost while quietly retrieving the wrong
files. v0.23.0 adds the relevance fitness function that catches that.

- **`neuralmind/quality.py`** — pure, stdlib-only ranked-retrieval metrics:
  **precision@k**, **recall@k**, **MRR**, and **answerability** (whether at
  least one relevant module is in the top-k), plus a `QualityThresholds`
  regression gate and `compare_to_baseline` deltas.

- **`neuralmind benchmark --quality`** — runs those metrics over **golden
  query suites** spanning three repos (Python / TypeScript / Go, **30 queries**
  with expected-module labels), reports per-suite MRR / answerability /
  recall@k / precision@k, and **exits non-zero when a suite regresses past its
  floor**. `--suite <name>` scopes to one language; `--baseline <file.json>`
  reports metric deltas vs a saved run; `--json` emits machine-readable output
  for dashboards. Like `neuralmind eval`, it's a contributor/CI self-test
  against suites that ship with the source repo (`evals/quality/`).

- **CI gate (live).** The self-benchmark workflow runs the eval on every PR
  and **fails the build if any suite drops below the quality floors** — wired
  where real embeddings work (the unit-test job firewalls the model download).
  A measured **baseline ships in the repo** (`evals/quality/baseline.json`):
  Python MRR 0.90 / TS 0.90 / Go 0.95, answerability 100%, recall@5 0.80–0.83;
  the PR comment shows per-suite metrics and deltas vs that baseline. A
  dependency-free `--selfcheck` validates the suites + metric math everywhere,
  and `tests/test_quality_harness.py` adds an env-gated end-to-end check.

```bash
# Score retrieval quality across all golden suites (CI self-test)
neuralmind benchmark --quality

# One language, machine-readable, compared to a saved baseline
neuralmind benchmark --quality --suite go --baseline baseline_go.json --json
```

```python
from neuralmind import quality

per = [quality.evaluate_query("q1", ranked_modules, expected_modules)]
suite = quality.aggregate("my-suite", per)
print(suite.mrr, suite.answerability, suite.mean_recall)
```

## PRD 5 — local daemon (experimental)

Today every `neuralmind` invocation re-initializes the backend, reloads the
graph, and re-opens the index from cold. The durable long-term boundary is a
**local service** that owns project state, the index lifecycle, caching, and
concurrency — with thin CLI/MCP/UI clients on top. v0.23.0 ships the
experimental first cut.

- **`neuralmind daemon start|stop|status|restart`.** A per-user localhost
  daemon (also `neuralmind-daemon`) with a **project registry**: each project's
  `NeuralMind` is initialized **once** and reused across requests, so warm
  queries skip cold backend init. `start` detaches into the background and
  writes a discovery file; a **stale discovery file** (dead pid / unreachable)
  is cleaned up automatically so a crashed daemon never wedges the CLI.

- **CLI prefers the daemon automatically.** `neuralmind query` and
  `neuralmind stats` use the daemon when it's running and **fall back to direct
  mode** otherwise — identical output either way (the daemon path is marked
  `via: daemon` in `--json`). Force direct mode with `NEURALMIND_NO_DAEMON=1`.

- **One shared API contract.** A transport-agnostic `dispatch()` core maps
  `(method, path, body) → (status, payload)` — `health`, `status`, `query`,
  `search`, `stats`, `build`, `validate`, `jobs`. The HTTP handler is a thin
  wrapper over it; the CLI client speaks the same contract, and MCP/UI move onto
  it next (so behavior can't drift between surfaces).

- **Concurrency-safe.** A **per-project lock** serializes build/query/watch so
  they can't corrupt the index or the synapse store; slow rebuilds run as
  **background jobs** with pollable status (`/jobs`), token-guarded even on
  loopback, with graceful shutdown.

```bash
neuralmind daemon start            # background; warms state on first query
neuralmind query . "how does auth work?"   # served warm, marked via: daemon
neuralmind daemon status           # pid, uptime, warm projects, active jobs
neuralmind daemon stop
```

## Honest scope & what's next

- **Phase 1 only.** This is the "hidden internal adapter, legacy mode default"
  phase. The embedder still consumes `graph.json`; the IR is materialized and
  validated in parallel. Future phases dual-write, then make the IR the read
  path, then deprecate the legacy storage.
- **Coverage is `coarse` today.** The `graph.json` schema is intentionally
  locked to graphify's shape (a parity test enforces it), so the adapter infers
  kind from `file_type` + the call-form label convention (`name()` → function)
  rather than pretending to know more than the parser did. A precise (SCIP/LSP)
  backend that carries real kind metadata is the path to `precise`.
- **The daemon is experimental (PRD 5 Phase 1).** It's opt-in (`neuralmind
  daemon start`), serves the read path (`query`/`stats`) with direct-mode
  fallback, and runs one localhost process per user. Making it the default,
  moving MCP and the graph UI onto its shared API, and richer watch/rebuild
  coordination are the next phases.
- **Next:** the pluggable ingestion framework (PRD 7) registers alternate
  backends behind this same IR, explainability traces (PRD 3) attribute
  retrieval decisions across the IR's layers, and MCP/UI adopt the daemon's
  shared API (PRD 5 Phase 3).
