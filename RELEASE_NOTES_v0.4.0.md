# NeuralMind v0.4.0 — Brain-like Synapse Layer

**Release Date:** May 3, 2026

## What's New

v0.4.0 turns NeuralMind into a **second brain that runs alongside the
LLM**. Until now, NeuralMind was a stateless retrieval layer over a
static graph. This release adds a persistent associative memory that
learns continuously from how the agent and the codebase actually
interact, with weighted "synapses" between code nodes that strengthen
through co-activation, decay with disuse, and propagate activation
through spreading recall — the brain analogues of Hebbian learning,
synaptic pruning, and associative retrieval.

### Two-brain architecture

| Role | What it does | Where state lives |
|------|--------------|-------------------|
| Claude / agent (cortex) | Reasoning, generation, working memory | The context window |
| NeuralMind (hippocampus + assoc. cortex) | Persistent associative recall, learning by co-activation | `<project>/.neuralmind/synapses.db` |

The two communicate over narrow channels: Claude Code hooks feed
activation signals into NeuralMind, NeuralMind injects ranked
associations back via `additionalContext`. Claude never sees the
weights; NeuralMind never sees Claude's reasoning. They just get
better together over time.

## New features

### 1. The synapse store (`neuralmind/synapses.py`)

A SQLite-backed weighted graph over code nodes. Self-contained, stdlib
only, persistent at `<project>/.neuralmind/synapses.db`.

- **`reinforce(node_ids)`** — Hebbian update: every pairwise edge
  among co-activated nodes gets stronger (capped at 1.0).
- **`decay()`** — multiplicative decay; weights below the prune
  threshold are deleted.
- **`spread(seeds, depth, top_k)`** — spreading activation; an energy
  pulse propagates from seed nodes outward through weighted edges.
- **Long-term potentiation** — edges crossing an activation threshold
  get a weight floor and slower decay, protecting frequently-used
  associations from being forgotten.
- **Hub normalization** — nodes with runaway connectivity have their
  outgoing contributions scaled so a single utility file can't
  dominate retrieval.

### 2. File activity watcher (`neuralmind watch`)

Every edit to project files becomes an activation signal: files
edited within a debounce window are treated as "fired together" and
the synapse store reinforces edges between every node living in
those files. The brain keeps learning even when no query runs.

```bash
neuralmind watch                      # foreground daemon
neuralmind watch --decay-interval 600 # decay tick every 10 min
neuralmind watch --quiet &            # background
```

Backed by `watchdog` when present, polling fallback otherwise.

### 3. Claude Code lifecycle hooks

`install-hooks` now wires four events instead of one:

| Event | What NeuralMind does |
|-------|---------------------|
| `SessionStart` | Warm the synapse store, run a decay tick, export memory |
| `UserPromptSubmit` | Spread activation from the prompt; inject ranked neighbors as additional context |
| `PreCompact` | Normalize hub nodes before the agent compacts its context |
| `PostToolUse` | (existing) Compress Read/Bash/Grep output |

All gated by env vars for opt-out (`NEURALMIND_SYNAPSE_INJECT=0`,
`NEURALMIND_SYNAPSE_EXPORT=0`).

### 4. Synapse memory export

`neuralmind/synapse_memory.py` renders the learned graph as markdown
and writes it where Claude Code's auto-memory system picks it up
natively:

- `<project>/.neuralmind/SYNAPSE_MEMORY.md` — always written, ready
  to import from `CLAUDE.md` via `@.neuralmind/SYNAPSE_MEMORY.md`.
- `~/.claude/projects/<slug>/memory/synapse-activations.md` — written
  when Claude Code's auto-memory directory exists, so the model loads
  the learned associations without anyone calling an MCP tool.

### 5. MCP tools

Three new tools for any MCP client (Cursor, Cline, Managed Agents,
Claude Desktop):

- `neuralmind_synaptic_neighbors(query, depth, top_k)` — spreading
  activation recall, complementing vector search with usage-based recall.
- `neuralmind_synapse_stats()` — edge count, LTP edges, top hubs,
  total weight.
- `neuralmind_synapse_decay()` — manual decay tick.
- `neuralmind_export_synapse_memory()` — write the markdown export
  on demand.

### 6. Per-query search dedup (performance)

Every `mind.query()` previously hit `embedder.search` up to three
times (L2 community selection, L3 deep search, synapse update).
ContextSelector now caches a single search per query and slices
results for each layer. `ContextResult.top_search_hits` exposes the
cached hits so downstream consumers reuse them. Result: 3× fewer
embedder round trips per query.

## API additions

```python
from neuralmind import (
    NeuralMind,
    SynapseStore,
    FileActivityWatcher,
    render_synapse_memory,
    export_synapse_memory,
)

mind = NeuralMind("/path/to/project")
mind.build()

# Hebbian update from arbitrary node ids
mind.activate(["auth.py:authenticate_user", "session.py:Session"])

# Hebbian update from file paths (resolved to node ids via embedder)
mind.activate_files(["src/auth.py", "src/session.py"])

# Spreading activation recall
mind.synaptic_neighbors("how does login work", depth=2, top_k=10)
```

`NeuralMind.synapses` exposes the underlying `SynapseStore` for direct
inspection (stats, neighbors, normalize_hubs, reset).

## Environment variables

| Var | Default | Effect |
|-----|---------|--------|
| `NEURALMIND_SYNAPSE_INJECT` | `1` | `0` disables prompt-time recall injection |
| `NEURALMIND_SYNAPSE_EXPORT` | `1` | `0` disables session-start memory export |
| `NEURALMIND_BYPASS` | `0` | (existing) `1` skips all PostToolUse compression |

## Tests

50 new tests across the synapse layer, all stdlib-only so they run
without the full ChromaDB dep set:

- `tests/test_synapses.py` — Hebbian, decay, LTP, prune, spreading,
  hub normalization, persistence, reset (13)
- `tests/test_synapse_integration.py` — `activate_files` resolution,
  no-op edge cases (5)
- `tests/test_hooks_synapses.py` — lifecycle event registration,
  idempotency, SessionStart decay + export, PreCompact hub
  normalization, prompt-submit gating (11)
- `tests/test_watcher.py` — ignore-list, batch flushing, idempotent
  stop (5)
- `tests/test_synapse_memory.py` — slug derivation, render formatting,
  Claude auto-memory write, project-local fallback (11)
- `tests/test_query_search_dedup.py` — exactly one search per query,
  hits surface on result (5)

## Backwards compatibility

- `ContextResult` gained `top_search_hits` (defaults to `[]`).
  Existing callers ignore it.
- `NeuralMind.__init__` gained `enable_synapses` (defaults to `True`).
  Existing callers get the new behavior automatically.
- Hook block adds three new lifecycle events. Re-running
  `install-hooks` is idempotent and leaves user hooks untouched.
- No migrations required. The synapse DB is created on first use.

## Upgrade

```bash
pip install -U neuralmind
neuralmind install-hooks       # wires the new lifecycle hooks
neuralmind watch &             # optional: always-on learning daemon
```

For dogfooding on the project's own codebase, add this line near the
end of your `CLAUDE.md`:

```
@.neuralmind/SYNAPSE_MEMORY.md
```

The `.neuralmind/` directory should be gitignored — its contents are
generated and per-developer.

## What's next

- Auto-watcher launch from `SessionStart` (no need for manual `watch`).
- Synapse weight import/export so a team can share a learned brain.
- Benchmark suite measuring retrieval quality with vs without synapses.
