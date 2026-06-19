# PRD: Honest public benchmark — NeuralMind vs. the alternatives, reproducibly

**Status:** Draft · **Owner:** dfrostar · **Created:** 2026-06-19
**Tracking branch:** `claude/public-benchmark` · **Target:** v0.31.0

## 1. Background & strategic motivation

NeuralMind's headline claim is "40–70× fewer tokens on code questions." The
competitive review (`DeusData/codebase-memory-mcp` + the broader code-graph-MCP
field) is settled: breadth and packaging are commodity (closed in v0.27–v0.29),
and the moat is the learned synapse layer (shipped as a team artifact in
v0.30.0). What is **not** yet defensible is the *evidence*. Today's
`neuralmind benchmark` runs on our own `sample_project` fixture and reports a
reduction ratio. To a skeptical senior engineer on HN/Reddit that is a vendor
microbenchmark on a vendor fixture — dismissed in one reply.

This release makes the claim **survive hostile expert scrutiny**: a reproducible,
no-cherry-picking benchmark on **real, recognizable repositories**, against
**strong baselines** (not strawmen), reporting **cost _and_ correctness
together**, with raw data and a forkable runner published so a skeptic can
reproduce it without trusting us.

### 1.1 The credibility bar (non-negotiable design constraints)

The first objection to any "we send fewer tokens" benchmark is always: *"sure,
but did the agent still get the right answer?"* A token number unpaired with a
correctness number is worthless. Every requirement below exists to pre-empt a
specific, predictable expert objection.

| Predictable objection | Design answer |
|---|---|
| "Toy fixture you control." | Run on **pinned commits of real OSS repos** (Flask, Requests, FastAPI, Django…). Anyone can `git checkout <sha>` and verify. |
| "You sent fewer tokens but lost the answer." | **Cost and correctness are reported jointly**, per query, on the same task. The headline is a Pareto frontier, never a lone reduction ratio. |
| "You benchmarked against a strawman baseline." | Baselines include **plain embedding RAG** and **ripgrep**, configured strongly and disclosed — not just naive whole-file dump. |
| "You cherry-picked queries." | **Pre-registered query set**, committed before tuning; **every** query reported, including losses. |
| "One lucky run." | **Multiple seeds**; report mean ± spread, not a hero number. |
| "I can't reproduce it." | **One command, pinned deps, fixed seeds**, raw JSON + methodology doc published, **forkable GitHub Action**. |
| "Your LLM judge is rigged." | Primary correctness metric is **deterministic gold-file recall** (no LLM). Any LLM-judged arm is **secondary, opt-in, with the judge prompt + model published**. |
| "You configured the competitor to lose." | Competitor run is **best-effort to its own docs**, exact version/commit + config disclosed, and we **link their own reproduction steps**. |
| "Self-serving — where do you lose?" | Report **explicitly includes NeuralMind's losses and weak repos.** Admission is the credibility purchase. |

## 2. What already exists (build on, don't reinvent)

The measurement primitives are mature — the benchmark must reuse them so the
public numbers are the *same* numbers our CI gates on:

- **Self-benchmark** (`tests/benchmark/run.py`, `python -m tests.benchmark.run`)
  — Phase 1 token reduction vs. naive concatenation; Phase 2 synapse-recall A/B.
  tiktoken with char-approx fallback. Emits `results.json` + `report.md`.
- **Quality harness** (`neuralmind/quality.py`, `evals/quality/`) — standard
  ranked-retrieval metrics: precision@k, recall@k, **MRR**, **answerability@k**,
  over committed golden query sets (Python/TS/Go), CI-gated to a `baseline.json`.
- **Faithfulness eval** (`evals/faithfulness/`) — gold-fact recall of NeuralMind's
  selected context vs. a **matched-token-budget** naive truncation (the fair
  "smart selection vs. dumb truncation at equal cost" fight).
- **Parity gate** (`evals/parity/run.py`) — built-in vs. graphify backend.
- **Onboarding-lift** (`evals/onboarding/`) — cold vs. team-memory recall A/B.
- **Community leaderboard** (`docs/community-benchmarks.json` + schema,
  `neuralmind benchmark --contribute`) — user-submitted real-repo results.

