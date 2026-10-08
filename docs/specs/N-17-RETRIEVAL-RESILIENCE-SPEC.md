# N-17 Retrieval Resilience — Fail-Loud Index Health, Self-Healing Recovery, and Watch Instance Safety

**Status:** DRAFT for review
**Date:** 2026-10-08
**Baseline:** v4.11.0 (`main` @ `ed66521`). Every `file:line` below was checked against that commit.
**Scope:** the retrieval read path (`search`, `query`, MCP tools), the turbovec index lifecycle, `doctor`, `build`, and `watch` process management.
**Companions:** none yet. Relates to `PERFORMANCE-FUTURE-PROOFING-SPEC.md` §5 (daemon/latency) and `RETRIEVAL-BENCHMARK-SPEC.md` (retrieval *quality*).

> **Scope note.** This spec covers retrieval **availability and truthfulness**. It does not cover retrieval *quality* (ranking, nDCG, relevance grading) — that is N-15's domain.

---

## 1. Summary

NeuralMind can be simultaneously **"healthy" by every surface it exposes** and **returning zero results for every query**. The failure is silent in three independent places:

| Layer | What it reports | Reality |
|---|---|---|
| `search` / `query` | `[]` with exit code 0 | index unavailable |
| `build` | `Build successful!` | index still unusable |
| `doctor` | `[FAIL] Index quarantined` | may be a false positive on a *working* index |

An agent (or a human) that trusts any of these gets a confident wrong answer: "the codebase does not contain that symbol." That is worse than an error, because it is indistinguishable from a true negative.

This spec specifies the fixes as **five product-level requirements** that hold regardless of how the index became unusable: version mismatch, corruption, partial write, empty store, or missing directory.

---

## 2. Background — the turbovec index lifecycle

The vector index is a turbovec `.tvim` file (`IdMapIndex`) alongside a SQLite row store:

```
<project>/.neuralmind/neuralmind_turbovec/
  index.code.tvim        <- the vector index (binary, version-stamped)
  store.code.sqlite      <- nodes table: uid, node_id, document, ...  (source of truth)
  bm25_index.code.json   <- lexical index
  index.code.tvim.stale  <- quarantine backup, written when load fails
```

`turbovec.IdMapIndex.load()` raises `ValueError`/`OSError` when the on-disk stamp is incompatible with the installed `turbovec`. The current handler in `neuralmind/turbovec_backend.py:443-461` catches that, renames the file to `<name>.stale`, and attempts recovery via `_rebuild_index_from_store()`.

That recovery logic is **sound**. The defects are in how the result of a failed/absent index is *communicated* and *retriggered*.

### 2.1 Evidence base

All findings below were reproduced on the baseline commit against a real 5,780-node project index.

| # | Finding | Evidence |
|---|---|---|
| F1 | Retrieval returns empty silently | `neuralmind search <proj> "score_predictions"` → `[]`, exit 0, no stderr. After repair, same command returns 5 ranked hits (0.70…0.64). |
| F2 | `build` reports success while index is quarantined | `neuralmind build <proj> --scope code` → `Build successful! … Delta: +3 new, =4,471 skipped`. Index still quarantined; `search` still `[]`. |
| F3 | `doctor` quarantine check is a file-existence test | `neuralmind/doctor.py:470` — `if stale_path.exists(): return <FAIL>`. No load attempt, no liveness check. Persists as FAIL after the index is repaired and working. |
| F4 | `watch` has no single-instance guard | Two `watch --reindex` processes ran against the same project concurrently for ~24h (one in `D` state, 1.7 GB RSS). A `flock` helper already exists at `neuralmind/metrics_pipeline.py:44-66` (`_lock_file`/`_unlock_file`); `watch` does not use it. |
| F5 | Recovery requires knowing an undocumented flag | `--rebuild-index` (`cli.py:6346`, implies `force` at `cli.py:675`) is the only path that re-embeds; a plain `build` skips unchanged nodes by design and therefore never repairs a quarantined index. |
| F6 | Read path has no index-health preflight | `neuralmind/cli.py:2059-2069` (`cmd_search`) calls `mind.search()` and prints whatever comes back, including `[]`. |

**F2 and F3 are the load-bearing defects.** F2 produces a false success on the write path; F3 produces a false failure on the diagnostic path. Together they make the true state of the index unknowable from the CLI.

---

## 3. Requirements

### R1 — Retrieval must fail loud, never empty

**R1.1** `search` and `query` must never print an empty result set as if it were a successful search when the vector index is unavailable, quarantined, or empty.

**R1.2** When results are empty, the tool must distinguish two cases, and say which:

| Case | Meaning | Required behaviour |
|---|---|---|
| No matches | index healthy, query genuinely has no hits | report "no matches" + the fact that the index was consulted |
| Index unavailable | index missing/quarantined/empty | report an **error** naming the state and the repair command; non-zero exit |

