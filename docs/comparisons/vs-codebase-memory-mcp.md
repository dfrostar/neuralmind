---
title: "NeuralMind vs. codebase-memory-mcp — breadth and raw speed, or ranking quality and a graph that learns?"
description: "Honest comparison of NeuralMind and DeusData's codebase-memory-mcp for AI coding agents, including the scored, reproducible retrieval head-to-head we actually ran: 162-language single-binary structural indexing vs. progressive disclosure, Hebbian usage learning, and tool-output compression."
---

# NeuralMind vs. codebase-memory-mcp

> **TL;DR** — This is the one competitor we have **scored live, on
> pinned repos, with committed traces**. At matched retrieval depth
> (top-8), on the two repos that eval covers, NeuralMind ranked the
> objectively-correct file far higher (MRR 0.96 vs. 0.23 on `requests`)
> at roughly an order of magnitude fewer tokens. That result is real,
> reproducible, and **narrower than it sounds** — two repos, pure
> retrieval ranking with no agent loop on either side, and not
> re-verified against our current four-repo corpus. Meanwhile
> codebase-memory-mcp beats us decisively on **breadth and scale**: 162
> vendored languages to our 10, a single static C binary with no
> language runtime, and the Linux kernel fully indexed in about three
> minutes. Pick on which of those axes your repo actually lives.
> Assessed September 2026 against version 0.8.1 — re-check before
> relying on specifics.

## What codebase-memory-mcp is

[codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp)
(MIT) is a native C executable that runs as an MCP server, indexing a
repo into a persistent knowledge graph. Its indexing pipeline stacks
three techniques:

- **Tree-sitter AST analysis** over vendored grammars for 162 languages,
  compiled into the binary.
- **Hybrid LSP type resolution** — embedded C implementations of
  type-resolution algorithms the project describes as structurally
  compatible with tsserver, pyright, gopls, Roslyn, Eclipse JDT and
  rust-analyzer — handling generics, inheritance, and stdlib resolution
  for about ten major languages.
- **Bundled vector embeddings** (`nomic-embed-code`, 768d int8)
  compiled into the binary, so semantic search needs no API key and no
  Ollama.

Storage is SQLite compressed with zstd. It exposes **15 MCP tools**,
including `search_graph`, `semantic_query`, `trace_path`,
`get_architecture`, `query_graph` (Cypher-like traversal), `manage_adr`
and `ingest_traces`. There's a built-in 3D graph viewer on
`localhost:9749`.

Its performance figures are genuinely impressive and we cite them as
published: the Linux kernel (28M LOC, 75K files) indexed in ~3 minutes
to 4.81M nodes and 7.72M edges; Django in ~6s; Cypher queries under 1ms.
It reports 83% answer quality with 10× fewer tokens across 31
repositories, and a 99.2% token reduction on a five-query structural
comparison.

Critically for the comparison below: **it does not learn.** Indexing is
static analysis; a file watcher triggers re-indexing on change, but
nothing reweights from how the codebase is actually used.

## The scored head-to-head

Unlike every other page in this directory, this one has numbers from a
run rather than a capability table. We drove both tools headless over
the **same** pinned repos, same questions, same objective def-site gold
files, scored by the **same** `quality.py`, at retrieval depth matched
to our `embedding-rag` baseline (top-8).

| repo | backend | gold-file recall | found-rate | MRR (rank quality) | mean tokens |
|---|---|---:|---:|---:|---:|
| requests | `codebase-memory-mcp` | 0.50 | 43% | 0.23 | 25,214 |
| requests | **neuralmind** | **1.00** | **100%** | **0.96** | **1,095** |
| click | `codebase-memory-mcp` | 0.64 | 57% | 0.50 | 38,538 |
| click | **neuralmind** | **1.00** | **100%** | **0.60** | **924** |

Reproduce it yourself:

```bash
pip install codebase-memory-mcp==0.8.1
python -m evals.public.competitor
```

Raw per-query traces, `results.json`, and pinned provenance are
committed under
[`bench/public/competitor/`](../../bench/public/competitor/).

**The fairness terms matter as much as the numbers:**

- **We used the mapping most favorable to the competitor.** Its
  interface takes a keyword array rather than free text; we tested three
  reproducible mappings and used the best-performing one for it. This
  isn't a crippled-baseline result.
- **Pure retrieval ranking, no agent loop on either side** — the same
  way we test NeuralMind's own `search`. The competitor's *published*
  numbers come from an LLM-driven agent loop we don't reproduce and
  don't dispute.
- **Token cost is a proxy**: it returns paths the agent then reads, so
  we count the tokens of the whole files it surfaces at depth 8.
- **Two repos, off by default.** This eval covers `requests` and `click`
  only, needs an external binary download, and has not been re-verified
  against the four-repo corpus our main benchmark now uses (93.75% mean
  gold-file recall, 79–100% per repo).

## How NeuralMind differs architecturally

