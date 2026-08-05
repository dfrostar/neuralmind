# NeuralMind — Session Handoff Document (v3.0.2 → v3.1.0)

**Date:** 2026-08-05
**Status:** v3.0.2 stable, v3.1.0 in progress (document retrieval eval)

---

## Summary of Last Session

### What Was Done

1. **Adversarial QA on NeuralMind marketing site** — Corrected inflated claims:
   - Synapse uplift: +14pts → +6.1pts (actual: 0.833-0.772 = +6.1pts)
   - CI fixture ratio: 6.6× → 6.1× (actual avg: 6.05)
   - Test count: 55 → 40 (test_server=23 + test_dashboard=17)

2. **Documentation sweep** — Fixed all current-state docs with correct synapse numbers:
   - README.md (lines 100, 278, 282, 283)
   - benchmarks/README.md
   - docs/wiki/Home.md, Benchmarks.md, CLI-Reference.md
   - docs/benchmarks/public.md, docs/llms.txt
   - docs/about.html
   - docs/releases/RELEASE_NOTES_v0.19.0.md, v0.25.0.md, v0.31.0.md
   - evals/onboarding/README.md, evals/onboarding/harness.py
   - Historical release notes (v0.19, v0.20, v0.25, v0.31) left as-is

3. **Book retrieval eval** — Built infrastructure for testing document retrieval:
   - Downloaded "Underground" by Suelette Dreyfus (Project Gutenberg, 150K words, 11 chapters)
   - Extracted chapters to evals/book_retrieval/underground/chapters/
   - Created 30 gold-standard queries covering all chapters
   - Built evals/book_retrieval/run.py — runner that ingests, queries, scores
   - First run: **86.7% recall, 248× token reduction** vs full-text baseline

4. **GLM adversarial QA** — Dispatched subagent to verify all claims in session prompt
   - Found test split misstated (29+11 vs actual 23+17)
   - Found README was stale (still +14pts)
   - Found "6.6×" was unsupported by any data file

### Key Decisions

- **N-06 (Scope decision):** User chose **code-only** positioning. Document ingestion stays as a feature but NOT marketed as "second brain."
- **Adversarial QA:** GLM subagent model is `nvidia/nemotron-3-ultra-550b-a55b`
- **Onboarding lift +11.6pts:** Different eval (evals/onboarding/), no committed results file. NOT changed.

---

## Current Repo State

### NeuralMind (v3.0.2)

```
Tag: v3.0.2
Branch: main
Remote: dfrostar/neuralmind (pushed)
Commits this session:
  b8b0bdf eval: book retrieval initial results — 86.7% recall, 248× token reduction
  e80bc32 feat: add book retrieval eval for document ingestion testing
  7e0ea39 docs: correct synapse baseline in onboarding README
  6fe106a eval: book retrieval initial results (rebased)
  ...
```

### cmmc20

```
Commits this session:
  fda00c2 docs: correct synapse uplift + test count in session prompt
```

### Files Changed (NeuralMind)

```
evals/book_retrieval/
  __init__.py
  manifest.json (30 queries, gold paragraphs)
  run.py (eval runner)
  corpus/ (peptide book chapters — moved to archive)
  underground/chapters/ (11 chapters from Project Gutenberg)

README.md (synapse + CI fixture corrections)
benchmarks/README.md (synapse correction)
docs/wiki/Home.md, Benchmarks.md, CLI-Reference.md (synapse corrections)
docs/benchmarks/public.md, docs/llms.txt (synapse corrections)
docs/about.html (synapse corrections)
docs/releases/RELEASE_NOTES_v0.19.0.md, v0.25.0.md, v0.31.0.md
evals/onboarding/README.md, evals/onboarding/harness.py (baseline correction)
```

---

## v3.1.0 Release Plan

### Goal: Document Retrieval as a First-Class Feature

The book retrieval eval proves document ingestion works. v3.1.0 makes this discoverable, usable, and marketed.

### Features to Build

1. **CLI: `neuralmind ingest` command** — Clean, documented way to ingest documents
   - Support PDF, Markdown, text
   - Show progress (nodes created, time)
   - Error handling for missing files, wrong formats

2. **Site: Document retrieval page** — New page on neuralmind.uk
   - Explain the feature
   - Show the Underground eval results (86.7% recall, 248× reduction)
   - Provide ingestion instructions

3. **README: Document section** — Add to feature list
   - "Ingest PDFs, books, documentation"
   - "Search across code + documents in one query"

4. **Eval expansion** — More books, more queries
   - Add at least one more public domain cybersecurity book
   - Target: 100+ total queries across 2+ books
   - Compare NeuralMind vs static RAG baseline

5. **Synapse layer for documents** — Enable `NEURALMIND_LLM_SEED=1` for ingested docs
   - Currently disabled (requires ANTHROPIC_API_KEY)
   - Wire up so document co-activations create synapse edges
   - Measure: does synapse layer improve document retrieval over time?

### Release Criteria

- [ ] `neuralmind ingest` CLI command works end-to-end
- [ ] Book retrieval eval: 100+ queries, 2+ books
- [ ] README documents the feature
- [ ] Site has a page for it
- [ ] All existing tests pass (test_benchmark_regression debug-token-expire is pre-existing failure)
- [ ] Synapse document seeding enabled

---

## Pre-Existing Issues (Not Mine)

- `tests/test_benchmark_regression.py::test_every_query_has_at_least_one_module_hit` — FAILING
  - Root cause: `debug-token-expire` query has 0% hit rate in results.json
  - Not caused by this session's changes

- `tests/test_server.py` — 23 tests passing
- `tests/test_dashboard.py` — 17 tests passing
- `tests/test_onboarding_eval.py` — 13 tests passing

---

## File Map

```
neuralmind/                          — Code (v3.0.2 tagged)
neuralmind-autopilot/docs/neuralmind/ — Planning docs + kanban
cmmc20/                              — Level2Logic CMMC SaaS platform
ai-agent-playbook-v2/                — Book engine (peptide book, AI playbook)
```

---

## Uncommitted / In-Progress

None — all work is committed and pushed.

---

## Next Steps (Priority Order)

1. Build `neuralmind ingest` CLI command
2. Add a second book to the eval (another public domain cybersecurity text)
3. Wire up synapse layer for document co-activations
4. Create site page for document retrieval
5. Update README with document section

---

*Generated by Hermes Agent | 2026-08-05*
