---
title: "NeuralMind vs. Hindsight — and running both"
description: "Hindsight (vectorize-io) gives coding agents an LLM-written memory of conversations, commits and decisions; NeuralMind indexes the code itself and learns which parts are used together. Where they overlap, where they don't, and what to expect when Claude Code or Hermes runs both."
---

# NeuralMind vs. Hindsight

> **TL;DR** — Mostly complementary. Hindsight remembers *what happened*:
> facts, conversations, commit history, and LLM-written pages about the
> repo (a component map, conventions, key decisions). NeuralMind knows
> *where things are*: a parsed graph of the code, ranked retrieval against a
> question, and associations learned from which files you edit and ask about
> together. They overlap in three places: both keep engineering decisions,
> both carry one session into the next, and both add context to every
> prompt. Running both costs two blocks of context per turn, and we haven't
> tested them together. Every Hindsight detail below comes from its README
> and docs as read on 2 November 2026, not from running it.

## What Hindsight is

[Hindsight](https://github.com/vectorize-io/hindsight) (vectorize-io, MIT,
about 57.7k GitHub stars on 2 November 2026, up from 23.9k in September) is
an agent memory system built on three operations:

- **retain**: an LLM extracts facts, entities, relationships and temporal
  data from what it's given, and indexes them.
- **recall**: four searches in parallel, semantic, BM25 keyword, graph
  (entity, temporal and causal links) and time range, merged.
- **reflect**: a deeper pass over the memories, for questions that need
  synthesis rather than lookup.

In the background it consolidates facts into *observations* (beliefs kept
with their supporting quotes) and maintains *mental models* and *knowledge
pages*: standing answers it rewrites as the bank learns, which an agent
reads without an LLM call.

Writing memory needs an LLM. Hindsight supports 25+ providers, local ones
included (Ollama, LM Studio, llama.cpp), and existing subscriptions such as
Claude Pro/Max through its `claude-code` provider, which needs no API key.
Storage is PostgreSQL with pgvector, or Oracle AI Database; the Docker image
and the `hindsight-all` Python package bundle an embedded Postgres (pg0), so
a separate database server is optional. Hindsight Cloud is the hosted
option.

Its headline evidence is LongMemEval, a benchmark of memory across long
conversations. Its README's January 2026 table puts it first among the memory
systems listed, and says the Virginia Tech Sanghani Center and The Washington
Post reproduced its results; the other systems' scores are self-reported.

### Hindsight for coding agents

The part that sits next to NeuralMind is the
[coding-agents package](https://hindsight.vectorize.io/sdks/integrations/coding-agents)
(`npx @vectorize-io/hindsight-coding-agents install`). It wires itself into
Claude Code, Codex CLI, Cursor CLI, GitHub Copilot CLI, opencode, Cline CLI
and several more, and replaced Hindsight's earlier Claude Code integration,
which is no longer maintained. For each repo it:

- seeds a memory bank from git history: commit messages by default,
  per-commit diffs with `gitIngest: "full"`, the newest 300 commits;
- runs a one-time headless "codebase survey" of a cold repo through the
  agent's own CLI (for Claude Code, `claude -p --model haiku` with a $2
  cap), and re-runs it every 20 commits;
- keeps five knowledge pages (component map, core concepts, conventions and
  patterns, key decisions and rationale, initiatives and enhancements), each
  refreshed by one LLM synthesis when stale, hourly by default;
- writes each session's transcript back to the bank when the agent stops;
- injects a low-budget reflect on a session's first prompt (a 2,000-token
  recall budget by default) and the page roster and tool guide on each turn.

The package stores the bank in Hindsight Cloud by default; a self-hosted
server or a local daemon are the alternatives.

