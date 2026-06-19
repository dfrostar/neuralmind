# PRD: Competitor head-to-head — `codebase-memory-mcp` in the public benchmark

**Status:** Draft · **Owner:** dfrostar · **Created:** 2026-06-19
**Tracking branch:** `claude/competitor-benchmark` · **Target:** v0.33.0

## 1. Background & strategic motivation

v0.31.0 shipped the honest public benchmark (`neuralmind benchmark --public`) with
the competitor row scaffolded as a documented fast-follow. That fast-follow is
the **single most important credibility piece before any public launch**: the
first question on HN/Reddit will be *"how does this compare to
codebase-memory-mcp?"* (6.6k★, the obvious incumbent). A benchmark that answers
that question *in the table*, reproducibly, pre-empts the top comment. Leaving it
as a scaffold invites "so you didn't actually compare."

Feasibility is now **confirmed by a live probe** (not assumed): the competitor
runs **headless with no LLM API key** — on-device embeddings, a single-binary
CLI (`cli --json search_graph`) that returns ranked `semantic_results[]` with
`file_path` + `score`. We indexed `requests` with it and ran real queries. So the
head-to-head can be a *live, reproducible* row, scored by the **same
`quality.py`** gold-file-recall code every other backend uses.

## 2. What already exists

- `evals/public/` — the benchmark harness, the pinned `requests`/`click` corpus
  with objective def-site gold files, the `full-file`/`ripgrep`/`embedding-rag`/
  `neuralmind` backends, deterministic runner, and `quality.py` scoring.
- `bench/public/competitor/REPRODUCE.md` — the provenance scaffold defining the
  exact procedure (pin version, reuse the same query set + gold, same scorer),
  with a placeholder `competitor_adapter` command.

## 3. The gap (what v0.33.0 adds)

1. **`evals/public/competitor.py`** — a real, thin adapter that shells out to
   `codebase-memory-mcp`: index a pinned checkout, then for each query issue a
   `search_graph` semantic call and project `semantic_results[].file_path` to the
   gold-file basename. Emits a `BackendResult` exactly like the other backends
   (scored by `quality.py`), so the competitor row is apples-to-apples on **both**
   axes (gold-file recall + a token/cost proxy — see §5).
2. **A documented, fair NL→keyword mapping.** The competitor's semantic interface
   takes a **keyword array**, not free text. We derive keywords from each
   benchmark question. We tested three reproducible mappings and ship the one
   **most favorable to the competitor** (all question words, via
   `competitor_keywords()`) — no per-query hand-tuning — and disclose it
   prominently. This is the crux of fairness (§6).
3. **Live but quarantined.** The competitor is a **separate entrypoint**, not
   part of `python -m evals.public.run` (the public CI table never depends on an
   external binary download): run it with `python -m evals.public.competitor`.
   Its results + **raw per-query traces** are committed under
   `bench/public/competitor/`, and the row is folded into
   `docs/benchmarks/public.md` marked with the pinned competitor version.
4. **Honest accounting of differences** — index node counts, the keyword-mapping
   caveat, and the competitor's *own* published claims (and where marketing and
   their paper disagree) so the comparison is contextualized, not a gotcha.

## 4. Goals / non-goals

**Goals**
- A reproducible competitor row in the public benchmark: same pinned repos, same
  questions, same objective gold, same `quality.py` scorer, pinned competitor
  version, committed raw traces.
- Fair to the competitor: documented keyword mapping, its intended interface, no
  hand-tuning; report where it wins too.

**Non-goals**
- Not gating CI on the competitor (external binary download; stays a separate
  `python -m evals.public.competitor` entrypoint). Not re-implementing its
  scoring. Not an agentic end-to-end eval — same findability metric (gold-file
  recall) as the rest of the suite.

## 5. Measuring cost fairly

NeuralMind's cost axis is assembled-context tokens. The competitor returns ranked
**file paths** (the agent then reads them), so its honest "cost" proxy is the
tokens of the files it surfaces at its retrieval depth — analogous to how the
`ripgrep` baseline is costed (top-N whole files). We report the competitor on the
**recall axis primarily** (its semantic ranking quality vs. gold), and give a
clearly-labeled cost proxy (tokens of surfaced files at matched depth) rather than
overstate a tokens-saved number its interface doesn't directly define.

## 6. Fairness & honesty (the credibility crux)

The benchmark is worthless to skeptics if it looks rigged against the competitor.
Hard requirements:

| Risk | Mitigation |
|------|-----------|
| "You gave it bad keywords." | We tested three reproducible mappings and ship the one **most favorable to the competitor** (`competitor_keywords()` — all question words, no stopword filtering), on the **same** question — no per-query tuning. The mapping is one published function; a skeptic can change it and re-run. |
| "You used a stale/old version." | **Pin the exact competitor version** (probed: 0.8.1) in the adapter + REPRODUCE.md; print it in the row. |
| "You misconfigured it." | Use its documented `cli index_repository` + `search_graph` path verbatim; commit the exact commands + raw JSON traces. |
| "You only showed where you win." | Report **every** query incl. ones where the competitor ties/beats NeuralMind; keep the "where NeuralMind loses" section honest across backends. |
| "Self-serving framing." | Cite the competitor's **own** published numbers (its paper: ~90% of the Explorer agent, C=0.58, ~120× token claim) and note where its marketing ("158 languages") and paper (31 scored) diverge — factually, without snark. |

## 7. Acceptance criteria

- [x] `evals/public/competitor.py` — pinned-version (0.8.1) adapter (index +
      semantic query), `competitor_keywords()` all-words mapping (most favorable
      to the competitor), returns a `quality.py`-scored `BackendResult`; fails
      closed (clean skip) if the binary isn't installed.
- [x] `python -m evals.public.competitor` runs it — a **separate entrypoint**,
      not wired into `python -m evals.public.run` (kept off the CI path).
- [ ] Real competitor row produced on `requests` + `click`, raw per-query traces
      committed under `bench/public/competitor/raw/`, REPRODUCE.md updated from
      scaffold → executed (pinned version, exact commands).
- [ ] `docs/benchmarks/public.md` + `bench/public/report.md` include the
      competitor row, the keyword-mapping disclosure, and the competitor's own
      cited claims; every query reported incl. losses.
- [ ] Hermetic tests for the adapter's parsing/scoring (mock the binary's wrapped
      `content[0].text` JSON; no network in CI).
- [ ] Docs + SEO per CLAUDE.md (release notes, README pointer, keywords like
      `codebase-memory-mcp-benchmark`, `code-mcp-comparison`).

## 8. Rollout

PRD → build on `claude/competitor-benchmark` → run the real head-to-head → CI
green (adapter tests hermetic; live row reproduced out-of-band and committed) →
hold for merge okay → merge cuts **v0.33.0**. After this lands, the benchmark
answers the launch's hardest question, and the **announcement** (Show HN +
r/LocalLLaMA + awesome-mcp PR) is the next step.
