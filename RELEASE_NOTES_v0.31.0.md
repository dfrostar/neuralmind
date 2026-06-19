# NeuralMind v0.31.0 — the honest public benchmark

**Release Date:** June 2026

## TL;DR

NeuralMind's headline claim has always been "40–70× fewer tokens on code
questions." v0.31.0 backs it with evidence built to **survive hostile expert
scrutiny**: a reproducible, no-cherry-picking benchmark on **real, pinned OSS
repos** (`requests`, `click`), against **strong baselines** (full-file paste,
ripgrep, a same-encoder vector RAG), reporting **cost _and_ correctness
together** — and shipping the forkable runner + raw data so anyone reproduces it
without trusting us.

```bash
# The harness ships in the source tree (evals/public), not the PyPI wheel:
git clone https://github.com/dfrostar/neuralmind && cd neuralmind
pip install -e . tiktoken
python -m evals.public.run              # clones pinned repos, prints the table
# or, from the clone: neuralmind benchmark --public
```

## The result (real numbers, reproduce them yourself)

Gold-file recall (objective **def-site** oracle — no LLM judge) vs. context
tokens, tiktoken `o200k_base`, deterministic:

| repo | backend | gold-file recall | mean tokens/query | vs full-file |
|---|---|---:|---:|---:|
| requests | full-file | 1.00 | 41,729 | 1× |
| requests | ripgrep | 0.79 | 26,543 | 1.6× |
| requests | embedding-rag | 1.00 | 607 | 69× |
| requests | **neuralmind** | **1.00** | **1,095** | **38×** |
| click | full-file | 1.00 | 78,514 | 1× |
| click | ripgrep | 0.79 | 45,059 | 1.7× |
| click | embedding-rag | 1.00 | 649 | 121× |
| click | **neuralmind** | **1.00** | **924** | **85×** |

**Honest headline:** against what agents actually do today — paste files or grep
— NeuralMind reaches **100% gold-file recall at 38–85× fewer tokens**, and beats
ripgrep on *both* recall and cost. We also show, without hiding it, that a
well-tuned vector RAG is excellent at *findability* too (and cheaper on raw
tokens) — because credibility comes from reporting the losses, not just the wins.
Full analysis, caveats, and "where NeuralMind loses" in
[`docs/benchmarks/public.md`](docs/benchmarks/public.md).

## Why it's hard to dismiss

- **Real pinned repos**, not our fixtures — `git checkout <sha>` and audit.
- **Objective gold, no LLM judge** — each gold file is a symbol's definition
  site, verifiable with one `rg`. Scoring reuses the same `neuralmind/quality.py`
  the CI gate runs.
- **Cost + correctness jointly** — never a lone reduction ratio.
- **Pre-registered queries, every one reported, including losses.**
- **Deterministic** — synapse injection off (session-dependent learning can't be
  a fixed public number; its +11.7pt lift is measured separately by the synapse
  A/B eval). Re-running matches to the token.
- **Forkable** — `.github/workflows/bench-public.yml` regenerates the table on
  demand; raw per-query data committed at `bench/public/results.json`.
- **Competitor, fairly (fast-follow)** — a `codebase-memory-mcp` head-to-head is
  **not in this release yet**; its deps don't install in our CI sandbox. The
  provenance scaffold (`bench/public/competitor/REPRODUCE.md`) defines the pinned,
  same-query-set procedure so that when it's run the rows land marked "reproduced
  externally" with committed raw traces — auditable rather than taken on our word.

## What ships

- **`neuralmind benchmark --public`** (and `python -m evals.public.run`) — the
  reproducible vs-alternatives benchmark, `--repo` to scope, `--json` for CI.
- **`evals/public/`** — manifest (pinned repos + pre-registered queries),
  baseline matrix, deterministic runner, all scoring via `neuralmind.quality`.
- **`docs/benchmarks/public.md`** — methodology, results, honest caveats,
  reproduce steps.
- **`bench/public/`** — committed snapshot (`report.md`, `results.json`) + the
  competitor reproduce scaffold.
- **`.github/workflows/bench-public.yml`** — forkable, on-demand reproduction.
- Tests: `tests/test_public_benchmark.py` (hermetic — scoring/assembly pinned
  with synthetic data, no network).
- PRD: `docs/prd/public-benchmark.md`.

## Per-agent expectations

| Agent | What changes in v0.31.0 |
|-------|--------------------------|
| **All** | Nothing in runtime behavior — this release is *evidence*: a public, reproducible benchmark you can cite, fork, and extend. |
| **Evaluators / skeptics** | `neuralmind benchmark --public` reproduces the published table to the token on pinned real repos. |

## Upgrade

```bash
pip install --upgrade neuralmind
```

No migration. Install `tiktoken` for exact token counts (the harness falls back
to a disclosed chars/4 approximation without it).
