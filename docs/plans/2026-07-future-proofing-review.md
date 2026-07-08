# NeuralMind Future-Proofing Review — 2026-07

**Date:** 2026-07-08
**Reviewed release:** v0.41.0
**Status:** Current — supersedes the forward-looking framing of
[`../FUTURE-PROOFING-PLAN.md`](../FUTURE-PROOFING-PLAN.md) and
[`../NEXT-RELEASE-PLAN.md`](../NEXT-RELEASE-PLAN.md) (both retained as historical
planning artifacts).

---

## The inversion thesis

NeuralMind has **executed** most of its own future-proofing plan. The eval-first
arc (v0.13 "Measure" → v0.16 "Anticipate") and the bulk of the nine-initiative
durability pack in
[`2026-06-10-future-proofing-prd-pack.md`](2026-06-10-future-proofing-prd-pack.md)
are **shipped** across v0.13 → v0.41. The engineering machinery is genuinely
strong: ruff + black, cross-OS CI (Linux / macOS / Windows, Python 3.10–3.12),
967 tests, OIDC trusted publishing, per-release CycloneDX SBOM, GHCR multi-arch
images, release-please automation, a Dependabot + CVE-watch posture.

**The future-proofing risk has therefore inverted.** It is no longer "build the
durability features." It is now:

1. **Drift** — planning and reference docs that describe a v0.4/v0.13-era product
   the code left behind, so a reader gets a wrong mental model.
2. **Unenforced guarantees** — gates that *look* active but pass unconditionally,
   and declared promises (typed package) that aren't actually delivered.
3. **A few concentrated structural/operational risks** — one external-service
   single point of failure, broad silent exception handling, and a handful of
   oversized modules.

This review reconciles plan-vs-shipped, catalogs the current gaps (ranked, with
evidence), records what the accompanying PR fixes, and sets the forward plan.

---

## Plan → shipped reconciliation

Legend: ✅ shipped · ◐ partial (baseline shipped, later phases open) · ⏸ open

### Eval-first arc (`NEXT-RELEASE-PLAN.md`, ROADMAP "Next")

| Release | Theme | Status | Evidence |
|---|---|:--:|---|
| v0.13 | Measure — faithfulness/retrieval eval harness | ✅ | `neuralmind eval` (`cli.py:cmd_eval`), `quality.py`, `test_eval_faithfulness.py`, `test_quality_harness.py`, `test_onboarding_eval.py`, `evals/` |
| v0.14 | Decouple — graph-source adapter | ✅ | Built-in tree-sitter backend `graphgen.py` (no external graphify); `test_graphgen.py` (140 tests) |
| v0.15 | Endure — host-capabilities resilience | ◐ | `hooks.py` `HOOK_VERSION` managed blocks + Claude Code version workarounds; `mcp_install.py` multi-client; formal contract-test suite still thin |
| v0.16 | Anticipate — proactive + cross-agent memory | ✅ | `neuralmind next` / `neuralmind_next_likely`; committed team memory `memory publish` |

### Nine-initiative durability pack

| PRD | Initiative | Status | Evidence |
|---|---|:--:|---|
| 1 | Versioned internal index contract (IR) | ✅ | `ir.py` (963 lines), `neuralmind validate` (`cmd_validate`), `test_ir.py`, `ir_version` in state |
| 2 | Retrieval quality harness | ✅ | `neuralmind eval`, `quality.py`, polyglot fixtures, CI eval gate |
| 3 | Explainability & debug traces | ✅ | `--trace` / `--explain` (v0.39), `test_trace.py`, `probe.py`, `relevance` sidecar (v0.41) |
| 4 | Memory namespaces & branch isolation | ✅ | `namespaces.py`, `test_synapse_namespaces.py`, `docs/use-cases/branch-isolated-memory.md` |
| 5 | Daemon-first architecture | ✅ | `daemon.py` (634), `daemon_client.py`, `neuralmind-daemon` entry point, `neuralmind daemon`, `test_daemon.py` |
| 6 | Polyglot monorepo support | ◐ | 10-language fixtures (`test_polyglot_fixtures.py`), `docs/use-cases/growing-monorepo.md`; partition-aware incremental indexing not yet a first-class surface |
| 7 | Pluggable ingestion framework | ◐ | `graphgen.py` + `SUPPORTED_SUFFIXES` seam, SCIP fixture, `test_competitor_adapter.py`; a formal capability-model adapter API is not yet public |
| 8 | Durable team-memory portability | ◐ | `memory publish` (v0.30+), `team_memory.py`, `test_team_memory.py`; portable signed cross-machine bundles still in progress (as the PRD itself notes) |
| 9 | Agent-agnostic orchestration layer | ◐ | Per-client adapters (`mcp_install.py`), hook versioning; formal lifecycle event model + conformance suite still open |

