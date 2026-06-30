# Honest assessment

The skeptic's companion to [BUSINESS-CASE.md](BUSINESS-CASE.md). The
business case makes the compelling, fact-based argument *for*
NeuralMind. This page is the counterpart: when NeuralMind isn't
worth installing, what the headline numbers don't measure, and
where the evidence is still thin. Read both before deciding.

This document represents the project's stance, drafted with AI
assistance and reviewed by the maintainer. Pull requests that
sharpen the honesty are welcome.

> **Operational companion:** this page is about *whether to install*.
> For *where it stops working once installed* — when a single query
> isn't enough, the repo-size envelope, and the per-language support
> matrix with explicitly-unsupported features — see
> [Limits & Failure Modes](wiki/Limits-and-Failure-Modes.md). For the
> reproducible numbers, see [`benchmarks/`](../benchmarks/README.md).

---

## TL;DR

NeuralMind is **most useful** if you are a Claude Code or Cursor user
with a codebase larger than ~10K lines who is feeling token cost or
context-limit pressure today. It is **not very useful** if your
codebase fits in a single context window, you don't pay for inference,
or you've already invested in prompt caching plus a long-context
model.

The headline "40–70×" reduction is real, but it's a reduction in
**retrieval input tokens**, not a reduction in your total LLM bill.
What you actually save depends on how much of your spend is retrieval
vs. generation, which varies wildly by workload. For a typical
Claude Code session the realistic end-to-end savings is **3–10×**
total cost, not 40–70×.

The community-benchmark table is currently **two entries from the
maintainer's own projects**. Numbers from outside contributors are
the single most valuable thing you can give back if NeuralMind ends
up working for you.

---

## When NeuralMind is worth setting up

You'll likely see real benefit if **all** of these are true:

- You pay for inference (Claude API, OpenAI API, Cursor's metered
  plan, etc.) — not the case for free-tier users on capped plans.
- Your codebase is **>10K lines** and growing. Below that, modern
  long-context models can hold the whole thing.
- You hit context-limit errors mid-task at least weekly, OR your
  monthly LLM bill is large enough that a 3–10× reduction is worth
  ~30 min of setup.
- You use an **AI agent** (Claude Code, Cursor, Cline, Continue) for
  multi-step code work — not just inline completions.
