# Session handoff — launch readiness

**Last updated:** 2026-06-20 · **State:** v0.30→v0.34 shipped & merged to `main`
**Copy-paste this whole file into the next session's first message to resume with full context.**

---

## ▶ Do this first (next session, in order)

1. **Merge the v0.34.0 release-please PR.** It opens automatically after the
   answerability `feat:` (#264) merged; merging it tags `v0.34.0` and fires the
   PyPI + GHCR publish. Nothing else ships until this lands. (Tell the session
   "merge the release-please PR and watch it to green.") Never hand-edit the
   version/CHANGELOG — release-please owns them.
2. **Generate + commit the answerability transcripts** (optional but
   recommended). The `--judge` harness shipped in v0.34.0 but `bench/public/judge/`
   is empty. Run `neuralmind benchmark --public --judge` with `ANTHROPIC_API_KEY`
   set (costs real tokens) and commit the transcripts, so the launch posts can
   show a concrete answerability table, not just "run it yourself."
3. **Launch — maker's move, disclosed only.** Copy is ready in `docs/launch/`
   (Show HN, r/LocalLLaMA, awesome-mcp PR, warm-up comments). Post as yourself.
   The disclosed-maker-only rule below is non-negotiable.
4. **Pick the next roadmap item** (all four value-ordered ones are shipped),
   ranked: (a) **more languages** (C#/Ruby/PHP) behind the
   `_SUFFIX_LANG`→`_EXTRACTORS` seam — additive, parity-gated; (b) **expand the
   benchmark corpus** beyond `requests`/`click`; (c) **schema.org JSON-LD** on
   docs pages (the SEO gap in CLAUDE.md).

## TL;DR for the next session

NeuralMind is **launch-ready**. Five releases shipped (v0.30→v0.34): team
memory, the honest public benchmark, C/C++, the competitor head-to-head, and the
opt-in LLM-judged answerability arm. Public-facing positioning is the **four
data-backed benefits**, and the launch copy lives in `docs/launch/`. The
remaining work is **execution** (the maker posts to HN / r/LocalLLaMA /
awesome-mcp) plus the next roadmap item. Nothing is blocked on code.

The one hard standing rule, carried across sessions: **disclosed-maker only**
for all outreach. No unaffiliated-end-user posts, no sockpuppet/persona
creation, no platform-rule evasion. This was asked for repeatedly and declined
every time — keep declining it; the benchmark credibility is the whole asset.

---

## What shipped this arc (done — on `main`, released)

| Version | Feature | PR | Evidence |
|---|---|---|---|
| v0.30.0 | **Team memory** — commit learned synapse signal; teammates' agents inherit it (`.neuralmind-team-memory.json`, `shared` namespace, content-hash idempotent, fail-open) | shipped within #257 | `tests/test_team_memory.py` |
| v0.31.0 | **Honest public benchmark** — `neuralmind benchmark --public`, gold-file recall (objective def-site oracle, no LLM judge), cost+correctness jointly | #257 | `evals/public/`, `docs/benchmarks/public.md` |
| v0.32.0 | **C / C++ extractors** — tree-sitter backend now 7 languages, proven at parity (100% coverage, 0 dangling) | #259-ish | `tests/test_graphgen.py` (C/CExtractorEdgeCase) |
| v0.33.0 | **Live competitor head-to-head** vs `codebase-memory-mcp` 0.8.1 — same repos/questions/scorer, raw traces committed | #259/#260 | `evals/public/competitor.py`, `bench/public/competitor/` |
| v0.34.0 | **Opt-in LLM-judged answerability arm** (`--judge`) — each backend answered from its real window by a pinned model, graded vs. the def-site gold anchor; closes the "recall ≠ answering" gap | #264 | `evals/public/judge.py`, `bench/public/judge/` (transcripts TODO) |
| (docs) | **Four-benefit positioning** across README + docs + wiki | #261 | README "Why NeuralMind" |
| (docs) | **Launch kit** — this folder | #263 | `docs/launch/` |

## Current state of the repo

- `main` includes v0.34.0's `feat:` (#264 merged); the **v0.34.0 release-please PR
  will open automatically** — merging it tags the release and publishes.
- PRs #263 (launch kit) and #264 (answerability arm) are **merged**.
- Outstanding: merge the release PR; optionally generate the `bench/public/judge/`
  transcripts (needs `ANTHROPIC_API_KEY`). See "▶ Do this first" at the top.

## The four data-backed benefits (single source of truth: README "Why NeuralMind")

| Benefit | Result | Where measured |
|---|---|---|
| Cheaper context | 100% gold-file recall at **38–85× fewer tokens** vs pasting files; beats `ripgrep` on both axes | public benchmark (`requests`, `click`) |
| Finds the *right* code | 100% recall, **MRR 0.96**; beats `codebase-memory-mcp` ranking (0.96 vs 0.23) | same benchmark |
| Learns how you work | Hebbian synapses **+11.7 pts** hit-rate (71.7%→83.3%), budget-neutral | synapse A/B |
| Better-grounded answers | matched budget: **faithfulness +0.143, grounding 1.00** | parity/faithfulness gate |

Honest-scope caveat (carry it everywhere): cost+accuracy are real pinned-OSS-repo
reproducible; learning+grounding are reference-fixture A/Bs (real, smaller-scope);
a well-tuned vector RAG ties on findability and is cheaper on raw tokens — shown
in the table, not hidden.

---

## Recommended next steps (in priority order)

1. **Merge #263** once you're happy with the post copy (held for your okay;
   docs-only, won't trigger a release).
2. **Execute the launch** — you, as the disclosed maker:
   - Submit the Show HN (`docs/launch/show-hn.md`), post the first comment
     immediately, be around to answer for the first few hours.
   - Post the r/LocalLLaMA self-post (`docs/launch/r-localllama.md`).
   - Open the awesome-mcp-servers PR (`docs/launch/awesome-mcp-servers.md`).
   - Use the warm-up comments (`docs/launch/hn-warmup-comments.md`) only on
     genuinely relevant threads, disclosed.
3. **Pick the next roadmap item** (see candidates below). The value-ordered
   four are done; the next tier is about deepening the proof and breadth.

### Candidate next roadmap items (not yet started)

- **Opt-in LLM-judged answerability arm** for the public benchmark
  (`--judge`, publish model+prompt+transcripts as a clearly-labeled *secondary*
  signal). Already scoped as "planned" in `docs/benchmarks/public.md`. Directly
  answers the "recall ≠ answering" critique a serious reviewer will raise.
- **schema.org JSON-LD** (`SoftwareApplication` / `Article`) on docs pages —
  an explicit SEO gap noted in CLAUDE.md as of v0.10.0; richer Google results.
- **More languages** behind the same `_SUFFIX_LANG` → `_EXTRACTORS` seam
  (C# / Ruby / PHP are the obvious breadth adds; each is additive + parity-gated).
- **Expand the public benchmark corpus** beyond `requests`/`click` (one
  `manifest.json` entry per repo with def-site gold) to harden "you picked easy
  repos."

---

## How we work here (cadence + constraints — keep these)

- **Per feature:** PRD (`docs/prd/`) → build on a fresh branch (code + tests +
  docs/SEO per the CLAUDE.md checklist) → CI green → **hold for explicit merge
  okay** → merge → release-please cuts the release. Docs+SEO ship in the *same*
  PR as the feature.
- **Fresh branch per feature** (avoids the CI-trigger dead-end).
- **Never** bump `pyproject.toml` / manifest / `CHANGELOG.md` by hand —
  release-please owns versioning off `feat:`/`fix:` commits.
- **Benchmarks deterministic:** `NEURALMIND_SYNAPSE_INJECT=0` for fixed numbers.
- **Bar for any public/benchmark work:** must pass engineering + Reddit scrutiny
  by serious technicians. Report losses, pin versions, commit raw traces.
- **Disclosed-maker only** for all outreach (the standing ethical line above).

---

## Pointers

- Launch copy: `docs/launch/` (README is the index).
- Benchmark methodology + raw data: `docs/benchmarks/public.md`,
  `bench/public/`.
- Reproduce headline: `python -m evals.public.run`; competitor:
  `python -m evals.public.competitor`.
- Architecture + shipping checklist: `CLAUDE.md`.