**R1.3** The distinction must be machine-readable, not only human-readable. `--json` output must carry an explicit status so an agent cannot mistake one case for the other:

```json
{ "status": "ok",      "results": [ ... ] }
{ "status": "no_matches", "results": [], "index_available": true }
{ "status": "index_unavailable", "results": [], "index_available": false,
  "reason": "quarantined", "repair": "neuralmind build <path> --rebuild-index" }
```

**R1.4** Backwards compatibility: the `--json` payload must keep returning a top-level array when `status == "ok"`, **or** the change must be versioned behind a flag. Consumers exist (hooks, MCP, `savings`). Prefer a `--json-v2` opt-in for the envelope and keep the bare array as default, so no existing caller breaks.

**R1.5** Exit codes: `0` = ok or genuine no-matches; non-zero = index unavailable. A script that greps for results must be able to detect the failure without parsing prose.

### R2 — `build` must not report success on an unusable index

**R2.1** `build` must verify the index is loadable **after** writing it, before printing any success line. A build that leaves a quarantined index must not print `Build successful!`.

**R2.2** When a build detects a quarantined index, it must **self-heal** rather than requiring the operator to know `--rebuild-index`: escalate automatically to the store-backed rebuild (`_rebuild_index_from_store`), and only fall back to a full re-embed if that returns 0.

**R2.3** The `Delta` line must not imply success when the index was not repaired. `=N skipped` with a quarantined index is a **failure to repair**, not an optimisation. Report it as such:

```
Build incomplete!
  Nodes: 4474
  Vector index: QUARANTINED — recovery from store failed
  Run: neuralmind build <path> --rebuild-index
```

**R2.4** `--rebuild-index` remains available for explicit operator use, but is no longer *required* for recovery.

### R3 — Index health is a state machine, and `doctor` reports it truthfully

**R3.1** Replace the `.stale`-existence test with an actual load attempt. The states are:

| State | Detection | `doctor` verdict |
|---|---|---|
| `missing` | index file absent | FAIL — "no index; run build" |
| `healthy` | loads successfully | ok |
| `quarantined_unrecovered` | load fails and no store rebuild possible | FAIL — actionable |
| `recovered` | loads successfully **and** a `.stale` backup exists | **ok** (with an advisory note) |

**R3.2** `recovered` must report **ok**, not FAIL. The presence of a `.stale` file is *evidence of a past incident*, not a current fault. Report it as an advisory line so the history is visible without failing the check:

```
[ ok ] Turbovec compatibility: index loads (1 stale backup present, from a repaired mismatch)
```

**R3.3** `doctor` must attempt the load, so its verdict cannot drift from what `search` will experience. A cheap `IdMapIndex.load()` is acceptable; `doctor` is not on a hot path.

**R3.4** `doctor`'s overall `Setup incomplete` summary must be driven by the state machine, not by the count of advisory lines.

### R4 — One watcher per project, enforced

**R4.1** `watch` must take an exclusive, per-project lock on startup and exit cleanly (code 0, one clear line) if another instance holds it:

```
neuralmind watch: another watcher already holds /home/.../.neuralmind/watch.lock (pid 1234) — exiting
```

**R4.2** Reuse the existing flock helper (`neuralmind/metrics_pipeline.py:44-66`, `_lock_file`/`_unlock_file`) rather than adding a second locking idiom. POSIX `flock(LOCK_EX|LOCK_NB)`; on Windows fall back to the byte-0 lock already implemented there.

**R4.3** The lock must be per-project (keyed on the resolved project path), not global — multiple projects legitimately run one watcher each.

**R4.4** Stale locks must not deadlock: a lock whose holder PID is gone must be reclaimable without manual cleanup. `flock` gives this for free (the lock dies with the process); the byte-0 fallback needs an explicit liveness check.

**R4.5** The systemd unit must not `Restart=always` a second instance into a hot loop. Combined with R4.1 the unit should observe a clean exit and stay stopped.

### R5 — Format-version preflight with an idempotent migration

**R5.1** Detect an incompatible index **before** the slow path, and name the cause:

```
Vector index format mismatch.
  On-disk: written by turbovec <X>
  Installed: turbovec <Y>
Recovery: automatic store-backed rebuild (fast). Full re-embed only if that fails.
```

**R5.2** Expose an idempotent, safe-to-rerun migration entry point so upgrade tooling can call it non-interactively:

```bash
neuralmind migrate-index <project>    # exit 0 if already healthy (no-op)
```

**R5.3** `neuralmind doctor` must surface a version mismatch as its own finding, distinct from generic quarantine, so operators can tell "my toolchain moved" from "the file is corrupt".

---

## 4. Non-requirements / out of scope

