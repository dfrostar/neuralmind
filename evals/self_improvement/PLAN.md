# Self-improvement engine — plan

Status: proposed. Sequencing: subsystems A and B first (~2–3 days),
then closed-loop tuning (subsystem C) once `evals/faithfulness/` lands.

## Goal

NeuralMind already learns associations via the Hebbian synapse layer
(`neuralmind/synapses.py`). That tunes *which nodes are co-active*. It
does **not** tune:

- **what gets surfaced at query time** — the L2 recall set size, the
  L3 escalation threshold, the synapse spread-activation params.
- **the quality of stored summaries** — the L2 community summaries in
  ChromaDB, which are the only LLM-generated text in the index and
  the only thing where regeneration is meaningful.

This document specifies an outer loop that uses observed agent behavior
to tune both, plus the closed-loop variant that uses the faithfulness
eval as a fitness function.

## What we are NOT doing

- Regenerating L0 / L1. They are computed on-the-fly from project
  metadata (CLAUDE.md, README.md, mempalace.yaml) and graph stats —
  there's nothing stored to refine. (See `context_selector.py:230-308`.)
- Replacing the Hebbian synapse store. This sits on top.
- Anything that requires the agent to give explicit feedback. The
  signal must be implicit (which tools were used, did the agent
  re-query, did escalation happen).
- Touching the README or producing marketing material.

## Available signals

From the existing MCP tools (`mcp_server.py`):

- `neuralmind_wakeup` was called with project hash H at time T.
- `neuralmind_query` was called with query Q, returned `layers_used`
  (e.g. `["L0", "L1", "L2"]` or `["L0", "L1", "L2", "L3"]`), recall
  set R (the node IDs surfaced), session S.
- Within a session, queries Q1, Q2, … and which nodes overlapped.
- PostToolUse hook fires on these — we can log without changing tool
  behavior.

Derived signals:

- **L3 escalation rate per query type.** If a class of queries always
  escalates to L3, L2 is under-recalling for that class.
- **Re-query rate.** Two queries in the same session whose recall sets
  overlap by ≥50% suggests the first query under-disclosed.
- **Wakeup-only sessions.** If `neuralmind_wakeup` is called and no
  `neuralmind_query` follows within the session, L0/L1 was
  sufficient — this is the *positive* signal.
- **Per-community escalation rate.** Queries that touch community C
  and escalate to L3 → C's summary is inadequate for that query type.

## Architecture

One new SQLite table next to the existing synapse store, one new
module per subsystem, no changes to the public MCP surface.

### Storage: `query_events` table

Lives in the existing synapse DB at `<project>/.neuralmind/synapses.db`
to share the connection / WAL setup. Schema (added via
`CREATE TABLE IF NOT EXISTS`, no migration framework needed yet):

```sql
CREATE TABLE IF NOT EXISTS query_events (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  ts           REAL NOT NULL,             -- unix timestamp
  session_id   TEXT NOT NULL,             -- Claude Code session id
  tool         TEXT NOT NULL,             -- 'wakeup' | 'query'
  query_hash   TEXT,                      -- sha1(query text), null for wakeup
  query_text   TEXT,                      -- truncated to 512 chars, null for wakeup
  layers_used  TEXT,                      -- JSON array, e.g. '["L0","L1","L2"]'
  recall_nodes TEXT,                      -- JSON array of node ids
  community_id TEXT,                      -- primary community touched, if any
  escalated_l3 INTEGER NOT NULL DEFAULT 0 -- 1 if L3 was used
);
CREATE INDEX IF NOT EXISTS idx_query_events_session ON query_events(session_id, ts);
CREATE INDEX IF NOT EXISTS idx_query_events_community ON query_events(community_id);
```

Retention: cap at 50k rows per project, prune oldest on insert past
threshold (cheap, no separate cron).

Writer: `neuralmind/query_log.py` (new). Single function
`record_query_event(...)` — opens the existing synapse DB, inserts,
commits. Stdlib-only, parallels `synapses.py` style.

### Hook point

`hooks.py` already registers PostToolUse hooks. Add one for
`neuralmind_query` and `neuralmind_wakeup` that calls
`record_query_event`. The tool's response already contains
`layers_used` and the node ids — no change to the tool body required.

