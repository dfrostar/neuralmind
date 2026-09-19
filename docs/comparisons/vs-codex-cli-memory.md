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
> **NeuralMind's own Codex integration is unverified.** Codex supports
> arbitrary MCP servers via `config.toml`, and `neuralmind-mcp` should
> register the same way it does on Hermes-Agent and OpenClaw — but nobody
> has driven it end-to-end on Codex yet, unlike the three tools below,
> which all document the setup explicitly. Assessed September 2026 —
> re-check before relying on specifics; this space is moving fast.

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
MIT, 23.9k stars) is the most coding-CLI-native of the three. It builds a
per-repo memory bank two ways at once: mining git history automatically
and accumulating live session context, with no setup command — install
the npm package and ingestion starts. Its three operations are **retain**
(LLM extracts facts, entities, relationships, and temporal data, then
embeds them), **recall** (four parallel strategies — semantic, BM25,
graph-based, temporal — merged and reranked), and **reflect** (an LLM
synthesis pass that finds connections across memories, e.g. for risk
assessment or pattern recognition). It exposes an MCP endpoint per memory
bank and explicitly supports Codex CLI, Claude Code, Cursor CLI, GitHub
Copilot CLI, opencode, and Cline CLI. Storage is PostgreSQL with pgvector
(or Oracle AI Database 23ai) — a real database server, not an embedded
file. Nothing in its documentation describes AST parsing or call-graph
extraction; it operates entirely at the fact/entity level.

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
- **No database server to run.** Hindsight needs Postgres+pgvector (or
  Oracle AI DB) reachable from wherever the agent runs. NeuralMind and
  Basic Memory are both embedded/local-file — `.neuralmind/` vs. Basic
  Memory's markdown notes — with nothing to provision.
- **Bootstrap direction is reversed.** Hindsight's git-history mining
  gives it something useful on day one, before any live session happens.
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
| Parses source code / builds a call graph | No | No | No | Yes — tree-sitter, 10 languages |
| Ranked-file retrieval against a gold-file oracle | No | No | No | Yes — CI-gated, reproducible |
| Extraction mechanism | LLM (retain), LLM synthesis (reflect) | LLM (single-pass extraction) | Manual / agent-written notes | Explicit record; local ONNX embeddings, no LLM |
| Storage | PostgreSQL + pgvector (or Oracle AI DB) | Hosted (Mem0 platform) or self-hosted | Local markdown files, or hosted cloud | Local SQLite + files (`.neuralmind/`) |
| Requires a database server | Yes | No (hosted) / Yes (self-hosted) | No | No |
| Bootstraps from git history automatically | Yes | No | No | No — static graph from current tree; usage-learning starts at zero |
| Setup on Codex | npm package, zero-config ingestion | One `[mcp_servers]` block | One `[mcp_servers]` block | Same MCP seam should apply — **unverified** |
| Cross-agent portability | Yes (multi-CLI MCP) | Yes (multi-CLI MCP) | Yes (multi-CLI MCP) | Yes (`.neuralmind-team-memory.json`, git-portable) |
| License | MIT | Apache 2.0 | Not publicly specified in docs | MIT (core); source-available commercial modules for Team tier |
| GitHub stars (point-in-time) | 23.9k | 65k+ (Mem0 overall) | Not found in docs | — |

## When to pick which

**Pick Hindsight if:** you want a memory layer built specifically for
coding-agent CLIs, with git-history mining giving you something useful
immediately, and you're fine running Postgres to get four-strategy recall
and an LLM-driven "reflect" synthesis step. It's the most direct answer
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

**On Codex specifically, today:** if you need something working now, pick
one of the three above — they're documented, and someone has run them.
NeuralMind's Codex path exists on paper (same MCP mechanism, listed as
"Theoretical" in the [host table](../../README.md#who-this-is-for)) but
hasn't been verified end-to-end. Treat that as the honest current answer,
not a reason to rule it out — it's the same one-line `[mcp_servers]`
config as the others, just not yet confirmed working in practice.

## The honest caveats

- **NeuralMind's own Codex support is unverified — this is the most
  important caveat on this page.** Every other page in this directory
  compares a working NeuralMind integration against a competitor;
  this one is honest that the Codex side of that comparison is
  theoretical. Anyone relying on this page to justify a Codex deployment
  should verify `neuralmind-mcp` actually registers and responds via
  `codex mcp add` before assuming parity with Hermes-Agent or OpenClaw.
- **All Hindsight/Mem0/Basic Memory figures and architecture details are
  from their own docs and repos**, gathered directly, not reproduced or
  benchmarked by us. Star counts are a snapshot.
- **No AST/call-graph claim here is airtight.** We read each project's
  *public* documentation and found no mention of structural code
  analysis; a feature added after September 2026 or undocumented could
  change that.
- **This is a young, fast-moving corner of the ecosystem.** Codex's own
  native memory is explicitly described as immature by third parties
  building around it; the tools filling the gap today may not be the
  ones filling it in six months.

## See also

- [vs. Mem0 and Zep](./vs-mem0-zep.md) — the general-purpose memory
  category Hindsight and Mem0 both belong to
- [vs. Graft](./vs-graft.md) — the closest thing to an actual code-graph
  competitor, unrelated to the Codex-specific gap this page covers
- [Memory Layer wiki page](../wiki/Memory-Layer.md) — NeuralMind's own
  decision-memory feature
- [All comparisons](./README.md)