**Gap:** none of these compare NeuralMind to an **external tool** or run on a
**real third-party repo**. This PRD adds exactly that, reusing the metric math
above verbatim (no new scoring logic invented behind closed doors).

## 3. What 0.31.0 adds

A new, self-contained benchmark suite — `bench/public/` — plus an
`evals/public/` harness and a published report:

1. **Real-repo corpus, pinned.** A small manifest of public repos at fixed
   commit SHAs, each with a **pre-registered, objectively-gradable query set**
   (see §5 for how gold sets stay objective). Start with 3–5 Python repos
   (where we have the strongest gold-fact tooling), structured to add TS/Go.
2. **A baseline matrix.** For each (repo, query), assemble context four ways and
   measure both axes:
   - `full-file` — read the whole candidate file(s) (the naive ceiling on cost).
   - `ripgrep` — keyword search → top files (the "just grep it" baseline).
   - `embedding-rag` — chunk + embed + top-k (the "just use a vector DB" baseline,
     same embedding model NeuralMind uses, so the delta isolates *structure +
     synapses*, not the encoder).
   - `neuralmind` — progressive L0–L3 disclosure + synapse recall.
   - `competitor:codebase-memory-mcp` — best-effort per its docs (§6).
3. **Joint cost/correctness reporting.** Per query: context tokens (cost) and
   **gold-file recall@k** (correctness). Aggregate to a **Pareto plot** +
   a table. Headline = "equal-or-better recall at N× fewer tokens," with the
   per-repo breakdown and every loss visible.
4. **`neuralmind benchmark --public`** (and `python -m evals.public.run`) — one
   command, deterministic per `--seed`, `--json` for machines, writes
   `bench/public/report.md` + `results.json` + raw per-query traces.
5. **A published, reproducible report** — `docs/benchmarks/public.md` (methodology
   + results + **how to reproduce**), linked from README/docs, plus a forkable
   `bench-public.yml` workflow (`workflow_dispatch`) that regenerates it.

## 4. Goals / non-goals

**Goals**
- A number we can post publicly that an adversarial expert reproduces in one
  command and cannot wave away as fixture-rigged or correctness-blind.
- Reuse existing metric code; the public report cites the same `quality.py`
  math the CI gates use.
- Honest, including losses; the report names repos/queries where a baseline
  ties or beats NeuralMind.

**Non-goals**
- Not a leaderboard of every code tool — a focused, defensible head-to-head.
- Not an end-to-end "did the LLM write correct code" agentic eval (too noisy to
  be objective; the LLM-judged answer arm is secondary and clearly labeled).
- No new retrieval/scoring math invented for the benchmark — that would be
  unauditable. Reuse `quality.py`.

## 5. Keeping "correctness" objective (the crux)

The central methodology decision, stated openly rather than hidden:

**Primary metric — deterministic gold-file recall (no LLM).** Each query's gold
answer is one or more **source files/symbols** that an independent, mechanical
source of truth identifies — not labels we hand-wrote to flatter ourselves.
Candidate objective oracles (pick per repo, documented per query):
- the symbol's **definition site** (resolvable by the language's own tooling /
  ctags / LSP) for "where is X defined / implemented" queries;
- the repo's **own tests** — the file under test for a behavior is gold;
- **commit ground truth** — for "what implements feature Y," the files a known PR
  touched are gold.
A baseline "answers" a query iff the gold file appears in its top-k context.
This is fully deterministic, re-runs identically, and has no judge to attack.

**Secondary metric (opt-in) — LLM-judged answerability.** Behind a `--judge`
flag, off by default: feed each baseline's assembled context + the question to a
fixed, **disclosed** model with a **published prompt**, and score whether the
answer is supported. Useful for real-repo scale, but it is *explicitly labeled
as the softer, gameable metric* and never the headline. Publishing the prompt +
model + raw transcripts is what keeps it honest.

