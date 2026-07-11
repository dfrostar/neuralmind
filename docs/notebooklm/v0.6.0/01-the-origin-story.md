# Why NeuralMind exists, and what v0.6.0 changes

*Founder-narrative source for the NotebookLM video. First-person,
conversational. Use as the "why does this exist" arc.*

---

I started NeuralMind because my Claude Code bill was climbing past
two hundred dollars a month on a single project and I wanted to
understand why. The answer was depressingly simple: every code
question loaded about fifty thousand tokens of context. The model
needed maybe a thousand of them. I was paying for the model to
re-read my entire codebase to answer "how does the auth middleware
work."

That's the problem in one sentence. Loading the whole codebase to
answer a small question is like reading the entire book to look up
one fact. Indexes have existed for centuries for exactly this
reason. We just hadn't built one for AI coding agents yet.

So I built one. The retrieval side was conceptually unremarkable —
a vector index over the call graph, a four-layer progressive
disclosure thing where the smallest layer is the project identity
and the largest is the semantic search results. The numbers were
nice: forty to seventy times reduction per query on real codebases.
That gets you a 30-second demo and a small but real audience of
developers who'd been quietly cursing their token bills.

But somewhere around version 0.4, I started thinking about the
problem differently. Retrieval is not the only thing brains do. The
human brain doesn't just *look up* memories — it also *learns
associations*. Things that fire together wire together. The auth
middleware and the user model become linked, in your head, because
you keep thinking about them together. The next time someone asks
you a question about authentication, the user model surfaces too,
without you having to "look it up."

I wanted that for code. So I built a second brain alongside the
retrieval brain — a persistent weighted graph that lives in a SQLite
file in your project. Every time the agent uses two pieces of code
together, the edge between them gets a little heavier. Edges decay
if they go unused, like real synapses. Frequently-used edges get
protection from decay, like long-term potentiation. When a new
question comes in, "activation" spreads through the learned graph
and surfaces related code that pure vector search would never find.

That's the conceptual leap. NeuralMind isn't just a retrieval index
anymore. It's an associative memory that gets sharper the longer
it runs on your codebase. The agent never sees the weights
directly. It just gets better context.

The hard part, and the reason version 0.6.0 matters, is that "the
agent has a learning memory" is a *claim*. It's not visible. It's
not falsifiable. If you install NeuralMind and your agent feels a
little smarter a week later, you can't tell whether the synapse
layer helped or whether you just got used to the tool. That gap
between "we built this" and "you can see it working" is the gap
where most software dies.

So in 0.6.0, we made the brain *legible*. There's a `neuralmind
serve` command that opens an Obsidian-style force-directed graph of
your codebase in the browser — every code node, every structural
edge, every learned synapse. That part shipped in 0.5.4. What's new
in 0.6.0 is that the graph is now *alive*. When the agent uses a
piece of code, the corresponding node *pulses* on the canvas. When
you save a file in your editor, the relevant nodes pulse. The
sidebar logs the events as they happen.

You can sit there, in real time, and watch the hippocampus learn
your codebase. That's the moment when "code RAG" turns into
"associative memory for your codebase." It's also the moment the
pitch flips. Before 0.6.0, the headline was a number: "forty to
seventy times fewer tokens." After 0.6.0, there's a *second*
headline, and it's a verb: *see the brain learning*. The number is
still there — it's still the measurable claim that justifies the
install — but there's now a visceral demo behind it.

There's a third thing in 0.6.0 that's quieter but maybe more
important long-term. We added a cross-process activity bridge — a
small JSON-lines file in `.neuralmind/events.jsonl` that lets
different processes feed into the same live feed. That sounds dull
until you realize what it enables: if you run Claude Code in one
terminal, OpenClaw in another, and the `neuralmind watch` daemon in
a third, all three are reinforcing the same synapse store. The
graph view shows the union of their activity. The brain is shared.

Pre-0.6.0, you couldn't see that. The synapse weights were getting
updated by every agent, but the experience was three separate tools
talking to a black box. Now there's one canvas, and any tool call
from any agent makes a node pulse. The brain isn't just learning
your codebase; it's learning your codebase across every tool you
use. That's a feature you couldn't have shipped in 0.5.4 because
the user couldn't perceive it.

So that's where we are. The retrieval index is the cortex — useful,
unsurprising, well-understood. The synapse layer is the
hippocampus — newer, weirder, and now finally visible. And the
graph view is the eye you point at the hippocampus to see it work.

The next thing on my list is making the graph view *useful for
debugging*. When an agent answers wrong, the natural question is:
"what did it actually look at?" The replay-last-query overlay
that shipped in 0.6.0 is the first step — it highlights the L3 hits
the agent received on its last query, so you can see whether
retrieval pulled the right nodes. The plan from here is to extend
that into a full audit trail: every query, every tool call, every
file edit, all timestamped, all replayable on the canvas. If
NeuralMind is going to be the shared memory layer underneath your
agents, it has to be inspectable. That's the long-term bet.

If you're a developer who's been watching your Claude or Cursor
bill climb, or if you're someone who's noticed that AI agents do
the same thing wrong over and over because they keep "forgetting"
what they learned about your codebase, this is for you. It's free,
it's MIT-licensed, and it runs entirely on your machine. The thirty
second demo is `bash scripts/demo.sh` on a fresh clone. If the
numbers move for you, install it for real. If they don't, the
honest assessment doc explains when NeuralMind isn't worth the five
minutes of setup — small codebases, low-volume LLM use, you don't
pay per token. We're not trying to convince everyone. We're trying
to be useful to the people for whom this is genuinely useful.

That's NeuralMind, in 2026, at version 0.6.0. The brain has a
window now. You can look in.
