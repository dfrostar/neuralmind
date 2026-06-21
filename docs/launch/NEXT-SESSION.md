# Session handoff — launch readiness

**Last updated:** 2026-06-21 · **State:** v0.30→v0.37 shipped & merged to `main`
**Copy-paste this whole file into the next session's first message to resume with full context.**

---

## ▶ Do this first (next session, in order)

1. **Nothing is blocked on code.** The value-ordered roadmap *and* the next
   breadth tier are all shipped and released (v0.30→v0.37, see table below).
   The remaining work is **execution + proof + discovery**, not engineering.
2. **Generate + commit the answerability transcripts** (the one remaining
   *proof* item). The `--judge` harness shipped in v0.34.0 but
   `bench/public/judge/` is still empty. Run
   `neuralmind benchmark --public --judge` with `ANTHROPIC_API_KEY` set (costs
   real tokens) and commit the transcripts, so the launch posts show a concrete
   answerability table instead of "run it yourself." This directly pre-empts the
   "recall ≠ answering" critique a serious reviewer will raise. **Still blocked
   on a key in the session env.**
3. **Two GitHub-UI edits only the maker can do** (no API in the agent toolset
   sets these; paste-ready copy is in this session's history / below):
   - Repo **About → description + Topics** — add the comparison/complementary
     terms (`codebase-memory-mcp-alternative`, `headroom-alternative`,
     `ponytail`, `context-engineering-stack`, `graphify-alternative`) so the
     surface search engines weight most carries them.
   - **v0.37.0 Release body** — swap the raw changelog for the umbrella notes
     (`RELEASE_NOTES_v0.37.0.md`) + the honest comparison footer.
4. **Launch — maker's move, disclosed only.** Copy is ready in `docs/launch/`
   (Show HN, r/LocalLLaMA, awesome-mcp PR, warm-up comments). Post as yourself.
   The disclosed-maker-only rule below is non-negotiable.

## TL;DR for the next session

NeuralMind is **launch-ready and feature-complete for this arc**. Eight releases
shipped (v0.30→v0.37): team memory, the honest public benchmark, C/C++, the
live competitor head-to-head, the opt-in LLM-judged answerability arm, then the
**full language-breadth tier (C#, Ruby, PHP → ten languages)**, a **4-repo /
40-query benchmark corpus** (`requests`, `click`, `flask`, `rich`), and
**schema.org JSON-LD** on the docs pages. Public-facing positioning is the
**four data-backed benefits**, and the launch copy lives in `docs/launch/`. The
remaining work is **execution** (the maker posts to HN / r/LocalLLaMA /
awesome-mcp), the **answerability transcripts** (needs a key), and two
**GitHub-UI edits** (About/topics, Release body). Nothing is blocked on code.

The one hard standing rule, carried across sessions: **disclosed-maker only**
for all outreach. No unaffiliated-end-user posts, no sockpuppet/persona
creation, no platform-rule evasion. This was asked for repeatedly and declined
every time — keep declining it; the benchmark credibility is the whole asset.

---

## What shipped this arc (done — on `main`, released)

| Version | Feature | Evidence |
|---|---|---|
| v0.30.0 | **Team memory** — commit learned synapse signal; teammates' agents inherit it (`.neuralmind-team-memory.json`, `shared` namespace, content-hash idempotent, fail-open) | `tests/test_team_memory.py` |
| v0.31.0 | **Honest public benchmark** — `neuralmind benchmark --public`, gold-file recall (objective def-site oracle, no LLM judge), cost+correctness jointly | `evals/public/`, `docs/benchmarks/public.md` |
| v0.32.0 | **C / C++ extractors** — tree-sitter backend → 7 languages, proven at parity (100% coverage, 0 dangling) | `tests/test_graphgen.py` |
| v0.33.0 | **Live competitor head-to-head** vs `codebase-memory-mcp` 0.8.1 — same repos/questions/scorer, raw traces committed | `evals/public/competitor.py`, `bench/public/competitor/` |
| v0.34.0 | **Opt-in LLM-judged answerability arm** (`--judge`) — each backend answered from its real window by a pinned model, graded vs. the def-site gold anchor | `evals/public/judge.py`, `bench/public/judge/` (transcripts TODO) |
| v0.35.0 | **C# extractor** — eighth language (`.cs`), 52/52 symbols (100%), 0 dangling | `RELEASE_NOTES_v0.35.0.md` |
| v0.36.0 | **Ruby extractor** — ninth language (`.rb`), 46/46 symbols (100%), 0 dangling | `RELEASE_NOTES_v0.36.0.md` |
| v0.37.0 | **PHP extractor** — tenth language (`.php`), 54/54 symbols (100%), 0 dangling; **benchmark corpus → 4 repos / 40 queries** (`flask` + `rich`); **schema.org JSON-LD** on docs pages | `RELEASE_NOTES_v0.37.0.md` (umbrella) |
| (seo) | **Complementary-app comparison keywords** propagated to PyPI metadata (Headroom / Ponytail / codebase-memory-mcp / graphify), matching the docs `<meta>` cluster | `pyproject.toml` keywords (PR #274) |
| (docs) | **Four-benefit positioning** + **launch kit** | README "Why NeuralMind", `docs/launch/` |

The bundled tree-sitter backend now indexes **ten languages** out of the box:
Python, TypeScript, Go, Rust, Java, C, C++, C#, Ruby, PHP — the C#/Ruby/PHP
breadth tier is **complete**.

## Current state of the repo

- `main` is at **v0.37.0** (PyPI + GHCR published, GitHub Release tagged).
- The GHCR auto-publish gap is permanently fixed (the release-please workflow
  dispatches the GHCR build on tag).
- Outstanding (all non-code): answerability transcripts (needs
  `ANTHROPIC_API_KEY`); the two GitHub-UI edits (About/topics, Release body);
  the launch itself.

## The four data-backed benefits (single source of truth: README "Why NeuralMind")

| Benefit | Result | Where measured |
|---|---|---|
| Cheaper context | 100% gold-file recall at **38–85× fewer tokens** vs pasting files; beats `ripgrep` on both axes | public benchmark (`requests`, `click`, `flask`, `rich`) |
| Finds the *right* code | 100% recall, **MRR 0.96**; beats `codebase-memory-mcp` ranking (0.96 vs 0.23) | same benchmark |
| Learns how you work | Hebbian synapses **+11.7 pts** hit-rate (71.7%→83.3%), budget-neutral | synapse A/B |
| Better-grounded answers | matched budget: **faithfulness +0.143, grounding 1.00** | parity/faithfulness gate |

Honest-scope caveat (carry it everywhere): cost+accuracy are real pinned-OSS-repo
reproducible; learning+grounding are reference-fixture A/Bs (real, smaller-scope);
a well-tuned vector RAG ties on findability and is cheaper on raw tokens — shown
in the table, not hidden.

## Complementary apps we compare to (honest, backed by in-repo docs)

These compose with NeuralMind as the **context-engineering stack** (retrieval →
transport → generation), each with a disclosed comparison doc that concedes
where the other tool leads:

- **Headroom** (`chopratejas/headroom`) — transport-layer compression →
  `docs/comparisons/vs-headroom.md`
- **Ponytail** (`DietrichGebert/ponytail`) — generation steering →
  `docs/comparisons/context-engineering-stack.md`
- **codebase-memory-mcp** — the live head-to-head → `docs/benchmarks/public.md`

Paste-ready GitHub copy (the maker applies these by hand):

> **About description:** Persistent memory + semantic code intelligence for AI
> coding agents. 100% local, 40–70× cheaper code questions. Composes with
> Headroom (transport compression) and Ponytail (generation steering) as the
> context-engineering stack; benchmarked head-to-head vs codebase-memory-mcp.

> **Topics:** ai-coding-agents · mcp-server · claude-code · cursor ·
> code-intelligence · semantic-code-search · token-optimization ·
> context-engineering · knowledge-graph · hebbian-learning · local-first ·
> tree-sitter · rag · codebase-memory-mcp-alternative · headroom-alternative ·
> ponytail · context-engineering-stack · graphify-alternative · code-memory-mcp ·
> retrieval-benchmark

---

## Recommended next steps (in priority order)

1. **Generate the answerability transcripts** (`bench/public/judge/`) — the one
   proof item left; needs `ANTHROPIC_API_KEY`. Commit them so launch posts show
   a concrete table.
2. **Apply the two GitHub-UI edits** (About/topics, Release body) — copy above.
3. **Execute the launch** — you, as the disclosed maker:
   - Submit the Show HN (`docs/launch/show-hn.md`), post the first comment
     immediately, be around to answer for the first few hours.
   - Post the r/LocalLLaMA self-post (`docs/launch/r-localllama.md`).
   - Open the awesome-mcp-servers PR (`docs/launch/awesome-mcp-servers.md`).
   - Use the warm-up comments (`docs/launch/hn-warmup-comments.md`) only on
     genuinely relevant threads, disclosed.
4. **Pick the next roadmap item** when ready (the breadth tier is done):
   - **Deepen the proof** — more benchmark repos / languages in the public
     corpus; publish the answerability arm as a standing secondary signal.
   - **Compiler-accurate calls** — promote the opt-in SCIP precision pass from
     experimental toward default for languages that support it.
   - **More languages** behind the same `_SUFFIX_LANG` → `_EXTRACTORS` seam
     (e.g. Kotlin, Swift, Scala) — each additive + parity-gated, one per PR.

---

## How we work here (cadence + constraints — keep these)

- **Per feature:** PRD (`docs/prd/`) → build on a fresh branch (code + tests +
  docs/SEO per the CLAUDE.md checklist) → CI green → **hold for explicit merge
  okay** → merge → release-please cuts the release. Docs+SEO ship in the *same*
  PR as the feature.
- **Fresh branch per feature** (avoids the CI-trigger dead-end).
- **Never** bump `pyproject.toml` version / manifest / `CHANGELOG.md` by hand —
  release-please owns versioning off `feat:`/`fix:` commits. (Package *keywords*
  in `pyproject.toml` are fair game; only the version line is off-limits.)
- **Batch-release option:** hold the release PR and land several features, then
  force the target version with a `Release-As: X.Y.Z` commit footer + umbrella
  release notes (the v0.37.0 pattern).
- **Benchmarks deterministic:** `NEURALMIND_SYNAPSE_INJECT=0` for fixed numbers.
- **Bar for any public/benchmark work:** must pass engineering + Reddit scrutiny
  by serious technicians. Report losses, pin versions, commit raw traces.
- **Disclosed-maker only** for all outreach (the standing ethical line above).

---

## Pointers

- Launch copy: `docs/launch/` (README is the index).
- Benchmark methodology + raw data: `docs/benchmarks/public.md`,
  `bench/public/`.
- Comparison docs: `docs/comparisons/` (vs Headroom, the context-engineering
  stack, vs generic RAG, vs prompt caching).
- Reproduce headline: `python -m evals.public.run`; competitor:
  `python -m evals.public.competitor`.
- Per-language parity gate: `python -m evals.parity.run`.
- Architecture + shipping checklist: `CLAUDE.md`.