**Net:** 6 of 9 PRDs and the whole eval-first arc are effectively delivered; the
three ◐ items have a shipped baseline with later phases genuinely outstanding.
The `FUTURE-PROOFING-PLAN.md` enterprise checklist (RBAC, SAML, FIPS, encrypt-at-rest,
Spark/Dask) remains intentionally deferred per the local-first rationale in
`NEXT-RELEASE-PLAN.md §1` and `§5` — it was never the plan of record and is not a gap.

---

## Current gaps (ranked)

Severity is impact-on-durability, not urgency. "This PR" = fixed by the change
that ships alongside this review; "Tracked" = forward-plan item below.

| # | Gap | Severity | Status |
|---|---|:--:|---|
| 1 | **Reference docs contradicted the code** — `COMPATIBILITY.md` / `VERSION-STRATEGY.md` / `requirements-pinned.txt` were frozen at v0.4.x and still called ChromaDB the default backend and graphify a required dependency (both false since v0.29 / v0.15). Misinforms every reader. | High | **This PR** |
| 2 | **Type-checking was theater** — a strict `[tool.mypy]` config existed, but the CI job disabled its error codes *and* set `continue-on-error: true`, so type regressions shipped freely. | High | **This PR** (grandfather list + gate on; incremental strictness = Tracked) |
| 3 | **External S3 model download is a single point of failure** — the "100% local" default still fetches the MiniLM ONNX model from a hardcoded Chroma-owned S3 bucket on first run (`onnx_embedder.py`); if it moves, first-run indexing breaks. | High | Tracked |
| 4 | **Missing `py.typed`** — package declares the `Typing :: Typed` classifier and is ~79% annotated, but shipped no PEP 561 marker, so downstream type checkers saw no types. | Medium | **This PR** |
| 5 | **No local quality gate** — `pre-commit` was a declared dev dependency with no `.pre-commit-config.yaml`; contributors relied entirely on CI. | Medium | **This PR** |
| 6 | **Systemic silent exception swallowing** — ~64 `except Exception → pass/continue` of 226 total, concentrated in `core.py`, `hooks.py`, `server.py`, `cli.py`. Some is the deliberate "never crash the host" contract, but with no debug logging, malfunctions are invisible. | Medium | Tracked |
| 7 | **Oversized modules** — `graphgen.py` (3149), `cli.py` (2534), `core.py` (1811, a god object with ~45 methods), `synapses.py` (1281), `mcp_server.py` `tool_review` (~330). Refactor risk grows with size. | Medium | Tracked |
| 8 | **Dependency fragility** — 10 `tree-sitter-*` grammars floored at `>=0.21` with no ceiling (historically ABI-breaking); the unmaintained `toml` package used where stdlib `tomllib` would do; the ChromaDB critical CVE with no fixed release. | Medium | Tracked (CVE watched) |
| 9 | **VS Code extension is dormant** — `editors/vscode/` at v0.1.0 while the package is v0.41.0; unpublished, no bundler/lint/test/CI. Most likely surface to rot unnoticed. | Medium | Tracked (decision needed) |
| 10 | **`about.html` duplicated a "What's New in v0.38.0" section** — violated the checklist's "demote, never duplicate" rule. | Low | **This PR** |
| 11 | **Coverage never gates** — Codecov is informational (`fail_ci_if_error: false`); coverage can erode silently across 21k LOC. | Low | Tracked |
| 12 | **Version dual-sourced** — declared in both `pyproject.toml` and `neuralmind/__init__.py`, kept in sync by hand. | Low | Tracked |
| 13 | **Duplicated data access** — `synapse_memory.py` re-implements SQLite reads that `SynapseStore` owns; a schema change must be mirrored in two places. | Low | Tracked |
| 14 | **SEO checklist line unsatisfiable** — the `CLAUDE.md` checklist asks for release-notes URLs in `docs/sitemap.xml`, but release notes live as root `.md`, not published pages, so the line is never met. | Low | Tracked (reword the checklist or publish notes) |

