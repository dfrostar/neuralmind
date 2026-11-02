---
title: "NeuralMind vs. the Codex CLI memory ecosystem — Hindsight, Mem0, and Basic Memory"
description: "OpenAI's Codex CLI ships with no persistent memory of its own. Honest comparison of the three MCP memory servers filling that gap — Hindsight, Mem0, and Basic Memory — against NeuralMind's code-structure index and decision memory, and where NeuralMind's own Codex support actually stands today."
---

# NeuralMind vs. the Codex CLI memory ecosystem

> **TL;DR** — Codex CLI has no native persistent memory: `AGENTS.md` is
> static and capped at 32KiB, and its auto-generated session summaries
> are markdown files recalled by `grep`, not search. Three MCP memory
> servers have moved into that gap — Hindsight, Mem0, and Basic Memory —
> and all three share the same shape: LLM-extracted facts/entities/notes,
> not source-code structure. None of them parse an AST, build a call
> graph, or rank files against a def-site oracle. NeuralMind is the only
> tool in this set that does. The honest caveat that matters most here:
> **`neuralmind-mcp` is confirmed to register with Codex CLI and speak the
> MCP protocol correctly, but no one has watched Codex's own agent call it
> mid-conversation.** `codex mcp add neuralmind -- neuralmind-mcp` writes
> the expected `[mcp_servers.neuralmind]` stdio entry and `codex doctor`
> reports it as a valid, enabled server; a direct MCP-protocol probe
> against the same binary confirms `initialize`, `tools/list` (25 tools),
> and real tool calls all work. What's still unverified is Codex's own
> Rust MCP client actually driving those tools inside a live turn, which
> needs an OpenAI API key this environment doesn't have. Assessed
> September 2026, Hindsight's details updated November 2026 — re-check
> before relying on specifics; this space is moving fast.

## The gap: what Codex does and doesn't remember natively

Codex CLI (OpenAI, latest stable v0.155.0, GPT-6-Astra as of September
2026) has two native context layers, and neither is a memory system in
the sense NeuralMind or its competitors mean it:

- **`AGENTS.md`** — a static markdown file read at session start. Manually
  maintained, silently truncated past 32KiB, and identical every session
  regardless of what happened last time.
- **Session summaries** (`~/.codex/memories/`) — Codex auto-writes markdown
  summaries of past sessions. Recall is "read the whole summary, then
  `grep` over longer files" — no semantic search, no ranking, no
  structure.

Codex does support arbitrary MCP servers — `codex mcp add`, or a
`[mcp_servers.<name>]` block in `~/.codex/config.toml`, stdio or HTTP
transport, shared across the CLI, IDE extension, and desktop app. That's
the seam every tool below (and NeuralMind, in principle) plugs into.

## The three tools that filled it

**[Hindsight](https://github.com/vectorize-io/hindsight)** (vectorize-io,
MIT, about 57.7k stars on 2 November 2026, up from 23.9k in September) is
the most coding-CLI-native of the three. Its coding-agents package builds a
per-repo memory bank two ways at once: mining git history automatically
(commit messages by default, diffs optionally) and accumulating live
session transcripts, with no setup command — install the npm package and
ingestion starts. Its three operations are **retain** (LLM extracts facts,
entities, relationships, and temporal data, then embeds them), **recall**
(four parallel strategies — semantic, BM25, graph-based, temporal — merged
and reranked), and **reflect** (an LLM synthesis pass that finds
connections across memories, e.g. for risk assessment or pattern
recognition). It exposes an MCP endpoint per memory bank and explicitly
supports Codex CLI, Claude Code, Cursor CLI, GitHub Copilot CLI, opencode,
Cline CLI and several more. Storage is PostgreSQL with pgvector (or Oracle
AI Database), but the Docker image and the Python package bundle an
embedded Postgres (pg0), and the coding-agents package defaults to the
hosted Hindsight Cloud, so a database server is optional. The nearest it
comes to code structure: a headless LLM "codebase survey" of a cold repo,
run through the agent's own CLI, feeds five LLM-written knowledge pages
(component map, core concepts, conventions, key decisions, initiatives).
Nothing in its documentation describes AST parsing or call-graph
extraction. See [the Hindsight page](./vs-hindsight.md) for the full
comparison and for running it alongside NeuralMind.

