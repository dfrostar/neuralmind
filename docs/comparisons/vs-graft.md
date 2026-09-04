---
title: "NeuralMind vs. Graft — a rebuilt-on-demand code graph, or a graph that learns from how you use the repo?"
description: "Honest comparison of NeuralMind and trailhq's Graft for AI coding agents: two-pass tree-sitter + LLM concept graph with published SWE-bench agent-loop results vs. progressive disclosure, Hebbian usage learning, and tool-output compression. When to pick which."
---

# NeuralMind vs. Graft

> **TL;DR** — Graft and NeuralMind are the closest architectural
> neighbours in this comparison set: both build a local code graph, both
> wire themselves into Claude Code / Cursor / Codex, both are MIT, and
> both exist to stop an agent re-exploring a repo from scratch. They
> differ on **what the graph is made of** and **whether it changes with
> use**. Graft compiles a two-pass graph — deterministic tree-sitter
> structure plus an optional LLM-written semantic layer — into a folder
> of plain-English markdown nodes, rebuilt against the working tree on
> every query. NeuralMind serves progressive-disclosure slices (L0→L3)
> from a graph whose edges are **reinforced and decayed by actual usage**,
> and additionally compresses the agent's own `Read`/`Bash`/`Grep` output
> in-session. Graft's headline evidence is **stronger in kind** than
> ours: it publishes agent-loop task outcomes on SWE-bench Verified,
> where we publish retrieval ranking. We have not run a head-to-head.
> Assessed September 2026 — re-check before relying on specifics.

## What Graft is