- **Retrieval ranking quality.** nDCG/MRR/relevance grading is N-15.
- **Changing the turbovec format or versioning scheme.** Upstream concern; we adapt.
- **Cross-repo / federated indexes.** Explicitly not a NeuralMind capability.
- **Daemon/MCP latency.** `PERFORMANCE-FUTURE-PROOFING-SPEC.md` §5.
- **The `--project-path` vs positional-argument inconsistency** across subcommands. Real, but a separate CLI-consistency ticket.

---

## 5. Acceptance criteria

Each is testable without a human in the loop.

| ID | Criterion |
|---|---|
| AC1 | With a quarantined index, `search` exits non-zero and names the repair command. With a healthy index and an unmatched query, `search` exits 0 and reports no-matches. |
| AC2 | `search --json` distinguishes the three statuses of R1.3; the default `--json` payload remains a bare array (R1.4). |
| AC3 | `build` on a quarantined index either repairs it or exits non-zero. It never prints `Build successful!` while the index remains unloadable. |
| AC4 | A plain `build` (no `--rebuild-index`) repairs a quarantined index by escalating automatically. |
| AC5 | `doctor` returns **ok** for the `recovered` state, with the stale backup noted as advisory. |
| AC6 | `doctor` returns FAIL for `missing` and `quarantined_unrecovered`, and the message is different for each. |
| AC7 | `doctor`'s verdict matches a subsequent `search` on the same index (no drift between the two). |
| AC8 | A second `watch` on the same project exits 0 within 2s with one clear message; the first is unaffected. |
| AC9 | Two `watch` processes on **different** projects both run (lock is per-project). |
| AC10 | Killing a watcher with `SIGKILL` leaves a reclaimable lock; a new watcher starts without manual cleanup. |
| AC11 | `migrate-index` on a healthy project exits 0 and changes nothing (idempotent). |
| AC12 | The full sequence — quarantine a healthy index, run `build`, run `search` — recovers without any `--rebuild-index` flag and without a manual `.stale` cleanup. |

---

## 6. Test plan

**Unit**
- State-machine transitions for R3.1: table-driven over `{index file present/absent} × {load ok/fails} × {.stale present/absent}` → expected state.
- `search` status derivation for R1.2/R1.3, including the empty-store case.
- Lock acquisition/release/reclaim for R4, including the `SIGKILL` path (AC10).

**Integration (fixture project)**
- Quarantine a valid index by stamping a wrong version → assert AC1, AC3, AC5, AC12.
- Delete the index file → assert AC6 (`missing`).
- Corrupt the index body (truncate) → assert `quarantined_unrecovered` and a distinct message.
- Two watchers, same project → AC8; two projects → AC9.

**Regression guards**
- `--json` default payload shape unchanged (R1.4) — this is the one that can silently break the hooks and MCP layer. Assert the bare-array shape explicitly.
- `savings` / `benchmark` still parse query results after the status field is added.
- An existing healthy project's `query` output is byte-identical before/after the change.

**Manual verification on a real corpus**
- Run the AC12 sequence against a large index (>5,000 nodes) and confirm the automatic escalation path completes without a full re-embed. Measure and record the wall time; the store-backed rebuild should be far cheaper than re-embedding.

---

## 7. Delivery

Suggested split, each independently mergeable and testable:

| PR | Contents | Requirements |
|---|---|---|
| 1 | Index-health state machine + truthful `doctor` | R3, AC5–AC7 |
| 2 | Fail-loud retrieval + status envelope | R1, AC1–AC2 |
| 3 | Self-healing `build` + truthful success line | R2, AC3–AC4, AC12 |
| 4 | Watch single-instance lock | R4, AC8–AC10 |
| 5 | Version preflight + `migrate-index` | R5, AC11 |

PR 1 first: it is the smallest, it is pure diagnosis, and PRs 2–3 read its state machine. PR 4 is fully independent and can land any time.

**Migration note.** PR 2 changes a CLI contract. It is additive by default (R1.4), so no downstream change is required — but the hooks and MCP layer should be audited for code that treats `[]` as "no results" and would now need to handle `index_unavailable`.

---

## 8. Why this matters beyond one project

Every defect here is a **silent-wrong-answer** class bug, which is the worst failure mode for a tool whose entire value proposition is "an agent can trust what I return."

The generalisable lessons:

1. **A tool that can return empty must distinguish "nothing" from "I couldn't look."** These are different answers and callers act on them differently.
2. **A write path must verify its own output.** `Build successful!` printed after a skipped, unrepaired index is a lie that costs hours of downstream debugging.
3. **A diagnostic must test the live thing, not a proxy for it.** `stale_path.exists()` is a proxy for "was quarantined once," not "is broken now."
4. **Long-running processes need mutual exclusion by default.** The locking primitive already existed in the codebase; it simply wasn't applied.
