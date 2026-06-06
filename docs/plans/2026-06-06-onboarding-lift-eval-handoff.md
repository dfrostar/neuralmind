# Session Accomplishments & Next-Session Plan — Onboarding-Lift Eval (E1.5)

**Created:** 2026-06-06 00:30 UTC
**Author:** Claude Code session (graph-backend decoupling)
**Predecessor:** `docs/plans/2026-06-05-graph-backend-decoupling.md`
**Purpose:** record what shipped this session, and hand off the one remaining
roadmap increment — the **E1.5 onboarding-lift eval** — with a copy-paste
prompt to resume in a fresh session.

---

## 1. What we accomplished this session

The entire graph-backend decoupling roadmap (Phase 0 + Items 1–4) was
**implemented, parity-gated, documented, released, and published to PyPI**.
Five releases, v0.15.0 → v0.19.0:

| Release | Item | What shipped | Evidence |
|---|---|---|---|
| **v0.15.0** | Phase 0 | Built-in tree-sitter graph backend (`pip install neuralmind && neuralmind build .` works with **no graphify**) + the **backend parity gate** CI job. | The gate caught the first cut retrieving *worse than naive truncation* (faithfulness −0.195); the producer was fixed — balanced per-file communities, markdown `document` nodes, full-body rationale, module/class symbol extraction — until it **beats** graphify: fact recall **0.717 vs 0.555**, grounding **1.000 vs 0.917**, reduction **6.66× vs 6.08×**, faithfulness delta **+0.143 vs +0.050**. |
| **v0.16.0** | Item 1 | Multi-language: **TypeScript + Go** extractors behind the `SUPPORTED_SUFFIXES` seam. | Parity gate extended per-language; built-in recovers **100%** of graphify's symbols for TS (54/54) and Go (45/45), zero dangling. |
| **v0.17.0** | Item 2 | Optional **SCIP precision pass** — compiler-accurate `calls`/`inherits` from a `*.scip` index, off by default (`NEURALMIND_PRECISION`). | Pure-stdlib protobuf reader (no runtime dep), class-aware symbol resolution; gate proves heuristic `run()→B.handle` (wrong) becomes `run()→A.handle` (right) and is a strict no-op when disabled. |
| **v0.18.0** | Item 3 | **Incremental** per-file graph updates → `neuralmind watch --reindex`. | `graphgen.update_files()` keeps unchanged files (incl. community numbers) byte-identical; editing one file re-embeds **2 nodes, skips 135**. |
| **v0.19.0** | Item 4 | **MCP distribution** — `neuralmind install-mcp` auto-detects + registers with Claude Code / Cursor / Cline / Claude Desktop. | Non-destructive, idempotent merge; pure-stdlib `mcp_install.py`, 11 tests. |

