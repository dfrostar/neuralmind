# Roadmap

A short, public list of where NeuralMind is going. Issues and PRs that
move any of these forward are very welcome.

## Now — v1.8.0 (security hardening, code quality, marketing site)

Latest release **v1.8.0** is live on PyPI and GHCR. All CI green
(pages-build-deployment removed — GitHub Pages decommissioned in favor
of Cloudflare Pages for the marketing site).

**What's shipped since v1.0.0 (the open-core launch):**

- **v1.0.0** — Open-core launch: MIT tier (free), Tier 2 paid
  (SSO, RBAC, multi-team sync), Ed25519 license validation, dual-bound
  grace window, clock-skew anti-tamper, governance hardening, audit
  log hash chain, self-hosted deployment. All security issues from
  DeepSeek QA patched.
- **v1.1.0** — Bug fixes: license-file deletion no longer resets paid
  tier to free, admin parameter required (not optional) on all
  governance mutations, atomic writes for validation sidecars.
- **v1.2.0** — C4 Quality Harness: independent gate, NaN-safe clamp,
  fail-open direction, backward compatibility.
- **v1.3.0–v1.6.0** — Incremental extraction hardening, D3 judge
  transcripts, documentation drift fixes, marketing surface audit.
- **v1.7.0** — Louvain modularity rewrite: resolution parameter,
  O(·k) community weight updates, Phase 2 self-loop weight
  preservation, falsy label fallback, dead code removal. DocEvolver
  for data-driven JSDoc optimization. Marketing audit + version bump.
- **v1.7.1** — .nojekyll for GitHub Pages, ruff formatting, ISC004 fix.
- **v1.7.2** — Release notes + public surface update.
- **v1.8.0** — DeepSeek QA patches (3 CRITICAL + WARNING), ruff bump
  0.15.18→0.16.0, SBOM publish to site, marketing chart refresh.

**Recent CI/deep-work (not yet versioned):**

- GitHub Pages decommissioned — marketing site served via Cloudflare
  Pages (eliminates the only failing CI job).
- Test matrix bumped Node 18→22 (fixes ESM module error in jsdom/vitest).
- Extraction_cache.json gitignore cleanup (test fixture timestamps).

### Remaining before v1.9.0:

- **Self-benchmark stability** — flaky chromadb embedding nondeterminism
  in CI; pin or widen the pass/fail band.
- **Marketing site pages-build-deployment** — REMOVED (decommissioned
  GitHub Pages). Cloudflare Pages deploy is the canonical path.
- **Test coverage for DocEvolver failure path** — rollback behavior
  untested.

## Shipped — v0.13 → v1.0.0

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

## Next (v1.9.0 — near term)

- **Broker pattern** — Pluggable payment provider (Stripe primary,
  LemonSqueezy fallback).
- **Grace period per-license** — Currently global; per-customer
  configurability.
- **Retrieval quality benchmarks beyond reduction** — Top-k accuracy
  and answer faithfulness on a public query set.
- **More languages in fixture suite** — TypeScript, Go, Rust, Java,
  C/C++ currently covered; add JS/JSX first.

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
