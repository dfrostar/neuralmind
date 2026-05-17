# Roadmap

A short, public list of where NeuralMind is going. Issues and PRs that
move any of these forward are very welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md) for how to start.

For the longer-horizon engineering plan (release cadence, monitoring,
compliance, scale targets), see
[`docs/FUTURE-PROOFING-PLAN.md`](docs/FUTURE-PROOFING-PLAN.md).

## Shipped in v0.6.1 — install anywhere

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
[v0.6.1 release notes](RELEASE_NOTES_v0.6.1.md) and the
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

## Now (v0.7) — Always-On

Distribution is sorted (v0.6.1); the next batch makes `neuralmind
watch` and `neuralmind serve` first-class production processes.
Tracking issue: [#119](https://github.com/dfrostar/neuralmind/issues/119).

- **systemd / launchd templates.** Committed `scripts/systemd/` and
  `scripts/launchd/` service / plist files for `watch` and `serve`
  with install instructions inline.
- **Windows Task Scheduler doc note.** Build on
  [`wiki/Scheduling-Guide.md`](docs/wiki/Scheduling-Guide.md)'s
  existing Task Scheduler section with NeuralMind-specific commands.
- **`/healthz` endpoint** on `neuralmind serve` — small JSON `{status:
  "ok", version: …}` for Docker `HEALTHCHECK` and systemd
  `ExecStartPost`.
- **Aider MCP integration.** Verify Aider's stdio MCP support, then
  add an integration block to the README — same shape as the
  Hermes-Agent / OpenClaw / Claude Code blocks.
- **`docs/use-cases/always-on.md`** — walkthrough per platform with
  verification steps.

## Then (v0.7.x) — Enterprise-Ready

Tracking issue: [#120](https://github.com/dfrostar/neuralmind/issues/120).

- **GHCR auto-build of the v0.6.1 Dockerfile** on tag push —
  multi-platform (`linux/amd64`, `linux/arm64`).
- **Air-gapped install doc** — PyPI mirror + ChromaDB embedding
  model pre-download script.
- **SBOM publication** on tagged releases via `cyclonedx-py` or
  `syft`.
- **`docs/COMPLIANCE-SUMMARY.md`** — one-pager consolidating NIST AI
  RMF + SOC 2 + GDPR claims scattered across
  [SECURITY-GUIDE](docs/SECURITY-GUIDE.md) and
  [ENTERPRISE](docs/ENTERPRISE.md).

## Graph-view backlog (v0.7 or later)

Frontend wins carried forward from the pre-v0.6.1 plan. Could roll
into v0.7 if there's appetite, or stay queued.

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
