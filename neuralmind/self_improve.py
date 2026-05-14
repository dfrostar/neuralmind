"""
self_improve.py — selector auto-tuning (self-improvement engine, subsystem A)

NeuralMind logs query/wakeup events (see memory.py). This module reads the
aggregated signal back and adjusts one selector parameter — `l2_recall_k`,
the number of L2 community summaries surfaced per query — persisting it in
the synapse store's meta table so it carries across sessions.

The tuner is deliberately conservative:
- driven by re_query_rate (consecutive same-session queries with high
  community overlap → the agent had to come back → under-disclosure);
- bounded to [L2_RECALL_K_MIN, L2_RECALL_K_MAX] with a single-step move;
- a dead band between the two thresholds so it doesn't oscillate;
- a warm-up gate so it never acts on thin data;
- events windowed to *since the last tune* so it doesn't chase a
  distribution it just perturbed.

It is gated OFF by default at the call site (the SessionStart hook only
runs it when NEURALMIND_SELECTOR_AUTOTUNE=1).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .memory import (
    project_query_events_file,
    re_query_rate,
    read_events,
    recent_events,
)
from .synapses import SynapseStore, default_db_path

META_KEY = "l2_recall_k"
META_KEY_TUNED_AT = "l2_recall_k_tuned_at"

L2_RECALL_K_DEFAULT = 3
L2_RECALL_K_MIN = 2
L2_RECALL_K_MAX = 6

WARMUP_MIN_EVENTS = 50
FALLBACK_WINDOW = 200

# Minimum events *in the tuning window* for re_query_rate to carry signal.
# Guards the common post-tune case: the window is keyed off the last tune
# timestamp, so right after a tune (before fresh events arrive) it is
# empty — and an empty window must mean "hold", not "rate is 0.0".
WINDOW_MIN_EVENTS = 20

# Provisional thresholds — re_query_rate is a weak, noisy signal and these
# bounds are unvalidated guesses. Subsystem C (eval-driven tuning) will
# replace this hand-tuned rule with a real fitness function.
RE_QUERY_RATE_HIGH = 0.40
RE_QUERY_RATE_LOW = 0.15


def _read_current_k(store: SynapseStore) -> int:
    raw = store.get_meta(META_KEY)
    if raw is None:
        return L2_RECALL_K_DEFAULT
    try:
        return int(raw)
    except (TypeError, ValueError):
        return L2_RECALL_K_DEFAULT


def _compute(project_path: str | Path, store: SynapseStore) -> dict:
    """Shared read-side computation for both tune_selector and selector_report.

    Returns the current k, the windowed re_query_rate, and the total event
    count — without writing anything.
    """
    events = read_events(project_query_events_file(project_path))
    total = len(events)
    current = _read_current_k(store)

    since = store.get_meta(META_KEY_TUNED_AT)
    if since:
        window = recent_events(events, since_ts=since)
    else:
        window = recent_events(events, last_n=FALLBACK_WINDOW)

    return {
        "current": current,
        "total_events": total,
        "windowed_events": len(window),
        "re_query_rate": re_query_rate(window),
    }


def _decide(current: int, rate: float) -> tuple[int, str]:
    """Apply the bounded, hysteretic tuning rule. Returns (new_k, reason)."""
    if rate > RE_QUERY_RATE_HIGH:
        new = min(current + 1, L2_RECALL_K_MAX)
        return new, ("raised" if new != current else "at_max")
    if rate < RE_QUERY_RATE_LOW:
        new = max(current - 1, L2_RECALL_K_MIN)
        return new, ("lowered" if new != current else "at_min")
    return current, "dead_band"


def tune_selector(project_path: str | Path, *, now: datetime | None = None) -> dict:
    """Read recent events, adjust l2_recall_k, persist to the synapse meta table.

    Never raises — any failure returns {"changed": False, "reason": "error"}.
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

        new, reason = _decide(current, stats["re_query_rate"])
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
