---
title: "NeuralMind vs. Mem0 and Zep — code-structure memory, or conversational-fact memory?"
description: "Honest comparison of NeuralMind against Mem0 and Zep/Graphiti, the popular AI-agent memory layers: why source-code retrieval and conversational/user-fact memory are different problems, what NeuralMind's Memory Layer does and doesn't share with LLM-based memory extraction, and when to run each."
---

# NeuralMind vs. Mem0 and Zep

> **TL;DR** — Mem0 and Zep are not competitors to NeuralMind; they solve a
> different problem. Both remember facts extracted from **conversations**
> — what a user said, preferred, or what was true and when — using an LLM
> in the write path. Neither parses source code, builds a call graph, or
> retrieves files. NeuralMind remembers **codebases**: a semantic index of
> code plus a Hebbian graph of which files actually move together on a
> given team, and (new in v4.1+) a narrow, git-tied record of *why*
> engineering decisions were made. There is no reproducible head-to-head
> here — gold-file recall doesn't apply to either tool, the same "wrong
> axis" situation as our [Headroom comparison](./vs-headroom.md). All
> Mem0/Zep/Graphiti figures below are their own published numbers or
> public repo state, not something we measured. Assessed September 2026;
> both projects ship fast — re-check before relying on specifics.

## What Mem0 is

