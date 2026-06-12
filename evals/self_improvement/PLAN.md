# Self-improvement engine — plan

Status: **Phases 1–2 rebuilt on v0.25** (post-reranker-removal). D1 (memory
substrate) and D2 (subsystem A, the selector auto-tuner scoped to the L2 recall
depth) are landed against the current codebase. Phase 3 (subsystem C,
eval-driven closed-loop tuning) is future work — see the section at the bottom.

This is the original PR #100 (May 2026) design rebuilt on top of three changes
that landed since:

- **v0.11** — directional transitions (`synapse_transitions` table,
  `next_likely`). The rebuilt tuner is transition-aware (see the dampener).
- **v0.23** — retrieval traces (PRD 3). Unaffected here.
- **v0.24** — memory namespaces (PRD 4). Synapses/transitions/activations now
  carry a `namespace`; the `meta` table does **not** (it is namespace-free, one
  row per key for the whole store), so tuner state is global per project.
- **v0.25** — the `learned_patterns` reranker was retired
  (`build_cooccurrence_index` / `write_learned_patterns` are gone from
  `memory.py`; `read_query_events` / `count_events` remain). The synapse layer
  is now the single learning signal. The original D2 plan referenced the
  reranker only obliquely; nothing in the rebuilt tuner depends on it.

## Goal

NeuralMind already learns associations via the Hebbian synapse layer
(`neuralmind/synapses.py`). That tunes *which nodes are co-active*. It does
**not** tune *what gets surfaced at query time* — the L2 recall set size, the
synapse spread params, the transition decay/prune knobs. This document
specifies an outer loop that uses observed agent behavior to tune the cheapest,
safest of those (L2 recall depth), plus the eval-driven variant (Phase 3) that
uses the faithfulness eval as a fitness function.

## What we are NOT doing

- Regenerating L0 / L1. Computed on-the-fly from project metadata + graph stats
  (`context_selector.py:243-321`) — nothing stored to refine.
- Replacing the Hebbian synapse store. This sits on top.
- Requiring explicit agent feedback. The signal is implicit (which layers were
  used, did the agent re-query, did it wake up and stop).
- An L3 escalation threshold. L3 deep search runs unconditionally per query
  (`context_selector.py:get_l3_search`); skipping it is net-new behavior with a
  correctness risk, deferred until `evals/faithfulness/` can validate it. So
  `escalation_rate` is logged but not yet a tuning driver — the tuner is driven
  by `re_query_rate` instead.
- Touching README / docs / SEO surfaces. This is an engineering doc only.

## D1 — logging substrate (landed)

`neuralmind/memory.py`, extended in place (no new module, no new storage):

- `_current_session_id()` — `CLAUDE_SESSION_ID` env var, else a lazy
  process-lifetime uuid. Both event types carry the resolved `session_id` so
  the intra-session signals can tell which events were truly consecutive.
- `log_query_event(..., session_id=None)` — now stamps `session_id`. Shape is
  otherwise unchanged (additive field), so pre-D1 logs still read.
- `log_wakeup_event(project_path, result, session_id=None)` — `event_type:
  "wakeup"`, same JSONL file + same consent gate. Wired from
  `core.NeuralMind.wakeup()` (mirrors the `log_query_event` call in `query()`).