---

## What the accompanying PR changes

Scope: docs + light config only. No product source or behavior changes, so no
`feat:`/`fix:` commits and no release-please bump. Adds no new command / hook /
env var, so the `CLAUDE.md` five-surface docs+SEO checklist does not apply.

- **This review doc** + "historical artifact" banners on `FUTURE-PROOFING-PLAN.md`
  and `NEXT-RELEASE-PLAN.md`.
- **Reference-doc reconciliation** — `COMPATIBILITY.md`, `VERSION-STRATEGY.md`,
  `requirements-pinned.txt` rewritten to v0.41 reality (backend default, graphify
  optional, real release-please/OIDC flow); duplicate `about.html` section removed.
- **mypy now gates** — `continue-on-error` removed from the CI `type-check` job;
  a grandfather list of the 15 currently-failing modules + a `demo_data` exclude
  live in `pyproject.toml [tool.mypy]`, and `--follow-imports=silent` scopes the
  gate to the package. The 41 clean modules (and any new module) now fail CI on a
  type regression; the grandfather list is the worklist for the strictness ratchet.
- **`py.typed`** added and included in the wheel + sdist.
- **`.pre-commit-config.yaml`** added (black + ruff + basic hygiene) and wired
  into `CONTRIBUTING.md`.
- **`ROADMAP.md`** "Next" repointed at the durability/hardening items below;
  "Shipped" updated to acknowledge the v0.13 → v0.41 arc.

---

## Forward plan (post-v0.41 durability & hardening)

Ranked by leverage. Each is a real project, tracked here, not attempted in the
reconciliation PR.

1. **Offline-first model asset** — remove the `onnx_embedder.py` S3 SPOF: bundle
   or mirror the ONNX model, add an offline-cache path and a checksum-verified
   local fallback. Highest-leverage because it undercuts the headline "100% local"
   promise on any first run without that specific bucket. Seed: the air-gapped
   use-case already documents a manual model cache.
2. **Type-strictness ratchet** — with the gate now real, remove the two baseline
   relaxations (`--disable-error-code=no-untyped-def`, `--implicit-optional`) and
   drain the 15-module grandfather list one module at a time.
3. **Observability for swallowed exceptions** — route the broad
   `except Exception` handlers through a `NEURALMIND_DEBUG`-gated logger so hook /
   server / watcher malfunctions are diagnosable without breaking the host.
4. **Dependency resilience** — cap the tree-sitter grammar upper bounds; migrate
   TOML reads to stdlib `tomllib`; hold the ChromaDB CVE watch until a fix ships.
5. **Structural refactors** — split `core.py`, `cli.py`, and `tool_review` behind
   the existing test coverage; collapse `synapse_memory.py`'s duplicate SQLite
   access into `SynapseStore`.
6. **VS Code extension decision** — invest (bundler + lint + test + Marketplace
   publish pipeline, version aligned to the package) or explicitly mark it
   experimental so the five-surface story is honest.
7. **Tighten the release gates** — a coverage floor (even a low one) so erosion is
   visible; single-source the version (derive `__init__.__version__` from package
   metadata); reword or satisfy the sitemap SEO checklist line.

The suggested sequence still holds: harden the operational foundation (1–4)
before the cosmetic-but-large refactors (5), because the foundation items each
protect a live promise (local-first, type-safety, debuggability, supply chain).

---

## Verification of this review's claims

Every plan-vs-shipped ✅ is backed by a named module + test that exists in the
tree at v0.41.0 (see the Evidence columns). The gap catalog's "This PR" items are
verifiable by the accompanying diff; the "Tracked" items are reproducible from
the cited files (`onnx_embedder.py` S3 URL, the `except Exception` counts, the
`wc -l` module sizes, the tree-sitter `>=` floors in `pyproject.toml`).
