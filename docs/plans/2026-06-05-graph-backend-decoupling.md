# Plan — Graph-Backend Decoupling (multi-language + beyond)

**Created:** 2026-06-05 18:09 UTC
**Branch line:** `claude/treesitter-backend` → PR **#187** (the Phase-1 foundation)
**Purpose:** session handoff — context, roadmap, conventions, and a copy-paste
prompt to resume in a fresh session.

---

## Snapshot (2026-06-05)

- **v0.14.0 is published** (PyPI + GHCR): the `neuralmind eval` faithfulness
  measurement + CI eval-gate, macOS added to the CI matrix, Windows demoted to
  ⚠️ experimental.
- **PR #187 — `feat: built-in tree-sitter graph backend` — is GREEN, still a
  draft.** It makes `pip install neuralmind && neuralmind build .` work with
  **no external graphify install** by generating a graphify-compatible
  `graph.json` from a tree-sitter parse (`neuralmind/graphgen.py`). Everything
  downstream of `graph.json` (embedder, context_selector, communities,
  synapses, server) is unchanged — only the graph *producer* is swapped.
  15 stdlib tests; schema-parity with graphify; `SCHEMA_VERSION` +
  `SUPPORTED_SUFFIXES` seam already in place. Would release as **v0.15.0**.
- **Issue #186** — Windows support (chromadb file-handle teardown, log-rotation
  rename, concurrent-append). Tracked, not started.
- **Dependabot #7** — chromadb CVE-2026-45829, documented not-exploitable
  (embedded `PersistentClient`, no server, no `trust_remote_code`); awaiting
  manual dismissal in the GitHub UI (no patched chromadb exists yet).

## Strategic context (2026 research, condensed)

The decoupling's future-proof property is **the seam** (pluggable graph
*producer* behind `graph.json`), not the parser. Research strongly validates
the direction:

- **tree-sitter is the converging structural standard** (GitHub code-nav, Zed,
  Neovim, Helix; some projects drop SCIP for tree-sitter incremental indexing).
- The exact pattern is independently validated **and** newly competitive —
  arxiv **2603.27277 "Codebase-Memory"** (Feb 2026): tree-sitter graph +
  persistence + MCP, 66 languages, ~120× fewer tokens than file-exploration,
  auto-detected by Claude Code/Codex/Gemini, 900★ in 4 weeks.
- **Hybrid (graph + vector) wins on correctness** (+8% vs vector-only); **AST-
  derived graphs beat LLM-extracted ones** for reliability (arxiv 2601.08773).
- **Threat:** "grep not vectors" (Claude Code agentic search). **Moat:** token
  economics + the **learned synapse layer** (usage memory — which static-graph
  competitors lack) + MCP distribution. The static graph is commoditizing;
  invest in the learned layer.

Sources: arxiv 2603.27277, arxiv 2601.08773, Sourcegraph SCIP announcement,
sheeptechnologies RFC (drop SCIP for tree-sitter), MindStudio "grep not
vectors", Zylos codebase-intelligence-2026.

---

## The plan

### Phase 0 — Land the foundation (do first)
- [ ] Review + merge **#187** → release-please cuts **v0.15.0**.
- [ ] **Parity gate (CI):** add a job to `.github/workflows/ci-benchmark.yml`
      that builds the fixture with **both** backends (graphify and the built-in
      tree-sitter one) and runs the **faithfulness eval + self-benchmark** on
      each, gating that the built-in backend's reduction ratio and
      faithfulness-delta stay within tolerance of graphify's. This is the
      safety net for every backend change after this.
- [ ] v0.15.0 **docs/SEO pass** (the "no graphify needed" standalone-build
      story) per the CLAUDE.md checklist.

### Item 1 — Multi-language (highest user value)
- Add tree-sitter extractors beyond Python — **TS + Go first** (fixtures exist:
  `tests/fixtures/sample_project_ts`, `tests/fixtures/sample_project_go`).
- Refactor `neuralmind/graphgen.py`: a per-language extractor keyed by suffix
  (`SUPPORTED_SUFFIXES` is the seam). Map each grammar's node types onto the
  same model (Python `function_definition`/`class_definition` → TS
  `function_declaration`/`class_declaration`, Go `function_declaration`/
  `type_declaration`, …) emitting the same `code` nodes + `contains`/`imports_from`/
  `inherits`/`calls` edges + docstring/comment `rationale`.
