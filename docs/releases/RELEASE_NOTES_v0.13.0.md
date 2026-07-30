# NeuralMind v0.13.0 — measurement foundation: faithfulness eval + polyglot fixtures + a docs process

**Release Date:** June 2026

## TL;DR

v0.13.0 is a **foundation release**, not a new command. It doesn't change
what your install does at runtime — it builds the scaffolding to *measure*
whether NeuralMind's memory actually makes an agent's answers **better**
(not just shorter), and to measure retrieval quality **beyond Python**.
Plus a documentation process so the docs stop drifting.

Three things land:

- **Faithfulness eval foundation (offline, 100% local).** A versioned
  query + gold-fact dataset and a pure-stdlib *expected-fact-recall*
  scorer — the zero-network signal future CI gates will run on. This is
  the dataset + scorer skeleton, **not** the full answer-generation /
  report pipeline (those are the next increments).
- **Polyglot retrieval-quality fixtures (TypeScript + Go).** Self-contained
  sample projects that mirror the existing Python fixture domain-for-domain,
  with per-language gold-module query sets — so retrieval hit-rate can be
  measured per language instead of Python-only.
- **A standard documentation process.** A written `DOCUMENTATION-PROCESS.md`,
  a PR-template checklist, and a CONTRIBUTING link, so every user-facing
  change ships its docs in the same PR and the landing-page version stops
  going stale.

**No migration, no new dependencies, no behavior change for existing
installs.** If you just use NeuralMind, upgrading changes nothing you'll
notice today. The point of this release is the credibility it buys the
*next* ones: quality claims backed by numbers, in the open.

---

## What the agent actually sees, post-install

**Honestly: nothing new at runtime.** There is no new `neuralmind` command,
no new hook, and no change to how the synapse layer, graph view, or MCP
tools behave. The eval harness is developer- and CI-facing — it lives under
`evals/` and `tests/fixtures/`, and nothing imports it on the hot path.

The one new toggle, `NEURALMIND_EVAL_LLM_JUDGE`, only affects the eval
runner (a developer tool), is **opt-in**, is **never** the default or the
CI gate, and prints a loud notice that turning it on would send text to a
third-party API. The default judge is the offline heuristic — zero network.

### Per-agent expectations

| Agent | What changes in v0.13.0 |
|-------|--------------------------|
| **Claude Code** | Nothing at runtime. Hooks, `SYNAPSE_MEMORY.md`, and predictions behave exactly as in v0.12.0. |
| **Cursor / Cline** | Nothing at runtime. Same MCP tools, same retrieval. |
| **Generic MCP client** | Nothing at runtime. The eval harness is not exposed as an MCP tool. |
| **Contributors / CI** | A runnable, dependency-light offline eval skeleton (`python evals/faithfulness/runner.py --selfcheck`) and TS/Go retrieval fixtures to measure against. |

---

## What ships

### 1. Faithfulness eval foundation (Epic E1.1)

Under `evals/faithfulness/`:

- **`queries.json`** — a versioned set of **18 queries / 52 expected
  facts** derived directly from the bundled sample project (auth/login,
  JWT HS256 + signature verify, session/refresh TTLs, logout revocation,
  API routes, user storage + soft-delete, SQLite, billing charge/refund,
  Stripe webhook verify + dispatch, invoices). Each query carries
  rubric-style *expected facts* with code-symbol aliases — not just gold
  module names.
- **`runner.py`** — a pure-stdlib loader + the offline
  expected-fact-recall scorer (`OfflineJudge.fact_recall`). It imports no
  chromadb / graphify / neuralmind at load time, so it runs in a minimal
  environment. Alias matching is token/phrase-boundary aware so the recall
  number can't be inflated by short substrings matching inside unrelated
  words — important, because this is the signal CI will gate on.
- **`schema.md`** — the data contract and the three intended scoring
  dimensions (expected-fact recall, citation/grounding rate, contradiction
  check).
- **`NEURALMIND_EVAL_LLM_JUDGE`** — opt-in only, documented as leaving the
  machine, never the default or the gate.

**Deliberately not in this release:** answer generation (with-NeuralMind vs
baseline), the grounding/contradiction scorers, the LLM-as-judge wiring,
and the `neuralmind eval` report. Those are the E1.2–E1.4 increments.

### 2. Polyglot retrieval-quality fixtures (Epics E2.2 / E2.3)

Under `tests/fixtures/`:

- **`sample_project_ts/`** (TypeScript) and **`sample_project_go/`** (Go) —
  small apps mirroring the Python fixture domain-for-domain.
- **`benchmark_queries_ts.json` / `benchmark_queries_go.json`** — per-language
  gold-module query sets mirroring the Python set's ids, questions, shapes,
  and learning seed, so per-language hit-rate compares like with like.
- **`_gen_graph.py`** — a generator that emits a `graph.json` in graphify's
  schema, deriving every symbol's line number — and every `calls`/`imports`
  edge location — from the real source, so the fixtures stay faithful.
- **`test_polyglot_fixtures.py`** — stdlib-only structural tests that keep
  the graphs, sources, and query sets mutually consistent.

### 3. A standard documentation process (PR #176)

- **`docs/DOCUMENTATION-PROCESS.md`** — the operational standard: docs ship
  in the same PR as the change, every doc answers *"what does the user/agent
  now see?"*, the five surfaces, the SEO + discoverability rules, and a
  three-loop cadence (per-PR → per-release → quarterly) that catches stale
  "Current/Next" version drift.
- **`.github/PULL_REQUEST_TEMPLATE.md`** — a "Documentation & discoverability"
  checklist section (with an N/A escape for internal refactors).
- **`CONTRIBUTING.md`** — links the process from the Documentation section.

---

## Why this matters

NeuralMind's headline claims — *cheaper, and the memory makes answers
better* — deserve to be **measured, not asserted**. v0.13.0 is the first
brick: an honest, offline, reproducible way to score answer faithfulness,
and fixtures that extend quality coverage past Python. None of it is
marketing surface; all of it is the fitness function the rest of the
eval-first roadmap (v0.13 → v0.16) builds on.

---

## What's next

- **E1.2** — A/B answer generation (with NeuralMind context vs a naive baseline).
- **E1.3** — the full offline judge (recall + grounding + contradiction); opt-in LLM-as-judge.
- **E1.4** — `neuralmind eval` report: faithfulness delta, grounding rate, per-query breakdown, `--json`.
- **E2.4** — the per-language retrieval hit-rate report built on the new TS/Go fixtures.

---

## Upgrade

```bash
pip install --upgrade neuralmind
```

Nothing else to do — no migration, no config changes. Contributors can
sanity-check the new eval skeleton with:

```bash
python evals/faithfulness/runner.py --selfcheck
```
