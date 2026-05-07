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

We do **not** need a new SQLite table — `neuralmind/memory.py` already
exists and handles per-project + global JSONL event logging behind an
opt-in consent sentinel. `core.NeuralMind.query()` already calls
`log_query_event()` at `core.py:283`. D1 extends that substrate
rather than duplicating it.

### Existing substrate (already in tree)

`neuralmind/memory.py` provides:

- `is_memory_logging_enabled()` — gates everything on the consent
  sentinel at `~/.neuralmind/memory_consent.json`.
- `log_query_event(project_path, question, result)` — appends a JSON
  line per query to both `<project>/.neuralmind/memory/query_events.jsonl`
  and `~/.neuralmind/memory/query_events.jsonl`. Captures
  `layers_used`, `communities_loaded`, `search_hits`, `tokens`,
  `reduction_ratio`, `timestamp`, `query`.
- `read_query_events(path)` — reads back the JSONL.

This satisfies most of subsystem A and B's data needs. The privacy
story (opt-in consent, local-first, JSONL on disk) is also already
designed and tested.

### What D1 adds

Four small gaps:

1. **Wakeup logging.** `core.NeuralMind.wakeup()` does not currently
   log. Add `log_wakeup_event(project_path, result, session_id)` and
   call it from `wakeup()`. Critical for the "L0/L1 was sufficient"
   positive signal — without wakeup events, we can't tell whether
   the agent woke up and stopped (good) or woke up and immediately
   queried (under-disclosure).

2. **`session_id` on events.** Both `query` and `wakeup` events need
   a session id so we can compute *intra-session* signals (re-query
   rate, wakeup-without-followup). Source order:
   - `CLAUDE_SESSION_ID` env var if set,
   - else a process-lifetime uuid generated lazily (one per
     `NeuralMind` instance).

3. **Derived `escalated_l3` flag.** Trivially `"L3" in layers_used`,
   but surface as a helper so subsystem A reads through one
   function rather than re-implementing the predicate.

4. **Aggregation helpers in `memory.py`.** Subsystem A's tuning rule
   needs:
   - `recent_events(path, *, since=None, window=None) -> list[dict]`
   - `escalation_rate(events) -> float`
   - `re_query_rate(events) -> float`
   - `wakeup_only_rate(events) -> float`

   Each is short (a few lines). They're the read-side primitives;
   subsystem A is the only consumer. Keeping them in `memory.py`
   (not a new module) so future readers find aggregation logic next
   to the storage that produces it.

### Tunables storage (subsystem A, later)

`l2_recall_k` and `l3_escalation_threshold` will live in the
existing `meta` table of `synapses.db` — that's already a
key-value scratchpad and avoids introducing a third storage
location. Subsystem C, when it lands, writes there too. (D1 does
not touch the meta table.)

### Why not hooks

The plan's earlier draft proposed PostToolUse hooks on
`neuralmind_query` / `neuralmind_wakeup`. In-process logging from
`core.py` is strictly better:
- The data is already structured (`ContextResult` object), no JSON
  re-parsing.
- `core.query()` already calls `log_query_event` — the substrate is
  in-process.
- Hooks would only fire when the user has Claude Code's hooks
  installed; in-process logging works for any caller (CLI, MCP,
  programmatic).

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

Developed on `claude/plan-next-task-nwJak`. Extends the existing
`memory.py` substrate; no new modules, no new storage backend.

1. **Add `log_wakeup_event` to `memory.py`.** Same JSONL file as
   query events, `event_type: "wakeup"`. Captures
   `layers_used`, `tokens`, `timestamp`, `session_id`,
   `project_path`. No `query` field.

2. **Add `session_id` to `log_query_event` and `log_wakeup_event`.**
   Resolution: `CLAUDE_SESSION_ID` env var, else a lazy
   process-lifetime uuid via `_current_session_id()`. Add the field
   to events emitted by both functions.

3. **Wire `core.NeuralMind.wakeup()` to call `log_wakeup_event`.**
   One line, mirrors the existing `log_query_event` call in
   `query()`.

4. **Aggregation helpers** in `memory.py`:
   - `recent_events(events, *, since_ts=None, last_n=None)`
   - `escalation_rate(events)` — fraction with `"L3"` in
     `layers_used` (query events only).
   - `re_query_rate(events)` — fraction of query events with ≥50%
     `communities_loaded` overlap with the previous query in the
     same session.
   - `wakeup_only_rate(events)` — fraction of sessions whose only
     events are wakeups (no queries).

5. **Tests** in `tests/test_memory.py` (or a sibling
   `tests/test_memory_aggregations.py` to keep file size sane):
   - `log_wakeup_event` writes to both project and global JSONL.
   - `session_id` is included on both event types.
   - `session_id` honors `CLAUDE_SESSION_ID` when set, falls back
     to a stable process-lifetime uuid otherwise.
   - Each aggregation helper on hand-built event streams.
   - Existing `test_memory.py` cases still pass (no regression on
     `log_query_event` shape — just additive field).

6. **No behavior change** for users without consent. All logging
   already gated by `is_memory_logging_enabled()`.

D1 ships nothing user-visible — purely fills gaps in the data layer
that subsystems A and B will read.

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
