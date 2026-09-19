# NeuralMind v3.7.0 — a project registry for multi-project operator mode

**Release Date:** 2026-08-30

## Summary

NeuralMind isolates per-project by default (`.neuralmind/` is scoped to
each repo), but an operator running it across several projects had no
central record of which projects exist or their state. `neuralmind/project_registry.py`
adds that registry. Alongside it, Team-tier licensing gained a
`license expiring` warning so renewals stop lapsing silently, and several
bug fixes landed in the multi-scope build path.

## What's new

- **Project registry** (`neuralmind/project_registry.py`) — a central
  record of projects an operator has built, for multi-project operator
  mode. See [`docs/wiki/Multi-Project-Scoping.md`](../wiki/Multi-Project-Scoping.md)
  for the scoping rules this registry sits alongside (NeuralMind isolates
  automatically per-project; the registry is bookkeeping on top of that,
  not a change to isolation).
- **tier2:** `license expiring` — a renewal-window warning so a Team-tier
  license doesn't lapse without anyone noticing. See the
  [Billing Runbook](../wiki/Billing-Runbook.md) for the operator-facing
  process this ties into.

## Fixes

- **operator:** incremental recovery when the index and the graph fall out
  of sync, with progress reporting and an enhanced `doctor` check.
- Per-scope SQLite store naming (`store.code.sqlite`, `store.content.sqlite`,
  `store.docs.sqlite`) — prevents cross-scope contamination when a single
  project runs multiple content types side by side.
- `cmd_build` now normalizes an invalid `--scope` value to `all` instead of
  failing.
- **tier2:** licenses now bill and expire on the calendar, not by
  30-day months — a license bought on the 31st no longer drifts.
- **tier2:** corrected the renewal window and a runbook step that could not
  actually run as documented.
- **cli:** the renewal-report header string is now correctly parenthesized.
- Corrected the cron recipe, an activation error message, and the exit-7
  help text (all three had drifted from actual behavior).
- **tier1:** updated a migration-warning assertion to match current wording.

## What the agent sees post-install

No new MCP tools or hooks. For an operator running NeuralMind across
multiple projects, `neuralmind` now tracks a project registry alongside
each project's own isolated `.neuralmind/` state — see
[Multi-Project-Scoping.md](../wiki/Multi-Project-Scoping.md) for how that
interacts with other tools that don't isolate (memU, Hermes memory,
session_search).