**Conventions held throughout:** every backend change cleared the eval +
benchmark parity gate; every user-facing change shipped docs + SEO in the same
PR across all five surfaces; versions were never hand-bumped (release-please
owned them); after each release PR merged, `release.yml` was manually
dispatched against the tag (issue #98) and PyPI was verified. Branch per
feature, draft PRs, merged green.

**Test suite:** grew from ~560 to **596 passing** (graphgen, parity-gate,
precision, incremental-update, and mcp-install suites added).

### The parity gate is now the durable safety net

`evals/parity/run.py` runs on every PR (`.github/workflows/ci-benchmark.yml`)
and gates three things: (1) Python faithfulness + reduction within tolerance of
graphify, (2) TS/Go structural symbol coverage ≥ 90%, (3) the SCIP precision
pass corrects a known-wrong edge and is a no-op when off. Any future backend
change must clear it.

---

## 2. What's left: E1.5 — the onboarding-lift eval

This is the **one remaining roadmap increment** (Item 4's measurement half).
It is tracked as **E1.5** in `evals/faithfulness/README.md` and issue **#175**.

### The question it answers

> Does an agent that inherits a **committed team synapse memory** answer/retrieve
> better on its *first* queries than a **cold agent with no memory** — and by how
> much? That "onboarding lift" is NeuralMind's headline differentiator: the
> usage-memory layer static-graph competitors don't have.

### What already exists (the foundation — reuse it)

- **`evals/faithfulness/`** — the gold-fact query set (`queries.json`), the
  offline `OfflineJudge` (fact recall / grounding / contradiction), and the A/B
  `harness.py`. Mirror this structure.
- **The self-benchmark already measures a version of this**:
  `tests/benchmark/run.py` **Phase 3 — synapse-recall A/B** reports top-k hit
  rate **71.7% → 83.3% (+11.7 points)** with recall on vs off, token-neutral.
  E1.5 should *formalize and commit* that as an onboarding eval with a
  **committed team baseline**, not a synthetically-seeded one.
- **Synapse layer**: `neuralmind/synapses.py` (SQLite store), `synapse_memory.py`
  (markdown export), `core.py` `activate_files()` / `_recall_for_selection()`
  (the recall wired into L2/L3 selection).

### Proposed design (mirror the faithfulness eval)

1. **A committed "team baseline" synapse state** for the reference fixture
   (`tests/fixtures/sample_project`). Either:
   - a small committed `synapses.db` (or JSONL co-edit/query history) that a
     deterministic seed script replays, representing "what a team already taught
     NeuralMind" — keep it **stdlib-only and deterministic** (the synapse tests
     are already stdlib-only), and document how it was generated; **or**
   - a `seed_history.json` of `(query, co-edited files)` events the harness
     replays through `activate_files()` to build the baseline at eval time.
   Prefer the replayable-history form so it's transparent and regenerable.

2. **`evals/onboarding/` harness** (parallel to `evals/faithfulness/`):
   - **Cold arm**: `NeuralMind(fixture)` with synapse recall **off / empty** —
     run the gold queries, score with `OfflineJudge`.
   - **Onboarded arm**: same, but with the committed team baseline loaded and
     synapse recall **on** — run the *same* gold queries, score.
   - **Report the lift**: deltas in fact-recall, grounding, and top-k hit-rate
     (cold → onboarded). Reuse `OfflineJudge`; reuse the faithfulness query set
     (or a small onboarding-specific gold set if the existing one doesn't
     exercise cross-file co-activation enough — check first).
   - Import-safe / lazy heavy imports, like `evals/faithfulness/harness.py`.

3. **A CI gate** (extend `ci-benchmark.yml` or add to `evals/parity/run.py`'s
   report) asserting **onboarding lift ≥ 0** — committed team memory must never
   *hurt* retrieval. Be conservative on the tiny fixture (the existing eval
   gates floor at 0 deliberately); tighten once a stable distribution exists.
   Watch for the same **HNSW query-time nondeterminism** that bit the parity
   gate — measure the cold-first-run, or average a few runs.

4. **A `neuralmind eval --onboarding` mode** (or a sibling command) so it's
   runnable like `neuralmind eval`, with the same "runs from a source checkout"
   caveat (the gold set + baseline ship in the repo, not the wheel).

### Acceptance criteria

- A committed, regenerable team baseline + an `evals/onboarding/` harness that
  reports a measured **onboarding lift** (recall/grounding/hit-rate deltas,
  cold vs onboarded) on the reference fixture.
- Stdlib-only unit tests for the harness math (no chromadb), plus the full A/B
  gated in CI (needs chromadb + a built index, like the faithfulness gate).
- CI gate: onboarding lift ≥ 0.
- Ships **docs + SEO in the same PR** (CLAUDE.md checklist) — it's a new
  user-facing measurement/command → release notes, README banner/table,
  `docs/index.html` + `docs/about.html`, wiki CLI reference, sitemap,
  `pyproject.toml` keywords. Release-please will cut the version from the
  `feat:` commit; **do not hand-bump**. After it merges, **manually dispatch
  `release.yml`** against the tag (issue #98) and **verify PyPI**.

### Watch-outs (learned this session)

- **Don't weaken a gate to make a number pass.** When the parity gate failed,
  the right move was fixing the *producer*, not relaxing the gate. Same here: if
  the onboarding lift is negative, investigate the synapse recall, don't lower
  the floor.
- **HNSW nondeterminism**: ChromaDB's approximate-NN search makes fact-recall
  jitter run-to-run on the tiny fixture. The full parity gate (fresh build per
  run) is stable, but repeated in-process queries drift. Measure deliberately.
- **Local iteration**: the heavy stack (chromadb) won't `pip install` into the
  sandbox's system Python, but a **fresh venv works**:
  `python -m venv /tmp/nmvenv && /tmp/nmvenv/bin/pip install -e ".[dev]" tiktoken graphifyy`.
  Run subprocess-based tools with the venv's `bin` on `PATH`.

---

## 3. Conventions (do not skip — same as the predecessor plan)

- **Every backend/retrieval change must pass the eval + benchmark parity gate.**
- **User-facing changes ship docs + SEO in the same PR** (CLAUDE.md checklist).
- **Never hand-bump versions** — release-please owns `pyproject.toml`,
  `.release-please-manifest.json`, `CHANGELOG.md`; `feat:`/`fix:` subjects drive
  the bump.
- **`release.yml` does NOT auto-fire** on the release-please tag (GITHUB_TOKEN).
  After the release PR merges, **manually dispatch `release.yml`** with input
  `tag: vX.Y.Z` (issue #98), then verify the PyPI version.
- Branch per feature; open **draft** PRs; keep synapse/eval tests stdlib-only.

---

## 4. Copy-paste prompt for the next session

```
You are continuing NeuralMind. FIRST read
docs/plans/2026-06-06-onboarding-lift-eval-handoff.md — it records what shipped
last session (the full graph-backend decoupling, v0.15.0→v0.19.0, all on PyPI)
and the design + conventions for the one remaining increment.

State: v0.19.0 is published. Phase 0 + roadmap Items 1–4 (built-in tree-sitter
backend + parity gate; multi-language TS/Go; optional SCIP precision;
incremental per-file updates; MCP auto-detection) are all done, parity-gated,
documented, and released.

Your task: build the E1.5 ONBOARDING-LIFT EVAL — the last roadmap increment
(tracked as E1.5 in evals/faithfulness/README.md and issue #175). Measure the
learned-synapse uplift as a committed-team-baseline-vs-cold-agent A/B, the way
the faithfulness eval (evals/faithfulness/) measures answer quality. The
self-benchmark's Phase-3 synapse A/B (tests/benchmark/run.py: top-k hit rate
71.7% → 83.3% with recall on) is the foundation to formalize.

Do:
1. Add a committed, regenerable "team baseline" synapse state for
   tests/fixtures/sample_project (prefer a replayable seed-history JSON over a
   binary synapses.db so it's transparent), representing what a team already
   taught NeuralMind.
2. Build evals/onboarding/ (mirroring evals/faithfulness/): a cold arm (no
   synapse memory) vs an onboarded arm (committed baseline, recall on) over the
   gold queries, reusing OfflineJudge; report the lift (fact-recall, grounding,
   top-k hit-rate deltas). Import-safe / lazy heavy imports.
3. Gate it in CI (extend ci-benchmark.yml or the parity report): onboarding
   lift ≥ 0 — committed memory must never hurt. Beware HNSW query-time
   nondeterminism (measure the cold first-run or average).
4. Add a `neuralmind eval --onboarding` mode (source-checkout caveat like
   `neuralmind eval`).
5. Ship docs + SEO in the SAME PR (CLAUDE.md checklist): RELEASE_NOTES_vX.Y.Z,
   README banner/table, docs/index.html + about.html, wiki CLI reference,
   sitemap, pyproject keywords.

Conventions: every retrieval change MUST pass the eval+benchmark parity gate;
docs+SEO in the same PR; never hand-bump versions (release-please owns them);
after the release PR merges, manually dispatch release.yml against the tag
(issue #98) and verify PyPI. Branch per feature; open draft PRs; keep
synapse/eval tests stdlib-only. Don't weaken a gate to make a number pass — fix
the producer. Local iteration needs a fresh venv (chromadb won't install into
the sandbox's system Python): python -m venv /tmp/nmvenv &&
/tmp/nmvenv/bin/pip install -e ".[dev]" tiktoken graphifyy.
```
