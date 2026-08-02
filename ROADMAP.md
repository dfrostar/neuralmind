# Roadmap

A short, public list of where NeuralMind is going. Issues and PRs that
move any of these forward are very welcome.

## Now — v1.14.0 (Agent OS multi-tenancy)

**Latest release v1.14.0** shipped to PyPI and GHCR (2026-08-02).

**What shipped:**
- **Agent OS package** — Multi-tenancy, RBAC, signal detection, and experiment runner. 5 modules (`tenant`, `governance`, `signals`, `experiment`, `api`).
- **Tenant registry** — Business-scoped project isolation with per-tenant RBAC (admin/operator/viewer). JSON-backed, thread-safe, atomic writes.
- **Page-Hinkley anomaly detection** — No fixed thresholds; detects small persistent shifts in metrics streams. Severity levels, cooldown, per-metric state.
- **A/B experiment runner** — Promote/rollback governance with `higher_is_better` metric support. Delta normalization.
- **Signal → experiment integration** — Anomaly-triggered experiments with full audit trail.

---

## Next (v1.10.0 — near term)

- **Self-benchmark stability** — flaky chromadb embedding nondeterminism in CI.
- **Retrieval quality benchmarks** — top-k accuracy and answer faithfulness on public query set.
- **Broker pattern** — pluggable payment provider (Stripe primary, LemonSqueezy fallback).
- **Grace period per-license** — configurability beyond global constant.

---

## Track D — Adjacent Products

### Book Content QA System (v1.9.x)

A second indexer type targeting book/markdown content instead of code. Reuses NeuralMind's turbovec backend, embedding pipeline, and hybrid search infrastructure.

| Module | Target | Query Type |
|--------|--------|------------|
| `neuralmind/code_graph/` | Code repos | "Find the function that handles X" |
| `neuralmind/content_qa/` | Book markdown | "What does the book say about Y?" |

**First use-case:** *The Peptide Patient's Guide* (~27,000 words, 8 chapters, 96 claims).

**Status:** Draft docs in Downloads (BRD/TRD/PRD/requirements, 2026-07-29). Implementation begins after v1.10.0.

---

## Shipped — v0.13 → v1.9.0

### The long arc (v0.13 → v0.54.0)

- **Eval-first foundation** — CI-gated faithfulness + retrieval-quality
  harness, tree-sitter seam, directional recall.
- **Backend independence** — Owned MiniLM + TurboVec backend,
  ChromaDB-free default install.
- **Durability PRDs** — Versioned IR, quality harness, debug traces,
  daemon, memory namespaces, git-branch isolation.
- **Ten languages** — Python, TypeScript, Go, Rust, Java, C, C++, C#,
  Ruby, PHP behind tree-sitter.
- **Honest public benchmark** — `neuralmind benchmark --public`,
  live head-to-head, LLM-judged answerability arm.
- **Team memory** — Synapse signal committed; teammates' agents
  inherit it (`.neuralmind-team-memory.json`).
- **Agent-facing surface** — VS Code extension, BM25 + dense search,
  MCP tools, CI auto-index, `neuralmind probe`, trust/transparency
  six, schema-artifact indexing.
- **Graph view + live activity feed** — Obsidian-style force-directed
  graph, SSE live feed, pin/unpin, depth slider, edge tooltips.
- **Install anywhere** — pip, pipx, uv, Docker, source. Multi-stage
  Dockerfile, non-root runtime.
- **Always-on** — `neuralmind watch` + `neuralmind serve` as
  production processes, systemd/launchd/Task Scheduler templates.
- **Enterprise-ready (v0.9.0)** — GHCR auto-build, CycloneDX SBOM,
  air-gapped walkthrough, compliance one-pager.
- **License enforcement (v0.52.0–v0.54.0)** — Impact tool, Tier 2
  Team tier, Ed25519 security hardening, autopilot integration.

### Open-core launch (v1.0.0)

See above — the public launch of the MIT + paid tier architecture.

### Shipped releases (v1.0.0 → v1.14.0)

- **v1.14.0** — Agent OS multi-tenancy (tenant registry, RBAC, Page-Hinkley anomaly detection, A/B experiments, signal → experiment integration). 44 tests.

- **v1.0.0** — Open-core launch: MIT tier (free), Tier 2 paid
  (SSO, RBAC, multi-team sync), Ed25519 license validation, dual-bound
  grace window, clock-skew anti-tamper, governance hardening, audit
  log hash chain, self-hosted deployment.
- **v1.1.0** — Bug fixes: license-file deletion no longer resets paid
  tier to free, admin parameter required on all governance mutations,
  atomic writes for validation sidecars.
- **v1.2.0** — C4 Quality Harness: independent gate, NaN-safe clamp,
  fail-open direction, backward compatibility.
- **v1.3.0–v1.6.0** — Incremental extraction hardening, D3 judge
  transcripts, documentation drift fixes, marketing surface audit.
- **v1.7.0** — Louvain modularity rewrite, DocEvolver for data-driven
  JSDoc optimization. Marketing audit + version bump.
- **v1.7.1** — .nojekyll for GitHub Pages, ruff formatting, ISC004 fix.
- **v1.7.2** — Release notes + public surface update.
- **v1.8.0** — DeepSeek QA patches, ruff bump, SBOM publish to site,
  marketing chart refresh.
- **v1.9.0** — G5 structural gap detection (Brandes betweenness,
  cross-community bridge detection, gap scoring, CLI, MCP tool).
  43 tests. DeepSeek QA patches. DocEvolver failure-path tests.
  Node 18→22. GitHub Pages decommissioned.

## Next (~1–2 quarters)

- **Self-contained pip-only demo** — `pip install neuralmind &&
  neuralmind demo` by shipping a pre-built sample graph in the wheel.
- **More integration walkthroughs** — One end-to-end guide per
  ecosystem (Claude Code, Cursor, Cline, Continue, Hermes-Agent,
  OpenClaw).
- **Broader install-mcp targets** — Add Windsurf, Continue.dev, Zed to
  `mcp_install.py`.
- **Language coverage expansion** — JS/JSX first, then others as
  `[extra-langs]` optional install.

## Where we want help

- **Run `neuralmind benchmark . --contribute`** on your own repo and
  open a PR. Real-world numbers are the most valuable contribution.
- **New context strategies** — The 4-layer L0–L3 selector is one
  approach; alternatives plug in via `context_selector.py`.
- **Connectors** — New MCP-host integrations: editor plugins,
  agent runtimes, CI pipelines.
- **Documentation** — Troubleshooting entries from real failures you
  hit, and short tutorials for specific codebase shapes.

## Out of scope (for now)

- **Cross-repo / org-wide search.** That's Sourcegraph Cody's niche;
  we intentionally stay per-project and local.
- **Hosted SaaS.** NeuralMind is local-first by design.
- **Inline completion.** Use Copilot or your editor's native
  autocomplete — NeuralMind is the context layer.

---

This roadmap is a living document. Open an issue to propose a change
or argue for re-prioritization.