[Graft](https://github.com/trailhq/Graft) (MIT, `npm install -g
@nanonets/graft`) builds a per-symbol code graph in two passes:

1. **Structural** — tree-sitter, deterministic, scope-aware call
   resolution. No model, no API key, no network.
2. **Semantic** — an optional LLM pass (`graft build --deep`) that
   summarizes files and groups them into *concept nodes* with typed
   links, cached so you pay for it once.

The output is a folder of linked markdown files where, in the project's
words, "each node says, in plain English, what a part of the system does
and how it connects to the rest." The graph is treated as a regenerable
local cache — `graft init` adds it to `.gitignore` the way you'd treat
`node_modules`.

Its freshness story is a genuine design strength: every query rebuilds
the structural graph against the working tree first — reported as ~3ms
when nothing moved — so answers reflect **uncommitted edits**, not the
last indexing run.

`graft init` wires into agents three ways: a native Claude Code skill
(`.claude/skills/graft/SKILL.md`), instruction files for CLI agents
(`AGENTS.md`, `.github/copilot-instructions.md`), and an MCP server
exposing six tools (`graft_find_code`, `graft_file_api`,
`graft_trace_calls`, `graft_find_all`, `graft_repo_map`,
`graft_check_freshness`). On Claude Code it also installs a statusline,
auto-sync hooks, and post-edit blast-radius warnings.

**Its published numbers** (cited as-is; we have reproduced none of them):
an internal 162-run sweep across two repos reporting 46% fewer tool
calls, 42% fewer tokens, 60% less latency at equal 93% correctness; and
SWE-bench Verified (50 issues, Claude Sonnet 5) reporting 66% vs. 54%
baseline correctness, 23% fewer tokens, and $42.43 vs. $52.34 cost.

## How NeuralMind differs

Both tools answer "give the agent less, better context." The divergence
is on three axes.

**1. The graph learns, or it doesn't.** This is the substantive
difference. Graft's graph is a pure function of the code at build time —
excellent for freshness and reproducibility, and the project is explicit
that it is a regenerable cache rather than an adaptive system.
NeuralMind's [synapse layer](../../neuralmind/synapses.py) applies
Hebbian reinforcement to edges that actually co-activate during real
queries and edits, with exponential half-life decay (60 days for the
shared team baseline, 1 day for session scratch) so stale associations
fade. After a month on one repo, the two tools' graphs encode different
things: Graft's encodes *the code*, NeuralMind's encodes *the code plus
how this team moves through it*. Whether that's worth having is
workload-dependent — on a repo you touch rarely, it isn't.

**2. Retrieval-side vs. both sides.** Graft reduces the *need* for tool
calls by front-loading ranked context — its own framing, and its 46%
fewer-tool-calls figure measures exactly that. NeuralMind does that too
(L0→L3 progressive disclosure, ~600 tokens at wake-up, ~500–1000 per
query) **and** compresses what comes back from the calls the agent still
makes, via `PostToolUse` hooks on `Read`/`Bash`/`Grep`. These are
different levers and they compose; Graft does not attempt the second.

**3. Portable team memory.** NeuralMind exports learned associations to
a git-portable `.neuralmind-team-memory.json` plus a markdown memory
file any MCP-capable agent reads. Graft's graph is deliberately
git-ignored and per-checkout.

| Dimension | Graft | NeuralMind |
|---|---|---|
| Structural extraction | Tree-sitter, deterministic, no key | Tree-sitter, deterministic, no key |
| Semantic layer | LLM pass (`--deep`), cached, your provider/key | Local embeddings (MiniLM ONNX); no LLM in the build loop |
| Graph artifact | Folder of plain-English markdown concept nodes | Embedded graph + ChromaDB vectors under `.neuralmind/` |
| Freshness | Rebuilt against working tree per query (~3ms unchanged), sees uncommitted edits | Incremental rebuild + file watcher |
| Learns from usage | No — fixed at build time, regenerable cache | Yes — Hebbian reinforcement with half-life decay |
| Tool-output compression | No — reduces the need for calls, doesn't compress their output | Yes — `PostToolUse` on `Read`/`Bash`/`Grep` |
| Blast radius | Yes — `graft callers -d N`, post-edit warnings | Spreading activation over synapses (different shape, not a transitive caller set) |
| Team memory | Git-ignored, per-checkout | Git-portable `.neuralmind-team-memory.json` |
| Language coverage | 8 full-fidelity, ~14 name-resolved, optional LSP refinement | 10 tree-sitter, optional SCIP precision on Python/TS/Go |
| Agent wiring | Skill + `AGENTS.md` + MCP (6 tools); statusline, auto-sync hooks | MCP + Claude Code lifecycle hooks; VS Code extension |
| Published evidence | Agent-loop task outcomes (SWE-bench Verified, internal sweep) | Retrieval ranking + token reduction, CI-gated and reproducible |
| License | MIT | MIT (core); source-available commercial modules for the Team tier |

## When to pick which

**Pick Graft if:**

- You want the context layer to read as **documentation** — plain-English
  markdown nodes a human can open, review, and correct — rather than an
  opaque retrieval index.
- **Blast radius is your core question.** `graft callers <symbol> -d N`
  giving a transitive caller set is a first-class answer there; our
  spreading activation is a different (associative, not exhaustive)
  shape and is not a substitute.
- You work with heavy uncommitted state and want every query to reflect
  the working tree with no indexing step you have to remember.
- You weight **agent-loop task-outcome evidence** over retrieval metrics.
  Graft publishes SWE-bench Verified numbers; on that axis it has
  evidence we currently don't.

**Pick NeuralMind if:**

- You want the layer to **get better on this repo over time**, not just
  stay accurate to the current commit — and you're on the repo enough
  for that to accumulate.
- You want savings on **both** sides of the loop: less context retrieved
  *and* compressed tool output from the calls the agent still makes.
- Several people or several agents (Claude Code, Cursor, Cline, Codex)
  hit the same repo and you want one memory they all reinforce, moved
  between machines by git.
- You want the build to require no LLM provider at all — Graft's
  structural pass is likewise key-free, but its semantic layer, the part
  that produces the plain-English nodes, is not.

**Running both is coherent** and we'd expect it to work: they occupy the
same retrieval slot, so the honest reason to run both is evaluation —
point them at the same repo and compare — rather than stacking. If you
do stack them, NeuralMind's `PostToolUse` compression still applies to
whatever Graft's tools return.

## The honest caveats

- **No head-to-head. This is a capability comparison, not a scored
  result.** Every Graft figure above is its own published number, cited
  as-is. We have not reproduced any of them, and nothing here should be
  read as us having tested Graft.
- **Their evidence class is stronger than ours where it overlaps.**
  SWE-bench Verified measures whether the agent *solved the issue*;
  our public benchmark measures whether retrieval *ranked the right
  file* (93.75% mean gold-file recall, 79–100% per repo, four pinned OSS
  repos). Ranking is cheaper to run and fully reproducible without
  paying for an LLM, which is why we run it — but it is a weaker claim
  about end-task outcomes, and a reader comparing the two headline
  numbers is not comparing like with like.
- **Graft looks tractable for our eval harness, unlike most entries in
  it.** `graft ask` is headless, returns ranked nodes with `file:line`,
  and the structural pass needs no API key — which satisfies the first
  two clauses of the fairness contract in
  [`evals/public/COMPETITORS.md`](../../evals/public/COMPETITORS.md).
  It's listed there as contribution-ready; the seam is the same one
  `competitor.py` already uses.
- **The learning claim has a floor.** Hebbian reinforcement needs usage
  before it beats a cold graph. On a repo you touch twice a month, or in
  the first session on a new checkout, NeuralMind's synapse layer
  contributes little and Graft's always-fresh rebuild is the safer
  default. We have not measured where the crossover sits.
- Graft's language tiering and ours are both self-reported and measured
  differently — read both matrices rather than comparing the counts.

## See also

- [vs. codebase-memory-mcp](./vs-codebase-memory-mcp.md) — the other
  local code-graph MCP, and the one we *have* scored
- [vs. graphify](./vs-graphify.md) — the general corpus-to-graph engine
- [vs. Tree-sitter / ctags / grep](./vs-treesitter-ctags.md) — the
  deterministic-extraction floor both tools build on
- [All comparisons](./README.md)
