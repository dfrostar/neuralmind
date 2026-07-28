# NeuralMind v0.6.0 — see the brain learning your codebase

**Release Date:** May 2026

## TL;DR

`neuralmind serve` is no longer a static graph view. It now pulses
in real time as the synapse layer learns from your file edits, your
Claude Code prompts, and your queries. Synapse and file events stream
to the browser over SSE; affected nodes flash on the canvas; a
sidebar log keeps the most recent ~80 events. A cross-process JSONL
bridge means a separate `neuralmind watch` daemon, hook-driven Claude
Code session, or any other process feeds the same live feed.

The pitch flipped. v0.5.4 was "Obsidian-style graph view over your
code." v0.6.0 is "**watch the hippocampus learn your codebase, live.**"

No migration. Same `graph.json`, same `synapses.db`, same hooks. If
you ran `neuralmind serve` before, you already know v0.6.0 — it's
just alive now.

## What's new

### Live activity feed

`neuralmind serve` now exposes `/api/events` — a long-lived
Server-Sent Events stream subscribed to an in-process event bus. The
synapse store publishes a `synapse` event on every pair-touching
`reinforce()` call; the file watcher publishes a `file_activity`
event on every coalesced edit batch.

The browser side does two things with that stream:

- **Canvas pulse rings.** Every node referenced in a recent event
  gets a short, animated radial pulse — colour-coded by event source
  (synapse vs file activity). Multiple pulses stack so a hot subgraph
  visibly *throbs* without being annoying.
- **Sidebar log.** The most recent ~80 events render as a scrolling
  feed with timestamps, event type, and node ids. Click an entry to
  focus the corresponding node on the canvas.

`event_bus.publish()` is O(1) when there are no subscribers and no
JSONL writer configured — emit-points cost nothing on headless servers
or CLI-only runs.

### Cross-process activity bridge

The in-process bus is great when `serve` and the activity source live
in the same Python process. The common real-world case is *not* that:
you run `neuralmind serve` in one terminal and `neuralmind watch` in
another, or your Claude Code session triggers synapse events in a
completely separate process from the long-running server.

v0.6.0 adds a deliberately boring side channel: each `event_bus.publish()`
call also appends to `<project>/.neuralmind/events.jsonl`, and the
`serve` process tails that file and re-emits anything it didn't
originate. Net result: one canvas, all sources, no IPC complexity.

Behaviour controls:

- `NEURALMIND_EVENT_LOG=0` disables the writer (you still get the
  in-process feed).
- The tailer is best-effort; if the file disappears or rolls, the
  next event re-creates it.
- The bus stays the primary path. The JSONL bridge is the fallback,
  not a queue.

### Visible pin glyph + Pin/Unpin button + Unpin-all

Drag-to-pin has saved layout positions since v0.5.x, but you couldn't
tell at a glance which nodes were pinned. v0.6.0:

- Every pinned node renders a warm-coloured pin marker.
- The detail panel shows a Pin / Unpin toggle for the focused node.
- The sidebar has an "Unpin all" button for resetting layout.

### Quick-switch shortcuts

`Cmd/Ctrl-K` and `/` both focus the semantic search field from
anywhere on the page. `Esc` clears the field and blurs.

### Local-graph depth slider

The "show only local neighborhood" toggle now has a depth slider:
1–3 hops via BFS from the focused node. Defaults to 1, so existing
behavior is unchanged. When the parent toggle is off, the range
slider sets `disabled` so it stays visibly inert.

### Replay-last-query overlay

The detail panel grew a "Replay last query" action that re-highlights
the L3 hits the agent most recently received. Useful for closing the
trust gap when a retrieval feels wrong — you can see what the model
actually got, on the same canvas you use to navigate the codebase.

### Edge tooltips + min-weight synapse slider

Hover any edge to see the relationship type (call, import, synapse)
and, for synapses, the weight and activation count. A new slider
below the synapse-overlay toggle filters edges below a minimum weight,
so the canvas isn't noisy when you have thousands of low-weight links.

