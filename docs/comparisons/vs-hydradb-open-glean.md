---
title: "NeuralMind vs. HydraDB and Open Glean — a graph database, a memory API, and a knowledge workspace"
description: "HydraDB ships an open-source graph database on object storage, a hosted memory API with a Claude Code plugin and MCP server, and Open Glean, a self-hosted workspace for cited answers across your files and apps. Which of the three touches what NeuralMind does, where they overlap, and how they run alongside it."
---

# NeuralMind vs. HydraDB and Open Glean

> **TL;DR** — "HydraDB" names three things, and only one of them comes near
> NeuralMind. The **open-source HydraDB** is a distributed graph database:
> infrastructure, not an agent tool. **Open Glean** is a workspace where people
> ask questions across their documents and connected apps (Slack, Notion,
> Gmail and the like) and get cited answers: a different job, and a
> complementary one. The **hosted HydraDB memory API**, reached from Claude
> Code through its plugin or MCP server, is the overlap. It hooks Claude Code
> at the same points NeuralMind does, but it remembers your Markdown docs and
> your conversations, where NeuralMind indexes the code. Running both means
> two context blocks per prompt, and we haven't tested them together. Every
> HydraDB and Open Glean detail below comes from their READMEs on 2 November
> 2026, not from running them.

## What HydraDB is

