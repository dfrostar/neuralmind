# `benchmarks/` — run the numbers yourself

> "Trust me bro" is not a benchmark. Every headline NeuralMind claims is produced
> by code in this repo, most of it **gated in CI**, and you can re-run all of it
> from a source checkout. This folder is the **index + one-command runner** for
> those harnesses — the harness code itself lives under
> [`evals/`](../evals/), [`bench/`](../bench/), and
> [`tests/benchmark/`](../tests/benchmark/).

The harnesses pre-date this folder; they were just scattered across three trees
with no single entry point. This page is that entry point, plus an honest
statement of **what is *not* measured yet**. Methodology write-up:
[`docs/benchmarks/public.md`](../docs/benchmarks/public.md); rendered results:
[`docs/wiki/Benchmarks.md`](../docs/wiki/Benchmarks.md).

---

## Quick start

```bash
# from a source checkout (the eval gold sets ship in the repo, not the pip wheel)
pip install -e ".[dev]" tiktoken

# the deterministic, offline, CI-gated suite — no network, no API key:
bash benchmarks/run_all.sh

# add the real-OSS-repo public benchmark (clones pinned repos, needs network):
bash benchmarks/run_all.sh --public

# add the scored competitor head-to-head (needs: pip install codebase-memory-mcp==0.8.1):
bash benchmarks/run_all.sh --competitor

# everything except the opt-in LLM-judged arm:
bash benchmarks/run_all.sh --all
```

Each harness prints a report and **exits non-zero if it falls below its gate** —
the same checks that run on every PR.

---

## The harnesses

| # | What it measures | Command | Network / key | Committed results |
|---|---|---|---|---|
| 1 | **Token reduction + learning + synapse A/B** (CI floor 4.0×) | `python -m tests.benchmark.run` | none | [`tests/benchmark/`](../tests/benchmark/) (golden queries; report printed on run) |
| 2 | **Answer quality** — faithfulness Δ at *matched budget* vs naive truncation | `python -m evals.faithfulness.runner --run` | none | `evals/faithfulness/` |
| 3 | **Onboarding lift** — does an agent inheriting committed team memory retrieve better cold? | `python -m evals.onboarding.runner --run` | none | `evals/onboarding/` |
| 4 | **Backend parity** — turbovec vs ChromaDB + multi-language structural parity | `python -m evals.parity.run` | none | `evals/parity/` |
| 5 | **Public benchmark** — cost *and* recall vs full-file / ripgrep / vector-RAG on **real pinned OSS repos** (`requests`, `click`) | `python -m evals.public.run` | network (clones repos) | [`bench/public/`](../bench/public/) |
| 6 | **Competitor head-to-head** — scored retrieval ranking vs `codebase-memory-mcp 0.8.1` | `python -m evals.public.competitor` | `pip install codebase-memory-mcp==0.8.1` | [`bench/public/competitor/`](../bench/public/competitor/) |
| 7 | **Latency / memory / disk** — turbovec vs chroma index size, search p50/p95, RSS | `python benchmark_turbovec.py --out results.json` | none | [`BENCHMARK_TURBOVEC.md`](../BENCHMARK_TURBOVEC.md) |
| 8 | **Your own repo** — reduction ratio, tokens/query, est. monthly savings | `neuralmind benchmark .` | none | — |

Useful variants of #8:

- `neuralmind benchmark . --quality` — precision@k / recall@k / MRR / answerability
  over the golden polyglot suites (contributor/CI self-test).
- `neuralmind benchmark . --public` — reproduce harness #5 against the pinned repos.
- `neuralmind benchmark . --public --judge` — opt-in LLM-judged answerability arm
  (needs `ANTHROPIC_API_KEY`; **never runs in CI**; the recall table is
  byte-identical with or without it; transcripts written under `bench/public/judge/`).
- `neuralmind benchmark . --contribute` — emit a schema-ready JSON blob to paste
  into a [community-benchmark submission](https://github.com/dfrostar/neuralmind/issues/new?template=community-benchmark.yml).
  Nothing is uploaded.

---

## What the numbers say (short version)

Full tables on the [Benchmarks](../docs/wiki/Benchmarks.md) page. Headline:
**100% gold-file recall at 38–85× fewer tokens** than pasting files on real OSS
repos, beating `ripgrep` on *both* recall and cost; **+0.143** faithfulness at a
matched budget; **+11.7 pts** top-k hit-rate from the synapse layer
(budget-neutral). We also report where NeuralMind **doesn't** win — a well-tuned
vector RAG ties it on pure findability and is cheaper on raw tokens, and the
competitor row is **pure retrieval ranking**, not their LLM-agent loop.

---

## What we don't measure yet (honestly)

The critique that asks "where are the independent benchmarks?" is partly right.
These gaps are real and **not** papered over with invented numbers — they're
tracked on [`ROADMAP.md`](../ROADMAP.md):

- **SWE-bench / agent-loop task completion.** Every harness here scores
  **retrieval** (does the right code land in the window?), not end-to-end
  **issue-resolution** accuracy. NeuralMind is a context layer; wiring it behind a
  full agent on SWE-bench and reporting solve-rate deltas is unbuilt.
- **Aider polyglot *agent* accuracy.** We compare *features* against Aider's
  repo-map ([`docs/comparisons/vs-aider-repomap.md`](../docs/comparisons/vs-aider-repomap.md))
  and score our own retrieval, but there is no head-to-head "Aider+LLM vs
  NeuralMind+LLM solve-rate per language" number.
- **Scored head-to-heads beyond one competitor.** Harness #6 scores exactly one
  incumbent (`codebase-memory-mcp`). Bloop, Sourcegraph Cody, Continue/Cline, and
  Headroom have **qualitative** comparison pages
  ([`docs/comparisons/`](../docs/comparisons/README.md)) but no reproducible scored
  runs — their differing interfaces (server, IDE extension, HTTP proxy) make
  fair-play normalization real work.
- **Independent third-party runs.** The public benchmark is reproducible, but the
  published numbers are still maintainer-run. Outside runs — *especially*
  disappointing ones (e.g. "8× not 50× on my Rust monorepo") — are the single most
  valuable contribution; `--contribute` makes one in a copy-paste.
- **Large-real-repo quality & incremental latency.** Gated quality is on a small
  fixture + two real OSS repos; 1M–10M LOC quality and "200-file `git pull`
  re-index in N ms" are "trust the gate," not benchmarked. See
  [Limits & Failure Modes](../docs/wiki/Limits-and-Failure-Modes.md).
- **Customer case studies.** None published. We won't fabricate dashboard
  screenshots.

If you close any of these with real data, a PR is welcome — that's exactly the
contribution the project most needs.