## Why this is a different pitch

v0.5.4 made the brain *inspectable*. v0.6.0 makes it *legible*.
"The agent has a learning memory" is a claim. Watching a node flash
the instant you save a file in your editor is evidence.

For people deciding whether to install NeuralMind, the demo that
matters now is:

1. `neuralmind query` — show the 40–70× per-query token reduction
   (still the headline measurable claim).
2. `neuralmind serve` — pop the graph view, scroll around the
   codebase.
3. Edit a file in another terminal — pulse rings fire on the canvas
   in real time.

That third beat is where "code RAG" becomes "associative memory
for your codebase." It's also the screenshot/clip that anchors the
v0.6.0 LinkedIn and screencast assets (see
[`docs/LINKEDIN-POST-DRAFT.md`](docs/LINKEDIN-POST-DRAFT.md) and
[`docs/SCREENCAST-v0.6.0.md`](docs/SCREENCAST-v0.6.0.md)).

## Upgrading

```bash
pip install --upgrade neuralmind
```

That's it. No data migration, no config changes, no hook reinstall.
Open `neuralmind serve` and the live feed is on by default.

### Opting out

| Want to skip… | Set |
|---------------|-----|
| The JSONL bridge (process-local feed only) | `NEURALMIND_EVENT_LOG=0` |
| Synapse-prompt context injection | `NEURALMIND_SYNAPSE_INJECT=0` |
| Synapse memory export | `NEURALMIND_SYNAPSE_EXPORT=0` |
| All hook-time work | `NEURALMIND_BYPASS=1` |

## Compatibility

- **CLI**: no breaking changes. All v0.5.x commands behave identically.
- **MCP tools**: unchanged.
- **On-disk state**: `synapses.db` and the ChromaDB index are
  forward-compatible. `events.jsonl` is new and self-creating.
- **Hooks**: same registration as v0.5.x. The `PostToolUse` /
  `SessionStart` / `UserPromptSubmit` / `PreCompact` blocks are
  unchanged.
- **Python**: 3.10, 3.11, 3.12 all pass CI.

## What's next (graph-view follow-ups)

> Note (updated post-v0.7.0): v0.7.0 ended up being the "Install
> Anywhere" release; v0.8 is "Always-On". The graph-view backlog
> below moved to ROADMAP's [`Graph-view backlog (v0.8 or later)`](ROADMAP.md#graph-view-backlog-v08-or-later)
> section.

Originally tracked in [`ROADMAP.md`](ROADMAP.md) under "Now (v0.7)":

- **Saved views.** Obsidian-style named filter/zoom/depth presets,
  persisted in `localStorage`.
- **Right-click context menu on nodes.** Surface the detail-panel
  verbs (open-in-editor, pin/unpin, focus, copy id) where mouse-driven
  users expect them.
- **PNG / SVG export** of the canvas, for design docs and PRs.
- **Time-based edge filter.** `synapses.last_activated` is already
  persisted — pair it with the v0.6.0 min-weight slider for a "last
  N days" view.
- **Unify `neuralmind watch` with the in-process bus** when they
  share a process, so the JSONL bridge becomes a pure cross-process
  fallback.

## Verification

Smoke against this release:

```bash
pip install neuralmind==0.6.0 graphifyy
cd your-project
graphify update . && neuralmind build .
neuralmind serve .                              # terminal 1
neuralmind watch . --quiet                      # terminal 2
$EDITOR src/whatever.py                         # save, then watch terminal 1's
                                                # canvas — affected nodes pulse.
```

If the canvas stays quiet, see the FAQ entry in the wiki:
"Why does my serve canvas stay quiet when I edit files?"

## Thanks

The v0.5.x graph-view foundation made this release straightforward —
the synapse store already published the right signals, the watcher
already coalesced edits, and the only missing pieces were the
subscription bus, the SSE endpoint, and the canvas pulse renderer.
That's a small surface for a release that changes the pitch.