Beyond ranking, three structural differences:

**1. It learns; codebase-memory-mcp doesn't.** Our
[synapse layer](../../neuralmind/synapses.py) applies Hebbian
reinforcement to edges that co-activate during real queries and edits,
with exponential half-life decay so stale associations fade. The
competitor's graph is a faithful snapshot of the code and stays one.

**2. Tool-output compression.** NeuralMind's `PostToolUse` hooks
compress what comes back from the agent's own `Read`/`Bash`/`Grep`
calls. codebase-memory-mcp addresses retrieval only — which is why its
own token comparison is framed against file-by-file grep exploration.

**3. Progressive disclosure vs. query-per-tool.** We serve L0→L3 slices
(~600 tokens at wake-up, ~500–1000 per query) sized to the question.
It exposes 15 tools the agent chooses among — more expressive for
structural questions like `trace_path` or `get_architecture`, and more
dependent on the agent picking well.

| Dimension | codebase-memory-mcp | NeuralMind |
|---|---|---|
| Distribution | Single static C binary, no runtime | Python package (PyPI), Docker, VS Code extension |
| Languages | 162 vendored grammars (~31 benchmarked, quality-tiered) | 10 tree-sitter, Python-first eval coverage |
| Type resolution | Hybrid LSP for ~10 major languages | Heuristic by default; SCIP precision opt-in (Python/TS/Go) |
| Embeddings | Bundled `nomic-embed-code`, compiled in | MiniLM ONNX, downloaded on first build |
| Scale ceiling | Linux kernel (28M LOC) in ~3 min | Tuned for single-project repos, not kernel-scale monorepos |
| Query latency | Sub-ms Cypher traversal | Slower — vector + graph, Python |
| Tool surface | 15 MCP tools incl. Cypher traversal, ADR management | MCP tools + Claude Code lifecycle hooks |
| Learns from usage | No | Yes — Hebbian reinforcement with half-life decay |
| Tool-output compression | No | Yes — `PostToolUse` on `Read`/`Bash`/`Grep` |
| Team memory | Per-machine cache | Git-portable `.neuralmind-team-memory.json` |
| Retrieval ranking (our eval) | MRR 0.23 / 0.50 | MRR 0.96 / 0.60 |
| License | MIT | MIT (core); source-available commercial modules for the Team tier |

## When to pick which

**Pick codebase-memory-mcp if:**

- **Your repo is polyglot or in a language we don't parse well.** This
  is the decisive case. We index ten languages; it vendors 162. If your
  codebase is Kotlin, Swift, Elixir, Perl or Objective-C, our ranking
  advantage on `requests` is irrelevant to you.
- **Your repo is very large.** Kernel-scale indexing in minutes is a
  different engineering envelope from ours, and we don't claim to match
  it.
- **You want no language runtime** — a single signed static binary with
  no Python, no Node, no API key is an easier security review and an
  easier CI story.
- **You want structural graph queries as a first-class interface** —
  Cypher-like traversal, `trace_path`, architecture extraction.

**Pick NeuralMind if:**

- **Ranking quality on your language matters more than breadth.** On the
  repos we scored, the competitor surfaced the gold file in its top-8
  about half the time; the files it did surface cost an order of
  magnitude more tokens to read.
- You want the layer to **improve on this repo with use**, and to carry
  that memory between machines and agents via git.
- You want **both** levers — less context retrieved *and* compressed
  tool output.
- You're on Python/TypeScript/Go and want compiler-accurate edges via
  the SCIP precision mode.

## The honest caveats

- **Version-pinned and aging.** Our row tests **0.8.1**. That project
  ships frequently; a newer version may rank better. The eval is
  committed and re-runnable precisely so this can be checked rather than
  argued.
- **Two repos is not a corpus.** `requests` and `click` are both
  mid-sized, clean, single-language Python packages — the shape our
  approach handles best and the shape least likely to exercise a
  162-language indexer's strengths. Read the ranking result as
  directional.
- **We measure ranking; they publish agent-loop quality.** Their ~83%
  answer-quality figure comes from an LLM-driven loop. Our MRR figure
  comes from scoring ranked files. Both are legitimate; they are not the
  same measurement, and neither refutes the other.
- **Breadth comparison isn't like-for-like.** "162 languages" is
  vendored grammars, not 162 benchmarked languages — their own docs tier
  quality, with some languages below 75%. Our ten are structurally
  parity-gated in CI but quality-measured mostly on Python. Both counts
  need reading, not comparing.

## See also

- [Public benchmark methodology](../benchmarks/public.md#competitor-head-to-head--codebase-memory-mcp-081)
  — full provenance for the table above
- [`evals/public/COMPETITORS.md`](../../evals/public/COMPETITORS.md) —
  why this is the only live scored row, and the fairness contract a new
  one must meet
- [vs. Graft](./vs-graft.md) — the other local code-graph tool, compared
  on capability only
- [All comparisons](./README.md)
