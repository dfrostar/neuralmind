# Roadmap

A short, public list of where NeuralMind is going. Issues and PRs that
move any of these forward are very welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md) for how to start.

For the longer-horizon engineering plan (release cadence, monitoring,
compliance, scale targets), see
[`docs/FUTURE-PROOFING-PLAN.md`](docs/FUTURE-PROOFING-PLAN.md). For the
sequenced feature map of the next arc, see
[`docs/NEXT-RELEASE-PLAN.md`](docs/NEXT-RELEASE-PLAN.md). For the
nine-initiative durability arc beyond that (versioned IR, retrieval quality
harness, daemon-first architecture, and more), see
[`docs/plans/2026-06-10-future-proofing-prd-pack.md`](docs/plans/2026-06-10-future-proofing-prd-pack.md).

## Next — v0.13 → v0.16 (the eval-first arc)

The spine is *measure, then change, then measure again.* Full detail,
epics, and acceptance criteria in
[`docs/NEXT-RELEASE-PLAN.md`](docs/NEXT-RELEASE-PLAN.md); tracked in
issues [#171](https://github.com/dfrostar/neuralmind/issues/171)–[#175](https://github.com/dfrostar/neuralmind/issues/175).

| Release | Theme | What it does |
|---|---|---|
| **v0.13** | **Measure** | CI-gated faithfulness + retrieval-quality eval harness (100%-local offline judge; opt-in API judge). Polyglot TS/Go fixtures. The fitness function everything else depends on. |
| **v0.14** | **Decouple** | A `GraphSource` adapter so tree-sitter / LSP / SCIP can feed the pipeline, proven at parity by the v0.13 harness. Reduces the single-graph-backend dependency, widens language coverage. |
| **v0.15** | **Endure** | Host-capabilities adapter + integration-contract tests pinning Claude Code hook / MCP behaviour, so upstream drift is a one-adapter swap. |
| **v0.16** | **Anticipate** | Promote directional "what you edit next" recall to first-class; ship a portable cross-agent memory format. |

**Team/shared memory — approved in principle, gated on measurement.**
An opt-in, git-committed team baseline (reviewed in PRs, no SaaS) overlaid
by each developer's private personal layer. Its day-one onboarding lift is
*measured* by the v0.13 harness before the design is locked — see
[#175](https://github.com/dfrostar/neuralmind/issues/175). This is what
un-gates an honest enterprise lane: the compliance surface (RBAC, audit
of the shared layer) sequences *after* a real multi-writer surface exists,
not in anticipation of one.

## Shipped since v0.9.0

- **v0.12.0 — install doctor.** `neuralmind doctor` inspects an install
  and reports each piece with a status + exact fix; friendlier first-run
  error. See [v0.12.0 release notes](RELEASE_NOTES_v0.12.0.md).
- **v0.11.0 — directional synapses.** The brain layer learns *what comes
  next*, not just *what goes together* (`neuralmind next`,
  `neuralmind_next_likely`). See [v0.11.0 release notes](RELEASE_NOTES_v0.11.0.md).
- **v0.10.0 — agent ergonomics.** PostToolUse Bash footer reports what was
  dropped; `neuralmind last` recovers it. See [v0.10.0 release notes](RELEASE_NOTES_v0.10.0.md).

## Shipped in v0.9.0 — enterprise-ready

Phase 3 of the release arc. Turn the v0.6.0 → v0.7.0 → v0.8.0
foundation into something a CTO, security team, or regulated-industry
operator can actually adopt.

- **GHCR auto-build.** Every tagged release publishes
  `ghcr.io/dfrostar/neuralmind:vX.Y.Z` and `:latest`, multi-platform
  (`linux/amd64` + `linux/arm64`). `:latest` excludes pre-release
  tags. Workflow:
  [`docker-publish.yml`](.github/workflows/docker-publish.yml).
- **CycloneDX SBOM** attached to every release as
  `neuralmind-vX.Y.Z.sbom.json`. Workflow:
  [`sbom.yml`](.github/workflows/sbom.yml).
- **Air-gapped install walkthrough** —
  [`docs/use-cases/air-gapped.md`](docs/use-cases/air-gapped.md).
  Bundle-and-sneakernet pattern for PyPI wheels + ChromaDB ONNX model
  cache, with the Docker variant via `docker save`.
- **Compliance one-pager** —
  [`docs/COMPLIANCE-SUMMARY.md`](docs/COMPLIANCE-SUMMARY.md).
  Consolidates NIST AI RMF + SOC 2 + GDPR claims with a "how to
  verify yourself" command for every claim.

No production code changes — pure CI + docs. See
[v0.9.0 release notes](RELEASE_NOTES_v0.9.0.md).

## Shipped in v0.8.0 — always-on

`neuralmind watch` and `neuralmind serve` are first-class production
processes now. The synapse store accumulates 24/7 whether you're at
the keyboard or not, and the graph view is always listening.

- **Service templates.**
  [`scripts/systemd/neuralmind-{watch,serve}.service`](scripts/systemd/)
  user-scope units with hardening; matching macOS
  [`scripts/launchd/com.neuralmind.{watch,serve}.plist`](scripts/launchd/)
  user agents with `RunAtLoad` + `KeepAlive`; Windows Task Scheduler
  section in [`wiki/Scheduling-Guide.md`](docs/wiki/Scheduling-Guide.md).
- **`/healthz` endpoint** on `neuralmind serve` — unauthenticated,
  returns `{"status":"ok","version":"..."}` for Docker `HEALTHCHECK`
  + systemd `ExecStartPost`.
- **Cross-platform walkthrough** at
  [`docs/use-cases/always-on.md`](docs/use-cases/always-on.md) —
  Linux / macOS / Windows / Docker with install + verify + uninstall
  + troubleshooting.

Aider integration block deferred — current Aider stable has no
MCP-client support per docs check 2026-05-17. Adds when upstream
lands it.

See [v0.8.0 release notes](RELEASE_NOTES_v0.8.0.md).

## Shipped in v0.7.0 — install anywhere

Distribution release, not a features release. The brain is the same;
the matrix of ways to reach it widened.

- **Five install paths.** `pip`, `pipx`, `uv`, Docker, and source —
  all in a single matrix at the top of the README, the wiki
  Installation page, and the wiki Setup-Guide. Same package every
  path; smoke-test verified.
- **`Dockerfile` in the repo root.** Multi-stage, non-root runtime.
  Transitive deps (including `graphifyy`) pre-wheeled in the builder
  stage so the runtime image never reaches PyPI at build time.
- **PyPI keyword refresh.** Eight new keywords matching v0.6.0
  product copy (`graph-view`, `hebbian-learning`,
  `force-directed-graph`, …) so search ranking finally matches what
  we ship.
- **`fix(event_log)` (#115).** P2 correctness fix from a Codex
  review: rotated event logs reopen at offset 0 so events written
  before the next poll aren't dropped. The `reopen_at_start` flag
  also survives failed open attempts (the common rename-then-create
  gap) and the file-vanished branch.
- **`test(server)` (#116).** Explicit no-`?n=` default-20 coverage
  for `/api/queries`.

No migration. Same `graph.json`, same `synapses.db`, same hooks. See
[v0.7.0 release notes](RELEASE_NOTES_v0.7.0.md) and the
[install-paths walkthrough](docs/use-cases/install-paths.md) for the
full surface.

## Shipped in v0.6.0 — graph view + live activity feed

The v0.5.x graph-view foundation is now a story you can *see*. The
canvas pulses while the brain learns. Highlights:

- **Live activity feed.** `neuralmind serve` streams synapse + file
  events over SSE while running. Affected nodes pulse on the canvas
  in real time; a sidebar log keeps the most recent ~80 events. The
  pitch flipped from "view your code graph" to "watch the brain
  learning your codebase."
- **Cross-process activity bridge.** A separate `neuralmind watch`
  daemon (or hook-driven Claude Code session) now feeds the same live
  feed via `<project>/.neuralmind/events.jsonl`. The in-process bus
  stays the primary path; the JSONL is a deliberately boring side
  channel. Opt out with `NEURALMIND_EVENT_LOG=0`.
- **Visible pin glyph + Pin/Unpin button + Unpin-all.** Drag-to-pin
  already saved positions; v0.6.0 surfaces it: pinned nodes get a
  warm-colored marker, the detail panel has a Pin/Unpin toggle, and
  the sidebar has an Unpin-all button.
- **Cmd/Ctrl-K + `/` jump-to-search.** Focus the semantic search
  field from anywhere; Esc clears and blurs.
- **Local-graph depth slider.** 1–3 hops via BFS from the focused
  node; defaults to 1 so existing behavior is unchanged.
- **Replay-last-query overlay.** Re-highlight the L3 hits the agent
  most recently received — closes the trust gap on retrieval.
- **Edge tooltips + min-weight synapse slider.** Hover an edge to
  see the relationship and weight; filter the synapse overlay to
  hide weak edges.
- **Docs refresh.** Roadmap, README hero, landing page, about, and
  wiki all positioned around the graph view rather than treating it
  as a side feature.

No migration needed. Same ChromaDB index, same `synapses.db`, same
hooks — `neuralmind serve` just makes everything visible.

## Ecosystem — hub & registry listings

Distribution-channel work that runs in parallel with feature releases.
Investigated 2026-05-16: only **Agent Zero** publishes a public plugin
registry; **OpenClaw** and **Hermes-Agent** are config-only (already
documented in the README integration blocks).

- **Agent Zero** ([`agent0ai/a0-plugins`](https://github.com/agent0ai/a0-plugins))
  — draft listing ready at
  [`docs/integration-submissions/agent-zero/index.yaml`](docs/integration-submissions/agent-zero/index.yaml).
  Cross-repo PR pending maintainer go-ahead.
- **Anthropic MCP server registry** — worth a sweep when it stabilises;
  no firm submission process today.
- **`punkpeye/awesome-mcp-servers`** — community awesome-list, low
  effort, drive-by visibility.

Richer **Agent Zero plugin** (UI surface, settings panel, embedded
synapse-graph viewer in A0's web UI) is a follow-up if the
basic MCP listing draws users. Few hundred lines of Python against
[A0's plugin API](https://www.agent-zero.ai/p/docs/plugins/).

## Now — marketing rollout for v0.7/v0.8/v0.9

The three shipped releases above each have a deferred marketing pass.
Code + structural docs are done; the LinkedIn / NotebookLM / screencast
artifacts are drafted for v0.7 and pending for v0.8 + v0.9.

- **v0.7 marketing** — LinkedIn drafts at
  [`docs/LINKEDIN-POST-DRAFT.md`](docs/LINKEDIN-POST-DRAFT.md),
  NotebookLM pack at [`docs/notebooklm/v0.7.0/`](docs/notebooklm/v0.7.0/),
  screencast script at
  [`docs/SCREENCAST-v0.7.0.md`](docs/SCREENCAST-v0.7.0.md). Awaiting
  maintainer approval to publish.
- **v0.8 marketing** — LinkedIn draft + NotebookLM pack +
  screencast script for "Always-On" (audience: ops/SREs). Not yet
  drafted.
- **v0.9 marketing** — LinkedIn for CTOs/security, NotebookLM
  enterprise pack, screencast showing the GHCR pull + SBOM ingestion
  flow, optional Hacker News submission ("Show HN: NeuralMind 0.9 —
  local AI code memory, now containerized + SBOM"). Not yet drafted.

## Next (post-marketing)

- **Agent Zero `a0-plugins` listing** — draft at
  [`docs/integration-submissions/agent-zero/index.yaml`](docs/integration-submissions/agent-zero/index.yaml).
  Cross-repo PR pending.
- **`RELEASE_PLEASE_TOKEN` PAT secret** — the workflow change shipped
  in v0.8.0 (#126) is in place; needs the maintainer to add the PAT
  secret to make every future tag auto-publish to PyPI without manual
  `gh workflow run release.yml` dispatch (#98).
- **`punkpeye/awesome-mcp-servers`** — community awesome-list, low
  effort, drive-by visibility.
- **GitHub App** for release automation (long-term variant of #98) —
  more durable than a maintainer PAT, survives turnover.
- **Optional cosign image signing** on the GHCR images — provenance
  attestation for the enterprise pitch.

## Graph-view backlog (v0.10+ or later)

Frontend wins carried forward from the pre-v0.7.0 plan. Not currently
prioritised; could roll into a future graph-view focused release.

- **Saved views.** Obsidian-style named graph filter/zoom/depth
  combos, persisted in `localStorage`. Lets users keep "auth tour",
  "data layer", "hot synapses" around as one-click presets.
- **Right-click context menu on nodes.** Open-in-editor, Pin/Unpin,
  Focus, Copy id. The detail panel has the verbs already — surface
  them where mouse-driven users actually reach for them.
- **PNG / SVG export.** PNG is a one-liner via `canvas.toDataURL`;
  SVG needs a separate render path. Useful for design docs and PRs
  about retrieval behavior.
- **Time-based edge filter.** `synapses.last_activated` is already
  persisted — add a slider that complements the v0.6.0 min-weight
  slider with a "last N days" filter. Surfaces fresh vs stale
  associations.
- **Unify `neuralmind watch` with the in-process bus.** A single
  `serve` + `watch` process should not need the JSONL bridge — wire
  the daemon into `event_bus.publish()` directly when they share a
  process, keep JSONL as the cross-process fallback.

## Earlier wins (pre-v0.6)

Carried forward so the trail is legible — these were the "Now"
items before the graph view took over.

- **Graph view UI base** (v0.5.4) — `neuralmind serve` ships a
  local, dependency-free Obsidian-style force-directed graph with
  the synapse overlay, backlinks, semantic quick-switch,
  open-in-editor, per-session auth token, and layout persistence.
  v0.6.0 made it live.
- **Bundled MCP server** (v0.5.0) — the `[mcp]` extra is now a
  no-op; `pip install neuralmind` ships the MCP server by default.
  Closes the most common install footgun.
- **One-command demo on the bundled fixture.** `bash scripts/demo.sh`
  reproduces the headline reduction claim in under a minute. ✅ shipped.
- **Fact-based business case + honest assessment docs.**
  [`BUSINESS-CASE.md`](docs/BUSINESS-CASE.md) makes the compelling
  argument with provable claims; [`HONEST-ASSESSMENT.md`](docs/HONEST-ASSESSMENT.md)
  documents where it isn't worth installing. ✅ shipped.
- **README slim.** Cut the inflated savings table, the duplicate
  "who is this for" section, and the Enterprise Use Cases marketing
  wall (moved to [`ENTERPRISE.md`](docs/ENTERPRISE.md) with honest
  framing). ✅ shipped (first pass; further trimming possible).
- **Seed community benchmarks with outside submissions** so the
  table doesn't look maintainer-only. ⏳ still wanted — best path
  is running `neuralmind benchmark . --contribute` on a handful of
  well-known OSS repos with permission. See
  [`docs/community-benchmarks.json`](docs/community-benchmarks.json).
- **Asciinema clip of the demo** embedded at the top of the README.
  ⏳ Runbook in [`docs/RECORDING-DEMO.md`](docs/RECORDING-DEMO.md);
  needs to be recorded by the maintainer (can't run in CI because
  of the chromadb model download). v0.6.0's pulse-rings demo is a
  candidate second clip.

## Next (~1–2 quarters)

- **Self-contained pip-only demo.** `pip install neuralmind &&
  neuralmind demo` — no graphify, no checkout — by shipping a
  pre-built sample graph inside the wheel.
- **More integration walkthroughs.** One end-to-end guide per
  ecosystem we support (Claude Code, Cursor, Cline, Continue, Claude
  Desktop, Hermes-Agent, OpenClaw). Each walkthrough should run
  cleanly on a fresh machine.
- **Retrieval quality benchmarks beyond reduction.** Token reduction
  is necessary but not sufficient — add top-k accuracy and answer
  faithfulness measurements on a public query set.
- **More languages in the fixture suite.** Python is covered; add
  TypeScript and Go fixtures so the per-language numbers in
  `tests/benchmark/multi_model.py` reflect real differences.
- **Language coverage expansion.** Add JS/JSX first (grammar
  available, extractor is close to the existing TS path), then Rust,
  Java, and Ruby as an `[extra-langs]` optional install.
  `ir.py` already maps all the suffixes; only `graphgen.py` needs the
  extractors and grammar deps. Graceful fallback is already wired so
  new grammars are additive with no breakage.
- **`neuralmind_impact` blast-radius tool.** Reverse-edge traversal
  from any node — "what code depends on this?" The forward graph is
  fully built at index time; materialise the reverse index during
  `neuralmind build` and expose it as a new MCP tool
  (`neuralmind_impact`) and CLI command (`neuralmind impact`). Closes
  the one structural capability gap vs. dependency-graph peers.
- **Broader `install-mcp` targets.** Add Windsurf
  (`.windsurf/mcp.json`), Continue.dev (`~/.continue/config.json`),
  and Zed (`~/.config/zed/settings.json`) to `mcp_install.py`. The
  JSON config format is identical across all MCP hosts; only the
  destination path differs. Gets from 4 to 7 agents with no logic
  changes.

## Where we want help

- **Run `neuralmind benchmark . --contribute`** on your own repo and
  open a PR (or an issue — a maintainer will convert it). Real-world
  numbers are the most valuable contribution right now.
- **New context strategies.** The 4-layer L0–L3 selector is one
  approach; alternatives (graph walks, learned policies, hybrid
  dense+sparse) plug in via `context_selector.py`.
- **Connectors.** New MCP-host integrations: editor plugins,
  agent runtimes, CI pipelines.
- **Documentation.** Especially: troubleshooting entries from real
  failures you hit, and short tutorials for specific codebase shapes
  (monorepo, microservices, polyglot).

## Out of scope (for now)

- **Cross-repo / org-wide search.** That's
  [Sourcegraph Cody's](docs/comparisons/vs-cody.md) niche; we
  intentionally stay per-project and local.
- **Hosted SaaS.** NeuralMind is local-first by design; a hosted
  variant is not on the roadmap.
- **Inline completion.** Use [Copilot](docs/comparisons/vs-github-copilot.md)
  or your editor's native completion — NeuralMind is the context
  layer, not the completion layer.

---

This roadmap is a living document. Open an issue to propose a change
or argue for re-prioritization.
