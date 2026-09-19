---
title: "NeuralMind vs. Claude Code's native subagent memory — a per-agent notebook, or a learned, cross-host codebase index?"
description: "Honest comparison of NeuralMind against Claude Code's built-in subagent memory feature (the `memory` frontmatter field): manually-curated MEMORY.md notes scoped to one subagent in one host, vs. a semantic code index, Hebbian usage learning, and structured decision memory that's portable across Claude Code, Hermes-Agent, OpenClaw, and Agent Zero."
---

# NeuralMind vs. Claude Code's native subagent memory

> **TL;DR** — Claude Code ships a native `memory` field for subagents:
> point it at `user`, `project`, or `local` scope and the subagent gets a
> `MEMORY.md` file it can read and write with its own `Read`/`Write`/`Edit`
> tools. It's the closest first-party analog to what NeuralMind does, and
> it's genuinely useful for what it is — but it's a manually-curated
> notebook, not an index. No automatic collection, no semantic search
> (retrieval is a full read of the first 200 lines or 25KB, hard-truncated),
> no learning from usage, no decay, and no reach beyond Claude Code. This
> page is capability-only — there's no benchmark that applies to a
> bespoke per-agent notes feature, the same "wrong axis" situation as the
> [Mem0/Zep](./vs-mem0-zep.md) and [Codex ecosystem](./vs-codex-cli-memory.md)
> pages. Sourced directly from Anthropic's own subagent documentation, not
> third-party summaries. Assessed September 2026 — re-check before relying
> on specifics.

## What Claude Code's native subagent memory is

Set `memory: user`, `memory: project`, or `memory: local` in a subagent's
frontmatter (`.claude/agents/<name>.md`) and Claude Code enables a
persistent knowledge store for that subagent, at one of three locations:

| Scope | Location |
|---|---|
| `user` | `~/.claude/agent-memory/<name>/` |
| `project` | `.claude/agent-memory/<name>/` |
| `local` | `.claude/agent-memory-local/<name>/` |

When enabled, the subagent's system prompt is extended two ways: it
includes instructions for reading and writing to the memory directory, and
it includes the first 200 lines or 25KB of that directory's `MEMORY.md`
(whichever limit hits first), with instructions to curate the file down if
it grows past that. `Read`, `Write`, and `Edit` are automatically enabled
so the subagent can manage its own memory files. Nothing is collected
automatically — the subagent has to be told (or told to tell itself) to
save what it learned, and Anthropic's own docs frame the intended usage
as exactly that: "Now that you're done, save what you learned to your
memory."

## How NeuralMind differs

**1. Manually written notes vs. an automatically built and reinforced
index.** Populating Claude Code's subagent memory is entirely on the
subagent: nothing is indexed, embedded, or extracted from the codebase
itself — it's whatever prose the subagent chose to write down, whenever
it remembered to. NeuralMind's code graph is built once
(`neuralmind build`) from the actual source via tree-sitter, and its
[synapse layer](../../neuralmind/synapses.py) reinforces edges between
code nodes automatically from real queries and edits — no agent has to
remember to "save what it learned" for that part to work at all. The one
place NeuralMind *does* ask for explicit input — the
[Memory Layer](../wiki/Memory-Layer.md)'s decision records — still stores
structured fields (`rationale`, `confidence`, `decision_type`, `evidence`,
`files_affected`) rather than free prose, and is queryable by natural
language rather than read top-to-bottom.

**2. Full-file read vs. progressive disclosure and semantic search.**
Subagent memory retrieval is exactly one operation: read the first 200
lines or 25KB of `MEMORY.md`, verbatim, every time. There is no ranking,
no query-relevance filtering, and a project-level `MEMORY.md` that grows
past that ceiling is silently truncated from what the subagent actually
sees unless it curates the file down itself. NeuralMind serves
L0→L3 progressive disclosure sized to the question (~800 tokens for a
typical query) and ranks results by relevance — the two systems solve
"what fits in the prompt" oppositely: one caps the source file's size,
the other caps and ranks what's retrieved from an unbounded index.

**3. Siloed per subagent identity vs. one shared brain.** Two subagents
with different `name`s on the same project get two separate memory
directories that never see each other's notes, even at `project` scope.
NeuralMind's graph and synapse store are per-*project*, not per-agent:
every tool, subagent, and host that touches the same `.neuralmind/`
reinforces and reads the same associations. A pattern one subagent's
queries strengthen is immediately visible to a completely different
agent's next query — including on a different host entirely.

**4. Claude Code only vs. cross-host by design.** All three memory scopes
live under `.claude/` or `~/.claude/` — paths that mean nothing outside
Claude Code. NeuralMind's `.neuralmind/` directory and
`.neuralmind-team-memory.json` export are read by the same MCP tools
regardless of which host is asking: Claude Code, Hermes-Agent, OpenClaw,
Agent Zero, or Cursor via `neuralmind install-mcp`. If your team runs more
than one agent tool against the same repo, subagent memory can't be the
shared layer between them; NeuralMind already is one.

