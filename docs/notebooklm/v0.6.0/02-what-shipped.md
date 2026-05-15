# What ships in NeuralMind v0.6.0

*Technical feature-tour source for the NotebookLM video. Neutral
third-person, concrete. Use as the "what's actually in the box"
arc.*

---

NeuralMind 0.6.0 is a single coherent feature release. The headline
is the live activity feed in `neuralmind serve`, but the release
ships eight closely related improvements that together turn the
browser-based graph view from "a static map of your codebase" into
"a live observatory for the synapse layer." Here's what each piece
does and where it shows up.

## The live activity feed

`neuralmind serve` starts a small local web server — stdlib HTTP,
no external dependencies — that renders a force-directed graph of
the project in the browser. In 0.5.4, that view was a snapshot.
You could click nodes, see backlinks and synaptic neighbors,
search semantically, and open files in your editor, but the canvas
didn't change unless you refreshed it.

In 0.6.0, the canvas is live. The server exposes a long-lived
Server-Sent Events stream at `/api/events`. Two things publish to
the stream automatically. First, the synapse store: every time
`SynapseStore.reinforce()` is called — meaning the brain learned
something — it publishes a `synapse` event with the pair of nodes
that just got connected. Second, the file activity watcher: every
time a batch of file edits is coalesced into a single
co-activation event, it publishes a `file_activity` event with the
affected nodes.

The browser side does two things with that stream. It draws short
animated radial pulses around each node referenced in a recent
event — color-coded by event source, synapse versus file activity —
and it logs the most recent eighty events in a sidebar feed with
timestamps. Click a sidebar entry, and the corresponding node
focuses on the canvas.

The effect is hard to convey in prose. You watch a node flash the
instant you save a file in your editor. You see a cluster of nodes
light up when you run a build that touches twenty modules at once.
You see synapse events fire when the agent calls `neuralmind_query`
and the brain reinforces the co-activated hits. The graph
visibly *throbs*. The phrase that keeps coming up in early feedback
is "second screen for my agent."

## The cross-process JSONL bridge

The in-process event bus is great when `serve` and the activity
source live in the same Python process. The common real-world case
is not that. You run `serve` in one terminal, the `neuralmind
watch` daemon in another, and a Claude Code session in a third —
three processes, three sources, one canvas that you'd like to show
all of them.

0.6.0 adds a deliberately boring side channel. When the event bus
publishes, it also appends a JSON line to
`<project>/.neuralmind/events.jsonl`. The `serve` process tails that
file in a background thread and re-emits any events it didn't
originate. Net result: every process talking to the same project
contributes to the same live feed.

The design choice worth noting is that the JSONL bridge is a
*fallback*, not a queue. The in-process bus is still the primary
path; the file is best-effort and reconstructs itself if it
disappears or rolls. The environment variable
`NEURALMIND_EVENT_LOG=0` disables the writer if you want the
in-process feed only.

The unlock here is bigger than it looks. Pre-0.6.0, running Claude
Code, OpenClaw, and Hermes-Agent against the same project meant
three tools reinforcing the same synapse store but no way to *see*
the union of their activity. With the JSONL bridge, you get one
canvas showing every tool call from every agent. NeuralMind
becomes the shared memory layer underneath the polyglot agent
stack.

## Pin glyph plus Pin/Unpin button plus Unpin-all

The graph view has had drag-to-pin since 0.5.x. Hold a node, drag
it where you want it, and it stays there across re-renders.
Useful, but invisible — you couldn't tell at a glance which nodes
were pinned versus which had just settled there because of the
force-directed layout.

0.6.0 surfaces the state. Every pinned node renders a warm-colored
pin marker. The node detail panel grows a Pin/Unpin toggle for
the focused node. The sidebar gets an Unpin-all button for
resetting layout. Small change, large daily quality-of-life impact
for anyone using the graph view to maintain a curated "auth tour"
or "data layer view."

## Cmd/Ctrl-K and forward-slash for quick-switch

Two new keyboard shortcuts both focus the semantic search field
from anywhere on the page. Cmd-K and Ctrl-K work for the
power-user crowd; forward-slash for the vim-flavored. Escape
clears the search field and blurs the focus.

The motivation: in a force-directed graph with hundreds or
thousands of nodes, mouse-based navigation breaks down fast.
Semantic search is the fastest path between any two nodes, and
0.6.0 makes it always one keystroke away.

## Local-graph depth slider

The graph view has a "show only the local neighborhood" toggle
that hides all but the nodes within one hop of the focused one.
0.6.0 adds a depth slider that ranges from one to three hops,
breadth-first from the focused node. Default is one, so existing
behavior is unchanged. The slider uses the standard `disabled`
attribute when the parent toggle is off, so it stays visibly
inert.

The expected use: depth one for "what does this function talk to
directly," depth two for "what's in this function's tactical
neighborhood," depth three for "what's the architectural cluster
this function lives in." Past three hops, force-directed layouts
on a real codebase become an unreadable hairball, so the slider
caps at three by design.

## Replay-last-query overlay

The detail panel grows a "Replay last query" action that
re-highlights the L3 hits the agent most recently received. This
is the trust-gap closure feature. When a retrieval feels wrong —
the agent answered with the wrong file, or missed the obvious
function — you can pop the graph view, hit replay, and *see* which
nodes the model actually got. Often the answer is obvious as soon
as it's visible: a stale cluster boundary, a missing edge, an
unexpected hub. Without the overlay, you'd be debugging by
reading log files.

## Edge tooltips and the min-weight synapse slider

Hover any edge to see the relationship type — call, import, or
synapse — and for synapses, the current weight and activation
count. The synapse-overlay toggle now has a companion slider that
filters edges below a configurable minimum weight, so the canvas
isn't cluttered with thousands of low-weight noise links when
you're trying to see the structural backbone.

## Docs refresh and positioning

The roadmap, the README hero, the landing page, the about page,
and the wiki all reframe NeuralMind's positioning around the
graph view. Pre-0.6.0, the graph view was treated as a side
feature underneath the headline 40-70x token reduction. Post-0.6.0,
it's a second pillar: the reduction number is the *measurable*
claim, the graph view is the *visceral* claim. Both land.

## What's *not* in 0.6.0

A few things that came up during scoping but didn't ship, tracked
for 0.7: saved named views (filter plus zoom plus depth combos
persisted in localStorage), right-click context menus on nodes,
PNG and SVG export of the canvas, and a time-based edge filter
that complements the new min-weight slider with a "last N days"
view. The synapse store already records `last_activated`, so that
last one is a frontend-only follow-up.

## Compatibility

No breaking changes. Same `graph.json` format, same `synapses.db`
schema, same hook registration. If you ran `neuralmind serve`
before, you already know 0.6.0 — it's just alive now. The CLI
surface is unchanged. The MCP tool surface is unchanged. The
on-disk state is forward-compatible. The `events.jsonl` file is
new and self-creating. Python 3.10, 3.11, and 3.12 all pass CI.

The upgrade is `pip install --upgrade neuralmind`. Open
`neuralmind serve`, watch the canvas, save a file. That's the
demo and the verification in one motion.