> **Open recommendation for review:** ship **primary (gold-file recall) as the
> headline and CI-gated number**, and **secondary (LLM-judge) as an opt-in,
> clearly-captioned supplement** with full transcript disclosure. This gives the
> objectivity skeptics demand without capping us to only hand-labeled queries.
> I want sign-off on this split before building, since it shapes the corpus.

## 6. Running the competitor fairly & reproducibly

`codebase-memory-mcp` is a separate tool with its own deps; our CI network policy
may not permit installing/running it in-pipeline. To stay both fair and
reproducible:
- Pin the **exact competitor version/commit**; document install + the config we
  used; **link their own reproduction steps** so readers can re-run independently.
- The harness defines a thin `Backend` adapter interface; the competitor adapter
  shells out to its documented retrieval entrypoint. If it cannot run in our
  sandbox, we run it in a **documented, scripted environment**, commit the **raw
  output traces**, and the report clearly marks competitor rows as
  "reproduced via `bench/public/competitor/REPRODUCE.md`," not live-in-CI.
- We never tune the competitor to lose; if a config materially changes its
  numbers, we disclose both. Where we are unsure we represent it best, we say so.

## 7. Acceptance criteria

_Checked items shipped in v0.31.0; unchecked are explicit fast-follows (noted)._

- [x] `evals/public/manifest.json` — real repos (`requests`, `click`) pinned to
      commit SHAs, each with a pre-registered query set committed **before** any
      tuning.
- [x] Objective gold sets per query, with the oracle (def-site) documented per
      query; no hand-waved labels.
- [x] `evals/public/run.py` + `neuralmind benchmark --public [--repo NAME]
      [--seeds N] [--json]` assembles the baselines and reports **cost +
      gold-file recall jointly**, deterministically. _(An opt-in `--judge`
      answerability arm is a planned fast-follow, not in 0.31.0.)_
- [x] Baseline matrix includes `full-file`, `ripgrep`, `embedding-rag`,
      `neuralmind`. _`competitor` is a documented-external fast-follow (§6) — its
      deps don't install in CI; scaffolded at `bench/public/competitor/`._
- [x] Deterministic by design (synapse injection off): re-runs match to the
      token, so a single run *is* the reproducible result. _(The `--seeds` flag
      records the seed count; true multi-seed mean ± spread would only matter if
      a stochastic baseline is added later.)_
- [x] **Every** query in the report, including losses; a "where NeuralMind loses"
      section is present (and the degraded-env case says "not evaluated", never a
      false clean sweep).
- [x] `docs/benchmarks/public.md` — methodology + results + exact reproduce
      steps; numbers trace to the same `quality.py` metric code as CI.
- [x] Forkable `bench-public.yml` (`workflow_dispatch`) regenerates the report.
- [x] Reuses `neuralmind/quality.py` for all scoring; no new metric math.
- [x] Docs + SEO propagated (release notes, README, both HTML, CLI-Reference
      `benchmark --public`, sitemap, keywords) per CLAUDE.md.

## 8. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Real-repo corpus too small to generalize | Be explicit it's a **focused** suite; publish the runner so the community adds repos via the existing `--contribute` path. |
| Competitor can't run in our CI sandbox | Scripted, documented external run + committed raw traces; report marks it non-live and links independent reproduce steps (§6). |
| Embedding-RAG baseline strawmanned | Use the **same encoder** NeuralMind uses + sensible chunking; disclose config; invite a stronger config via PR. |
| Gold sets accused of bias | Derive from **mechanical oracles** (def-site/test/commit), document the oracle per query, keep the set pre-registered and diffable in git history. |
| LLM-judge arm attacked as rigged | Off by default, secondary only, model+prompt+transcripts published; headline never depends on it. |
| Looks self-serving | Mandatory losses section; if NeuralMind doesn't dominate the frontier on a repo, the report says so plainly. |

## 9. Rollout

Per CLAUDE.md shipping pattern: PRD → build on `claude/public-benchmark` → CI
green → hold for merge okay → merge cuts **v0.31.0** via release-please, docs +
SEO in the same PR. The published report + forkable workflow ship with it so the
moment the version lands, the evidence is live and reproducible.
