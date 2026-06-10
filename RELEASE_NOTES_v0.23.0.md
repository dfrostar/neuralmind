# NeuralMind v0.23.0 — versioned index contract (IR) + retrieval-quality harness

**The headline:** two foundations from the future-proofing roadmap land
together — a **versioned internal index contract (IR)** that decouples the
stack from any one graph producer (**PRD 1**), and a **retrieval-quality
harness** that proves NeuralMind retrieves the *right* code, not just *less* of
it (**PRD 2**). The IR is the contract everything reads; the quality harness is
the fitness function that keeps retrieval honest as ranking evolves.

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
  breakdowns, and any issues:
  - **errors** — dangling edge endpoints, missing endpoints, duplicate node
    ids, unsupported IR version;
  - **warnings** — orphaned (edgeless) nodes, unknown node kinds, unknown edge
    relations (forward-compatibility signals for new backends).

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
| **Claude Code** | No workflow change. Builds now also write `.neuralmind/index_ir.json` and show an `IR: v1 (valid)` line; `neuralmind validate` is available for a schema check. |
| **Cursor / Cline** | Same MCP tools, same retrieval. The IR is internal; nothing about the tool surface changes. |
| **Generic MCP client** | No new tool in this release. The IR is the internal contract MCP responses are built on; trace/attribution work (PRD 3) builds on it next. |
| **Contributors / CI** | New `neuralmind/ir.py` contract + `neuralmind validate` (backend-free, `--json`). `validate_project()` / `from_graph_json()` / `validate_ir()` are the new seams; IR metadata appears in `stats`/`build_stats`. New `neuralmind/quality.py` metrics + `neuralmind benchmark --quality` (precision@k / recall@k / MRR / answerability over golden suites), gating on a regression floor. |

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

- **CI gate.** A dependency-free `--selfcheck` validates the golden suites and
  metric math, and `tests/test_quality_harness.py` runs the suite under pytest
  (the retrieval-backed run is gated on a built fixture). The rollout follows
  the PRD: internal suite now → CI-required for retrieval-affecting PRs next.

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

## Honest scope & what's next

- **Phase 1 only.** This is the "hidden internal adapter, legacy mode default"
  phase. The embedder still consumes `graph.json`; the IR is materialized and
  validated in parallel. Future phases dual-write, then make the IR the read
  path, then deprecate the legacy storage.
- **Coverage is `coarse` today.** The tree-sitter/graphify extractors can't
  reliably split a code symbol into function vs class vs method, so the adapter
  reports `coarse` and maps them to the generic `symbol` kind rather than
  pretending to know more than the parser did. A precise (SCIP/LSP) backend
  will populate the finer kinds and report `precise`.
- **Next:** the pluggable ingestion framework (PRD 7) registers alternate
  backends behind this same IR, and explainability traces (PRD 3) attribute
  retrieval decisions across the IR's layers.