- Deps: `tree-sitter-typescript`, `tree-sitter-go`.
- **Acceptance:** valid graph on TS + Go fixtures; key symbols present; parity
  gate green per language.

### Item 2 — Optional precision backend
- Behind the same `graph.json` seam, an optional LSP/SCIP-backed pass that
  replaces heuristic `calls`/`inherits` with compiler-accurate edges where a
  language server / SCIP index is available (proven hybrid: tree-sitter breadth
  + LSP/SCIP precision per language).
- **Acceptance:** opt-in, off by default; parity gate shows ≥ graphify-quality
  call/inherit edges.

### Item 3 — Incremental graph updates
- Per-file re-parse on change (graphgen is already file-by-file); re-embed only
  changed nodes (embedder already content-hashes). Wire to `watcher.py`.
- **Acceptance:** editing one file regenerates only its nodes/edges; no-op
  rebuild is ~constant time.

### Item 4 — Lean into the moat (strategic)
- Static graph is commoditizing; invest where NeuralMind is unique: the learned
  synapse layer + MCP distribution.
- Concrete: ensure the MCP server is **auto-detected by Claude Code / Cursor /
  Cline** out of the box; surface synapse-recalled neighbours in retrieval +
  the graph view; measure the **learned uplift** (E1.5 onboarding-lift eval) as
  the headline differentiator.

---

## Conventions (do not skip)

- **Every backend change must pass the eval + benchmark parity gate** — that is
  the whole reason the eval harness exists.
- **User-facing changes ship docs + SEO in the same PR** (CLAUDE.md checklist:
  `RELEASE_NOTES_v*.md`, README banner, `docs/index.html`, `docs/about.html`,
  `docs/wiki/CLI-Reference.md`, `docs/use-cases/*`, `docs/sitemap.xml`,
  `pyproject.toml` keywords).
- **Never hand-bump versions** — release-please owns `pyproject.toml`,
  `.release-please-manifest.json`, `CHANGELOG.md`; `feat:`/`fix:` commit
  subjects drive the bump.
- **`release.yml` does NOT auto-fire on the release-please tag** (created with
  `GITHUB_TOKEN`). After the release PR merges, **manually dispatch
  `release.yml` against the tag** — `run_workflow` with input `tag: vX.Y.Z`
  (issue #98). Verify the PyPI version afterwards.
- Branch per feature; open **draft** PRs; keep the synapse-layer tests
  stdlib-only.

---

## Copy-paste prompt for the next session

```
You are continuing the NeuralMind graph-backend decoupling. FIRST read
docs/plans/2026-06-05-graph-backend-decoupling.md — it has the full context,
the 2026 research, and the conventions you must follow.

State: v0.14.0 is published. PR #187 (branch claude/treesitter-backend) adds a
built-in tree-sitter graph backend so `pip install neuralmind && neuralmind
build .` works with no graphify — it is GREEN and ready. The 4 roadmap items
build on it.

Do, in order:
0. Review and merge #187 → let release-please cut v0.15.0. Add the parity-gate
   CI job (build the fixture with BOTH graphify and the built-in backend, run
   the faithfulness eval + self-benchmark on each, gate that the built-in stays
   within tolerance). Ship the v0.15.0 docs/SEO pass.
1. Multi-language: add tree-sitter TypeScript + Go extractors behind graphgen's
   SUPPORTED_SUFFIXES seam (fixtures exist at tests/fixtures/sample_project_ts
   and _go), proven at parity per language via the gate.
2. Optional LSP/SCIP precision pass for exact calls/inherits, behind the same
   graph.json seam, off by default.
3. Incremental per-file graph updates wired to the watcher.
4. Lean into the moat: MCP auto-detection by Claude Code/Cursor/Cline + measure
   the learned-synapse uplift (E1.5 onboarding-lift eval).

Conventions: every backend change MUST pass the eval+benchmark parity gate;
user-facing changes ship docs+SEO in the same PR (CLAUDE.md checklist); never
hand-bump versions (release-please owns them); after a release PR merges,
manually dispatch release.yml against the tag (issue #98) and verify PyPI.
Branch per feature; open draft PRs.
```