This keeps query logging entirely in the hook layer, so users who
disable hooks (`NEURALMIND_QUERY_LOG=0`) lose self-improvement but
retain core behavior.

## Subsystem A: selector auto-tuning

Module: `neuralmind/selector_tuning.py` (new). Read-side; no LLM calls.

### What it tunes

Two scalars per project, persisted in the existing `meta` table of
the synapse DB:

- `l2_recall_k` — how many community summaries to include in L2
  (currently a hard-coded constant in `context_selector.py`).
- `l3_escalation_threshold` — score below which we escalate to L3
  deep search.

### Tuning rule (deliberately simple)

Run once per session-end (hook into SessionEnd or recompute at
SessionStart from accumulated `query_events`):

```
window = last 200 query_events
if rate(escalated_l3) > 0.4:
    l3_escalation_threshold *= 0.95   # escalate more eagerly
    l2_recall_k = min(l2_recall_k + 1, 12)
elif rate(escalated_l3) < 0.1 and rate(re_query) < 0.05:
    l3_escalation_threshold *= 1.05   # tighten
    l2_recall_k = max(l2_recall_k - 1, 3)
```

Bounded, hysteretic, cheap. Nothing fancy until subsystem C exists to
score it.

### Warm-up

Tuner refuses to act until `query_events` has ≥50 rows. Until then,
hard-coded defaults stand.

### Toggle

`NEURALMIND_SELECTOR_AUTOTUNE=1` (default off until we've observed it
on real traffic for a week).

### Read path integration

`context_selector.py` reads `l2_recall_k` and `l3_escalation_threshold`
from the meta table at construction time. One read per `get_context`
call is fine; the values change at most once per session.

## Subsystem B: L2 summary refinement

Module: `neuralmind/summary_refiner.py` (new). Write-side; LLM cost.

### Trigger

A community C is enqueued for refinement when, over the last 200
`query_events` touching C:

- escalation-to-L3 rate ≥ 0.5, AND
- ≥ 10 events touched C (avoid refining on tiny samples).

### Refinement

1. Pull the current community summary from ChromaDB (via
   `embedder.get_community_summary()` at `embedder.py:360-408`).
2. Pull the top-N node bodies that recent L3 escalations actually
   surfaced for queries touching C — these are what the agent
   *needed* but didn't get from the summary.
3. Prompt: re-summarize C such that the surfaced bodies' key
   properties are recoverable from the summary. Same model used for
   the original summarization pass (so cost/format match).
4. **A/B promote, don't replace.** Write the new summary as
   `summary_candidate` in ChromaDB metadata alongside the existing
   `summary`. Tag with `candidate_since_ts`.
5. After 50 more events touching C, compare L3 escalation rate when
   the candidate was used vs. baseline. If candidate's rate is
   lower, promote (overwrite `summary`, drop candidate). If not,
   discard the candidate and add a cool-down on C to avoid
   thrashing.

### Where it runs

Refinement is *not* on the hot path. Two options:

- **Watcher hook** — `FileActivityWatcher` already has a debounce
  loop (`watcher.py:88-100`). Piggyback: after the file activity
  flush, drain a small refinement queue (≤1 community per flush).
  Pro: no new process. Con: refinement only happens when there's
  also file activity.
- **CLI subcommand** — `neuralmind refine` runs a bounded pass;
  user or cron triggers it. Pro: deterministic. Con: needs scheduling.

D2 builds the watcher hook variant first; CLI subcommand is a small
addition on top.

### Toggle

`NEURALMIND_REFINE_SUMMARIES=0` by default. Refinement does an LLM
call per community; users should opt in explicitly.

### Failure modes

- LLM call fails → log, leave existing summary, retry next eligible
  trigger. Don't block the watcher.
- ChromaDB upsert fails → roll back the candidate write, keep the
  existing summary intact.
- A/B verdict noisy on low-traffic communities → require ≥50
  candidate-served events before deciding; until then, both stay.

## Subsystem C: closed-loop eval-driven tuning (later)

Depends on `evals/faithfulness/` shipping (see
`evals/faithfulness/PLAN.md`).

A nightly job:

1. Snapshot current `(l2_recall_k, l3_escalation_threshold,
   synapse decay rate, recall threshold)` as the baseline.