**5. No decay, no invalidation, no measurement.** Subagent memory has no
mechanism for a note to go stale — the only aging pressure is the 200-line
soft ceiling nudging the subagent to summarize. NeuralMind's synapse edges
decay on an exponential half-life, and its decision records are
automatically invalidated by file-touch and commit-mismatch rules (a
`PreToolUse` guard warns the agent before it edits code governed by a
now-stale decision). Neither system's retrieval quality is published for
subagent memory — there's no equivalent of NeuralMind's CI-gated gold-file
recall to compare against, because it's not attempting to be a ranked
retrieval system at all.

| Dimension | Claude Code subagent memory | NeuralMind |
|---|---|---|
| Population | Subagent manually writes `MEMORY.md` | Automatic: tree-sitter build + Hebbian reinforcement from usage; explicit only for decision records |
| Retrieval | Full read, first 200 lines / 25KB, verbatim | Progressive disclosure (L0→L3), ranked semantic search |
| Content shape | Free prose | Code graph + vector index + structured decision records |
| Scope | Per-subagent `name`, siloed | Per-project, shared across every agent/tool/host |
| Host reach | Claude Code only (`.claude/`) | MCP-portable: Claude Code, Hermes-Agent, OpenClaw, Agent Zero, Cursor |
| Staleness handling | None automatic — subagent must curate | Exponential half-life decay (synapses); rule-based invalidation (decisions) |
| Size limit | Hard-truncated at 200 lines / 25KB | Token-budgeted per query (~800 tokens typical), not a hard file cap |
| Requires an LLM to populate | Yes — the subagent itself writes it | No — local ONNX embeddings; decision records are explicit, rule-based |
| Setup | Built into Claude Code, one frontmatter field | Separate install (`pip install neuralmind`), `neuralmind build` |
| Cost to run | Free, native | MIT core; source-available commercial modules for the Team tier |

## When to pick which

**Pick subagent memory if:** you want a specific subagent — a
`code-reviewer` or `security-auditor`, say — to keep its own freeform
scratchpad of conventions and recurring issues it personally noticed, with
zero setup, and you're Claude-Code-only. It costs nothing extra and needs
no index to build.

**Pick NeuralMind if:** you want the agent to stop re-discovering your
codebase's structure every session regardless of which subagent or host
is asking, want retrieval that's ranked and token-budgeted rather than a
raw file read, or want a record of *why* past decisions were made that
goes stale automatically instead of silently rotting in a markdown file
nobody re-reads.

**Run both — they don't compete.** A subagent's own `MEMORY.md` for
personal scratch notes and NeuralMind's `neuralmind_query` /
`neuralmind_synaptic_neighbors` MCP tools for actual codebase facts sit at
different layers entirely. Nothing about enabling one changes what the
other does; NeuralMind's tools are already reachable from any subagent
that has MCP tool access.

## The honest caveats

- **This is the newest, least-adversarial-tested feature compared on this
  site.** It shipped in Claude Code v2.1.33 (February 2026); exact
  behavior (the 200-line/25KB cutoff, the three scope paths) is quoted
  directly from Anthropic's own subagent documentation as of this writing,
  not reverse-engineered or independently tested by us.
- **It is not trying to be what NeuralMind is**, so most of this
  comparison is explaining why the two aren't on the same axis rather than
  declaring a winner — the same honest framing this directory already uses
  for [Headroom](./vs-headroom.md) (compression, not retrieval) and
  [Mem0/Zep](./vs-mem0-zep.md) (conversational facts, not code).
- **A hard 200-line/25KB cutoff is a real constraint, not a strawman.** A
  `project`-scope `MEMORY.md` actively maintained by a busy subagent over
  months could plausibly exceed it; the mitigation is Anthropic's own
  "curate it down" instruction to the subagent, not a size-independent
  retrieval mechanism.
- **Claude Code shipping this at all is worth taking seriously as a
  competitive signal.** It's evidence Anthropic sees value in giving
  agents persistent memory natively — worth watching for follow-on
  features (search over multiple memory files, cross-subagent sharing)
  that would narrow this gap further.

## See also

- [Memory Layer wiki page](../wiki/Memory-Layer.md) — NeuralMind's own
  decision-memory feature, the closest thing it has to a manually-curated
  store
- [vs. Mem0 and Zep](./vs-mem0-zep.md) — the same "different axis" framing
  for general conversational memory
- [vs. the Codex CLI memory ecosystem](./vs-codex-cli-memory.md) — the
  equivalent gap on a different host, filled by third parties instead of
  the vendor
- [All comparisons](./README.md)
