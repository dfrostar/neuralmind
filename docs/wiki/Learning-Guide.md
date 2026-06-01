# Brain-Like Learning Guide

> How NeuralMind improves retrieval over time through the synapse layer

## Overview

NeuralMind's learning system improves as you use it — automatically, with
no manual step. The more you and your agent work in the codebase, the more
the **synapse layer** learns which code nodes belong together, and the
better recall gets.

Learning has two cooperating parts:

1. **Query-event memory log** — an opt-in, local record of the queries you
   run and which modules they retrieved. This is the raw signal of how the
   codebase is actually used.
2. **The synapse layer** — a continuous, decay-based associative memory
   (Hebbian: "nodes that fire together wire together"). It updates on every
   query, tool call, and file edit, strengthens frequently co-active
   associations, and forgets stale ones. This is the system that makes
   retrieval adapt to your team's behavior.

There is no batch "analyze my patterns" command — the synapse layer learns
live, in the background.

## Step 1: Enable Memory Logging

First-time only. When you run your first query, you'll be prompted:

```bash
$ neuralmind query . "How does authentication work?"

Enable local NeuralMind memory logging to improve retrieval over time? [y/N]: y
```

✅ Consent saved to `~/.neuralmind/memory_consent.json`

**To disable:** Set `NEURALMIND_MEMORY=0`

Each query logs:
- The question you asked
- Which modules were retrieved
- How many tokens used
- Which communities matched

These events are written to `.neuralmind/memory/query_events.jsonl` and feed
the synapse layer's co-activation signal.

## Step 2: Install the Lifecycle Hooks

The synapse layer learns from how your agent uses the codebase. Install the
Claude Code lifecycle hooks once (idempotent — safe to re-run):

```bash
neuralmind install-hooks .
```

This wires up `SessionStart`, `UserPromptSubmit`, `PreCompact`, and
`PostToolUse`, so co-activation is captured automatically as the agent
queries, reads, and runs code.

## Step 3 (optional): Run the File Watcher

For always-on learning from file edits, run the watcher daemon. Files that
are co-edited within a short window wire together:

```bash
neuralmind watch &
```

That's it — the synapse store grows continuously. Inspect what was learned:

```bash
cat .neuralmind/SYNAPSE_MEMORY.md
```

## How Synapse Learning Happens

Five activation paths, all of which strengthen pairwise edges between
co-active nodes (Hebbian: "nodes that fire together wire together"):

1. **Every `mind.query()`** — top search hits + loaded communities reinforce.
2. **`PostToolUse` hook** — when the agent reads/runs/searches code together.
3. **`UserPromptSubmit` hook** — current prompt's neighbors get an activation pulse.
4. **`SessionStart` hook** — runs decay so weights age between sessions, then exports memory.
5. **`neuralmind watch` daemon** — debounces file edits into co-activation batches; co-edited files wire together.

The synapse layer is an associative memory that can recall related code even
when vector search wouldn't have found it — because the relationship isn't
textual or graph-structural, it's *behavioral*, learned from co-activation.
It uses Hebbian strengthening, multiplicative decay so stale associations
fade, and an LTP (long-term potentiation) floor that protects frequently
used associations from decaying away.

## Surface in Claude Code

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
✅ **Persistent** — Everything stays in your `.neuralmind/` directory
✅ **Forgets stale patterns** — multiplicative decay ages unused edges

### File Locations

```
~/.neuralmind/
├── memory_consent.json              # Consent flag (once per user)
└── memory/
    └── query_events.jsonl           # Global event log

project/.neuralmind/
├── memory/
│   └── query_events.jsonl           # Project-specific events
├── synapses.db                      # Weighted associative graph (SQLite)
└── SYNAPSE_MEMORY.md                # Exported associations (markdown)
```

### Environment Variables

```bash
# Disable memory logging
export NEURALMIND_MEMORY=0

# Skip prompt-time synapse recall injection
export NEURALMIND_SYNAPSE_INJECT=0

# Skip the synapse auto-memory export
export NEURALMIND_SYNAPSE_EXPORT=0
```

You can also disable the synapse layer entirely in code with
`NeuralMind(..., enable_synapses=False)`, or wipe the learned graph any time
with `mind.synapses.reset()`.

## Troubleshooting

### "No query events found"

**Problem:** Memory logging doesn't seem to be recording anything

**Solution:**
1. Have you run at least 1 query? `neuralmind query . "test"`
2. Did you consent to memory logging? You should see a prompt on first query
3. Check the memory file exists: `ls -la project/.neuralmind/memory/query_events.jsonl`
4. Check `NEURALMIND_MEMORY` is not set to `0`

### "Synapses aren't growing"

**Problem:** `SYNAPSE_MEMORY.md` stays empty or `synapses.db` doesn't change

**Solution:**
1. Install the hooks: `neuralmind install-hooks .`
2. For file-edit learning, make sure `neuralmind watch` is running
3. Check the layer isn't disabled (`enable_synapses=False`)
4. Synapses need a few sessions of real usage before associations surface

## Best Practices

### 1. Natural Querying
```bash
✅ DO: Ask questions naturally as they come up
neuralmind query . "How does user login work?"

❌ DON'T: Artificially create queries just for learning
```

### 2. Keep the Hooks Installed
```bash
✅ DO: Run install-hooks once per project so co-activation is captured
neuralmind install-hooks .

❌ DON'T: Expect learning without the hooks or watcher running
```

### 3. Meaningful Questions
```bash
✅ DO: Ask varied questions about your codebase
- "How does auth work?"
- "What are the API routes?"
- "How is data validated?"

❌ DON'T: Ask the exact same question repeatedly
```

### 4. Let It Run
```bash
✅ DO: Let the synapse layer accumulate signal over days/weeks of usage
❌ DON'T: Hand-edit synapses.db or SYNAPSE_MEMORY.md (they're auto-generated)
```

## What's Coming

- **Synapse import/export** — let teams share a learned brain.
- **Quality benchmark** — measure retrieval gain with vs without synapses.
- **Auto-watcher launch from `SessionStart`** — no manual `watch` invocation needed.
- **Feedback signals** — explicit ratings improve association accuracy.

## See Also

- [CLI Reference](CLI-Reference) — All commands
- [Architecture](Architecture#synapse-layer-v04) — synapse layer architecture
- [Troubleshooting](Troubleshooting) — Common issues
