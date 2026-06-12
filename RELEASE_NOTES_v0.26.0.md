# NeuralMind v0.26.0 — the selector starts tuning itself

**The headline:** NeuralMind's progressive-disclosure selector can now **adjust
its own L2 recall depth** from how an agent actually uses it. This is phases 1–2
of the self-improvement engine (issue #156): a logging substrate that records
query and wakeup events with a `session_id`, and an opt-in **tuner** that reads
that signal back and widens or narrows how many community summaries L2 surfaces
per query. The whole thing is **off by default** behind
`NEURALMIND_SELECTOR_AUTOTUNE=1`, and with the flag unset behavior is
byte-identical to v0.25.0 — zero extra I/O on the hot path.

The signal it tunes on is the **re-query rate**: when an agent issues two
consecutive same-session queries whose recalled communities heavily overlap, the
first query under-disclosed and the agent had to come back. Persistent overlap
means L2 is too narrow, so the tuner raises the recall depth one step; a
consistently low overlap means it can narrow. The tuned value is persisted in the
synapse store's `meta` table, so it carries across sessions per project.

## What the agent actually sees post-install

**With the flag off (the default): nothing changes.** The selector keeps its
hard-coded L2 recall depth of 3, the hot query path does no extra meta reads, and
recall is exactly what it was in v0.25.0. The logging substrate still records
events (under the existing memory-consent gate), but no tuning happens and the
read path never touches the persisted value.

**With the flag on (`NEURALMIND_SELECTOR_AUTOTUNE=1`):** once enough query events
have accumulated, the L2 recall depth **adapts to how often the agent had to
re-query.** If the agent keeps coming back for more of the same area, L2 widens
(up to 6 communities) so the next query lands what it needs in one shot; if it
rarely re-queries, L2 narrows (down to 2) to stop spending tokens on context the
agent didn't use. The change is gradual — at most one step per session — and the
agent simply gets a recall depth better matched to its query distribution.

There is also a **transition-margin dampener**: when the agent's directional
transition graph (v0.11+) already predicts the next hop decisively (top-1
probability ≥ 0.70), an otherwise-warranted raise is **suppressed**. If the agent
already knows where it's going next, widening L2 wouldn't reduce the re-query — it
would just spend tokens — so the tuner holds.

## Per-agent expectations

| Agent | What changes in v0.26.0 |
|-------|--------------------------|
| **Claude Code** | With the flag off, nothing. With the flag on, the `SessionStart` hook runs the tuner once per session (after the decay tick), and subsequent queries use the tuned L2 recall depth. The tuner is fail-open — a failure is swallowed and the hook still returns 0. |
| **Cursor / Cline** | With the flag off, nothing. With the flag on, the tuned value is threaded into the selector at build time, so normal MCP queries get the adapted recall depth — no tool-surface change, no new tool to call. |
| **Generic MCP client** | Same as Cursor / Cline: with the flag on, the tuned recall depth flows through ordinary queries; with it off, the selector default stands. |
| **Contributors / CI** | New module `neuralmind/self_improve.py` (read-side, no LLM calls). New read-only CLI `neuralmind self-improve status`. New `get_meta`/`set_meta` accessors on `SynapseStore`. New `NEURALMIND_SELECTOR_AUTOTUNE` env var. Phase 3 (eval-driven closed-loop tuning) is future work, surveyed in `evals/self_improvement/PLAN.md`. |

## How to try it

Enable the tuner for a session and inspect its state:

```bash
# Opt in (default is off). The tuner runs at SessionStart under Claude Code;
# for the CLI it persists across runs in the synapse store's meta table.
export NEURALMIND_SELECTOR_AUTOTUNE=1

# Read-only: current recall depth, when it was last tuned, event counts,
# warm-up state, the windowed re-query rate, and whether autotune is enabled.
neuralmind self-improve status .
neuralmind self-improve status . --json
```

Sample output:

```
Project: my-project
Autotune enabled: True (NEURALMIND_SELECTOR_AUTOTUNE)
l2_recall_k: 4
Last tuned at: 2026-06-12T17:58:10+00:00
Query events logged: 132 (warmed up: True)
Query events in tuning window: 41
re_query_rate: 0.512
```

`self-improve status` is purely read-only — it never writes, and it reports the
default state on a project that has never run the tuner.

## Conservative by design

The tuner only moves the cheapest, most reversible knob — the L2 community budget
— and every guard is there to keep it from acting on thin or self-referential
data:

- **Warm-up gate.** It holds until at least 50 query events have accumulated, so
  it never acts on a handful of early queries.
- **Hysteretic dead band.** Raise above a high re-query rate, lower below a low
  one, hold in between — so it doesn't oscillate around a threshold.
- **Single-step moves, clamped to `[2, 6]`.** At most one step per session, and
  the bounds are enforced both in the tuner (before persisting) and in the
  selector (on read), so a garbage value can never widen recall out of range.
- **Windowed signal.** Events are counted only *since the last tune*, so the
  tuner doesn't chase a distribution it just perturbed (raising the recall depth
  changes which communities load, which feeds the re-query rate). A too-thin
  window means "hold", not "rate 0.0, lower it".
- **Transition-margin dampener.** A decisive directional-transition prediction
  suppresses a raise — the tokens wouldn't help.
- **Fail-open everywhere.** `tune_selector()` never raises; any failure returns
  defaults and never breaks a query. The `SessionStart` hook swallows tuner
  failures and always returns 0.
- **Default-off is default-identical.** With the flag unset, the hot path does
  zero extra I/O and the selector uses its hard-coded default — proven by the
  unmodified existing test suite.

## Why it matters

Until now the selector's recall depth was a single hard-coded number that suited
the average project but not yours. The self-improvement engine closes that gap
without asking the agent for explicit feedback: the re-query rate is an *implicit*
signal that's already there in how the agent works. A project where the agent
keeps re-querying gets a wider L2 automatically; a project where the first answer
usually suffices gets a tighter one. And because every move is bounded, windowed,
and reversible — and the whole thing is opt-in — turning it on is safe to try and
trivial to ignore.

Phase 3 (subsystem C) will replace the hand-tuned re-query thresholds with an
eval-driven fitness function over the faithfulness suite, and can widen tuning to
the surveyed synapse knobs without touching the engine's storage contract. See
`evals/self_improvement/PLAN.md` for the full survey.
