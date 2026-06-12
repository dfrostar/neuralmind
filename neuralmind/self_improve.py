"""
self_improve.py — selector auto-tuning (self-improvement engine, subsystem A)

NeuralMind logs query/wakeup events (see :mod:`neuralmind.memory`). This module
reads the aggregated signal back and adjusts one selector parameter — the L2
recall depth (how many community summaries L2 surfaces per query, the
``l2_recall_k`` in ``context_selector.py``) — persisting it in the synapse
store's ``meta`` table so it carries across sessions.

The tuner is deliberately conservative:

- driven by ``re_query_rate`` (consecutive same-session queries with high
  community overlap → the agent had to come back → under-disclosure);
- bounded to ``[L2_RECALL_K_MIN, L2_RECALL_K_MAX]`` with a single-step move;
- a hysteretic dead band between the two thresholds so it doesn't oscillate;
- a warm-up gate so it never acts on thin data;
- events windowed to *since the last tune* so it doesn't chase a distribution
  it just perturbed;
- a transition-margin dampener (v0.11+): when the agent's directional
  transition graph shows it decisively knows where it's going from the most
  recent query's recall, widening L2 won't help — so a raise is suppressed.

It is gated OFF by default at the call site: the SessionStart hook only runs it
when ``NEURALMIND_SELECTOR_AUTOTUNE=1``. The query hot path only reads the
persisted value under the same flag (see ``core.NeuralMind._tuned_l2_recall_k``).

Tuner state is stored in the synapse store's ``meta`` table, which is
namespace-free (one row per key for the whole store), so the tuned recall depth
is global per project regardless of the active memory namespace. The keys are
prefixed ``self_improve:`` so the tuner's scratch can't collide with the
store's own ``meta`` keys (``schema_version``, ``last_decay``).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .context_selector import ContextSelector
from .memory import (
    project_query_events_file,
    re_query_rate,
    read_events,
    recent_events,
)
from .synapses import SynapseStore, default_db_path

META_KEY = "self_improve:l2_recall_k"
META_KEY_TUNED_AT = "self_improve:l2_recall_k_tuned_at"

# Bounds + default mirror the selector's clamp (the selector is the source of
# truth for the knob's range, so the tuner can never persist a value the
# selector would reject).
L2_RECALL_K_DEFAULT = ContextSelector.L2_RECALL_K_DEFAULT
L2_RECALL_K_MIN = ContextSelector.L2_RECALL_K_MIN
L2_RECALL_K_MAX = ContextSelector.L2_RECALL_K_MAX

WARMUP_MIN_EVENTS = 50
FALLBACK_WINDOW = 200

# Minimum events *in the tuning window* for re_query_rate to carry signal.
# Guards the common post-tune case: the window is keyed off the last tune
# timestamp, so right after a tune (before fresh events arrive) it is empty —
# and an empty window must mean "hold", not "rate is 0.0".
WINDOW_MIN_EVENTS = 20

# Provisional thresholds — re_query_rate is a weak, noisy signal and these
# bounds are unvalidated guesses. Phase 3 (eval-driven tuning, subsystem C)
# will replace this hand-tuned rule with a real fitness function.
RE_QUERY_RATE_HIGH = 0.40
RE_QUERY_RATE_LOW = 0.15

# Transition-margin dampener (v0.11+). When the top-1 outgoing transition from
# the most recent query's recall seed carries at least this probability mass,
# the agent's directional graph already knows where it's going next — widening
# L2 recall wouldn't reduce the re-query, it would just spend tokens. So an
# otherwise-warranted raise is held. A weak/flat distribution (margin below
# this) leaves the raise path untouched.
TRANSITION_MARGIN_HIGH = 0.70


def _read_current_k(store: SynapseStore) -> int:
    raw = store.get_meta(META_KEY)
    if raw is None:
        return L2_RECALL_K_DEFAULT
    try:
        return int(raw)
    except (TypeError, ValueError):
        return L2_RECALL_K_DEFAULT


def transition_top1_margin(store: SynapseStore, node_id: str) -> float:
    """Top-1 outgoing transition probability for ``node_id``, or 0.0.

    A cheap read of the directional-transition distribution (v0.11+): if the
    agent has a decisive "after touching this, I go there" pattern, the top-1
    probability is high. Returns 0.0 when the node has no learned transitions
    (cold graph) or anything goes wrong — so a missing signal never widens
    recall and never blocks the tuner.
    """
    if not node_id:
        return 0.0
    try:
        dist = store.next_likely(node_id, top_k=1)
    except Exception:
        return 0.0
    if not dist:
        return 0.0
    return float(dist[0][1])


def _recent_recall_seed(window: list[dict]) -> str | None:
    """Pick the transition-graph seed from the most recent windowed query.

    Uses the last community the most recent query loaded, encoded as the
    ``community_<id>`` pseudo-node the synapse layer reinforces (see
    ``core._reinforce_from_query``). Returns None when the window has no
    query that loaded a community.
    """
    for event in reversed(window):
        communities = (event.get("retrieval_summary") or {}).get("communities_loaded") or []
        if communities:
            return f"community_{communities[-1]}"
    return None


def _compute(project_path: str | Path, store: SynapseStore) -> dict:
    """Shared read-side computation for both tune_selector and selector_report.

    Returns the current k, the windowed re_query_rate, the query-event counts,
    and the window itself (for the transition-margin secondary signal) —
    without writing anything.
    """
    events = read_events(project_query_events_file(project_path))
    # The warm-up / window gates and the signal both key off *query* events
    # only. Wakeup events share the same JSONL file but carry no re_query
    # signal — counting them toward the thresholds would let the tuner act
    # (and drift l2_recall_k down) without query evidence.
    queries = [e for e in events if e.get("event_type") == "query"]
    current = _read_current_k(store)

    since = store.get_meta(META_KEY_TUNED_AT)
    if since:
        window = recent_events(queries, since_ts=since)
    else:
        window = recent_events(queries, last_n=FALLBACK_WINDOW)

    return {
        "current": current,
        "total_events": len(queries),
        "windowed_events": len(window),
        "re_query_rate": re_query_rate(window),
        "window": window,
    }


def _decide(current: int, rate: float, transition_margin: float = 0.0) -> tuple[int, str]:
    """Apply the bounded, hysteretic tuning rule. Returns (new_k, reason).

    ``transition_margin`` is the secondary dampener: a high top-1 transition
    probability means the agent already knows where it's going, so a raise the
    re_query_rate would otherwise warrant is suppressed (reason
    ``"transition_dampened"``). It never *forces* a move and never affects the
    lower or dead-band paths.
    """
    if rate > RE_QUERY_RATE_HIGH:
        if transition_margin >= TRANSITION_MARGIN_HIGH:
            return current, "transition_dampened"
        new = min(current + 1, L2_RECALL_K_MAX)
        return new, ("raised" if new != current else "at_max")
    if rate < RE_QUERY_RATE_LOW:
        new = max(current - 1, L2_RECALL_K_MIN)
        return new, ("lowered" if new != current else "at_min")
    return current, "dead_band"


def tune_selector(project_path: str | Path, *, now: datetime | None = None) -> dict:
    """Read recent events, adjust l2_recall_k, persist to the synapse meta table.

    Never raises — any failure returns ``{"changed": False, "reason": "error"}``.
    Safe to call from the SessionStart hook.
    """
    try:
        store = SynapseStore(default_db_path(project_path))
        stats = _compute(project_path, store)
        current = stats["current"]

        if stats["total_events"] < WARMUP_MIN_EVENTS:
            return {
                "changed": False,
                "old": current,
                "new": current,
                "reason": "warmup",
                "events": stats["total_events"],
                "re_query_rate": stats["re_query_rate"],
            }

        if stats["windowed_events"] < WINDOW_MIN_EVENTS:
            return {
                "changed": False,
                "old": current,
                "new": current,
                "reason": "insufficient_recent",
                "events": stats["windowed_events"],
                "re_query_rate": stats["re_query_rate"],
            }

        seed = _recent_recall_seed(stats["window"])
        margin = transition_top1_margin(store, seed) if seed else 0.0
        new, reason = _decide(current, stats["re_query_rate"], transition_margin=margin)
        changed = new != current
        if changed:
            ts = (now or datetime.now(timezone.utc)).isoformat()
            store.set_meta(META_KEY, str(new))
            store.set_meta(META_KEY_TUNED_AT, ts)

        return {
            "changed": changed,
            "old": current,
            "new": new,
            "reason": reason,
            "events": stats["windowed_events"],
            "re_query_rate": stats["re_query_rate"],
            "transition_margin": margin,
        }
    except Exception:
        return {
            "changed": False,
            "old": L2_RECALL_K_DEFAULT,
            "new": L2_RECALL_K_DEFAULT,
            "reason": "error",
            "events": 0,
            "re_query_rate": 0.0,
        }


def selector_report(project_path: str | Path) -> dict:
    """Read-only view of the tuner state for the CLI. Never writes, never raises."""
    try:
        store = SynapseStore(default_db_path(project_path))
        stats = _compute(project_path, store)
        return {
            "l2_recall_k": stats["current"],
            "l2_recall_k_tuned_at": store.get_meta(META_KEY_TUNED_AT),
            "total_events": stats["total_events"],
            "windowed_events": stats["windowed_events"],
            "re_query_rate": stats["re_query_rate"],
            "warmed_up": stats["total_events"] >= WARMUP_MIN_EVENTS,
        }
    except Exception:
        return {
            "l2_recall_k": L2_RECALL_K_DEFAULT,
            "l2_recall_k_tuned_at": None,
            "total_events": 0,
            "windowed_events": 0,
            "re_query_rate": 0.0,
            "warmed_up": False,
        }
