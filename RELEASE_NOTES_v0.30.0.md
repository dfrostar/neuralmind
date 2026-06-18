# NeuralMind v0.30.0 — team memory: your agents inherit each other's intuition

**Release Date:** June 2026

## TL;DR

NeuralMind's synapse layer learns *what code goes with what* from how you work.
v0.30.0 makes that learned signal a **team artifact**: commit one file and every
teammate's agent **inherits the team's learned associations automatically** on
its next session — so a fresh `git clone` starts with the team's earned
intuition instead of relearning it from scratch.

```bash
neuralmind memory publish          # writes .neuralmind-team-memory.json (commit it)
git add .neuralmind-team-memory.json && git commit -m "publish team memory"
# teammates: next `neuralmind build` / Claude Code session inherits it — zero setup
```

This is the differentiator a static code-index can't copy: there's no learned
signal to share. It reframes NeuralMind from "another code-graph MCP" to **"the
one that gives your team's agents shared, earned intuition."**

## How it works

- **`neuralmind memory publish`** exports the union of your `personal` + `shared`
  learned memory (MAX-merged, strongest associations first) to a committed file
  at the repo root: **`.neuralmind-team-memory.json`**. It's beside `.gitignore`,
  *not* inside the per-machine `.neuralmind/` state dir, so it commits and travels
  with `git clone` — no `.gitignore` gymnastics.
- **Auto-inherit, once.** On a teammate's next `SessionStart` (Claude Code) or
  `neuralmind build` (Cursor / Cline / generic MCP), the committed bundle is
  imported **once** into the `shared` namespace. It's gated by the bundle's
  **content hash** (recorded in the synapse store's `meta` table), so it never
  re-imports the same bundle.
- **Transparent in recall.** The `shared` namespace already blends into retrieval
  at 0.5× via the v0.24 merged-read weighting — inherited associations surface
  co-edited modules a cold, purely-textual search would rank lower, without any
  new tool call.

### Per-agent expectations

| Agent | What changes in v0.30.0 |
|-------|--------------------------|
| **Claude Code** | The `SessionStart` hook inherits a committed team bundle once into `shared`. New `neuralmind memory publish` to share your own. |
| **Cursor / Cline / generic MCP** | `neuralmind build` inherits the committed bundle (prints a one-line `+N shared synapses` notice). |
| **All** | Recall is seeded with the team's associations on day one; no manual step, no network. |

## Safe by construction

- **Off-switch:** `NEURALMIND_TEAM_MEMORY=0` disables auto-import entirely.
- **`shared`-only:** inheritance only ever writes the `shared` namespace — a
  teammate's `personal` and `branch:<name>` memory is never touched.
- **MAX-merge + decay:** an import can only *raise* the weight of pairs it
  asserts (never double-counts), and the `shared` namespace decays, so a stale or
  over-eager bundle can't permanently distort recall. `neuralmind memory reset
  --namespace shared` clears it.
- **Fail-open:** a missing/corrupt/newer-version bundle is a silent no-op — it
  never breaks a session or a build.
- **Private by design:** the bundle is association *pairs* (node ids) + weights —
  **no source code, no prose** — and it travels via git, 100% local, no server.

## Measuring the value

The lift is real and measurable: `neuralmind eval --onboarding` reports the
top-k retrieval improvement a cold agent gets from inherited memory (the v0.20
onboarding-lift eval). Publish a bundle, run the eval on a fresh clone, and the
number is the day-one head start your team's agents inherit.

## What ships

- **`neuralmind/team_memory.py`** — `publish_team_memory`, `maybe_import_team_memory`,
  `build_team_bundle`, content-hash idempotency, committed-path convention.
- **`neuralmind memory publish`** CLI command.
- **Auto-inherit** wired into the `SessionStart` hook and `neuralmind build`.
- **`NEURALMIND_TEAM_MEMORY`** env var (off-switch).
- Public API exported from `neuralmind` (`publish_team_memory`, …).
- Tests: `tests/test_team_memory.py` (publish/inherit roundtrip, `shared`-only,
  idempotency, off-switch, fail-open).
- PRD: `docs/prd/team-memory.md`.

## Upgrade

```bash
pip install --upgrade neuralmind
```

No migration. Nothing changes until a project commits a
`.neuralmind-team-memory.json` (via `neuralmind memory publish`). The raw
`neuralmind memory export`/`import` commands still work for ad-hoc bundles.