**Mem0 for Codex** is not a separate product — it's [Mem0](./vs-mem0-zep.md)
(the same conversational-memory layer compared elsewhere on this site),
reachable from Codex via a hosted MCP endpoint
(`[mcp_servers.mem0]`, `url = "https://mcp.mem0.ai/mcp"`) exposing nine
tools (`add_memory`, `search_memories`, etc.). What it adds over Codex's
native memories: cross-machine sync, semantic (embedding) search instead
of grep, no 32KiB ceiling, and one memory backend shared across Codex and
other MCP clients. It is general user/fact memory wired into a new host,
not a new architecture.

**[Basic Memory](https://docs.basicmemory.com/integrations/codex)** takes
a different shape: plain markdown files as the source of truth, organized
by project, with semantic search across notes. It runs as a local MCP
subprocess or a hosted cloud endpoint. Notes Codex creates are
"immediately available in Claude Code, Cursor, Claude Desktop, or any MCP
client" — the interoperability angle is its main pitch. Its public docs
don't describe code-structure analysis either; it reads as a persistent
notes/knowledge-base layer an agent (or a human) writes into, closer in
spirit to Graft's "folder of plain-English markdown nodes" than to a
retrieval index, but without Graft's tree-sitter structural pass
underneath it.

## How NeuralMind differs from all three

The pattern across Hindsight, Mem0, and Basic Memory is the same one this
site's [Mem0/Zep comparison](./vs-mem0-zep.md) already names: they
remember **facts, entities, and notes**, extracted or written by an LLM
(or a human, for Basic Memory), not **code structure**. None of them:

- Parse source into an AST or resolve a call graph.
- Rank files against a question the way `neuralmind_query`'s progressive
  disclosure or `neuralmind_search` do.
- Publish (or could satisfy) the gold-file-recall fairness contract in
  [`evals/public/COMPETITORS.md`](../../evals/public/COMPETITORS.md) —
  none return a ranked file list against a pinned repo, so there's no
  reproducible head-to-head to run here, the same "wrong axis" situation
  as [Headroom](./vs-headroom.md).

Where NeuralMind's [synapse layer](../../neuralmind/synapses.py) and
[Memory Layer](../wiki/Memory-Layer.md) sit relative to this group:

- **No LLM required for the core loop.** Hindsight's retain/reflect and
  Mem0's extraction both need an LLM call to write a memory. NeuralMind's
  code index uses local ONNX embeddings (no LLM, no API key), and its
  decision memory is explicitly recorded by the caller — no extraction
  step to get wrong or pay for.
- **Nothing to provision, on any side now.** Hindsight's embedded Postgres
  (pg0) or Hindsight Cloud removes the database server it used to need,
  though the coding-agents default puts the bank in the cloud. NeuralMind
  and Basic Memory are both embedded/local-file — `.neuralmind/` vs. Basic
  Memory's markdown notes.
- **Bootstrap direction is reversed.** Hindsight's git-history mining and
  its LLM codebase survey give it something useful on day one, before any
  live session happens.
  NeuralMind's static code graph is also available immediately (it's
  built from the current tree, not usage), but the *learning* half — the
  Hebbian synapse layer — starts from nothing and needs real usage to
  accumulate. Hindsight's approach to "useful before you've used it" is
  a genuine edge worth naming rather than glossing over.
- **Cross-client interoperability exists on both sides.** Basic Memory's
  "write once, read from any MCP client" pitch is real and matches
  NeuralMind's own "one brain, several hosts" design — the meaningful
  difference is *what* gets shared: notes an agent wrote, vs. a code
  index plus usage-learned associations no one had to write down.

| Dimension | Hindsight | Mem0 (Codex) | Basic Memory | NeuralMind |
|---|---|---|---|---|
| Parses source code / builds a call graph | No (an LLM survey writes a component map) | No | No | Yes — tree-sitter, ten languages plus JavaScript |
| Ranked-file retrieval against a gold-file oracle | No | No | No | Yes — CI-gated, reproducible |
| Extraction mechanism | LLM (retain), LLM synthesis (reflect) | LLM (single-pass extraction) | Manual / agent-written notes | Explicit record; local ONNX embeddings, no LLM |
| Storage | PostgreSQL + pgvector, embedded (pg0) or external, or Oracle AI DB; Hindsight Cloud by default for coding agents | Hosted (Mem0 platform) or self-hosted | Local markdown files, or hosted cloud | Local SQLite + files (`.neuralmind/`) |
| Requires a database server | No (embedded or hosted) / Yes (external Postgres) | No (hosted) / Yes (self-hosted) | No | No |
| Bootstraps from git history automatically | Yes, plus an LLM codebase survey | No | No | No — static graph from current tree; usage-learning starts at zero |
| Setup on Codex | npm package, zero-config ingestion | One `[mcp_servers]` block | One `[mcp_servers]` block | One `[mcp_servers]` block — **config + protocol confirmed working; a live Codex agent turn is not** |
| Cross-agent portability | Yes (multi-CLI MCP) | Yes (multi-CLI MCP) | Yes (multi-CLI MCP) | Yes (`.neuralmind-team-memory.json`, git-portable) |
| License | MIT | Apache 2.0 | Not publicly specified in docs | MIT (core); source-available commercial modules for Team tier |
| GitHub stars (point-in-time) | ~57.7k (2 Nov 2026) | 65k+ (Mem0 overall) | Not found in docs | — |