- Read-side aggregation helpers (the read primitives subsystem A consumes):
  - `read_events(events_file)` — all events (query + wakeup), unfiltered.
  - `recent_events(events, *, since_ts=None, last_n=None)` — window slice.
  - `escalation_rate(events)` — fraction of query events whose `layers_used`
    includes the L3 layer (matched exactly as `"L3"` / `"L3:"` prefix, never a
    bare substring, so `"L30"` can't false-match).
  - `re_query_rate(events)` — fraction of consecutive same-session query pairs
    whose `communities_loaded` sets overlap ≥50% of the smaller set. Pairs with
    no community signal (denom 0) and events with no `session_id` are skipped.
  - `wakeup_only_rate(events)` — fraction of wakeup-bearing sessions that never
    issued a query (the positive "L0/L1 sufficed" signal).

D1 is purely additive and consent-gated; no behavior change for users without
the memory consent sentinel.

## D2 — subsystem A: selector auto-tuning (landed)

Module: `neuralmind/self_improve.py`. Read-side; no LLM calls. Tunes one scalar:

- **`l2_recall_k`** — how many community summaries L2 surfaces per query. It is
  the `community_budget` cap in `context_selector.py:get_l2_context`
  (`context_selector.py:359,384`), default `3`, clamped `[2, 6]`. The selector
  takes it as a constructor arg (`ContextSelector(..., l2_recall_k=...)`,
  `context_selector.py:118-133`) and clamps defensively on read.

### Tuning rule (deliberately simple, hysteretic, fail-open)

Runs once per session at SessionStart, recomputed from accumulated events:

```
queries = query events only        # wakeups carry no re_query signal
if len(queries) < 50:        hold   # warm-up gate
window  = queries since self_improve:l2_recall_k_tuned_at  (else last 200)
if len(window) < 20:         hold   # insufficient recent signal
rate    = re_query_rate(window)
margin  = transition_top1_margin(store, last recall seed in window)
if   rate > 0.40 and margin >= 0.70:  hold     # transition_dampened
elif rate > 0.40:  l2_recall_k = min(k + 1, 6) # under-disclosing → widen
elif rate < 0.15:  l2_recall_k = max(k - 1, 2) # over-disclosing → narrow
else:              hold                         # dead band
```

Single-step moves, hysteretic dead band, windowed signal, once-per-session
cadence. `tune_selector()` never raises (fail-open — safe for the hook path):
any exception returns defaults and never breaks a query.

### Transition-margin dampener (v0.11+ extension)

The rebuild is transition-aware. `transition_top1_margin(store, node_id)` reads
the top-1 outgoing transition probability from the synapse store's directional
graph (`SynapseStore.next_likely`, `synapses.py:747`). The tuner seeds it with
the most recent windowed query's last loaded community (the `community_<id>`
pseudo-node the synapse layer reinforces). When that margin is decisively high
(≥ `TRANSITION_MARGIN_HIGH` = 0.70), the agent already knows where it's going
next — widening L2 wouldn't reduce the re-query, just spend tokens — so an
otherwise-warranted *raise* is suppressed (`reason == "transition_dampened"`).
It never forces a move and never touches the lower / dead-band paths. A flat or
cold transition graph (margin 0.0) leaves the raise path untouched. This is the
single v0.11 extension; the full multi-surface tuner registry is **not** built.

### Storage

Tuner state lives in the synapse store's `meta` table (`synapses.py`,
`get_meta` / `set_meta`), which is **namespace-free** (one row per key for the
whole store), so the tuned recall depth is global per project regardless of the
active memory namespace. Keys are prefixed `self_improve:` so they can't
collide with the store's own `meta` keys (`schema_version`, `last_decay`):

- `self_improve:l2_recall_k` — the tuned scalar.
- `self_improve:l2_recall_k_tuned_at` — ISO timestamp of the last change, used
  both as a diagnostic and to window the tuning signal.

Windowing on `tuned_at` stops the tuner chasing a distribution it just
perturbed (raising `l2_recall_k` changes `communities_loaded`, which feeds
`re_query_rate` — a self-referential loop). The `< 20` window guard handles the
common post-tune case where the window is empty (no fresh events yet) — empty
means "no signal, hold", not "rate 0.0, lower it".

### Read-path integration (new in this rebuild)

The original D2 series *persisted* the value but never landed the consume side
(the original PLAN.md described it, but the commits stopped at the tuner +
hook + CLI). This rebuild wires it: `core.NeuralMind.build()` reads the
persisted value via `_tuned_l2_recall_k()` and passes it to the
`ContextSelector` constructor (`core.py`, the `ContextSelector(...)` call in
`build()`). Read **once at construction**, not per `get_query_context` — the
value changes at most once per session (the SessionStart tuner tick), so a
per-call DB read would be pure overhead.

### Toggle & default-off invariant

