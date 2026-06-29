# CLI Reference

Complete command-line interface documentation for NeuralMind.

## Table of Contents

- [Overview](#overview)
- [Global Options](#global-options)
- [Commands](#commands)
  - [build](#build)
  - [query](#query)
  - [wakeup](#wakeup)
  - [search](#search)
  - [benchmark](#benchmark)
  - [probe](#probe-v0270)
  - [stats](#stats)
  - [validate](#validate-v0230)
  - [doctor](#doctor-v0120)
  - [eval](#eval-v0140)
  - [learn (deprecated)](#learn-deprecated-v0250)
  - [self-improve status](#self-improve-status-v0260)
  - [next](#next-v0110)
  - [memory](#memory-v0240)
  - [skeleton](#skeleton)
  - [last](#last-v0100)
  - [install-hooks](#install-hooks)
  - [init-hook](#init-hook)
  - [watch](#watch-v040)
  - [serve](#serve-v054-live-feed-v060)
  - [daemon](#daemon-v0230)
  - [savings](#savings-v0400)
  - [review](#review-v0400)
- [Exit Codes](#exit-codes)
- [Environment Variables](#environment-variables)
- [Examples](#examples)

---

## Overview

NeuralMind provides a command-line interface for building neural indexes, querying codebases with natural language, and managing knowledge graphs.

```bash
neuralmind [OPTIONS] COMMAND [ARGS]
```

### Getting Help

```bash
# General help
neuralmind --help

# Command-specific help
neuralmind build --help
neuralmind query --help
```

---

## Global Options

| Option | Description |
|--------|-------------|
| `--help` | Show help message and exit |
| `--version` | Show version number |

---

## Commands

### build

Build or rebuild the neural index from a knowledge graph.

```bash
neuralmind build <project_path> [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | Yes | Path to project root containing `graphify-out/graph.json` |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--force`, `-f` | False | Force re-embedding of all nodes, even if unchanged |
| `--dry-run` | False | Scan the project and estimate token savings **without** building the index (v0.40.0+) |
| `--json`, `-j` | False | Emit structured JSON output (for `--dry-run`) |

#### Output

Displays build statistics including:
- Number of nodes processed
- Number of nodes embedded (new/changed)
- Number of nodes skipped (unchanged)
- Number of communities indexed
- Build time elapsed

#### Examples

```bash
# Basic build
neuralmind build /path/to/project

# Force complete rebuild
neuralmind build /path/to/project --force

# Estimate token savings without building (Gap 1: 1-click setup)
neuralmind build /path/to/project --dry-run
# → NeuralMind dry run — my-project
# →   Files scanned : 142
# →   Lines of code : 18,342
# →   Languages     : 89 Python, 53 TypeScript
# →   Est. token reduction  : ~42x per query
# →   No index was built. Run `neuralmind build .` to activate these savings.
```

#### Prerequisites

**As of v0.15.0, none beyond `pip install neuralmind`.** When no
`graphify-out/graph.json` exists, `build` auto-generates one with the bundled
**tree-sitter backend** (`neuralmind/graphgen.py`) and prints:

```
[neuralmind] generated code graph via the built-in tree-sitter backend → graphify-out/graph.json
```

Backend precedence:
1. A real **graphify** graph always takes priority where present (`graphify update /path/to/project`).
2. Otherwise the **built-in tree-sitter backend** generates the graph. It indexes **Python, TypeScript, Go, Rust, Java, C, C++, C#, Ruby, and PHP** (`.py`, `.ts`/`.tsx`, `.go`, `.rs`, `.java`, `.c`/`.h`, `.cpp`/`.cc`/`.cxx`/`.hpp`/`.hh`/`.hxx`, `.cs`, `.rb`, `.php`) out of the box (Java added in v0.28.0; C and C++ in v0.32.0; C# in v0.35.0; Ruby in v0.36.0; PHP in v0.37.0); more grammars register behind the `SUPPORTED_SUFFIXES` seam. A mixed-language repo is indexed in one pass.
3. `--force` only regenerates graphs *we* wrote — it never clobbers a graphify build.
4. An empty/non-code project writes no graph, so you still get the "no graph" guidance rather than a silent 0-node success.
5. **Optional precision (v0.17.0+):** set `NEURALMIND_PRECISION=1` and place a `*.scip` index (from `scip-python`/`scip-typescript`/`scip-go`) in the project root to replace the built-in backend's heuristic `calls`/`inherits` edges with compiler-accurate ones for the files the index covers. Off by default.

---

### query

Query the codebase with natural language and get optimized context.

```bash
neuralmind query <project_path> "<question>" [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | Yes | Path to project root |
| `question` | Yes | Natural language question about the codebase |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--json`, `-j` | False | Output results as JSON |
| `--trace` | False | *(v0.23.0+)* Attach a per-layer retrieval trace (see below) |
| `--trace-verbose` | False | *(v0.23.0+)* With `--trace`, keep full candidate/hit lists |
| `--explain` | False | *(v0.40.0+)* Human-friendly breakdown of token savings, layers used, top hits, and synapses that fired (implies `--trace`) |

#### Output

Returns:
- Optimized context text for AI consumption
- Token count and breakdown by layer
- Reduction ratio compared to full codebase
- Communities/modules loaded

#### Retrieval traces *(v0.23.0+)*

`--trace` explains **why** a result came back (PRD 3) — useful when retrieval
surprises you. It records, layer by layer:

- **candidates** — the raw vector-search pool (ids + scores);
- **cluster_scores** — per-cluster score with **vector-vs-synapse attribution**
  (how much of each cluster's score came from learned co-activation);
- **synapse_boost** — individual co-activation boosts;
- **hits** — the final ranked hits, flagging which were synapse-recalled;
- **budget** — tokens per layer + reduction ratio.

Plain `--trace` prints a compact per-layer summary; `--json` includes the full
trace object (bounded, and path-redactable via the `RetrievalTrace` API for
sharing in bug reports). Tracing is off by default and zero-overhead. The
daemon's `/query` honors `trace` too, so daemon and direct mode return the same
attribution.

#### Examples

```bash
# Basic query
neuralmind query /path/to/project "How does authentication work?"

# JSON output
neuralmind query /path/to/project "What are the main API endpoints?" --json

# Explain the retrieval path (raw trace)
neuralmind query /path/to/project "How does billing work?" --trace
neuralmind query /path/to/project "How does billing work?" --trace --json

# Human-friendly explanation of why this context was chosen (v0.40.0+)
neuralmind query /path/to/project "auth flow" --explain
# → Why this context?
# →   Token budget breakdown:
# →     L0 identity   :    142 tokens
# →     L1 summary    :    513 tokens
# →     L2 communities:    800 tokens
# →     L3 search     :    980 tokens
# →     Total used    :  2,435 tokens
# →     Est. saved    : 47,565 tokens  (20.5x reduction)
# →   Top search hits (L3, 4 nodes):
# →     0.912  authenticate  (auth/handlers.py)
# →     0.887  JWTMiddleware  (auth/middleware.py)
```

#### Sample Output

```
=== Query: How does authentication work? ===

[Context]
# Project: MyApp
MyApp is a web application with JWT-based authentication...

[Authentication Module]
The auth module handles user login, token generation, and validation...

[Relevant Code]
- auth/jwt_handler.py: JWT token generation and validation
- auth/middleware.py: Authentication middleware for routes
- models/user.py: User model with password hashing

---
Tokens: 847 | Reduction: 59.0x | Layers: L0, L1, L2, L3 | Communities: [5, 12]
```

---

### wakeup

Get minimal wake-up context for starting a new conversation.

```bash
neuralmind wakeup <project_path> [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | Yes | Path to project root |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--json`, `-j` | False | Output results as JSON |

#### Output

Returns L0 (Identity) + L1 (Summary) context, typically ~600 tokens, suitable for:
- Starting new AI conversations
- Providing project context to coding assistants
- Initial system prompts

#### Examples

```bash
# Get wake-up context
neuralmind wakeup /path/to/project

# Redirect to file
neuralmind wakeup /path/to/project > context.md

# JSON format
neuralmind wakeup /path/to/project --json
```

#### Sample Output

```
=== Wake-up Context ===

# Project: MyApp

MyApp is a full-stack web application for task management built with React and Node.js.

## Architecture Overview

### Core Components
- **Frontend**: React 18 with TypeScript, Tailwind CSS
- **Backend**: Node.js/Express REST API
- **Database**: PostgreSQL with Prisma ORM
- **Auth**: JWT-based authentication

### Main Modules
1. User Management (users/) - Registration, profiles, settings
2. Task Engine (tasks/) - CRUD operations, scheduling, notifications
3. API Layer (api/) - REST endpoints, middleware, validation

---
Tokens: 412 | Layers: L0, L1
```

---

### search

Perform direct semantic search across codebase entities.

```bash
neuralmind search <project_path> "<query>" [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | Yes | Path to project root |
| `query` | Yes | Semantic search query |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--n` | 10 | Maximum number of results |
| `--json`, `-j` | False | Output results as JSON |

#### Output

Returns matching code entities with:
- Entity name and type
- Similarity score (0-1)
- File path
- Community membership

#### Examples

```bash
# Basic search
neuralmind search /path/to/project "authentication"

# Limit results
neuralmind search /path/to/project "database connection" --n 5

# JSON output
neuralmind search /path/to/project "API endpoint" --json
```

#### Sample Output

```
=== Search: authentication ===

1. authenticate_user (function) - Score: 0.92
   File: auth/handlers.py
   Validates user credentials and returns JWT token
   Community: 5 (Authentication)

2. AuthMiddleware (class) - Score: 0.87
   File: auth/middleware.py
   Express middleware for JWT validation
   Community: 5 (Authentication)

3. hash_password (function) - Score: 0.81
   File: utils/crypto.py
   Securely hashes passwords using bcrypt
   Community: 5 (Authentication)

---
Results: 3 | Query time: 45ms
```

---

### benchmark

Run performance benchmark with sample queries.

```bash
neuralmind benchmark <project_path> [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | Yes | Path to project root |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--json`, `-j` | False | Output results as JSON |
| `--quality` | False | *(v0.23.0+)* Quality-eval mode — see below |
| `--suite` | (all) | *(v0.23.0+)* With `--quality`, run one suite: `python` / `typescript` / `go` |
| `--baseline` | — | *(v0.23.0+)* With `--quality`, a saved suite JSON to compare against (reports metric deltas) |
| `--public` | False | *(v0.31.0+)* Public-benchmark mode — reproduce the honest vs-alternatives comparison on pinned real repos (see below). Ignores `project_path` (it uses the pinned corpus, not your project) and requires a **source checkout** — the `evals/public` harness ships in the repo, not the PyPI wheel |
| `--repo` | (all) | *(v0.31.0+)* With `--public`, scope to one corpus repo: `requests` / `click` |
| `--seeds` | `1` | *(v0.31.0+)* With `--public`, the seed count recorded in the report. The pipeline is deterministic (synapse injection off), so variance across seeds is exactly 0 — recorded honestly rather than padded with artificial noise |
| `--judge` | False | *(v0.34.0+)* With `--public`, also run the opt-in **answerability arm** — each backend answered from its real window by a pinned model (`claude-opus-4-8`), graded vs. the def-site gold anchor (0–2 + `grounded`). A clearly-labeled **secondary** signal. Needs `ANTHROPIC_API_KEY`; **never runs in CI**; the recall table is byte-identical with or without it; skips cleanly without a key (see below) |
| `--judge-out` | `bench/public/judge` | *(v0.34.0+)* With `--public --judge`, where to write the raw answerability transcripts (question, context tokens, answer, verdict, rationale) |

#### Output

Comprehensive benchmark report including:
- Token counts for each query type
- Reduction ratios
- Query latencies
- Comparison with full codebase size

#### Examples

```bash
# Run default benchmark
neuralmind benchmark /path/to/project

# JSON output
neuralmind benchmark /path/to/project --json
```

#### Quality-eval mode *(v0.23.0+)*

`--quality` switches the command from token-reduction benchmarking to
**retrieval-quality** measurement: does NeuralMind surface the *right* code,
not just *less* of it? It scores **precision@k**, **recall@k**, **MRR**, and
**answerability** over golden query suites (Python / TypeScript / Go — 30
queries with expected-module labels) and **exits non-zero if a suite regresses
past its floor**, so CI can gate retrieval-affecting changes.

Like `neuralmind eval`, this is a contributor/CI self-test that runs against
the golden suites shipping with the **source repo** (the `evals/quality/`
package), not the installed wheel. The pure metrics live in
`neuralmind.quality` (`from neuralmind import quality`).

```bash
# Score all golden suites
neuralmind benchmark --quality

# One language, machine-readable
neuralmind benchmark --quality --suite go --json

# Compare against the committed measured baseline (reports metric deltas)
neuralmind benchmark --quality --baseline evals/quality/baseline.json

# Dependency-free validation of the suites + metric math (no embeddings)
python -m evals.quality.runner --selfcheck
```

Sample (markdown) output — measured on the committed fixtures:

```
## NeuralMind retrieval-quality eval

| Suite | Queries | MRR | Answerability | Recall@5 | Precision@5 | Gate |
|-------|--------:|----:|--------------:|---------:|------------:|:----:|
| `go`         | 10 | 0.950 | 100% | 0.833 | 0.603 | PASS |
| `python`     | 10 | 0.900 | 100% | 0.833 | 0.612 | PASS |
| `typescript` | 10 | 0.900 | 100% | 0.800 | 0.562 | PASS |

**Overall: PASS**
```

The exit code is non-zero if any suite drops below the floors in
`evals/quality/harness.py` (`DEFAULT_THRESHOLDS`), so CI can gate on it. The
measured baseline lives at `evals/quality/baseline.json`; the self-benchmark
workflow runs this on every PR (where real embeddings are available) and posts
the table + baseline deltas as a PR comment.

#### Public-benchmark mode *(v0.31.0+)*

`--public` runs the **honest public benchmark**: a reproducible, no-cherry-picking
comparison of how much context different approaches put in an agent's window to
answer a real code question, and whether the **objectively-correct file** actually
makes it in. It clones **real, pinned OSS repos** at fixed commit SHAs
(`requests` @`0e322af877`, `click` @`874ca2bc1c`) and scores **cost _and_
correctness together** against strong baselines: `full-file` paste, `ripgrep`,
a same-encoder `embedding-rag`, and `neuralmind`'s progressive disclosure.

Gold-file recall is an **objective def-site oracle** — each query's gold file is
the definition site of a named symbol, verifiable with one `rg`; there is **no
LLM judge**. Scoring reuses `neuralmind/quality.py` verbatim — the same metric
code the CI quality gate runs. Pre-registered queries live in
`evals/public/manifest.json`; every one is reported, losses included.

```bash
# Clone the pinned repos and print the full table
neuralmind benchmark --public

# Scope to one repo
neuralmind benchmark --public --repo click

# Machine-readable output (for CI / further analysis)
neuralmind benchmark --public --json

# Equivalent module entrypoint (from a clone)
python -m evals.public.run
```

The run is **deterministic** — synapse injection is **OFF** (session-dependent
learning can't be a fixed, reproducible public number; its **+11.7pt** lift is
measured separately by the synapse A/B eval, `tests/benchmark/run.py` Phase 2).
This reuses the same `NEURALMIND_SYNAPSE_INJECT=0` toggle documented in the
[Environment Variables](#environment-variables) table. Re-running matches the
published table to the token.

**Honest headline:** against what agents actually do today — paste files or grep
— NeuralMind reaches **100% gold-file recall at 38–85× fewer tokens** than
pasting files, and beats `ripgrep` on *both* recall and cost. The benchmark also
reports, without hiding it, that a well-tuned vector RAG is excellent at
*findability* too (and cheaper on raw tokens). Full methodology, results, honest
caveats, and "where NeuralMind loses" are published at
[`docs/benchmarks/public.md`](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/public.md);
raw per-query data is committed at `bench/public/results.json`, and the forkable
runner is `.github/workflows/bench-public.yml`.

##### Competitor head-to-head *(v0.33.0+)*

The benchmark also ships a **live, reproducible row vs. `codebase-memory-mcp`
0.8.1** (the obvious incumbent), on the same pinned repos, questions, def-site
gold, and `quality.py` scorer, at retrieval depth matched to `embedding-rag`
(top-8). It lives in a **separate module** and is **off the default run** because
it downloads an external binary — invoke it explicitly from a clone:

```bash
pip install codebase-memory-mcp==0.8.1     # pins 0.8.1 — on-device embeddings, no API key
python -m evals.public.competitor   # prints the competitor row; fails closed without the binary
```

On **reproducible retrieval ranking** NeuralMind reaches **100% gold-file recall**
and ranks the right file far higher (MRR **0.96 vs 0.23** on `requests`, **0.60
vs 0.50** on `click`), while the competitor surfaces the gold file in its top-8
only ~half the time, at an order of magnitude more read cost. **Honest framing:**
this measures *pure retrieval* — no LLM agent loop on either side, exactly how we
test NeuralMind's own `search`; we used the competitor's **most-favorable**
reproducible keyword mapping; and we cite its *published* LLM-agent numbers (~90%
of an "Explorer" agent; C at 0.58) as-is rather than reproduce them. Per-query
traces and pinned `REPRODUCE.md` are committed under `bench/public/competitor/`;
full caveats are in the "Competitor head-to-head" section of
[`docs/benchmarks/public.md`](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/public.md).

#### Answerability arm — `--judge` *(v0.34.0+)*

Gold-file recall measures *locating* the right file, not *answering* the
question. The opt-in answerability arm adds the answering signal — a
clearly-labeled **secondary** to the recall headline:

```bash
ANTHROPIC_API_KEY=…  python -m evals.public.run --judge   # off by default
```

For each query it answers from **the real context each backend would put in the
window** (whole files / retrieved chunks / compact L0–L3 context) using a pinned
model (`claude-opus-4-8`), constrained to that context only, then a separate
judge call grades the answer against the same def-site gold anchor on a 0–2 scale
plus a `grounded` flag. It needs `ANTHROPIC_API_KEY` (and the `anthropic`
package), **never runs in CI**, and the recall table is byte-identical with or
without `--judge` — absent a key it skips cleanly and the recall benchmark still
runs. The answerer prompt, judge rubric, pinned model id, and **every raw
transcript** are committed under `bench/public/judge/` (transcripts written to
`--judge-out`, default `bench/public/judge`). Full framing + caveats: the
"Answerability arm" section of
[`docs/benchmarks/public.md`](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/public.md).

#### Sample Output

```
=== NeuralMind Benchmark ===

Project: MyApp
Total Nodes: 241
Communities: 93
Estimated Full Codebase: 50,000 tokens

| Query Type | Tokens | Reduction | Latency |
|------------|--------|-----------|----------|
| Wake-up context | 341 | 146.6x | 45ms |
| How does authentication work? | 739 | 67.7x | 187ms |
| What are the main API endpoints? | 748 | 66.8x | 192ms |
| Explain the database models | 812 | 61.6x | 201ms |
|------------|--------|-----------|----------|
| **Average** | **660** | **85.7x** | **156ms** |

---
Benchmark completed in 625ms
```

---

### probe *(v0.27.0+)*

Run a **retrieval self-probe** on your own codebase: does the index actually
find the right file when the agent asks about a symbol? Unlike `benchmark`
(which measures token reduction) and `benchmark --quality` (which scores ranking
against committed golden fixtures), `probe` runs **label-free** — no hand
annotation — so it works on **any** built project.

```bash
neuralmind probe [project_path] [OPTIONS]
```

For a deterministic sample of indexed symbols, it queries each one by its
*intent* — the symbol's **rationale** (the docstring text NeuralMind stores as
`rationale` nodes, e.g. `"Raised when the exp claim is in the past"`), which
doesn't contain the symbol name, so it's a real **natural-language → code** test
rather than a string match. It asks the backend for code hits directly, then
scores whether the symbol's source file came back: **recall@1/3/5**, **MRR**, and
**answerability@k** (reusing the `neuralmind.quality` metrics). Undocumented
symbols fall back to a humanized label, and the report **discloses the
rationale-vs-name split** so a mostly-fallback run reads as a sanity check, not a
quality score. The most actionable output is the **blind-spot list**: the sampled
symbols the index couldn't retrieve from their description — i.e. where an agent
would come up empty. `--k` must be ≥ 1 and `--sample-size` ≥ 0 (`0` = all).

The idea is borrowed from long-context "needle-in-a-haystack" evals (e.g. S-NIAH
in the *Recursive Language Models* paper): rather than measuring cost, it
measures whether the right node still surfaces as the index grows. It is
**read-only** — it never mutates the index or the synapse store.

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | No | Path to project root (default: `.`) |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--sample-size` | 50 | How many indexed symbols to probe (`0` = all) |
| `--k` | 10 | Retrieval depth — a symbol's file must surface in the top-k |
| `--seed` | 0 | Sampling seed; same seed = same sample, for stable/comparable runs |
| `--baseline` | — | A saved probe JSON to compare against (reports recall/MRR deltas) |
| `--json`, `-j` | False | Output the full report (including every blind spot) as JSON |

#### Examples

```bash
# Probe the current project
neuralmind probe .

# Tighter: the right file must be the #1 hit
neuralmind probe . --k 1

# Save a baseline, then check whether a refactor moved retrieval
neuralmind probe . --sample-size 100 --json > probe-baseline.json
neuralmind probe . --sample-size 100 --baseline probe-baseline.json
```

#### Sample Output

```
Retrieval self-probe — sample_project
Sampled 63 of 64 indexed symbols, retrieval depth k=10
Query source: 51 rationale, 12 label
============================================================
  answerability  : 98%  (file found in top-10)
  MRR            : 0.789
  recall@1/3/5   : 0.667 / 0.905 / 0.968
  blind spots    : 1
------------------------------------------------------------
Symbols the index couldn't retrieve from their own description (1 total):
  - get_me_endpoint()  (api/routes.py)   query: "GET /api/users/me — requires Authorization: Bearer header"
```

The `Query source` line discloses how strong the run was: `rationale` probes are
real NL→code tests; `label` probes are a weaker name-based fallback for
undocumented symbols. Because the probe is deterministic per `--seed` and emits
`--json` (with a `query_sources` tally), you can gate CI on a per-repo recall/MRR
floor, or diff two runs with `--baseline` to catch a retrieval regression before
it ships.

---

### stats

Show statistics about the neural index.

```bash
neuralmind stats <project_path> [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | Yes | Path to project root |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--json`, `-j` | False | Output as JSON |

#### Output

Displays:
- Node counts by type
- Community statistics
- Embedding information
- Index storage size
- Last build timestamp

#### Examples

```bash
# Basic stats
neuralmind stats /path/to/project

# JSON format
neuralmind stats /path/to/project --json
```

#### Sample Output

```
=== NeuralMind Statistics ===

Project: MyApp
Graph Path: /path/to/project/graphify-out/graph.json
DB Path: /path/to/project/graphify-out/neuralmind_db

## Index Summary
- Total Nodes: 241
- Total Edges: 203
- Communities: 93
- Embedding Dimensions: 384

## Node Types
- Functions: 142 (58.9%)
- Classes: 45 (18.7%)
- Files: 38 (15.8%)
- Database Models: 16 (6.6%)

## Storage
- Index Size: 12.4 MB
- Cache Size: 2.1 MB

## Build Info
- Last Build: 2024-01-15 14:30:22
- Build Duration: 8.3s
- Embedding Model: all-MiniLM-L6-v2
```

---

### validate *(v0.23.0+)*

Validate the project's canonical **intermediate representation (IR)** — the
versioned, producer-agnostic contract NeuralMind builds from `graph.json`.
Runs a static schema check; **no vector backend required** (it never touches
ChromaDB/turbovec).

```bash
neuralmind validate [project_path] [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | No (default `.`) | Path to project root |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--write` | False | (Re)materialize the IR to `.neuralmind/index_ir.json` — the in-place **migration** path for a legacy project that predates the IR (no rebuild). |
| `--json`, `-j` | False | Output a machine-readable summary (for CI/dashboards) |

#### What it checks

- **errors** (exit code `1`): dangling edge endpoints, missing endpoints,
  duplicate node ids, malformed synapse endpoints, unsupported (too-new)
  `ir_version`.
- **warnings**: orphaned (edgeless) nodes, unknown node kinds, unknown edge
  relations, and **stale synapses** (learned memory pointing at nodes a
  rebuild removed) — forward-compatibility / hygiene signals.

It also reports the IR contract version, source backend + producer schema
version, coverage (`coarse`/`precise`), per-kind / per-language counts, and the
learned-synapse count (folded in backend-free from the SQLite store).

#### Examples

```bash
# Validate the IR for the current project
neuralmind validate .

# Machine-readable summary
neuralmind validate . --json

# Migrate a legacy project's state to the IR in place (no rebuild)
neuralmind validate . --write
```

#### Sample Output

```
IR version:      1
Source backend:  neuralmind.graphgen (tree-sitter)
Source schema:   v1
Coverage:        coarse
Entities:        135 nodes, 185 edges, 18 clusters
Node kinds:      document=56, file=13, function=41, symbol=25
Languages:       python=135
------------------------------------------------------------
VALID — 0 errors, 0 warning(s).
```

> `function` is inferred from the built-in backend's call-form labels
> (`name()`); a producer that doesn't follow that convention maps those to the
> generic `symbol`. Learned synapses, when a `.neuralmind/synapses.db` exists,
> are folded in and shown in the `--json` `synapses` count.

> The IR is also exposed as a public Python API:
> `from neuralmind import IndexIR, from_graph_json, validate_ir, validate_project`.

---

### doctor *(v0.12.0+)*

Diagnose a project's NeuralMind setup and print an actionable fix for
anything that isn't wired up. Read-only — it never builds or mutates
state.

```bash
neuralmind doctor [project_path] [--json]
```

**Arguments:**

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `project_path` | No | `.` | Project root to inspect |
| `--json`, `-j` | No | `false` | Emit machine-readable JSON |

**Checks:** code graph, semantic index, **backend** *(v0.22.0+)*, synapse
memory, MCP server, Claude Code hooks, and query-memory consent. Each reports
`ok`, `warn` (optional/learned-over-time), or `fail` (setup incomplete). The
**Backend** check reports the configured value (e.g. `auto`), what it resolves
to (`turbovec` or `chroma`), and whether the turbovec stack is installed — so the
per-environment default is never a silent mystery.

**Exit codes:** `0` when no check failed (warnings allowed), `1` when any
check **failed** — so you can gate a CI step or an agent's provisioning on
`neuralmind doctor`.

**Example:**

```bash
neuralmind doctor .
```

```
NeuralMind doctor — /path/to/project
============================================================
  [ ok ] Code graph: 1240 nodes at /path/to/project/graphify-out/graph.json
  [ ok ] Semantic index: 1240 nodes embedded (turbovec backend)
  [ ok ] Backend: turbovec (auto-selected; turbovec stack available)
  [warn] Synapse memory: no synapses.db yet (nothing learned)
         -> It populates automatically as you query and edit the codebase.
  [ ok ] MCP server: MCP SDK importable (neuralmind-mcp ready)
  [warn] Claude Code hooks: not installed
         -> Install them: neuralmind install-hooks
  [ ok ] Query memory: enabled (logging queries for learning)
============================================================
```

JSON output (`--json`) is stable for scripting and agent consumption:

```json
{
  "status": "fail",
  "checks": [
    {"name": "Code graph", "status": "fail",
     "detail": "not found at /repo/graphify-out/graph.json",
     "fix": "Generate it: neuralmind build /repo"}
  ]
}
```

---

### eval *(v0.14.0+)*

Run the **faithfulness eval**: does NeuralMind's selected context contain
more gold facts than a *matched-budget* naive baseline? It self-evaluates
against the committed reference fixture + gold-fact set (which ship with the
source repository), so — like `neuralmind benchmark` — it's a quality
self-test, not a per-repo command.

```bash
neuralmind eval [project_path] [--json] [--selfcheck] [--onboarding]
```

**Arguments:**

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `project_path` | No | the gold-set fixture | Project to evaluate |
| `--json`, `-j` | No | `false` | Emit the report as JSON |
| `--selfcheck` | No | `false` | Validate the gold set + offline scorer only (no retrieval deps) |
| `--onboarding` | No | `false` | Run the **onboarding-lift** eval instead — committed team memory vs a cold agent (see `evals/onboarding/`) |

**What it reports:** the **faithfulness delta** — mean expected-fact recall of
NeuralMind's context minus the naive baseline's, at a matched per-query token
budget — plus grounding rate, contradiction rate, and a per-query breakdown.
A positive delta means smart selection beats dumb truncation at equal token
cost. The default judge is 100% offline; an opt-in LLM-as-judge sits behind
`NEURALMIND_EVAL_LLM_JUDGE=1` and is never the default or the CI gate.

**What `--onboarding` reports:** the **onboarding lift** — onboarded − cold
**top-k module hit-rate** (the share of a query's expected modules that land in
the ranked top-k retrieval the agent sees), the slice associative recall
re-ranks within. Fact-recall and full-context grounding print as honest
secondaries: at a fixed budget fact-recall is *budget-traded* (slightly negative
on the tiny fixture) and grounding *saturates*, so neither is the gated headline.
It's the same top-k hit-rate signal as the self-benchmark's Phase-3 A/B.

**Requirements:** the A/B needs the retrieval stack (chromadb) and a built
index; without them it degrades with an actionable message. `--selfcheck`
needs neither. From an installed wheel (where the `evals/` package isn't
bundled), run it from a source checkout instead:
`python -m evals.faithfulness.runner --run`.

---

### learn *(deprecated, v0.25.0)*

**Deprecated and a no-op since v0.25.0.** The `learned_patterns`
cooccurrence reranker this command used to populate was removed. The
command now prints a deprecation notice and **exits 0**, so existing
scripts and CI that call it keep working unchanged.

```bash
neuralmind learn <project_path>   # prints a deprecation notice, exits 0
```

Learning is now handled entirely by the **synapse layer**, which learns
continuously and automatically from queries, edits, and tool calls — no
manual step, and edges decay instead of going stale. A 2×2 A/B on the
benchmark fixture showed the old reranker added 0.0 points to top-k hit
rate while the synapse layer alone adds +11.6 points.

To see what's been learned, use [`neuralmind stats`](#stats) or
[`neuralmind memory inspect`](#neuralmind-memory). For the full rationale
and migration notes, see the
[v0.25.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/RELEASE_NOTES_v0.25.0.md).

---

### self-improve status *(v0.26.0+)*

Show the self-improvement engine's current selector-tuning state. **Read-only** —
it never writes and never runs the tuner; it only reports what the tuner has done.

```bash
neuralmind self-improve status [project_path] [--json]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | No (default `.`) | Path to project root |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--json`, `-j` | off | Machine-readable JSON output (adds `autotune_enabled`) |

#### What it reports

- `l2_recall_k` — the current (possibly tuned) L2 recall depth, i.e. how many
  community summaries a query surfaces. Default `3`, clamped to `[2, 6]`.
- `l2_recall_k_tuned_at` — ISO timestamp of the last change, or `never`.
- query-event count + warm-up state (the tuner holds until 50 query events
  accumulate).
- the windowed `re_query_rate` the tuner reads.
- whether autotune is enabled (the `NEURALMIND_SELECTOR_AUTOTUNE` flag).

```bash
$ neuralmind self-improve status .
Project: my-project
Autotune enabled: True (NEURALMIND_SELECTOR_AUTOTUNE)
l2_recall_k: 4
Last tuned at: 2026-06-12T17:58:10+00:00
Query events logged: 132 (warmed up: True)
Query events in tuning window: 41
re_query_rate: 0.512
```

The tuner itself runs only when `NEURALMIND_SELECTOR_AUTOTUNE=1` — under Claude
Code it ticks once per session from the `SessionStart` hook (after the synapse
decay tick); the tuned value is then threaded into the selector at build time so
ordinary queries (CLI or MCP) use the adapted recall depth. With the flag unset
the hot path does **zero** extra I/O and the selector keeps its hard-coded
default. The tuner is single-step, windowed, hysteretic, clamped, and fail-open;
see the [v0.26.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/RELEASE_NOTES_v0.26.0.md)
and `evals/self_improvement/PLAN.md` for the full design.

---

### next *(v0.11.0+)*

Predict what typically follows a node (file path or node id) in the
learned **directional transition** graph. Pairs with the
`record_sequence` calls the file watcher runs automatically on every
batched flush.

```bash
neuralmind next <project_path> <from_node> [--n 5] [--namespace NAME] [--json]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | Yes | Path to project root |
| `from_node` | Yes | Source node — usually a file path; can be any string the transition recorder has seen |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--n` | `5` | Top-N successors to return |
| `--namespace` | merged | *(v0.24.0+)* Read one memory namespace at raw weights (e.g. `branch:feature-x`). Default is the merged view: active namespace 1.0× + `personal` 0.8× + `shared` 0.5× |
| `--json`, `-j` | False | Output as JSON |

#### Examples

```bash
# What do I usually edit after the auth handlers?
neuralmind next . src/auth/handlers.py

# JSON for scripting
neuralmind next . src/auth/handlers.py --n 10 --json
```

Sample output:

```
After src/auth/handlers.py:
   45.2%  tests/test_auth.py
   28.4%  src/auth/middleware.py
   12.1%  docs/auth.md
    8.3%  src/auth/__init__.py
    6.0%  src/main.py
```

The same capability is exposed via MCP as `neuralmind_next_likely`
and via Python as `SynapseStore.next_likely(from_node, top_k=5)`. The
file watcher must have been running at some point for this to return
results — fresh installs need a few sessions before the transition
graph accumulates signal.

---

### memory *(v0.24.0+)*

Namespace-level controls over the learned synapse memory (PRD 4). Every
learned association carries a namespace — `personal` (default; all
pre-v0.24 memory migrates here losslessly), `shared` (imported team
baseline), `branch:<name>` (per-git-branch, detected automatically), and
`ephemeral` (session scratch, cleared at session boundaries). All four
subcommands work without a built index — the store is stdlib SQLite.

```bash
neuralmind memory inspect [project_path] [--namespace NAME] [--json]
neuralmind memory reset   [project_path] --namespace NAME [--json]
neuralmind memory export  [project_path] [--namespace NAME] [-o FILE]
neuralmind memory import  <file> [--project-path PATH] [--namespace NAME] [--json]
neuralmind memory publish [project_path] [--json]
```

#### Subcommands

| Subcommand | What it does |
|------------|--------------|
| `inspect` | Contribution by namespace — edges, total weight, transitions, nodes — plus the active namespace and schema version. Also folded into `neuralmind stats`. |
| `reset` | Clear **one** namespace (`--namespace` is required). The project index and every other namespace are untouched — the surgical alternative to a full retrain. |
| `export` | Write one namespace as a portable, versioned JSON bundle reusing the IR's `IRSynapse` shape. Defaults to the active namespace; `-o` writes a file, otherwise stdout. |
| `import` | Validate a bundle (format + version + entries) and merge it into a target namespace (default: the bundle's own). Merging keeps the MAX of weight/count per edge, so re-importing the same bundle is **idempotent**. A malformed bundle is rejected wholesale — never partially imported. |
| `publish` *(v0.30.0)* | **Team memory.** Export the project's learned memory (`personal` + `shared`, MAX-merged) to a committed bundle at the repo root, **`.neuralmind-team-memory.json`**. Commit it, and every teammate's agent inherits it once into `shared` on its next `SessionStart`/`build` (content-hash-gated, off-switch `NEURALMIND_TEAM_MEMORY=0`). |

#### Examples

```bash
# What has the agent learned, and where does it live?
neuralmind memory inspect .

# A feature branch merged — drop exactly its memory
neuralmind memory reset . --namespace branch:feature-x

# Ship a team baseline to a new teammate (ad-hoc bundle)
neuralmind memory export . --namespace personal -o team-baseline.json
neuralmind memory import team-baseline.json --namespace shared

# Team memory (v0.30.0): commit once, teammates inherit automatically
neuralmind memory publish .
git add .neuralmind-team-memory.json && git commit -m "publish team memory"
# teammates: their next `neuralmind build` / Claude Code session inherits it
```

#### How the active namespace is resolved

`NEURALMIND_NAMESPACE` env var → `memory_namespace:` in
`neuralmind-backend.yaml` → `branch:<name>` when the repo is on a
non-default git branch (best-effort `git rev-parse`, 3s timeout) →
`personal`. A non-repo, detached HEAD, or missing git all degrade safely
to `personal`. Long-lived processes (the daemon, the MCP server) detect a
`git checkout` between writes via a cheap `.git/HEAD` fingerprint and
re-resolve automatically — no restart needed.

#### Merged-read weighting

Recall, `next`, and stats default to a merged view with explicit,
published constants (`neuralmind/synapses.py`):

```
merged_weight = 1.0 × active  +  0.8 × personal  +  0.5 × shared
                (W_BRANCH)       (W_PERSONAL)        (W_SHARED)
```

On the default branch the active namespace *is* `personal` (read at
1.0×), so behavior is identical to pre-namespace releases. Per-namespace
decay: `shared` is sticky, `personal`/`branch:*` decay at the standard
rates, `ephemeral` fades fast with no LTP floor. Traced queries
(`query --trace`) attribute each synapse boost to its namespace via
`namespace_contribution`.

---

### skeleton

Print a compact graph-backed view of a file — functions, rationales, and call graph — without loading the full source.

```bash
neuralmind skeleton <file_path> [--project-path .] [--json]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `file_path` | Yes | Path to the source file (absolute or project-relative) |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--project-path` | `.` | Project root directory |
| `--json`, `-j` | False | Output as JSON |

#### Examples

```bash
# Skeleton for a file in the current project
neuralmind skeleton src/auth/handlers.py

# Skeleton with explicit project root
neuralmind skeleton src/auth/handlers.py --project-path /path/to/project

# JSON output
neuralmind skeleton src/auth/handlers.py --json
```

---

### last *(v0.10.0+)*

Print the most recent Bash output the PostToolUse hook cached, so an
agent can recover the dropped middle without re-running the command.

Every time the `compress-bash` hook fires, it stashes the raw
pre-compression stdout/stderr to
`<project>/.neuralmind/last_output.json` (single-slot, 2 MB cap,
atomic temp-file + rename writes). `neuralmind last` surfaces it.

```bash
neuralmind last [project_path] [--json]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | No | Project root containing `.neuralmind/last_output.json` (default: current directory) |
| `--json`, `-j` | No | Emit the full payload as JSON (timestamp, command, exit code, stdout, stderr) |

#### Examples

```bash
# Human-readable: what the agent would have seen pre-compression.
neuralmind last

# Full JSON payload — useful for scripted recovery flows.
neuralmind last --json

# When no cache exists yet (no Bash call has fired the hook).
neuralmind last
# → "No cached output found at <path>. Run a Bash tool call through Claude Code first…"
# → exits with status 1
```

#### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Cache present and printed |
| `1` | No cache exists (no recent Bash call) |

#### When to use

| Scenario | Recovery cost without `last` | With `last` |
|----------|------------------------------|-------------|
| Inspecting compressed `npm test` middle | Re-run (~28s) | Free lookup |
| Reading dropped log lines from a non-deterministic API call | Re-run + likely different output | Free lookup, identical bytes |
| Reading dropped output from a destructive command | Re-run impossible | Free lookup |

---

### install-hooks

Install or uninstall Claude Code lifecycle hooks. As of v0.4.0 this
registers four event blocks (idempotent — re-running only updates the
NeuralMind block, leaving any user hooks untouched):

| Event | What runs | Purpose |
|-------|-----------|---------|
| `PostToolUse` | Read/Bash/Grep compressors | Token reduction on tool output |
| `SessionStart` *(v0.4.0)* | `synapse decay()` + memory export | Age unused synapses; surface learned associations to Claude Code's auto-memory |
| `UserPromptSubmit` *(v0.4.0)* | Spreading activation from prompt | Inject ranked synapse neighbors as `additionalContext` |
| `PreCompact` *(v0.4.0)* | `normalize_hubs()` | Prevent runaway hub nodes before context compaction |

```bash
neuralmind install-hooks [project_path] [--global] [--uninstall]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | No | Project root (default: current directory). Ignored when `--global` is set |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--global` | False | Install hooks in `~/.claude/settings.json` (all projects) |
| `--uninstall` | False | Remove NeuralMind hooks while preserving other tools' hooks |

#### Examples

```bash
# Install hooks for current project
neuralmind install-hooks .

# Install hooks globally
neuralmind install-hooks --global

# Uninstall project hooks
neuralmind install-hooks --uninstall

# Uninstall global hooks
neuralmind install-hooks --uninstall --global
```

**Bypass temporarily:**

```bash
NEURALMIND_BYPASS=1 claude-code ...
```

---

### install-mcp *(v0.19.0+)*

Register the NeuralMind MCP server (`neuralmind-mcp`) with one or more AI coding
agents. Auto-detects installed clients and merges a `neuralmind` entry into each
client's `mcpServers` config **without clobbering** your other servers
(idempotent — re-running is a no-op).

```bash
neuralmind install-mcp [project_path] [--client NAME] [--all] [--print]
```

#### Clients & config locations

| Client | Scope | Config file |
|--------|-------|-------------|
| `claude-code` (default) | project | `.mcp.json` |
| `cursor` | project | `.cursor/mcp.json` |
| `claude-desktop` | user | platform `claude_desktop_config.json` |
| `cline` | user | VS Code `cline_mcp_settings.json` |
| `vscode` | user | VS Code `settings.json` (`mcp.servers` key, requires VS Code 1.99+) |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--client` | `claude-code` | Which single client to register with |
| `--all` | False | Register with every **detected** client (auto-detection) |
| `--print` | False | Print the config snippet to paste manually; write nothing |

#### Examples

```bash
# Register with Claude Code for this project (writes .mcp.json)
neuralmind install-mcp

# Register with every agent installed on this machine/project
neuralmind install-mcp --all

# A specific client
neuralmind install-mcp --client cursor

# Just show me the snippet
neuralmind install-mcp --print
```

Restart the client after registering so it picks up the new server. The agent
then exposes NeuralMind's MCP tools (`wakeup`, `query`, `search`, `skeleton`,
`build`, `stats`, …).

---

### init-hook

Install (or update) a Git post-commit hook that rebuilds the neural index automatically after every commit. Safe and idempotent — re-running only updates the NeuralMind block without touching other hooks.

```bash
neuralmind init-hook [project_path]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | No | Project root (default: current directory) |

#### Examples

```bash
# Install hook in current project
neuralmind init-hook .

# Install hook for a specific project
neuralmind init-hook /path/to/project
```

---

### watch *(v0.4.0+)*

Run the file activity → synapse co-activation daemon in the foreground.
Edits to project files are debounced into batches and fed into the
synapse store, so the v0.4.0 brain-like layer keeps learning even when
no query runs. Periodic decay ticks age unused weights without manual
intervention. Stops cleanly on Ctrl-C.

```bash
neuralmind watch [project_path] [--debounce SECONDS] [--decay-interval SECONDS] [--quiet] [--reindex]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | No | Project root (default: current directory) |

#### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--debounce` | `0.75` | Seconds to coalesce rapid edits into one co-activation batch |
| `--decay-interval` | `600` | Seconds between decay ticks; `0` disables periodic decay |
| `--quiet` | off | Suppress per-batch logging (still prints final summary on stop) |
| `--reindex` | off | *(v0.18.0+)* Incrementally re-index edited files into the built-in graph as they change — re-parses just those files and re-embeds only their nodes (unchanged files are skipped). Built-in backend only; needs the retrieval stack in the watch process. |

#### Examples

```bash
# Always-on learning for the current project
neuralmind watch &

# Background it and only log the final summary
neuralmind watch /path/to/repo --quiet &

# Disable periodic decay (decay only runs from SessionStart hook)
neuralmind watch . --decay-interval 0

# Keep the index live as you edit (incremental re-index, v0.18.0+)
neuralmind watch . --reindex
```

#### Notes

- Backed by `watchdog` when present, with a polling fallback when not. No mandatory new dependency.
- Pairs with `neuralmind install-hooks` — the watcher learns from
  edits, the lifecycle hooks learn from queries and tool calls, and the
  same `<project>/.neuralmind/synapses.db` store is the single source of truth.
- For "always on" across reboots, wrap in systemd, launchd, or tmux. NeuralMind deliberately doesn't self-daemonize.

---

### serve *(v0.5.4; live feed v0.6.0+)*

Start the graph-view UI — a local, dependency-free, Obsidian-style
force-directed graph over the same index and synapse store your AI
agent queries. v0.6.0 made the canvas live: synapse + file events
stream to the browser over SSE, affected nodes pulse, a sidebar log
shows recent events. Stops cleanly on Ctrl-C.

The server binds to 127.0.0.1 by default and prints a per-session
auth-token URL on startup; pass that URL to the browser so untrusted
local processes can't read your graph.

```bash
neuralmind serve [project_path] [--port PORT] [--no-browser] [--editor EDITOR] [--no-auth]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | No | Project root (default: current directory) |

#### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | `8765` | TCP port to bind to |
| `--no-browser` | off | Don't auto-open a browser tab on startup |
| `--editor` | `$EDITOR` | Editor command used by the "Open in editor" button — `code`, `code -n`, `cursor`, `vim`, `subl`, `idea`, etc. |
| `--no-auth` | off | Disable the per-session auth token. Only use on a trusted host. |

#### Examples

```bash
# Run against the current project
neuralmind serve .

# Custom editor for the "open in editor" button
neuralmind serve . --editor "code -n"

# Pick a different port and skip the browser
neuralmind serve . --port 9000 --no-browser

# Skip auth for a kiosk / trusted local host
neuralmind serve . --no-auth
```

#### Live activity feed (v0.6.0+)

The canvas updates in real time as the brain works:

- **Synapse events** — every `SynapseStore.reinforce()` call publishes
  a `synapse` event over the in-process event bus; the affected pair
  of nodes pulse on the canvas.
- **File activity events** — every coalesced edit batch from the
  `neuralmind watch` daemon (or from Claude Code's `PostToolUse`
  hooks) publishes a `file_activity` event; affected nodes pulse.
- **Sidebar log** — the most recent ~80 events render as a scrolling
  feed with timestamps. Click an entry to focus the corresponding
  node on the canvas.

#### Cross-process activity bridge (v0.6.0+)

When `serve` and the activity source live in different processes —
a separate `neuralmind watch` daemon, a Claude Code session — each
`event_bus.publish()` call also appends a JSON line to
`<project>/.neuralmind/events.jsonl`. The `serve` process tails that
file in a background thread and re-emits anything it didn't
originate. Net result: one canvas, all processes, no IPC complexity.

Behaviour:

- `NEURALMIND_EVENT_LOG=0` disables the writer (in-process feed
  still works).
- The tailer is best-effort. If the file disappears or rolls, the
  next event re-creates it.
- The bus stays the primary path. The JSONL is a fallback, not a queue.

#### Notes

- Read-only over HTTP. Edits to nodes/synapses still go through the
  regular CLI and MCP tools; the UI only inspects.
- The `/api/open` endpoint launches `$EDITOR` against an allowlist
  pre-computed from the graph's `source_file` set, so a tampered
  client can't trick the server into opening arbitrary paths.
- All assets in `neuralmind/web/` (HTML, JS, CSS) are read-only at
  runtime; the server doesn't generate any of them.
- Graph payload is cached per-session in `_Handler._graph_cache`; any
  endpoint touching graph state respects `_graph_lock`.
- Vanilla-JS frontend, stdlib-only HTTP server, no CDN. Safe to run
  behind a firewall.

---

### daemon *(v0.23.0+)*

Manage the local NeuralMind daemon (experimental — PRD 5). The daemon holds
each project's state **warm** so repeated queries skip cold backend init. CLI
read commands (`query`, `stats`) prefer it automatically when it's running and
fall back to direct mode otherwise.

```bash
neuralmind daemon {start|stop|restart|status} [OPTIONS]
```

#### Actions

| Action | Description |
|--------|-------------|
| `start` | Launch the daemon in the background (writes a discovery file). No-op if already running. |
| `stop` | Ask the running daemon to shut down gracefully; clears stale discovery. |
| `restart` | Stop (if running) then start. |
| `status` | Show pid, uptime, warm projects, and active jobs (exit 3 if not running). |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | `127.0.0.1` | Host to bind (loopback) |
| `--port` | `8787` | Port to bind |
| `--foreground` | False | Run in the foreground instead of detaching (`start`/`restart`) |
| `--json`, `-j` | False | Machine-readable `status` output |

#### Behavior

- **One per-user daemon, many projects.** A project registry initializes each
  `NeuralMind` once and reuses it; a per-project lock serializes
  build/query/watch so they can't corrupt the index or synapse store; slow
  builds run as background jobs.
- **Auto-preference + fallback.** `neuralmind query` / `stats` use the daemon
  when reachable (output marked `via: daemon` in `--json`), else run directly.
  Force direct mode with **`NEURALMIND_NO_DAEMON=1`**.
- **Crash-safe discovery.** A stale discovery file (dead pid / unreachable) is
  cleaned up automatically, so a crashed daemon never wedges the CLI.
- **Shared API.** The daemon speaks one transport-agnostic contract
  (`health` / `status` / `query` / `search` / `stats` / `build` / `validate` /
  `jobs`); the `neuralmind-daemon` console script runs it directly. Token-guarded
  even on loopback.

```bash
# Warm daemon, then fast repeat queries
neuralmind daemon start
neuralmind query . "how does auth work?"   # served warm (via: daemon)
neuralmind daemon status --json
neuralmind daemon stop
```

---

### savings *(v0.40.0+)*

Show cumulative token savings from the local query event log. Verifies the 40-70x claim against your own real usage rather than trusting the demo.

```bash
neuralmind savings [project_path] [OPTIONS]
```

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--global` | False | Show savings across ALL projects (reads the global event log at `~/.neuralmind/memory/`) |
| `--json`, `-j` | False | Emit structured JSON output |

#### Examples

```bash
# Show project-level savings
neuralmind savings .
# → NeuralMind token savings — my-project
# →   Queries logged    : 47
# →   Avg reduction     : 38.2x
# →   Tokens actually used :     83,140
# →   Est. cost without NM : 2,350,000
# →   Tokens saved         : 2,266,860

# Global savings across all projects
neuralmind savings --global

# JSON for dashboards or scripting
neuralmind savings . --json
```

Memory logging must be enabled (answer yes when first prompted, or set `NEURALMIND_MEMORY=1`).

---

### review *(v0.40.0+)*

Warn about likely co-breakage before a commit or when reviewing a diff.

Reads the current `git diff` (or a specified base ref), finds changed files, and runs spreading activation through the learned synapse graph to surface files that are **strongly associated but NOT in your diff** — files that have historically been edited together with the ones you're changing.

```bash
neuralmind review [project_path] [OPTIONS]
```

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--base` | `HEAD` | Git ref to diff against. Use `HEAD~1` to review the last commit or a branch name to review a feature branch. |
| `--top-k` | `10` | Maximum number of at-risk files to report |
| `--json`, `-j` | False | Emit structured JSON output |

#### Examples

```bash
# Review uncommitted changes (diff against HEAD)
neuralmind review .

# Review the last commit
neuralmind review . --base HEAD~1

# Review changes on a feature branch vs main
neuralmind review . --base main

# JSON output for CI integration
neuralmind review . --json
```

#### Sample Output

```
NeuralMind review — my-project  (diff against: HEAD)

Changed files (3):
  • auth/middleware.py
  • auth/handlers.py
  • tests/test_auth.py

Co-break candidates — files NOT in diff but strongly associated (4):
  0.782 ████████  auth/tokens.py
  0.654 ██████    auth/models.py
  0.431 ████      config/settings.py
  0.198 ██        docs/auth.md

These files have historically been edited together with the ones above.
Consider whether your change also needs to touch them.
```

Requires the synapse graph to have accumulated edges. Cold graphs (first few sessions) return empty results. Also available as the `neuralmind_review` MCP tool.

---

## Exit Codes

| Code | Meaning |
|------|----------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |
| 3 | graph.json not found |
| 4 | Index not built (run `build` first) |
| 5 | Database error |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEURALMIND_MEMORY` | `1` | Set to `0` to disable query memory logging |
| `NEURALMIND_LEARNING` | `1` | *(deprecated, v0.25.0)* Formerly disabled the `learned_patterns` cooccurrence reranker, which was removed in v0.25.0. Now inert — recognized but ignored. To disable the synapse layer's prompt-time recall, use `NEURALMIND_SYNAPSE_INJECT=0`. |
| `NEURALMIND_BYPASS` | unset | Set to `1` to bypass PostToolUse hook compression temporarily |
| `NEURALMIND_SYNAPSE_INJECT` | `1` | *(v0.4.0+)* Set to `0` to disable spreading-activation context injection in the `UserPromptSubmit` hook |
| `NEURALMIND_SYNAPSE_EXPORT` | `1` | *(v0.4.0+)* Set to `0` to disable session-start synapse memory export |
| `NEURALMIND_TEAM_MEMORY` | `1` | *(v0.30.0+)* Set to `0` to disable auto-inheriting a committed `.neuralmind-team-memory.json` team bundle. When enabled (default), a teammate's `SessionStart`/`build` imports the bundle **once** into the `shared` namespace (content-hash-gated, `shared`-only, fail-open). Publish your own with `neuralmind memory publish`. |
| `NEURALMIND_EVENT_LOG` | `1` | *(v0.6.0+)* Set to `0` to disable the cross-process JSONL event-bridge writer at `<project>/.neuralmind/events.jsonl`. The in-process event bus is unaffected; `serve` running in the same process as the activity source still gets a live feed. |
| `NEURALMIND_OUTPUT_CACHE` | `1` | *(v0.10.0+)* Set to `0` to disable the recovery cache that backs `neuralmind last`. |
| `NEURALMIND_OUTPUT_CACHE_MAX` | `2097152` | *(v0.10.0+)* Total size cap (bytes) for the recovery cache. Oversize payloads are split proportionally between stdout/stderr and truncated keeping head + tail. |
| `NEURALMIND_BASH_SMALL` | `500` | *(v0.10.0+)* Threshold below which failing Bash outputs pass through verbatim (no compression marker). Tunable to suit your noise tolerance. |
| `NEURALMIND_BASH_MAX_CHARS` | `3000` | Threshold above which successful Bash outputs get compressed. |
| `NEURALMIND_BASH_TAIL` | `3` | Number of tail lines always kept verbatim in compressed Bash output. |
| `NEURALMIND_EVAL_LLM_JUDGE` | `0` | *(v0.13.0+)* Opt-in LLM-as-judge mode for the offline faithfulness eval harness (`evals/faithfulness/`). Off by default and **never** the CI gate; when set, the runner prints a notice that answers + gold facts would be sent to a third-party API. The default judge is the zero-network offline expected-fact-recall scorer. |
| `NEURALMIND_PARITY_REDUCTION_TOL` | `0.25` | *(v0.15.0+)* Backend parity gate (`evals/parity/run.py`): max fraction the built-in backend's mean token reduction may sit below graphify's (0.25 = within 25%). |
| `NEURALMIND_PARITY_FAITHFULNESS_TOL` | `0.10` | *(v0.15.0+)* Backend parity gate: max absolute points the built-in backend's faithfulness delta / fact recall may sit below graphify's (0.10 = 10 points). |
| `NEURALMIND_PARITY_REDUCTION_FLOOR` | `4.0` | *(v0.15.0+)* Backend parity gate: absolute minimum mean reduction the built-in backend must clear, independent of graphify (mirrors the self-benchmark floor). |
| `NEURALMIND_PARITY_FAITHFULNESS_FLOOR` | `0.0` | *(v0.15.0+)* Backend parity gate: absolute minimum faithfulness delta the built-in backend must clear (mirrors the eval gate — smart selection ≥ matched-budget naive truncation). |
| `NEURALMIND_PARITY_COVERAGE_FLOOR` | `0.90` | *(v0.16.0+)* Backend parity gate: minimum fraction of the gold graph's per-language symbols the built-in backend must recover for TypeScript/Go/Rust/Java/C/C++ (structural parity, since no gold-fact set exists for those fixtures yet). |
| `NEURALMIND_PRECISION` | unset | *(v0.17.0+)* Set to `1` to enable the optional SCIP precision pass: when a `*.scip` index is present in the project root, the built-in backend's heuristic `calls`/`inherits` edges are replaced with compiler-accurate ones for the files the index covers. Off by default; a no-op when unset or when no index is found. |
| `NEURALMIND_ONNX_MODEL_DIR` | unset | *(v0.21.0+)* Path to a pre-extracted `all-MiniLM-L6-v2` ONNX folder (`model.onnx` + `tokenizer.json`) for the ChromaDB-free `turbovec` backend's bundled embedder. When unset, the model is resolved from NeuralMind's cache, an existing ChromaDB cache, or downloaded (SHA256-verified). Set it for **air-gapped** installs so no network is needed. |
| `NEURALMIND_NO_DAEMON` | unset | *(v0.23.0+)* Set to `1` to force CLI commands to run in direct mode even when a daemon is running (skips the daemon auto-preference for `query`/`stats`). |
| `NEURALMIND_NAMESPACE` | unset | *(v0.24.0+)* Pin the active memory namespace for this process (e.g. `ephemeral` for throwaway exploration, `shared` on a CI box building team baseline). Overrides config and git-branch detection. Resolution order: this var → `memory_namespace:` in `neuralmind-backend.yaml` → `branch:<name>` on a non-default git branch → `personal`. |
| `NEURALMIND_DAEMON_HOME` | unset | *(v0.23.0+)* Override the directory holding the daemon discovery file (`daemon.json`). Defaults to `~/.neuralmind`. Mainly for tests / running an isolated daemon. |
| `NEURALMIND_BM25` | `1` | *(v0.38.0+)* Set to `0` to disable the BM25 keyword index and fall back to pure vector search. When enabled (default), the BM25 index built by `neuralmind build` is merged with vector results via Reciprocal Rank Fusion at query time, improving exact-name retrieval for code queries like `"UserService"` or `"get_auth_token"`. The index is stored in `<project>/.neuralmind/bm25_index.json` and rebuilt automatically on every `neuralmind build`. |
| `NEURALMIND_SELECTOR_AUTOTUNE` | `0` | *(v0.26.0+)* Set to `1` to enable the self-improvement engine's selector auto-tuner: the `SessionStart` hook adjusts the L2 recall depth from the re-query rate (once per session), and `build()` threads the persisted value into the selector. Opt-in (`== "1"`, not the `!= "0"` pattern) because it is net behavior change. With it unset the hot path does **zero** extra I/O and the selector keeps its hard-coded default. Inspect state with `neuralmind self-improve status`. |

---

## Vector backend selection *(v0.21.0+)*

NeuralMind's vector store is pluggable. The default is `auto` (an unset config
behaves the same): it resolves to the **ChromaDB-free** `turbovec` backend when
its stack (`turbovec` + `onnxruntime` + `tokenizers`) is importable, and
otherwise falls back to `chroma`. **As of v0.29.0 the turbovec stack is a
platform-gated base dependency**, so a plain `pip install neuralmind` resolves
to turbovec (ChromaDB-free) out of the box on platforms with turbovec wheels
(Linux, macOS arm64, Windows x86_64). On platforms without a turbovec wheel
(Intel macOS, Windows ARM) ChromaDB is auto-installed as the fallback backend,
so the install always works. Install `pip install "neuralmind[chromadb]"` (and
pin `backend: graph`) to force ChromaDB anywhere. (Alpine/musl Linux: use a
`python:slim` glibc image or the `[chromadb]` extra — markers can't gate musl.)

To **pin** a backend explicitly (an explicit value always wins over `auto`), drop
a `neuralmind-backend.yaml` at the project root:

```yaml
backend: turbovec   # the default path: TurboVec ANN + bundled OnnxMiniLMEmbedder
# backend: graph    # force ChromaDB (alias: chroma) — needs `pip install "neuralmind[chromadb]"`
# backend: auto     # the default — turbovec when its deps are installed, else chroma
```

The turbovec/ONNX stack ships by default; `pip install "neuralmind[chromadb]"`
adds the opt-in ChromaDB backend. Vectors are byte-identical between backends, so
retrieval quality is at/above parity; the turbovec index is 8–16× smaller.
Selecting `graph`/`chroma` without the `[chromadb]` extra raises an actionable
error pointing at the install command. Accepted values: `auto` (default),
`graph` / `chroma`, `turbovec`, `in_memory` (offline tests).

**One-time auto-reindex.** When `auto` resolves to turbovec for a project that
still has a legacy ChromaDB index and no turbovec index yet, the next build
reindexes from `graph.json` and prints a one-line notice. The old ChromaDB index
is left in place as a fallback — nothing is deleted.

Run `neuralmind doctor` to see which backend the current environment resolves to
(see the **Backend** line).

---

## Examples

### Complete Workflow

```bash
# 1. Build neural index (the code graph is generated automatically)
neuralmind build ~/projects/myapp

# 3. View statistics
neuralmind stats ~/projects/myapp

# 4. Get wake-up context for new conversation
neuralmind wakeup ~/projects/myapp > context.md

# 5. Query specific functionality
neuralmind query ~/projects/myapp "How does the payment system work?"

# 6. Search for specific entities
neuralmind search ~/projects/myapp "PaymentController" --n 5

# 7. Run benchmark
neuralmind benchmark ~/projects/myapp
```

### Scripting Integration

```bash
#!/bin/bash
# update_and_query.sh - Update index and run queries

PROJECT="$1"
QUERY="$2"

# Rebuild if graph changed
if [ graphify-out/graph.json -nt graphify-out/neuralmind_db ]; then
    echo "Graph updated, rebuilding index..."
    neuralmind build "$PROJECT"
fi

# Run query
neuralmind query "$PROJECT" "$QUERY" --json
```

### Piping to AI Tools

```bash
# Get context and pipe to clipboard (macOS)
neuralmind wakeup ~/projects/myapp | pbcopy

# Get context and pipe to clipboard (Linux)
neuralmind wakeup ~/projects/myapp | xclip -selection clipboard

# Save context to file for AI assistant
neuralmind query ~/projects/myapp "Explain the auth system" > auth_context.md
```

---

## See Also

- [API Reference](API-Reference.md) - Python API documentation
- [Architecture](Architecture.md) - System design details
- [Integration Guide](Integration-Guide.md) - MCP and tool integrations