## When to pick which

**Pick Hindsight if:** you want a memory layer built specifically for
coding-agent CLIs, with git-history mining giving you something useful
immediately, and you're fine with an LLM writing its memories and, unless
you pick the local daemon or self-host, with the bank living in Hindsight
Cloud. You get four-strategy recall and an LLM-driven "reflect" synthesis
step. It's the most direct answer
to "give my coding agent memory" available today, and it's MIT-licensed
and self-hostable — no lock-in.

**Pick Mem0 for Codex if:** you already use Mem0 elsewhere (a product
with a conversational agent, say) and want the same user/fact memory
reachable from your coding CLI too. Not a reason to choose it *for*
coding specifically.

**Pick Basic Memory if:** what you actually want is a shared, human- and
agent-editable notes layer — a wiki your agent can read and write —
rather than an automatically-built index of anything.

**Pick NeuralMind if:** the problem is "the agent doesn't know this
codebase's structure and re-explores it every session," not "the agent
doesn't remember facts about me or past conversations." None of the three
above touch that problem at all — they're all note/fact layers wearing
coding-CLI integrations, not code-structure engines.

**On Codex specifically, today:** `codex mcp add neuralmind --
neuralmind-mcp` produces the correct `config.toml` entry, `codex doctor`
reports the server as configured and enabled, and speaking the MCP
protocol directly to the same binary (the official `mcp` Python SDK's
stdio client — the same class of client Codex's own Rust MCP client
implements against the identical spec) confirms `initialize`, a
25-tool `tools/list`, and real tool calls all succeed, Memory Layer tools
included. That's real evidence, not speculation — but it stops short of
watching Codex's own agent invoke a tool mid-conversation, which needs a
live OpenAI API key. Still listed as "Theoretical" in the
[host table](../../README.md#who-this-is-for)) for that reason, but this
is a materially stronger "Theoretical" than an unregistered guess.

## The honest caveats

- **NeuralMind's Codex integration is config-and-protocol verified, not
  agent-verified — this is the most important caveat on this page.**
  `neuralmind-mcp` registers correctly and answers the MCP protocol
  correctly when spoken to directly; what's unverified is Codex's own
  agent loop actually calling it, which needs an API key this
  environment doesn't have. Every other page in this directory compares
  a fully agent-verified NeuralMind integration against a competitor —
  this one is honest that the Codex side clears every bar except that
  last one.
- **All Hindsight/Mem0/Basic Memory figures and architecture details are
  from their own docs and repos**, gathered directly, not reproduced or
  benchmarked by us. Star counts are a snapshot.
- **No AST/call-graph claim here is airtight.** We read each project's
  *public* documentation and found no mention of parsing code structure.
  Hindsight's LLM codebase survey, which its November 2026 docs describe,
  is the closest any of them comes; a feature added later or undocumented
  could change that.
- **This is a young, fast-moving corner of the ecosystem.** Codex's own
  native memory is explicitly described as immature by third parties
  building around it; the tools filling the gap today may not be the
  ones filling it in six months.

## See also

- [vs. Hindsight](./vs-hindsight.md) — Hindsight on its own, and running
  it alongside NeuralMind in Claude Code or Hermes
- [vs. Mem0 and Zep](./vs-mem0-zep.md) — the general-purpose memory
  category Hindsight and Mem0 both belong to
- [vs. Graft](./vs-graft.md) — the closest thing to an actual code-graph
  competitor, unrelated to the Codex-specific gap this page covers
- [Memory Layer wiki page](../wiki/Memory-Layer.md) — NeuralMind's own
  decision-memory feature
- [All comparisons](./README.md)
