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
  - [stats](#stats)
  - [doctor](#doctor-v0120)
  - [eval](#eval-v0140)
  - [learn](#learn)
  - [next](#next-v0110)
  - [skeleton](#skeleton)
  - [last](#last-v0100)
  - [install-hooks](#install-hooks)
  - [init-hook](#init-hook)
  - [watch](#watch-v040)
  - [serve](#serve-v054-live-feed-v060)
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
2. Otherwise the **built-in tree-sitter backend** generates the graph. As of v0.16.0 it indexes **Python, TypeScript, and Go** (`.py`, `.ts`/`.tsx`, `.go`) out of the box; more grammars register behind the `SUPPORTED_SUFFIXES` seam. A mixed-language repo is indexed in one pass.
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

#### Output

Returns:
- Optimized context text for AI consumption
- Token count and breakdown by layer
- Reduction ratio compared to full codebase
- Communities/modules loaded

#### Examples

```bash
# Basic query
neuralmind query /path/to/project "How does authentication work?"

# JSON output
neuralmind query /path/to/project "What are the main API endpoints?" --json
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

**Checks:** code graph, semantic index, synapse memory, MCP server,
Claude Code hooks, and query-memory consent. Each reports `ok`, `warn`
(optional/learned-over-time), or `fail` (setup incomplete).

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
  [ ok ] Semantic index: 1240 nodes embedded (chromadb backend)
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
     "fix": "Generate it: graphify update /repo"}
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
neuralmind eval [project_path] [--json] [--selfcheck]
```

**Arguments:**

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `project_path` | No | the gold-set fixture | Project to evaluate |
| `--json`, `-j` | No | `false` | Emit the report as JSON |
| `--selfcheck` | No | `false` | Validate the gold set + offline scorer only (no retrieval deps) |

**What it reports:** the **faithfulness delta** — mean expected-fact recall of
NeuralMind's context minus the naive baseline's, at a matched per-query token
budget — plus grounding rate, contradiction rate, and a per-query breakdown.
A positive delta means smart selection beats dumb truncation at equal token
cost. The default judge is 100% offline; an opt-in LLM-as-judge sits behind
`NEURALMIND_EVAL_LLM_JUDGE=1` and is never the default or the CI gate.

**Requirements:** the A/B needs the retrieval stack (chromadb) and a built
index; without them it degrades with an actionable message. `--selfcheck`
needs neither. From an installed wheel (where the `evals/` package isn't
bundled), run it from a source checkout instead:
`python -m evals.faithfulness.runner --run`.

---

### learn

Analyze query history to discover cooccurrence patterns and improve future search relevance.

```bash
neuralmind learn <project_path>
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | Yes | Path to project root |

#### Examples

```bash
neuralmind learn .
neuralmind learn /path/to/project
```

After collecting 5–10 queries, this command:
1. Reads `.neuralmind/memory/query_events.jsonl`
2. Finds which modules frequently appear together
3. Saves patterns to `.neuralmind/learned_patterns.json`
4. Future queries automatically apply boosted reranking

**Note:** Learning must be enabled (not blocked by `NEURALMIND_LEARNING=0`).

---

### next *(v0.11.0+)*

Predict what typically follows a node (file path or node id) in the
learned **directional transition** graph. Pairs with the
`record_sequence` calls the file watcher runs automatically on every
batched flush.

```bash
neuralmind next <project_path> <from_node> [--n 5] [--json]
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
| `NEURALMIND_LEARNING` | `1` | Set to `0` to disable continual learning |
| `NEURALMIND_BYPASS` | unset | Set to `1` to bypass PostToolUse hook compression temporarily |
| `NEURALMIND_SYNAPSE_INJECT` | `1` | *(v0.4.0+)* Set to `0` to disable spreading-activation context injection in the `UserPromptSubmit` hook |
| `NEURALMIND_SYNAPSE_EXPORT` | `1` | *(v0.4.0+)* Set to `0` to disable session-start synapse memory export |
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
| `NEURALMIND_PARITY_COVERAGE_FLOOR` | `0.90` | *(v0.16.0+)* Backend parity gate: minimum fraction of graphify's per-language symbols the built-in backend must recover for TypeScript/Go (structural parity, since no gold-fact set exists for those fixtures yet). |
| `NEURALMIND_PRECISION` | unset | *(v0.17.0+)* Set to `1` to enable the optional SCIP precision pass: when a `*.scip` index is present in the project root, the built-in backend's heuristic `calls`/`inherits` edges are replaced with compiler-accurate ones for the files the index covers. Off by default; a no-op when unset or when no index is found. |

---

## Examples

### Complete Workflow

```bash
# 1. Generate knowledge graph
graphify update ~/projects/myapp

# 2. Build neural index
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