`NEURALMIND_SELECTOR_AUTOTUNE=1` (default off). Opt-in `== "1"` rather than the
`!= "0"` pattern used elsewhere, because this is net behavior change. Two
gates, both on the same flag:

- The SessionStart hook only runs `tune_selector()` when the flag is `1`
  (`hooks.py`, after the decay tick).
- `_tuned_l2_recall_k()` returns `None` (→ selector keeps its hard-coded
  default) unless the flag is `1`. So with the flag unset the hot path does
  **zero** extra I/O — no meta read at all — and behavior is byte-identical to
  a build without the engine.

### Observability

`neuralmind self-improve status [project] [--json]` (read-only) prints current
`l2_recall_k`, when it was last tuned, query-event counts + warm-up state,
windowed `re_query_rate`, and whether autotune is enabled. Nested under a
`self-improve` parser so Phase 3 can attach its own sub-actions.

## Tunable-surface survey (current code)

The knobs an outer loop *could* tune, with their current location. D2 tunes
only the first; the rest are surveyed for Phase 3 / future subsystems.

| Surface | Constant | File:line | Current value | Tuned by D2? |
| --- | --- | --- | --- | --- |
| L2 recall depth | `L2_RECALL_K_DEFAULT` (`l2_recall_k`) | `context_selector.py:109` (used `:359,384`) | 3 | **yes** |
| Transition decay rate | `TRANSITION_DECAY_RATE` | `synapses.py:76` | 0.01 | no |
| Transition prune threshold | `TRANSITION_PRUNE_THRESHOLD` | `synapses.py:77` | 0.5 | no |
| Transition recall top-K | `DEFAULT_NEXT_TOP_K` | `synapses.py:78` | 5 | no (read at margin=top_k=1) |
| LTP threshold | `LTP_THRESHOLD` | `synapses.py:66` | 5 | no |
| Synapse boost weight | `SYNAPSE_BOOST_WEIGHT` | `context_selector.py:99` (used `:481,527,568`) | 0.3 | no |

Why only `l2_recall_k`: it's the one knob that is (a) budget-bounded — moving it
trades which communities load, never how many tokens leak — and (b) reversible
per session. The decay/prune/LTP/boost knobs reshape the *stored* graph or the
ranking math, where a bad hand-tuned move is harder to detect and undo without
the eval-driven fitness function Phase 3 provides.

## Phase 3 — subsystem C: closed-loop eval-driven tuning (future work)

Depends on `evals/faithfulness/` providing a cached question set + a
correctness-vs-tokens fitness function. A nightly / on-demand job:

1. Snapshot the current tunable vector (start with `l2_recall_k`, then add the
   surveyed synapse knobs) as the baseline.
2. Sweep small perturbations (one or two params at a time, 3-point grid).
3. Re-run the faithfulness eval against the cached questions.
4. Promote the perturbation that improves the correctness-vs-tokens frontier;
   otherwise revert.

Subsystem A already reads its tunable from the `meta` table, so subsystem C can
write the same keys without touching A's code. Out of scope here beyond noting
the integration point: the `meta` table + the `self_improve:` key prefix are
the contract.

## Test strategy

Stdlib-only (the synapse store is stdlib sqlite; the embedder side is faked or
unused), like `tests/test_synapse*`:

- `tests/test_memory.py` — event schema, `session_id` on both event types,
  `log_wakeup_event` dual-scope write, and each aggregation helper on
  hand-built event streams (D1).
- `tests/test_self_improve.py` — synthetic event streams; the pure `_decide`
  rule, `tune_selector` warm-up / window / raise / lower / dead-band paths,
  fail-open, the transition-margin dampener, env-flag gating of the read path,
  and a meta-table persistence round-trip (D2).

## Configuration surface

| Env var | Default | What it controls |
| --- | --- | --- |
| `NEURALMIND_MEMORY` | `1` | Memory logging at all (consent still required) |
| `NEURALMIND_SELECTOR_AUTOTUNE` | `0` | Subsystem A active (tuner tick + read path) |

Goal: ship the logging substrate quietly on (behind consent); the tuning
behavior gated off until the operator opts in.