The [hydra-db](https://github.com/hydra-db) organization ships three things
under one name:

1. **[HydraDB](https://github.com/hydra-db/hydradb)** (AGPL-3.0, about 13.1k
   stars on 2 November 2026), an "object-store-native distributed graph
   database written in Rust". S3-compatible object storage holds the graph;
   query nodes keep only disposable caches, so they scale and restart freely.
   It speaks OpenCypher, Neo4j's Bolt protocol and an HTTPS query API, and
   runs locally with `CLOUD_PROVIDER=local` and a directory in place of S3.
   Its README describes graph queries and traversal, not vector search, and
   doesn't mention agent memory.
2. **The hosted HydraDB API** (`api.hydradb.com`), which the marketing site
   pitches as "the graph AI runs on" for agent memory, ontologies and context
   graphs. It stores *memories* and *knowledge*, recalls them with
   knowledge-graph context, and syncs connectors. Its
   [MCP server](https://github.com/hydra-db/hydradb-mcp) (`npx @hydradb/mcp`)
   exposes `hydradb_query`, `hydradb_ingest` and related tools, plus Cypher
   tools for property graphs you model yourself, and its
   [Claude Code plugin](https://github.com/hydra-db/hydradb-claude-code) wires
   it into Claude Code's lifecycle. Both need a HydraDB account key.
3. **[Open Glean](https://github.com/hydra-db/open-glean)** (Apache-2.0, about
   1.6k stars), a self-hosted Next.js app over the hosted API. Covered
   [below](#what-open-glean-is).

The landing page calls the database "10x cheaper"; the database's README
points to HydraDB's own benchmark site for latency and throughput. We
haven't checked either.

### The Claude Code plugin

This is the HydraDB piece shaped most like NeuralMind. It registers four
hooks:

- **`SessionStart`** prints HydraDB status and starts a background sync of
  workspace documentation: `CLAUDE.md`, `.claude/**/*.md`, `**/*.md` and
  `**/*.mdx` by default, at most 25 files per run.
- **`UserPromptSubmit`** recalls from HydraDB and injects a
  `<hydradb-context>` block of up to 7,000 characters (six memory chunks and
  four knowledge chunks by default, with graph entity paths).
- **`PostToolUse`** records file writes for the next incremental sync.
- **`Stop`** captures the finished turn, by default upserting one evolving
  transcript of the session.

It strips common secret patterns before upload, and a `hydra-ignore` marker
keeps a file or a prompt out of sync and capture. The default endpoint is
`https://api.hydradb.com`, which `HYDRADB_BASE_URL` overrides. The plugin was
4 stars on 2 November 2026, so it's early.

## What Open Glean is

Open Glean calls itself "your second brain on Hydra DB": one box where you
ask a question across your memories, files, saved webpages and
connector-synced knowledge, and it streams an answer with inline citations
and a sources panel. A Deep Research mode splits a question into a plan of
sub-questions, runs each against HydraDB, and merges the findings into one
cited answer. Collections scope a search, and a mind map shows the
knowledge graph HydraDB built from your content.

You run it yourself (`npm run dev` or Docker), but it talks to the hosted
HydraDB API with your key, writes answers with any OpenAI-compatible model
(a local one such as Ollama once private URLs are allowed), and keeps chats
in MongoDB. It's aimed at knowledge work, not code: it has no MCP server and
no coding-agent integration.

## How NeuralMind differs

**From the HydraDB database: different layer.** HydraDB is something you
would build a memory product *on*. NeuralMind is a finished tool for one
job, with its state in local SQLite and files under `.neuralmind/`. No
integration exists between the two.

**From Open Glean: different job, different user.** Open Glean answers a
person's question across a team's documents and apps. NeuralMind feeds a
coding agent the part of a codebase a question needs, as files and
functions from a parsed graph (tree-sitter, ten languages plus JavaScript):
670–961 mean tokens per question on the public benchmark, which finds the
gold file on 40 of 40 queries at v4.12.0 (the 150-question retrieval eval
misses 10). NeuralMind has no connectors; Open Glean doesn't read code
structure.

**From the Claude Code plugin: same hooks, different content.**

- *What's indexed.* The plugin syncs Markdown. NeuralMind parses source
  code, builds its call graph, and learns from edits and prompts which files
  are used together.
- *What's captured.* The plugin saves conversation turns, and
  `/hydradb:remember` stores a note, preference or decision. NeuralMind
  records prompts and edited paths for the next session's
  [recap](../use-cases/pick-up-where-you-left-off.md), and decisions only when
  recorded with `neuralmind decisions record`, each tied to the files it
  governs and marked stale when they change.
- *Where it lives.* The plugin sends synced docs and captured turns to the
  hosted API. NeuralMind keeps its state in the project and by default sends
  no telemetry and transmits no repository content off your machine.
- *What's measured.* HydraDB publishes no retrieval figures for the plugin
  that we found, and it returns memory chunks rather than ranked files, so
  [`evals/public/COMPETITORS.md`](../../evals/public/COMPETITORS.md) has no
  head-to-head to run.

## Where they overlap, and running both

**Open Glean and NeuralMind don't overlap.** One serves people searching team
knowledge; the other serves a coding agent working in one repo. Run both.

**The Claude Code plugin and NeuralMind overlap in mechanism and in docs.**
Both hook `SessionStart`, `UserPromptSubmit` and `PostToolUse`, and both
surface Markdown: NeuralMind's prompt block lists matching docs beside the
code. We haven't tested them together. From the two READMEs:

- Each prompt gets two blocks: NeuralMind's short list of matching files,
  linked code and docs, with at most one 40-line excerpt, plus any recorded
  decisions the prompt mentions; and HydraDB's up to 7,000 characters. Check
  what they add per turn together. NeuralMind's block has two switches:
  `NEURALMIND_SYNAPSE_INJECT=0` drops the code recall and
  `NEURALMIND_PROVENANCE_INJECT=0` the decisions. With both set it adds
  nothing to the prompt, and its MCP tools still work.
- Each prompt waits for both. HydraDB's reads time out at 15 s; NeuralMind's
  recall takes 1.3 s a prompt on hermes-agent's 269,151-node index on an M3.
- Pick one place to record decisions. NeuralMind's stale-decision guard only
  knows decisions recorded in NeuralMind.

## Feature matrix

| Dimension | HydraDB (open source) | HydraDB Claude Code plugin | Open Glean | NeuralMind |
|---|---|---|---|---|
| What it is | Distributed graph database | Claude Code hooks over the hosted memory API | Self-hosted knowledge workspace | Code index and memory for coding agents |
| Who uses it | Developers building on a graph | A Claude Code user | People asking questions | A coding agent |
| Indexes source code | No | No; Markdown docs | No | Yes; tree-sitter graph, ten languages plus JavaScript |
| Remembers conversations | n/a | Yes; turns or a session transcript | Chats, in MongoDB | Prompts and edited paths, for the recap |
| Connectors (Slack, Notion, Gmail…) | No | No | Yes, through HydraDB | No |
| LLM needed | No | Not stated (it sends extraction instructions to the server) | Yes, to write answers | No |
| Where data lives | Object storage you choose, or a local directory | Hosted HydraDB API | Hosted HydraDB API, plus your MongoDB | `.neuralmind/` in the project |
| Claude Code integration | No | Yes, four hooks | No | Yes, hooks plus MCP |
| MCP | No; `@hydradb/mcp` serves the hosted API | Separate (`@hydradb/mcp`) | No | Yes |
| License | AGPL-3.0 | Not checked | Apache-2.0 | MIT (core); source-available commercial modules for the Team tier |
| GitHub stars (2 Nov 2026) | ~13.1k | 4 | ~1.6k | — |

## When to pick which

**Pick the HydraDB database if** you're building a service that needs a graph
store that scales on object storage. It's a NeuralMind alternative only in
the sense that SQLite is.

**Pick Open Glean if** you want cited answers across a team's documents and
apps. Run it beside NeuralMind; they don't meet.

**Pick the HydraDB Claude Code plugin if** you want Claude Code to remember
your conversations and Markdown docs in a hosted store that other tools can
reach. **Pick NeuralMind if** the agent keeps re-exploring your code every
session. **Run both if** you want both, and check the two prompt blocks
together.

## The honest caveats

- **Not tested together.** The "running both" notes come from the two READMEs.
- **All HydraDB and Open Glean details are their own claims**, from their
  READMEs on 2 November 2026, not reproduced by us. Star counts are a
  snapshot.
- **The name covers products that change separately.** Whether the
  open-source database can serve the memory API that the plugin and Open
  Glean use isn't stated in any README we read; we've treated them as
  separate.
- **The plugin is young** (4 stars), and its README's install steps clone it
  from a different organization (`usecortex`), so expect it to change.

## See also

- [vs. Hindsight](./vs-hindsight.md): the larger agent-memory system with a
  coding-agent integration
- [vs. Mem0 and Zep](./vs-mem0-zep.md): the conversational-memory category
- [vs. Graft](./vs-graft.md): a tool that does build a local code graph
- [All comparisons](./README.md)
