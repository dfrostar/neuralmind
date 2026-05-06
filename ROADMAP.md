# Roadmap

A short, public list of where NeuralMind is going. Issues and PRs that
move any of these forward are very welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md) for how to start.

For the longer-horizon engineering plan (release cadence, monitoring,
compliance, scale targets), see
[`docs/FUTURE-PROOFING-PLAN.md`](docs/FUTURE-PROOFING-PLAN.md).

## Now (next ~6 weeks)

- **One-command demo on the bundled fixture.** `bash scripts/demo.sh`
  — proves the headline reduction claim in under a minute on real
  code. ✅ shipped.
- **Slim the README.** Lead with the demo, push reference material into
  `docs/`. The promise should fit on one screen.
- **Seed community benchmarks with 3–5 outside submissions** so the
  table doesn't look maintainer-only. See
  [`docs/community-benchmarks.json`](docs/community-benchmarks.json).
- **Asciinema clip of the demo** embedded at the top of the README.
  Static numbers get skimmed; a 30-second terminal recording gets watched.

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
