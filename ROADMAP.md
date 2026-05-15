# Roadmap

A short, public list of where NeuralMind is going. Issues and PRs that
move any of these forward are very welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md) for how to start.

For the longer-horizon engineering plan (release cadence, monitoring,
compliance, scale targets), see
[`docs/FUTURE-PROOFING-PLAN.md`](docs/FUTURE-PROOFING-PLAN.md).

## Now (active — v0.5.x)

The current development thread is the **graph view** (`neuralmind
serve`), introduced in v0.5.4. We're iterating it in small,
independently-mergeable slices — "Phase B" below — before tackling
the bigger live-activity feed step in Phase C.

### Graph view — Phase B (small UX wins)

- **Replay-last-query overlay.** Reads
  `~/.neuralmind/memory/query_events.jsonl`, highlights the L3 hits
  the agent received, draws a pulse from the query into them.
  Answers "what did the agent actually see?"
  [`#105`](https://github.com/dfrostar/neuralmind/pull/105) — green, awaiting merge.
- **Edge tooltips + min-weight synapse slider.** Hover any edge to
  see the relationship (`calls`, or `learned · w 0.42 · 7×`); a
  sidebar slider hides weak synapses on dense graphs.
  [`#106`](https://github.com/dfrostar/neuralmind/pull/106) — green, awaiting merge.
- **Pin UX.** Drag already pins silently; add a visible pin glyph, a
  detail-panel "Pin / Unpin" toggle, and a sidebar "Unpin all".
  Pure frontend.
- **Quick-switch keyboard shortcut.** Bind `Cmd/Ctrl-K` (and `/`) to
  focus the search input from anywhere on the canvas; Esc to clear.

### Graph view — Phase C (the next bigger lift)

- **Live activity feed.** Server-sent events stream synapse
  activations and file-watcher events into a small sidebar log so
  you can *see* the brain learning in real time. Touches
  `server.py`, `synapses.py`, `watcher.py`, and the frontend.

### Other in-flight maintenance

- **Seed community benchmarks with 3–5 outside submissions** so the
  table doesn't look maintainer-only. Best path is running
  `neuralmind benchmark . --contribute` on Mempalace, the cmmc20
  project, and 2–3 well-known OSS Python/TS repos with permission.
  Each seed: ~10 min wall time. See
  [`docs/community-benchmarks.json`](docs/community-benchmarks.json).
- **Asciinema clip of the demo** embedded at the top of the README.
  Runbook in [`docs/RECORDING-DEMO.md`](docs/RECORDING-DEMO.md);
  needs to be recorded by the maintainer (can't run in CI because
  of the chromadb model download).

### Shipped recently

- **Graph view UI base** (v0.5.4) — `neuralmind serve` ships a
  local, dependency-free Obsidian-style force-directed graph with
  the synapse overlay, backlinks, semantic quick-switch,
  open-in-editor, per-session auth token, and layout persistence.
- **Bundled MCP server** (v0.5.0) — the `[mcp]` extra is now a no-op;
  `pip install neuralmind` ships the MCP server by default. Closes
  the most common install footgun.
- **One-command demo on the bundled fixture** — `bash scripts/demo.sh`
  proves the headline reduction claim in under a minute on real
  code.
- **Fact-based business case + honest assessment docs** —
  [`BUSINESS-CASE.md`](docs/BUSINESS-CASE.md) makes the compelling
  argument with provable claims;
  [`HONEST-ASSESSMENT.md`](docs/HONEST-ASSESSMENT.md) documents
  where NeuralMind isn't worth installing.
- **README slim** — moved the Enterprise wall to
  [`ENTERPRISE.md`](docs/ENTERPRISE.md), cut the inflated savings
  table, killed the duplicate audiences section.

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
