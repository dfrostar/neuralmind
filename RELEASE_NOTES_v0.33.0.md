# NeuralMind v0.33.0 — the competitor head-to-head, run for real

**Release Date:** June 2026

## TL;DR

The public benchmark's competitor row is no longer a scaffold — it's a **live,
reproducible head-to-head vs. `codebase-memory-mcp` 0.8.1** (the obvious
incumbent), on the same pinned repos, same questions, same objective gold, scored
by the same `quality.py` as every other backend. At matched retrieval depth:

| repo | backend | gold-file recall | found | MRR | mean tokens |
|---|---|---:|---:|---:|---:|
| requests | `codebase-memory-mcp` | 0.50 | 43% | 0.23 | 25,214 |
| requests | **neuralmind** | **1.00** | **100%** | **0.96** | **1,095** |
| click | `codebase-memory-mcp` | 0.64 | 57% | 0.50 | 38,538 |
| click | **neuralmind** | **1.00** | **100%** | **0.60** | **924** |

**NeuralMind finds the objectively-correct file every time and ranks it far
higher, at a fraction of the read cost.** Reproduce: `python -m
evals.public.competitor`.

## Why this matters

This is the question every launch audience asks first — *"how does it compare to
codebase-memory-mcp?"* — answered **in the table, reproducibly**, instead of with
adjectives. It's the last credibility piece before going public.

## Fair by construction (so it can't be dismissed)

- **Most-favorable competitor config.** Its semantic interface takes a keyword
  array, not free text; we tested three reproducible mappings and used the one
  **best for the competitor** (all question words). We can't be accused of
  crippling it.
- **Pinned + auditable.** Exact version (0.8.1), documented CLI, raw per-query
  traces committed under `bench/public/competitor/`, every query reported
  including losses.
- **Honest caveats, stated plainly.** This measures *pure retrieval ranking* (no
  LLM agent loop on either side — same as how we test NeuralMind's own `search`).
  The competitor's *published* numbers (~90% of an "Explorer" agent across 31
  scored languages; C at 0.58) come from an LLM-driven loop that isn't
  reproducible without paying for an LLM — we cite those as-is and don't claim to
  reproduce them. Its "158 languages" is vendored grammars, not all benchmarked.
  Cost is a labeled proxy (tokens of the files it surfaces, since it returns
  paths the agent then reads).
- **Runs headless, no API key** — the competitor uses on-device embeddings, so the
  whole comparison is deterministic and free to re-run.

## What ships

- **`evals/public/competitor.py`** — index + semantic-query adapter (parses the
  competitor's MCP `content[0].text` envelope, caps at `sem_limit`, scores via
  `quality.py`). **Off the default run** (external binary download); invoke with
  `python -m evals.public.competitor`. Fails closed without the binary.
- **`bench/public/competitor/`** — `raw/{requests,click}.json` traces,
  `results.json`, and `REPRODUCE.md` (now executed, pinned 0.8.1).
- **`docs/benchmarks/public.md`** — the real competitor row + fairness caveats.
- Tests: `tests/test_competitor_adapter.py` (hermetic — mocked binary, no network).
- PRD: `docs/prd/competitor-benchmark.md`.

## Upgrade

```bash
pip install --upgrade neuralmind
```

No runtime changes — this release is **evidence**. To reproduce the competitor
row, `pip install codebase-memory-mcp==0.8.1` (pins 0.8.1) and run `python -m
evals.public.competitor` from a clone.