[Mem0](https://github.com/mem0ai/mem0) (Apache 2.0, 65k+ GitHub stars) is
"drop-in memory infrastructure for AI agents" — you feed it conversation
turns and it extracts and stores what's worth remembering about a user,
session, or agent, then retrieves it on later turns. It requires an LLM to
function: extraction defaults to a hosted OpenAI model, and its April 2026
rework moved to a single-pass "ADD-only" extraction call rather than
separate update/delete passes. Retrieval combines semantic search, BM25
keyword matching, and entity linking over embeddings (OpenAI's
`text-embedding-3-small` by default, swappable). It ships three ways: a
pip/npm library for prototyping, a self-hosted Docker server, and a hosted
Mem0 Platform.

## What Zep (and Graphiti) is

"Zep" names two different things today, and the distinction matters for
anyone evaluating it. [Graphiti](https://github.com/getzep/graphiti)
(Apache 2.0, ~31k stars) is the actual open-source engine: a framework
for building **temporal knowledge graphs** that track not just facts but
*when* they became true and when they were superseded — "what was true,
and when," not just "what is true now." It needs a graph database backend
(Neo4j, FalkorDB, or Amazon Neptune) and an LLM for entity/relationship
extraction and deduplication. [Zep](https://github.com/getzep/zep) itself
has pivoted: the repo is now examples and framework integrations for a
hosted **Zep Cloud** platform, and its self-hosted Community Edition is
explicitly deprecated ("no longer supported... moved to the `legacy/`
folder"). So the fair open-source comparison point is Graphiti, not "Zep"
as most people mean it; Zep proper is a managed product built on top of
it, adding multi-tenant governance and sub-200ms retrieval at scale.

## How NeuralMind differs

The honest framing is that these tools don't overlap in what they
remember:

**1. Different object of memory entirely.** Mem0 and Graphiti/Zep are
built to answer "what did the user tell me" and "what was true, and
when" — memory *about people and conversations*. NeuralMind's core is
memory *about a codebase*: a semantic index (L0→L3 progressive
disclosure) plus a [synapse layer](../../neuralmind/synapses.py) that
learns which files co-activate from real edits and queries. Neither Mem0
nor Graphiti parses an AST, resolves a call graph, or ranks files against
a def-site — that's simply not their problem, and it would be dishonest
to score them against our gold-file-recall benchmark the way we do
[codebase-memory-mcp](./vs-codebase-memory-mcp.md). This is the same
"wrong axis" situation the [Headroom page](./vs-headroom.md) already
names for a different reason.

**2. Where the Memory Layer actually gets close — and where it doesn't.**
NeuralMind's own [Memory Layer](../wiki/Memory-Layer.md) (v4.1+) is the
one part of NeuralMind that's shaped like Mem0/Graphiti: a persistent
store of discrete records (architectural decisions, not code) with
rationale, evidence, and a confidence score, queryable in natural
language via FTS5. But the design choices diverge sharply from both:

- **No LLM in the write or invalidation path.** Mem0 and Graphiti both
  *extract* memories automatically from raw conversation via an LLM call.
  NeuralMind's decision memory is explicitly recorded — the agent or
  developer calls `neuralmind memory record --title ... --rationale ...`
  themselves; nothing is inferred from a transcript. Invalidation is
  equally rule-based: a decision goes stale when its `files_affected`
  changes (file-touch, commit mismatch, age) or a cascade rule fires — not
  when an LLM judges the conversation's truth to have shifted. This means
  no API key or provider cost to record or invalidate a decision, but it
  also means NeuralMind will never spontaneously notice something worth
  remembering the way Mem0's extraction does.
- **Storage is a local SQLite file, not a vector/graph database service.**
  `.neuralmind/memory.db`, no server, no Neo4j/FalkorDB dependency, no
  hosted platform option. That's simpler to self-host and audit, and a
  ceiling compared to Graphiti's purpose-built temporal graph semantics —
  NeuralMind's staleness model is file/commit/age rules, not a first-class
  bi-temporal graph.
- **Scope is git-native and narrow by design.** A decision is tied to
  `files_affected` and an optional commit SHA; the `PreToolUse`
  stale-guard warns the agent *before* it edits a file governed by a
  now-stale decision. Mem0/Graphiti have no concept of a commit or a file
  — they don't need one for their use case, and NeuralMind's memory layer
  would be useless for "remember this user prefers dark mode."

**3. Complementary, not competing, if your agent needs both.** An agent
that both talks to end users and edits a codebase has two different kinds
of memory to manage. Mem0 (or Zep Cloud) for user/conversation state and
NeuralMind for codebase structure, usage patterns, and engineering
decisions is a coherent stack — they don't touch the same storage or the
same questions.

| Dimension | Mem0 | Zep / Graphiti | NeuralMind |
|---|---|---|---|
| Primary memory object | User/session/agent facts from conversation | Entities, relationships, facts with validity windows | Codebase structure, usage co-activation, engineering decisions |
| Parses source code | No | No | Yes — tree-sitter AST, 10 languages |
| Extraction mechanism | LLM-driven (single-pass ADD extraction) | LLM-driven entity/edge extraction + dedup | Explicit — caller records decisions directly; no LLM required |
| Invalidation | LLM re-evaluates on new input | Bi-temporal validity windows (LLM-assessed) | Deterministic rules: file-touch, commit mismatch, age, cascade |
| Storage | Vector store + BM25 index (pluggable) | Graph DB (Neo4j/FalkorDB/Neptune) | SQLite (local file, `.neuralmind/`) |
| Requires LLM to operate | Yes (extraction + default embeddings) | Yes (extraction/dedup) | No — indexing/embedding is local ONNX; decision memory needs no LLM at all |
| Self-hostable, fully offline | Yes (Docker server) | Yes (Graphiti + self-hosted graph DB); Zep Cloud itself is not | Yes — everything under `.neuralmind/`, air-gap installable |
| Team/cross-agent portability | Per-deployment store | Per-deployment graph | Git-portable: `.neuralmind-team-memory.json`, markdown export |
| Code-retrieval / progressive disclosure | No | No | Yes — L0→L3, ~800 tokens/query |
| Tool-output compression | No | No | Yes — `PostToolUse` on `Read`/`Bash`/`Grep` |
| Distribution | pip/npm, Docker, hosted platform | Graphiti: pip, self-hosted. Zep: hosted only | PyPI, Docker, VS Code extension, MCP |
| License | Apache 2.0 | Apache 2.0 (Graphiti); Zep Cloud proprietary | MIT (core); source-available commercial modules for the Team tier |
| GitHub stars (point-in-time) | 65k+ | Graphiti ~31k; Zep (examples repo) ~4.9k | — |

## When to pick which

**Pick Mem0 if:** you're building a conversational agent or consumer app
and need it to remember user preferences, facts, or history across
sessions — the "what did the user tell me" problem. NeuralMind has
nothing to offer there; it has never seen a chat message.

**Pick Zep Cloud (or self-hosted Graphiti) if:** you need entity memory
with genuine temporal reasoning — "what was true, and when, and what
superseded it" — typically for a customer-facing or multi-agent product
tracking evolving facts about people or accounts. If self-hosting matters,
note that's Graphiti-plus-your-own-graph-DB, not "Zep" as commonly
advertised.

**Pick NeuralMind if:** your agent operates on a codebase and the
recurring cost is re-discovering that codebase's structure, or losing the
rationale behind past engineering decisions when the person who made them
isn't in the room. Nothing here competes with Mem0/Zep's actual job.

**Run NeuralMind alongside either** if your agent does both: talks to
users *and* edits code. They occupy different storage, answer different
questions, and neither one's presence changes what the other measures.

## The honest caveats

- **No comparison is scored, and none can be under our own fairness
  contract.** [`evals/public/COMPETITORS.md`](../../evals/public/COMPETITORS.md)
  requires a competitor to return ranked files scored against the same
  def-site oracle NeuralMind uses. Mem0 and Graphiti don't retrieve files
  at all — there is no reproducible head-to-head to run, the same reason
  Headroom (a compression tool, not a retriever) has no scored row either.
- **All Mem0/Zep/Graphiti figures above are their own claims or public
  repo state**, gathered from their READMEs and GitHub metadata, not
  reproduced or independently verified by us. Star counts in particular
  are a snapshot and will be stale quickly for projects moving this fast.
- **The "no LLM required" framing is a real trade-off, not a pure
  advantage.** Mem0's automatic extraction means it notices things worth
  remembering without anyone asking. NeuralMind's decision memory only
  knows what a developer or agent explicitly chose to record — it will
  never spontaneously capture a decision the way Mem0 might surface a
  stray user preference from casual conversation.
- **Zep's self-hosted story changed recently and may change again.** As
  of this writing the Community Edition is deprecated and Graphiti is the
  only self-hostable path; if that's load-bearing for your evaluation,
  verify current status directly rather than trusting this page.
- **This is a young comparison.** Unlike [vs-graft.md](./vs-graft.md) or
  [vs-codebase-memory-mcp.md](./vs-codebase-memory-mcp.md), which describe
  tools in NeuralMind's own category, this page exists mainly to draw the
  category boundary clearly for readers who land here searching "AI agent
  memory" and expect a fight that isn't happening.

## See also

- [Memory Layer wiki page](../wiki/Memory-Layer.md) — full reference for
  NeuralMind's own decision-memory feature
- [vs. Graft](./vs-graft.md) — the closest thing to a real competitor in
  NeuralMind's actual category (local code graphs)
- [vs. Headroom](./vs-headroom.md) — another "different axis" comparison,
  for the same reason
- [All comparisons](./README.md)
