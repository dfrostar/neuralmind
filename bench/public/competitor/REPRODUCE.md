# Competitor head-to-head — `codebase-memory-mcp` (executed, reproducible)

This file is the **auditable provenance** for the `codebase-memory-mcp` row in
the public benchmark. The competitor runs headless with **no LLM API key**
(on-device embeddings), so we run it in a scripted, documented way and commit the
raw output under `raw/`. Anyone can re-run these exact steps independently.

We never tune the competitor to lose: we tested three reproducible NL→keyword
mappings and used the one **most favorable to the competitor** (all question
words). If you can represent it more fairly, open a PR.

## Pinned version

- Tool: `codebase-memory-mcp` (DeusData) — https://github.com/DeusData/codebase-memory-mcp
- Version: **0.8.1** (`codebase-memory-mcp --version`)
- Install: `pip install codebase-memory-mcp==0.8.1` (thin wrapper; downloads the pinned
  single static binary from GitHub Releases on first run — needs network, no GUI,
  no API key). Docs: https://deusdata.github.io/codebase-memory-mcp/

## Environment

- Same pinned repos and the **same `evals/public/manifest.json` query set** used
  for every other backend (identical questions, identical objective def-site gold
  files), scoped to the same `subdir` (`src/requests`, `src/click`).
- Retrieval depth capped at `sem_limit = 8`, matched to the `embedding-rag`
  baseline's top-k, so recall@k / MRR / cost are apples-to-apples.
- Same tokenizer (`tiktoken o200k_base`) for the cost proxy.

## Procedure (exactly what the adapter runs)

```bash
pip install codebase-memory-mcp==0.8.1        # pins 0.8.1; downloads binary on first run
export CBM_CACHE_DIR=.bench-work/cbm-cache

# 1. index the pinned checkout (the runner clones it from the manifest)
codebase-memory-mcp cli --json index_repository '{"repo_path": "<abs>/.bench-work/requests/src/requests"}'

# 2. one semantic query per question — keywords = ALL words of the question
codebase-memory-mcp cli --json search_graph \
  '{"project": "<project-name-from-step-1>", "semantic_query": ["how","is","http","basic",...], "sem_limit": 8}'
# → {"content":[{"text":"{... \"semantic_results\":[{\"file_path\":...,\"score\":...}] ...}"}]}
```

Or just run the whole thing (off the default benchmark path):

```bash
python -m evals.public.competitor            # both repos → bench/public/competitor/
python -m evals.public.competitor --repo requests
```

The adapter (`evals/public/competitor.py`) parses the MCP `content[0].text`
envelope, caps at `sem_limit`, projects `file_path` → basename, and scores with
the **same** `neuralmind.quality` gold-file-recall code as every other backend.
It is intentionally NOT wired into `python -m evals.public.run`, so the public CI
table never depends on an external binary download.

## Status — RUN

Executed against `codebase-memory-mcp 0.8.1`. Raw per-query traces (keywords +
ranked files + recall) committed under `raw/requests.json`, `raw/click.json`;
summary in `results.json`. Results table + honest caveats in
[`docs/benchmarks/public.md`](../../../docs/benchmarks/public.md).

### Honest caveats (read these)

- **Pure retrieval, no agent loop on either side.** This measures the
  competitor's *retrieval ranking given reproducible keywords* — exactly parallel
  to how we test NeuralMind's own `search` (question → ranked files). The
  competitor's published numbers (~90% of an "Explorer" agent) are a *different*,
  LLM-driven measurement that isn't reproducible without paying for an LLM; we
  don't claim to reproduce that.
- **Most-favorable keyword mapping.** All question words (its best of three
  reproducible strategies on this corpus).
- **Cost is a proxy.** The competitor returns ranked file paths (the agent then
  reads them); its "cost" here is the tokens of the distinct whole files it
  surfaces at depth 8 — analogous to how `ripgrep` is costed.
- **Its own claims, cited fairly:** the competitor's paper reports C at **0.58**
  and ~**90%** of the Explorer agent across 31 scored languages; marketing says
  "158 languages" (≈ vendored grammars, not all benchmarked).