In Hermes, Hindsight is a native
[memory provider](https://hermes-agent.nousresearch.com/docs/plugins/hindsight)
(`memory.provider: hindsight`), cloud by default, with local-embedded and
local-external modes. By default it recalls before every turn (observations
only, capped at 4,096 tokens) and retains every turn's conversation.

## How NeuralMind differs

**What's remembered.** Hindsight's memory of a repo is text an LLM wrote:
facts pulled from commits and transcripts, and pages summarizing the
codebase from a survey. NeuralMind's is parsed. Tree-sitter builds a graph
of the code (ten languages plus JavaScript), embeddings run locally, and
retrieval returns the files and functions that answer a question: 670–961
mean tokens per question on the public benchmark, which finds the gold file
on 40 of 40 queries at v4.12.0 (the 150-question retrieval eval misses 10).
On top of that, the [synapse layer](../wiki/Synapse-Module.md) learns which
files are edited and asked about together, by Hebbian co-activation, with no
model call.

So Hindsight's component map can tell an agent which directory owns
authentication and how sessions are stored. NeuralMind can hand it the
functions, with line numbers, in the files that answer the question it just
asked. Hindsight's map is as current as its last survey; NeuralMind's index
is as current as its last build, which the git hooks `neuralmind init-hook`
installs rerun after commits, merges, checkouts and rebases.

**Who writes memory.** Hindsight extracts automatically, so it keeps things
nobody asked it to: a real advantage. NeuralMind's decision memory holds only
what an agent or developer records with `neuralmind decisions record`, and
its synapses learn from activity (edits and prompts), not from reading the
conversation.

**What writing costs.** Every Hindsight retain and every knowledge-page
refresh is an LLM call, which a local model or an existing subscription can
serve. NeuralMind's indexing, recall and learning make no model calls.

**Where it lives.** The coding-agents package defaults to Hindsight Cloud,
so commit messages and session transcripts go to a bank there unless you
pick the daemon or self-host. NeuralMind keeps its state in the project's
`.neuralmind/` and by default sends no telemetry and transmits no repository
content off your machine.

**What each one measures.** Hindsight measures conversation memory
(LongMemEval). NeuralMind measures code retrieval (gold-file recall).
Neither has published a number on the other's axis, and no head-to-head is
possible under our fairness contract,
[`evals/public/COMPETITORS.md`](../../evals/public/COMPETITORS.md), which
needs a tool that returns ranked files. Hindsight doesn't.

## Where they overlap

1. **Engineering decisions.** Hindsight's "key decisions and rationale" page
   is synthesized from transcripts and commits. NeuralMind's
   [Memory Layer](../wiki/Memory-Layer.md) records decisions explicitly, ties
   each one to the files it affects, marks it stale when those files change,
   and warns the agent before it edits a file a stale decision governs (the
   [`PreToolUse` guard](../wiki/Memory-Layer.md#stale-decision-guard-v420)).
   With both running, one decision can surface twice in different words.
2. **Session continuity.** Hindsight writes the whole transcript back to the
   bank. NeuralMind's [recap](../use-cases/pick-up-where-you-left-off.md)
   carries the previous session's prompts and edited files into the next
   one. Both answer "where did we stop?".
3. **Prompt-time context.** In Claude Code both hook the start of a session
   and every prompt; in Hermes both add to the turn. That's two blocks of
   context per prompt.

Outside those three, they don't answer the same questions. Hindsight has no
ranked code retrieval or call graph, and NeuralMind remembers nothing about
a person or a conversation.

## Running both

We haven't tested them together. From the two sides' docs:

- **Claude Code.** Each installs its own hooks; neither removes the other's.
  On each prompt NeuralMind adds a short list of the files the prompt
  matches, the code linked to them and matching docs, with at most one
  40-line excerpt. Hindsight adds a reflect of up to 2,000 tokens on the
  first prompt and its page roster after. Check what the two add per turn
  before keeping both on. `NEURALMIND_SYNAPSE_INJECT=0` turns off
  NeuralMind's prompt-time block while keeping its MCP tools.
- **Hermes.** Hindsight takes the memory-provider slot, which only one
  provider can hold. NeuralMind's plugin is enabled through
  `plugins.enabled`, so it doesn't compete for that slot (see the
  [Hermes walkthrough](../use-cases/hermes-agent.md)). Hindsight's per-turn
  recall is capped at 4,096 tokens by default.
- **Decisions.** Choose one place to record them on purpose. NeuralMind's
  are tied to files and commits, which the stale-decision guard needs;
  Hindsight will still pick decisions up from conversation by itself.
- **Latency.** Every prompt waits for both. Hindsight's first-prompt reflect
  times out at 20 s and its injection at 7 s; NeuralMind's recall takes 1.3 s
  a prompt on hermes-agent's 269,151-node index on an M3.

## Feature matrix

| Dimension | Hindsight | NeuralMind |
|---|---|---|
| Remembers | Facts, experiences and observations from conversations and git; LLM-written pages about the repo | Code structure; which files are used together; recorded decisions; the last session's prompts and edits |
| Parses source / builds a call graph | No; an LLM survey writes a component map | Yes; tree-sitter, ten languages plus JavaScript |
| Ranked file retrieval for a question | No | Yes; gold file on 40 of 40 public-benchmark queries (v4.12.0) |
| LLM needed to write memory | Yes (local models and existing subscriptions work) | No |
| Captures without being asked | Yes: transcripts, commits | Activity only (edits, prompts); decisions are recorded explicitly |
| Decision memory | A synthesized "key decisions and rationale" page | Records tied to files and commits, with staleness rules and a pre-edit guard |
| Storage | Postgres + pgvector (embedded pg0 available) or Oracle AI Database; coding-agents default is Hindsight Cloud | SQLite and files in `.neuralmind/` |
| Coding-agent reach | 13 CLIs through one package, plus an MCP endpoint per bank | Claude Code hooks, Hermes plugin, MCP for any client |
| Hermes | Memory provider (`memory.provider`) | Plugin (`plugins.enabled`) |
| Headline benchmark | LongMemEval (conversation memory), independently reproduced | Public code-retrieval benchmark, recomputed in CI |
| License | MIT | MIT (core); source-available commercial modules for the Team tier |
| GitHub stars (2 Nov 2026) | ~57.7k | — |

## When to pick which

**Pick Hindsight if** you want the agent to remember people, conversations
and the story of a project (what was tried, why, what's in flight) across
any agent framework, and you're happy for an LLM to write that memory. Its
git seeding makes it useful in a repo's first session.

**Pick NeuralMind if** the cost you keep paying is the agent re-exploring the
code: grepping and reading files every session to find where something
lives and what it touches.

**Run both if** you want both kinds of memory and accept two blocks of
context per prompt. Decide where decisions get recorded, and measure what
the pair adds per turn on your own sessions.

## The honest caveats

- **Not tested together.** Everything under "Running both" is read from the
  two projects' docs, not observed.
- **Hindsight's details are its own claims**, from its README and docs on
  2 November 2026, not reproduced by us. The star count is a snapshot; it
  more than doubled between September and November.
- **Hindsight is ahead on things NeuralMind doesn't attempt**: an
  independently reproduced benchmark, 60+ integrations across agent
  frameworks, automatic capture, and memory that's useful before the first
  session thanks to git seeding. NeuralMind's code graph is ready on the
  first build, but its synapse layer starts empty and learns only from use.
- **This moves fast.** Our September page described Hindsight as needing a
  Postgres server and having no view of the code. Its docs on 2 November
  describe embedded storage, an LLM codebase survey with knowledge pages,
  and a retired first Claude Code integration. Re-check before relying on
  specifics.

## See also

- [vs. the Codex CLI memory ecosystem](./vs-codex-cli-memory.md): Hindsight,
  Mem0 and Basic Memory as Codex's missing memory
- [vs. Mem0 and Zep](./vs-mem0-zep.md): the conversational-memory category
- [vs. HydraDB and Open Glean](./vs-hydradb-open-glean.md): another
  memory backend with a Claude Code plugin
- [Hermes walkthrough](../use-cases/hermes-agent.md): NeuralMind next to a
  Hermes memory provider
- [All comparisons](./README.md)
