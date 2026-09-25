# Release Notes — NeuralMind v4.2.0

**Release Date:** 2026-09-18  
**License:** MIT  
**Compare:** [v4.1.0 → v4.2.0](https://github.com/dfrostar/neuralmind/compare/v4.1.0...v4.2.0)

---

## What's New

### PreToolUse Stale-Decision Guard

The Memory Layer (v4.1.0) stores decisions and invalidates them when code changes. v4.2.0 closes the loop **at edit time**: before your agent edits a file, a `PreToolUse` hook checks the decision store for any STALE or INVALIDATED decisions whose `files_affected` covers that file — and surfaces them into the agent's context *before the edit lands*.

```
[neuralmind stale-guard] 1 decision(s) governing neuralmind/db.py are no longer ACTIVE. Their rationale may not hold — verify before relying on them:
- [STALE] Use SQLite WAL (confidence 0.90, updated 2026-09-10): WAL mode required for concurrent readers...
```

This is the runtime counterpart of the eval harness's `stale_influence_rate` metric: instead of measuring how often stale memory steers edits, prevent it.

**Properties:**

- **Fail-open by design** — no store, guard error, or empty result produces no output; the edit proceeds normally
- **Never denies edits** — pure context injection; the agent and user decide what to do
- **Opt-out:** `NEURALMIND_STALE_GUARD=0`
- **Cap:** at most 5 decisions surfaced per edit, with a pointer to `neuralmind decisions audit`
- **Path normalization:** absolute hook paths resolved to repo-relative before matching

**Upgrade note:** ships with hook block v3. Existing installs pick up the new matcher automatically — re-run `neuralmind install-hooks` after upgrading.

### Fail-Open Visibility (carried from v4.1.x patch line)

All `except Exception: pass` blocks in `memory/` were replaced with logged failures (`bf59505`). Fail-open behavior is preserved — callers still get safe defaults — but failures are now visible in logs. A source-level regression test (`TestFailOpenLogging.test_no_silent_pass_in_memory_module`) fails CI if the pattern is reintroduced. This followed the discovery that a silent no-op in `DecisionStore.update()` (`066a48b`) had made every update a no-op.

## For the Agent (what changes in your session)

If you edit a file governed by decisions that are no longer ACTIVE, you'll see a `[neuralmind stale-guard]` context block before the edit. Treat surfaced decisions as warnings, not commands: verify the rationale still holds before relying on it. If the guard fires on a decision you know is fine, `neuralmind decisions restore <decision-id>` reactivates it.

## Documentation

- Wiki: [Memory Layer — Stale-Decision Guard](https://github.com/dfrostar/neuralmind/blob/main/docs/wiki/Memory-Layer.md#stale-decision-guard-v420)
- README: behavior toggles updated with `NEURALMIND_STALE_GUARD=0`

## Tests

- `tests/memory/test_stale_guard.py` — 14 new tests: context building (stale/invalidated/active/absolute-path/cap-at-5), hook registration, end-to-end `run_hook` with stdin payloads, env opt-out
- Memory suite total: 74 tests, all stdlib-only

---

**Full changelog:** [CHANGELOG.md](../CHANGELOG.md)