2. Sweep small perturbations (one or two params at a time, 3-point
   grid).
3. Re-run the faithfulness eval against the cached question set.
4. Promote the perturbation that improves the
   correctness-vs-tokens frontier; otherwise revert.

Out of scope for this plan beyond noting the integration points.
Subsystems A and B are designed to read their tunables from the meta
table, so subsystem C can write to the same place without touching
A or B's code.

## Configuration surface

| Env var                          | Default | What it controls                    |
| -------------------------------- | ------- | ----------------------------------- |
| `NEURALMIND_QUERY_LOG`           | `1`     | Record `query_events` at all       |
| `NEURALMIND_SELECTOR_AUTOTUNE`   | `0`     | Subsystem A active                  |
| `NEURALMIND_REFINE_SUMMARIES`    | `0`     | Subsystem B active                  |
| `NEURALMIND_QUERY_LOG_RETENTION` | `50000` | Max rows in `query_events`          |

Goal: ship the logging on by default, tuning behaviors gated.

## Observability

A small `neuralmind self-improve status` CLI subcommand prints:

- query_events row count, oldest / newest timestamps
- current `l2_recall_k`, `l3_escalation_threshold`
- recent L3 escalation rate, re-query rate
- pending refinement candidates and their A/B status

Read-only. Useful for debugging and for the eventual subsystem C
diagnosis.

## Test strategy

Tests are stdlib-only, like `tests/synapse_*` — don't drag in the
full dep set.

- `tests/test_query_log.py` — schema creation, insert, retention
  trim, JSON round-trip.
- `tests/test_selector_tuning.py` — synthetic event streams,
  assert tuning rule produces expected scalar movement.
- `tests/test_summary_refiner_logic.py` — mock the LLM call and
  ChromaDB; assert candidate is written, A/B promotion logic
  fires correctly, cool-down respected.

Integration test on the bundled sample fixture
(`neuralmind/demo_data/sample_project/`): run a synthetic session of
queries, verify a `query_events` row count of N, verify autotune
moves scalars in the expected direction.

## D1 deliverable (detailed)

In one branch, `claude/self-improvement-d1` (forked from
`claude/plan-next-task-nwJak` once we start coding):

1. **`neuralmind/query_log.py`** — `init_schema(conn)`,
   `record_query_event(...)`, `recent_events(window)`,
   `prune_to(retention)`. Reuses `synapses.default_db_path()` and
   the same connection-open helper.
2. **Schema bootstrap** — call `init_schema` from
   `synapses.SynapseStore.__init__` so a single open creates both
   sets of tables. No separate migration.
3. **Hook integration** — extend `hooks.py` PostToolUse handlers to
   record an event after `neuralmind_query` and `neuralmind_wakeup`.
   Read `tool_response.layers_used`, recall node ids, and escalation
   flag. Gate behind `NEURALMIND_QUERY_LOG`.
4. **Tests** — `tests/test_query_log.py` covering insert, JSON
   columns, retention trim, idempotent schema creation.
5. **No behavior change** for users with the env var unset
   (default is on, but the table is just inert append).

D1 ships nothing user-visible — purely the data layer that A, B, C
all depend on. This is intentional: gives us a logging substrate to
start collecting signal *while* we build A and B.

## D2 / D3 (sketch only)

- **D2:** subsystem A — `selector_tuning.py`, meta-table reads from
  `context_selector.py`, tests, `neuralmind self-improve status`
  subcommand stub.
- **D3:** subsystem B — `summary_refiner.py`, watcher hook,
  candidate/A-B logic, mocked LLM tests. Refinement disabled by
  default.

## Risks / open decisions

- **Privacy.** `query_text` is stored truncated; do we even need it?
  D1 stores it; we can drop the column in a follow-up if we decide
  `query_hash` is sufficient. Decision deferred to D2 when we see
  what tuning actually needs.
- **DB contention.** Synapse store already takes the lock for
  Hebbian writes; query event writes are short and append-only, so
  contention should be negligible, but worth measuring on D1.
- **Project relocation.** The DB lives under `<project>/.neuralmind/`
  — moving the project moves the history. Acceptable for now.
- **Multi-machine sync.** Out of scope. Self-improvement is
  per-checkout. If we want shared learning across a team later,
  that's a separate design.