- Your codebase is in a language [graphify](https://github.com/dfrostar/graphify)
  parses well: Python, TypeScript, JavaScript, and a handful of
  others via tree-sitter. Coverage drops outside that set.

If you check 3 of 5, marginal. If you check 4–5, run
`bash scripts/demo.sh` and then `neuralmind benchmark .` on your repo.

## When NeuralMind is **not** worth it

- **Your codebase is under ~5K lines.** Just paste it into the
  context. The setup cost will exceed the savings forever.
- **You don't pay per token.** Free-tier or flat-rate users don't
  recover the setup time.
- **You only want inline completions.** Use [Copilot](https://github.com/features/copilot)
  or your editor's native autocomplete. NeuralMind is the context
  layer for agents, not a completion layer.
- **You need cross-repo / org-wide search.** That's
  [Sourcegraph Cody's](https://about.sourcegraph.com/cody) niche.
  NeuralMind is intentionally per-project and local.
- **You've already adopted prompt caching with a long-context model.**
  Caching gets you ~80–90% of the cost reduction with zero retrieval
  infrastructure. NeuralMind composes with caching but the marginal
  win is smaller. Run the benchmark to see if it justifies the
  setup; for many teams it won't.
- **Your repo is non-standard** — heavily generated code, polyglot
  with weak tree-sitter coverage, or unusual layouts. Retrieval
  quality depends on graph quality, which depends on graphify, which
  depends on tree-sitter parsers per language. Real-world quality
  varies more than the headline numbers suggest.

## What "40–70× reduction" actually means

The number is honest **for what it measures**:

> Retrieval-stage input tokens vs. a "load every code file"
> baseline, on the same query, measured with `tiktoken`.

What it **does not** mean:

- It is **not** a 40–70× reduction in your monthly LLM bill. Output
  tokens are unchanged. Conversation history accumulates. The
  retrieval call is one of many a chatty agent makes.
- It is **not** measured against a smart-baseline like Cursor
  `@codebase` or Claude Code's built-in retrieval — those already do
  *some* retrieval. NeuralMind's marginal benefit over them is
  smaller than 40–70× and we have not yet measured it rigorously.
- It is **not** uniform across languages or repo shapes. Python
  repos with clean module structure see the high end; polyglot
  monorepos with generated code see the low end.

A realistic mental model: **NeuralMind shrinks the "what context to
load" decision from O(repo) to O(query)**. If your agent makes 100
context-loading calls a day on a 50K-token repo, that compounds.
If it makes 5 calls a day on a 5K-token repo, it doesn't.

## The community benchmark caveat

The table in [README.md](../README.md#community-benchmarks) currently
has **two entries**, both from repositories owned by the project
maintainer. This is honest disclosure, not a flaw — the project is
new and outside benchmarks take time to accumulate. But it means:

- The maintainer's repos may share structural patterns that
  NeuralMind happens to handle well.
- We don't yet have data on enterprise codebases, polyglot
  monorepos, or repos with heavy generated code.
- Until the table has 10+ outside entries, treat the headline range
  as **directional, not predictive**.

If you run the benchmark, please contribute your numbers — even
disappointing ones. A "I tried NeuralMind on my Rust monorepo and
got 8×, not 50×" entry is more valuable to the next visitor than a
"55× on my hand-picked Python repo" entry.

```bash
neuralmind benchmark . --contribute
```

## What we haven't measured well yet

The current benchmark suite covers **token reduction** rigorously
(self-benchmark in CI, regression-gated). It covers **retrieval
quality** weakly (top-k hit rate on a 10-query fixture). It does
**not** yet cover:

- **Answer faithfulness.** Does the agent's answer get *better*
  with NeuralMind context, or just shorter? We have anecdotes, not
  measurements.
- **End-to-end cost reduction.** Real workloads have multi-turn
  conversations, tool calls, and output generation — not just
  retrieval. We measure the retrieval step, not the workload.
- **Quality on languages other than Python.** The fixture is
  Python-only.
- **Quality on large real-world repos.** The fixture is ~500 lines.

These are tracked on [ROADMAP.md](../ROADMAP.md) under "Next" and
are open contribution targets.

## Setup cost (realistic)

| Step | First time | Re-run / re-build |
|---|---|---|
| `pip install neuralmind graphifyy` | ~30s | n/a |
| `graphify update .` (knowledge graph) | 10s–2min depending on repo size | seconds, incremental |
| `neuralmind build .` (vector index) | 30s–5min depending on graph size | seconds, incremental |
| Editor / agent integration | 5–10min | n/a |
| **Total to first query** | **~10–20 min for a 50K-line repo** | seconds |

Re-runs after code changes are fast (incremental). First-time setup
is the friction point. If your monthly LLM bill is under $50, that
~15 min may not pay back; if it's over $500, it almost certainly
will.

## Versus the obvious alternatives, honestly

- **Cursor `@codebase`** — free if you already use Cursor, zero
  setup. Quality is opaque and varies. NeuralMind wins if you want
  the same retrieval across multiple agents (Claude Code + Cursor +
  ChatGPT) or if you want measurable, reproducible numbers.
- **Claude Code's built-in retrieval** — improving constantly. The
  baseline keeps moving. NeuralMind's compression hooks
  (`PostToolUse`) compose with it; the retrieval value-add depends
  on how good Claude Code's built-in is on the day you measure.
- **Long context (1M, 2M tokens) + prompt caching** — the most
  honest competitor. Caching gives you ~90% cost reduction with no
  retrieval infrastructure. NeuralMind is additive (smaller cached
  prompt = cheaper cache reads) but the marginal win is smaller
  than the 40–70× headline suggests. Measure on your workload.
- **`grep` + `Read` + careful prompting** — if you only run a few
  questions a day, this is fine. NeuralMind's value scales with
  query volume.
- **Headroom (universal context compression)** — compresses tool
  outputs, conversation history, RAG chunks, and files for any
  provider, with prompt-cache alignment; strictly more general
  *compression* than ours, and more mature in that category. It has
  no semantic codebase index and no persistent memory of your code.
  The two compose (their proxy under, our retrieval on top). If
  compression is your whole problem, use Headroom.
- **Generic RAG (LangChain/LlamaIndex over code)** — more flexible,
  more setup, loses the call graph. NeuralMind is a pre-assembled
  default for code; pick this if you want the call-graph structure
  preserved without writing your own pipeline.

See [`docs/comparisons/`](comparisons/README.md) for longer
side-by-sides on each.

## What would change our minds

We'd downgrade our own claims if:

- Community benchmarks (n ≥ 10 outside repos) show median
  reduction below 5×. (Currently directionally above this on n=2.)
- Top-k retrieval hit rate on a real-world query set falls below
  60%. (Currently 71.7% on the fixture.)
- A long-context + prompt-caching baseline closes the cost gap to
  within 1.5× on representative workloads.

We'd upgrade them if:

- A faithfulness study shows agent answer quality measurably
  improves vs. naive retrieval, not just token count drops.
- Enterprise pilot data confirms the multi-developer cost-aggregation
  story.

## Decision in three lines

- Big repo, paying for tokens, hitting context limits → **try it,
  the demo is 30 seconds.**
- Small repo, free tier, or already using prompt caching → **probably
  skip; come back when something changes.**
- Anywhere in between → **`bash scripts/demo.sh`, then
  `neuralmind benchmark .` on your code, decide from data.**
