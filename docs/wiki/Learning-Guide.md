# Brain-Like Learning Guide

> How NeuralMind improves retrieval relevance by learning from how you
> actually use your codebase

## Overview

NeuralMind's learning system improves automatically as you use it. The
more you query, edit, and run tools over your code, the smarter recall
gets — with no manual step to remember.

As of **v0.25.0 there is a single learning system: the Hebbian synapse
layer.** It learns continuously from queries, edits, and tool calls,
reinforces the edges between code nodes that fire together, and lets
unused edges decay so recall tracks current usage instead of a stale
snapshot. (NeuralMind previously had a second mechanism — a
`learned_patterns` cooccurrence reranker driven by `neuralmind learn` —
which was removed in v0.25.0. See ["The old reranker"](#the-old-reranker-removed-in-v0250)
below if you arrived here from an older link.)

### The Learning Cycle

```
┌──────────────────────────────────────────────────────────┐
│ 1. Observe                                                │
│    Every query, tool call, and file edit co-activates a   │
│    set of code nodes.                                     │
│    ↓ The synapse layer reinforces edges between them      │
├──────────────────────────────────────────────────────────┤
│ 2. Recall                                                 │
│    A new query lights up the relevant nodes; activation   │
│    spreads across the learned graph.                      │
│    ↓ Related code surfaces that vector search would miss  │
├──────────────────────────────────────────────────────────┤
│ 3. Decay                                                  │
│    Unused edges age out automatically; long-term          │
│    potentiation protects frequently-used connections.     │
│    ↓ Recall tracks current usage, not a stale batch       │
├──────────────────────────────────────────────────────────┤
│ 4. Continuous improvement                                 │
│    No `neuralmind learn` step — the graph grows as you     │
│    work.                                                   │
└──────────────────────────────────────────────────────────┘
```

## Step-by-Step Workflow

### Step 1: Enable Memory Logging

First-time only. When you run your first query, you'll be prompted:

```bash
$ neuralmind query . "How does authentication work?"

Enable local NeuralMind memory logging to improve retrieval over time? [y/N]: y
```

✅ Consent saved to `~/.neuralmind/memory_consent.json`

**To disable:** Set `NEURALMIND_MEMORY=0` (query event logging) and/or
`NEURALMIND_SYNAPSE_INJECT=0` (prompt-time synapse recall).

### Step 2: Install hooks and (optionally) the watcher

The synapse layer learns the most when it can observe your work. Install
the lifecycle hooks once, and optionally run the file watcher for
always-on learning from edits:

```bash
# One-time: install the lifecycle hooks (idempotent — safe to re-run)
neuralmind install-hooks .

# Optional: always-on learning from file edits
neuralmind watch &
```

### Step 3: Use NeuralMind Naturally

Just query and edit as usual. Co-activations are recorded automatically.

```bash
# Daily usage - these all reinforce the synapse graph
neuralmind query . "How does authentication work?"
neuralmind query . "What are the API endpoints?"
neuralmind query . "How is data validated?"
neuralmind query . "Where's the database logic?"
neuralmind query . "What's the error handling?"
```

Each query also logs (when memory is enabled):
- The question you asked
- Which modules were retrieved
- How many tokens were used
- Which communities matched

The query event log is a local, auditable record; the synapse layer is
what turns that activity into better recall.

### Step 4: Automatic Improvements

On later queries, the synapse layer surfaces associations it has learned
— including related code that pure vector search would not have found,
because the relationship is *behavioral* (learned from co-activation),
not textual. Synapse-driven hits are labelled in the L3 output — a
`[recalled]` tag for code surfaced purely via the learned graph, and a
`(+X.XX synapse)` annotation on hits whose score the graph boosted:

```bash
$ neuralmind query . "How does auth work?"

## Search Results

1. **authenticate** (score: 0.91)
   Type: function
   File: auth.py

2. **validate_user** (score: 0.85 (+0.25 synapse))  ← boosted by the learned graph
   Type: function
   File: auth.py

3. **check_permissions** [recalled] (score: 0.23)  ← surfaced purely via the graph
   Type: function
   File: middleware.py
```

### Step 5: Continuous Improvement

There is no weekly `neuralmind learn` step to run. The synapse store
grows continuously as you work, and `SessionStart` runs decay so weights
age between sessions. Inspect what's been learned at any time:

```bash
neuralmind stats .            # includes a synapse breakdown
neuralmind memory inspect .   # contribution by namespace
cat .neuralmind/SYNAPSE_MEMORY.md
```

## How synapse learning happens

Five activation paths, all of which strengthen pairwise edges between
co-active nodes (Hebbian: "nodes that fire together wire together"):

1. **Every `mind.query()`** — top search hits + loaded communities reinforce.
2. **`PostToolUse` hook** — when the agent reads/runs/searches code together.
3. **`UserPromptSubmit` hook** — current prompt's neighbors get an activation pulse.
4. **`SessionStart` hook** — runs decay so weights age between sessions, then exports memory.
5. **`neuralmind watch` daemon** — debounces file edits into co-activation batches; co-edited files wire together.

The synapse layer has been namespace-aware since v0.24.0:
`branch:<name>` / `personal` / `shared` / `ephemeral` memory live
separately in the same store, with a transparent merged read view. See
the [memory namespaces](CLI-Reference#neuralmind-memory) commands.

### What the synapse layer learns

The store is a weighted graph in SQLite (`.neuralmind/synapses.db`) with
two parts:

- An **undirected co-activation graph** — which nodes tend to be active
  together. Drives spreading-activation recall.
- A **directional transition table** (`synapse_transitions`, v0.11.0+) —
  ordered `(from_node, to_node)` observations, so the agent can ask
  `neuralmind next <file>` for a probability distribution over what's
  typically edited next.

Weights follow a Hebbian + decay + LTP (long-term potentiation) model:
co-activation strengthens an edge, disuse decays it, and frequently-used
edges are protected by an LTP floor so they don't evaporate.

### Surface in Claude Code

Each `SessionStart` re-exports the synapse memory as markdown to:

- `<project>/.neuralmind/SYNAPSE_MEMORY.md` — import in `CLAUDE.md`
  via `@.neuralmind/SYNAPSE_MEMORY.md` so it's part of every session.
- `~/.claude/projects/<slug>/memory/synapse-activations.md` — Claude
  Code's auto-memory directory (when present); the model picks it up
  natively without anyone calling an MCP tool.

## Privacy & Data

✅ **100% Local** — All learning happens on your machine
✅ **No Telemetry** — Nothing sent to servers
✅ **User Control** — One-time consent, can disable anytime
✅ **Persistent** — Memory stays in your `.neuralmind/` directory

### File Locations

```
~/.neuralmind/
├── memory_consent.json              # Consent flag (once per user)
└── memory/
    └── query_events.jsonl           # Global event log

project/.neuralmind/
├── memory/
│   └── query_events.jsonl           # Project-specific events
└── synapses.db                      # SQLite-backed Hebbian synapse store
```

### Environment Variables

```bash
# Disable query event logging
export NEURALMIND_MEMORY=0

# Disable prompt-time synapse recall injection
export NEURALMIND_SYNAPSE_INJECT=0

# Disable the auto-memory export
export NEURALMIND_SYNAPSE_EXPORT=0
```

You can also disable the layer entirely in Python with
`NeuralMind(..., enable_synapses=False)`, or wipe the learned graph at
any time with `mind.synapses.reset()`.

## Troubleshooting

### "No query events found"

**Problem:** `neuralmind stats .` or `neuralmind memory inspect .` shows
nothing learned.

**Solution:**
1. Have you run at least one query, or installed the hooks / watcher?
2. Did you consent to memory logging? You should see the prompt on first query.
3. Check the memory file exists: `ls -la project/.neuralmind/memory/query_events.jsonl`
4. Check `NEURALMIND_MEMORY` is not set to `0`.

### "Recall isn't surfacing related code"

**Problem:** You see no synapse-recalled hits in search results.

**Solution:**
1. The synapse graph needs to warm up — query, edit, and run tools over a
   few sessions, or run `neuralmind watch .` to learn from edits.
2. Check `NEURALMIND_SYNAPSE_INJECT` is not set to `0`.
3. Inspect the store: `neuralmind stats .` and `cat .neuralmind/SYNAPSE_MEMORY.md`.

## Best Practices

### 1. Natural Usage
```bash
✅ DO: Ask questions and edit code naturally as you work
neuralmind query . "How does user login work?"

❌ DON'T: Artificially create queries just to "train" the layer
```

### 2. Let the watcher run
```bash
✅ DO: Run neuralmind watch . so co-edits feed the synapse graph
neuralmind watch &

❌ DON'T: Expect rich recall from a cold store on day one
```

### 3. Meaningful Questions
```bash
✅ DO: Ask varied questions about your codebase
- "How does auth work?"
- "What are the API routes?"
- "How is data validated?"

❌ DON'T: Ask the exact same question repeatedly
```

### 4. Inspecting what's learned
```bash
✅ DO: Use the built-in inspectors to understand your code's associations
neuralmind stats .
neuralmind memory inspect .

❌ DON'T: Hand-edit synapses.db (it's managed by the layer)
```

## Performance Impact

Learning has **negligible overhead**:

- **Recall (spreading activation):** a few ms over the existing vector search
- **Reinforcement:** a small SQLite write, batched by the watcher
- **Storage:** a compact SQLite graph in `.neuralmind/synapses.db`

The untraced hot path pays nothing for trace/attribution machinery.

## The old reranker (removed in v0.25.0)

Before v0.25.0, NeuralMind also shipped a **`learned_patterns`
cooccurrence reranker**. You ran `neuralmind learn .` to analyze logged
query events, which wrote `.neuralmind/learned_patterns.json`, and the
next query re-ordered its L3 hits by a `+0.3` cooccurrence boost.

**It was removed** after a 2×2 A/B on the benchmark fixture showed it
added **0.0 points** to top-k hit rate whether the synapse layer was on
or off (71.7% → 71.7% cold, 83.3% → 83.3% warm), while the synapse layer
alone added **+11.6 points**. The reranker was also runtime-inert on the
warm path — the synapse boost re-sort discarded its ordering anyway — it
required the manual `neuralmind learn` step to populate, and its JSON
captured a snapshot that went stale between runs. The synapse layer is
strictly better on all three counts: automatic instead of manual,
decaying instead of staling, and the only mechanism with measured lift.

What this means for you:

- **`neuralmind learn`** is now an exit-0 deprecation no-op. Scripts and
  CI that call it keep working; you can drop the call when convenient.
- **`.neuralmind/learned_patterns.json`** is no longer read or written.
  An existing one is simply ignored and can be deleted.
- **`NeuralMind(enable_reranking=...)`** is accepted and ignored for
  backward compatibility.
- The L3 output **no longer prints `(+X.XX boost)` reranker labels**;
  synapse-recall labels are unchanged.

See the [v0.25.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/RELEASE_NOTES_v0.25.0.md)
for the full evidence and migration notes.

## What's Coming

- **Synapse import/export** — let teams share a learned brain (shipped as
  `neuralmind memory export/import` in v0.24.0).
- **Quality benchmark** — measure retrieval gain with vs without synapses
  (the self-benchmark's Phase 2 synapse A/B).
- **Feedback signals** — explicit ratings to further improve recall.

## See Also

- [CLI Reference](CLI-Reference) — All commands
- [Brain-Like Learning](../brain_like_learning.md) — design rationale
- [Architecture](Architecture#synapse-layer-v04) — synapse layer architecture
- [Troubleshooting](Troubleshooting) — Common issues
