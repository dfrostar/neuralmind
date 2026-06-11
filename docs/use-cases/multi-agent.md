# Use Case: Multi-Agent Codebase (shared memory across tools)

## What you're solving for

You don't use just one AI coding tool. You use Claude Code for the
work you live in, Cursor when you want inline completions, OpenClaw
or Hermes-Agent for one-off automations, maybe Claude Desktop for
the chat-flavored questions. Each one is great at what it does.
None of them learn from the others.

You want a **shared memory layer** underneath all of them — a
single place where co-activations, file edits, and tool calls
reinforce the same brain, so the smarter your Claude Code session
gets, the smarter your Hermes session gets, automatically.

That's what NeuralMind v0.6.0 unlocks. It was *technically* true
in v0.5.x — every agent talking to the project hit the same
`synapses.db` — but you couldn't see it. v0.6.0 makes the union
visible.

## The shared substrate

Every agent that uses NeuralMind talks to the same three pieces of
local state:

- `graphify-out/graph.json` — the call graph (created by graphify)
- `graphify-out/neuralmind_db/` — the ChromaDB vector index
- `<project>/.neuralmind/synapses.db` — the learned synapse graph

There's no per-agent partition. When Claude Code calls
`neuralmind_query`, the brain reinforces the co-activated nodes.
When Hermes-Agent calls the *same tool* an hour later in a separate
process, the brain *also* reinforces. They're talking to the same
SQLite file.

In v0.5.x, that was an implementation detail. In v0.6.0, it's a
feature you can see.

## Setup (one-time, per project)

```bash
pip install neuralmind
cd your-project
neuralmind build .
```

That's the shared substrate. Now wire up every agent you use:

**Claude Code:**

```bash
neuralmind install-hooks .
```

Registers `PostToolUse` compression + `SessionStart` / `UserPromptSubmit` /
`PreCompact` synapse hooks. Auto-active in every session.

**Claude Desktop:** Edit `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "neuralmind": {
      "command": "neuralmind-mcp",
      "args": ["/absolute/path/to/project"]
    }
  }
}
```

**Cursor / Cline / Continue:** Drop a `.mcp.json` at the project root:

```json
{ "mcpServers": { "neuralmind": { "command": "neuralmind-mcp", "args": ["."] } } }
```

**Hermes-Agent:**

```bash
hermes mcp add  # or edit ~/.hermes/config.yaml
```

**OpenClaw:**

```bash
openclaw mcp set neuralmind '{"command":"neuralmind-mcp","args":["/absolute/path/to/project"]}'
```

All five point at the same project. Same MCP tools (`neuralmind_wakeup`,
`_query`, `_skeleton`, `_search`, ...). Same `.neuralmind/synapses.db`.

## The new v0.6.0 superpower: see the union

```bash
neuralmind serve .
```

Opens `http://127.0.0.1:8765/?token=…` in your browser — a
force-directed graph of the codebase with the learned synapse
overlay. Pre-v0.6.0, that was a static snapshot.

In v0.6.0, the canvas is **live**. Every time *any* agent — Claude,
Cursor, Hermes, OpenClaw — calls a NeuralMind MCP tool, the relevant
nodes pulse on the canvas in real time. The sidebar feed logs the
event with a timestamp.

The trick that makes this work across processes is the JSONL bridge
([`event_log.py`](../../neuralmind/event_log.py), shipped in
v0.6.0). Each `event_bus.publish()` call appends a line to
`<project>/.neuralmind/events.jsonl`. The `serve` process tails that
file and re-emits anything it didn't originate. Net result: one
canvas, all agents, no IPC complexity.

Opt out of the bridge with `NEURALMIND_EVENT_LOG=0` (you still get
the in-process feed for the agent that's running `serve` itself).

## A two-week walkthrough

**Day 1.** Set up the substrate. Wire up Claude Code + Cursor +
OpenClaw. Pop `neuralmind serve` in a browser tab.

**Day 2.** You use Claude Code as usual. Every prompt that triggers
a NeuralMind tool call pulses nodes on the canvas. You notice the
auth cluster lighting up a lot.

**Day 3.** Cursor finishes a refactor across five files. Save-on-edit
fires file activity events; nodes pulse. The synapse edges between
those five files strengthen.

**Day 4.** You ask Hermes-Agent to run a one-off audit. It calls
`neuralmind_query` against the same project. The auth cluster
pulses — because that's where Hermes started looking too. The
synapse store reinforces *those* co-activations.

**Day 7.** You ask Claude Code "how does billing flow through the
codebase?" Spreading activation now surfaces three files that
didn't even semantically match — they came from the Cursor refactor
and the Hermes audit a few days earlier. The agent's answer is
visibly better because the brain has learned from all three tools.

**Day 14.** The graph view's pulse density now visibly concentrates
around the parts of the codebase you actually live in. Dead corners
have decayed. Hub nodes are protected by LTP. You haven't done
anything special. You just used your tools normally.

That's the multi-agent story. NeuralMind is the shared associative
memory; the live graph is how you watch it work; the JSONL bridge
is what makes it work across processes.

## What you should pin on the canvas

The graph view supports persistent pins (drag a node, it stays).
v0.6.0 adds a visible pin glyph + Pin/Unpin button + Unpin-all.

Useful pins for a multi-agent workflow:

- **Project entry point(s).** They anchor the layout.
- **The "domain core"** — the few hub nodes everything else
  depends on.
- **Whatever the agent keeps getting wrong.** Pin it, ask the
  agent again, watch the canvas to see whether it actually hits
  the right node this time. If not, the replay-last-query overlay
  shows you which nodes it *did* hit. Often the fix is updating
  `CLAUDE.md` or rebuilding the index.

## What it's *not*

- **Not a database.** Synapse weights are derived state. If you
  blow away `<project>/.neuralmind/`, the brain forgets — but the
  next week of normal use rebuilds it. There's no migration cost.
- **Not a cross-repo brain.** Each project has its own
  `synapses.db`. NeuralMind is per-project local-first by design.
- **Not a network protocol.** The JSONL bridge is single-machine.
  Two developers on different machines have two independent
  brains; sharing a brain across machines would require
  `synapses.db` import/export (tracked for v0.7).
- **Not a queue.** The bridge is best-effort. If you need
  guaranteed delivery between agents, that's not what this is.

## Related env vars

| Variable | Default | Effect |
|----------|---------|--------|
| `NEURALMIND_EVENT_LOG` | `1` | `0` disables JSONL writer (in-process feed still works) |
| `NEURALMIND_SYNAPSE_INJECT` | `1` | `0` disables spreading-activation context injection on `UserPromptSubmit` |
| `NEURALMIND_SYNAPSE_EXPORT` | `1` | `0` disables session-start memory export |
| `NEURALMIND_BYPASS` | unset | `1` disables PostToolUse compression for one command |

---

[← Back to use-case index](./README.md) · [Main README](../../README.md) ·
[Architecture: synapse layer + event bus](../../docs/wiki/Architecture.md#synapse-layer-v04)
