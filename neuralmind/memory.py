"""Local-first memory scaffolding for opt-in continual learning."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONSENT_FILE_NAME = "memory_consent.json"
QUERY_EVENTS_FILE_NAME = "query_events.jsonl"

_PROCESS_SESSION_ID: str | None = None


def _current_session_id() -> str:
    """Resolve a session id for event logging.

    Honors CLAUDE_SESSION_ID when set so events from one Claude Code
    session group together. Otherwise generates a stable per-process
    uuid so programmatic / CLI callers still get session grouping —
    the intra-session signals (re_query_rate, wakeup_only_rate) need a
    stable key to know which events were truly consecutive.
    """
    env = os.environ.get("CLAUDE_SESSION_ID")
    if env:
        return env
    global _PROCESS_SESSION_ID
    if _PROCESS_SESSION_ID is None:
        _PROCESS_SESSION_ID = str(uuid.uuid4())
    return _PROCESS_SESSION_ID


def _is_disabled(env_name: str) -> bool:
    return os.environ.get(env_name, "1") == "0"


def is_memory_disabled() -> bool:
    return _is_disabled("NEURALMIND_MEMORY")


def is_learning_disabled() -> bool:
    return _is_disabled("NEURALMIND_LEARNING")


def global_root() -> Path:
    return Path.home() / ".neuralmind"


def global_memory_dir() -> Path:
    return global_root() / "memory"


def project_memory_dir(project_path: str | Path) -> Path:
    return Path(project_path) / ".neuralmind" / "memory"


def global_query_events_file() -> Path:
    return global_memory_dir() / QUERY_EVENTS_FILE_NAME


def project_query_events_file(project_path: str | Path) -> Path:
    return project_memory_dir(project_path) / QUERY_EVENTS_FILE_NAME


def consent_file() -> Path:
    return global_root() / CONSENT_FILE_NAME


def read_consent_sentinel() -> bool | None:
    path = consent_file()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        enabled = data.get("memory_logging_enabled")
        if isinstance(enabled, bool):
            return enabled
    except Exception:
        return None
    return None


def write_consent_sentinel(enabled: bool) -> None:
    path = consent_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "memory_logging_enabled": enabled,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def should_prompt_for_consent(*, is_tty: bool) -> bool:
    if not is_tty or is_memory_disabled():
        return False
    return read_consent_sentinel() is None


def prompt_for_memory_consent() -> bool:
    try:
        response = input(  # noqa: A001
            "Enable local NeuralMind memory logging to improve retrieval over time? [y/N]: "
        ).strip()
    except EOFError:
        return False
    return response.lower() in {"y", "yes"}


def is_memory_logging_enabled() -> bool:
    if is_memory_disabled():
        return False
    return read_consent_sentinel() is True


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, sort_keys=True) + "\n")


def count_events(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as file:
        return sum(1 for line in file if line.strip())


def log_query_event(
    project_path: str | Path,
    question: str,
    result: Any,
    session_id: str | None = None,
) -> bool:
    if not is_memory_logging_enabled():
        return False

    event = {
        "event_type": "query",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project_path": str(Path(project_path).resolve()),
        "session_id": session_id or _current_session_id(),
        "query": question,
        "retrieval_summary": {
            "layers_used": list(getattr(result, "layers_used", [])),
            "communities_loaded": list(getattr(result, "communities_loaded", [])),
            "search_hits": int(getattr(result, "search_hits", 0)),
            "tokens": int(getattr(getattr(result, "budget", None), "total", 0)),
            "reduction_ratio": float(getattr(result, "reduction_ratio", 0.0)),
        },
    }

    try:
        _append_jsonl(project_query_events_file(project_path), event)
        _append_jsonl(global_query_events_file(), event)
    except Exception:
        return False
    return True


def log_wakeup_event(
    project_path: str | Path,
    result: Any,
    session_id: str | None = None,
) -> bool:
    """Log a wakeup (L0+L1) event to the same JSONL file as query events.

    Distinct from query events because wakeups have no question and a fixed
    layer set; the value is in the *absence* of a follow-up query in the same
    session — that's the "L0/L1 was sufficient" positive signal the selector
    tuner reads via ``wakeup_only_rate``. Gated by the same consent sentinel
    as ``log_query_event``.
    """
    if not is_memory_logging_enabled():
        return False

    event = {
        "event_type": "wakeup",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project_path": str(Path(project_path).resolve()),
        "session_id": session_id or _current_session_id(),
        "retrieval_summary": {
            "layers_used": list(getattr(result, "layers_used", [])),
            "tokens": int(getattr(getattr(result, "budget", None), "total", 0)),
        },
    }

    try:
        _append_jsonl(project_query_events_file(project_path), event)
        _append_jsonl(global_query_events_file(), event)
    except Exception:
        return False
    return True


def read_query_events(events_file: Path) -> list[dict[str, Any]]:
    """Read query events from JSONL file.

    Args:
        events_file: Path to query_events.jsonl

    Returns:
        List of event dictionaries (empty if file doesn't exist)
    """
    if not events_file.exists():
        return []

    events = []
    try:
        with events_file.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    if event.get("event_type") == "query":
                        events.append(event)
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass

    return events


def read_events(events_file: Path) -> list[dict[str, Any]]:
    """Read all events (query + wakeup) from a JSONL file.

    Unlike :func:`read_query_events`, this does not filter by event_type, so
    aggregation helpers can compute cross-event-type signals like
    :func:`wakeup_only_rate`. Bad lines are skipped, missing file returns [].
    """
    if not events_file.exists():
        return []

    events: list[dict[str, Any]] = []
    try:
        with events_file.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    return events


def recent_events(
    events: list[dict[str, Any]],
    *,
    since_ts: str | None = None,
    last_n: int | None = None,
) -> list[dict[str, Any]]:
    """Slice an event list by ISO timestamp window and/or trailing count.

    ISO-8601 timestamps sort lexicographically, so the ``since_ts`` filter is
    a plain string comparison. Applying both keeps the trailing ``last_n`` of
    whatever survived the timestamp window.
    """
    out = events
    if since_ts is not None:
        out = [e for e in out if (e.get("timestamp") or "") >= since_ts]
    if last_n is not None:
        out = out[-last_n:]
    return out


def escalation_rate(events: list[dict[str, Any]]) -> float:
    """Fraction of *query* events whose ``layers_used`` includes L3.

    L3 is the deep-search layer; high escalation suggests L2 community
    summaries are under-recalling for the query distribution. ``layers_used``
    elements are decorated strings produced by the selector (e.g.
    ``"L3:Search(4 results)"``), so match the L3 layer exactly (``"L3"`` or a
    ``"L3:"`` prefix) rather than any "L3"-containing string — a bare prefix
    check would false-match a hypothetical ``"L30"``.
    """
    queries = [e for e in events if e.get("event_type") == "query"]
    if not queries:
        return 0.0
    escalated = sum(
        1
        for e in queries
        if any(
            str(layer) == "L3" or str(layer).startswith("L3:")
            for layer in (e.get("retrieval_summary") or {}).get("layers_used", [])
        )
    )
    return escalated / len(queries)


def re_query_rate(events: list[dict[str, Any]]) -> float:
    """Fraction of consecutive same-session queries with high recall overlap.

    Two queries in the same session whose ``communities_loaded`` sets overlap
    by >=50% (of the smaller set) suggest the first query under-disclosed and
    the agent had to come back. Computed only over consecutive query pairs,
    indexed by ``session_id``.
    """
    queries_by_session: dict[str, list[dict[str, Any]]] = {}
    for e in events:
        if e.get("event_type") != "query":
            continue
        sid = e.get("session_id")
        if not sid:
            # Pre-D1 events have no session_id. Without one we can't tell
            # which queries were truly consecutive, so skip them rather than
            # lumping unrelated history under a shared empty-string key.
            continue
        queries_by_session.setdefault(sid, []).append(e)

    re_query_count = 0
    pairs = 0
    for qs in queries_by_session.values():
        for i in range(1, len(qs)):
            prev = set((qs[i - 1].get("retrieval_summary") or {}).get("communities_loaded", []))
            cur = set((qs[i].get("retrieval_summary") or {}).get("communities_loaded", []))
            denom = min(len(prev), len(cur))
            if denom == 0:
                # A pair where either query loaded no communities carries no
                # overlap signal either way — it must not count toward the
                # denominator, or it would deflate the rate.
                continue
            pairs += 1
            if len(prev & cur) / denom >= 0.5:
                re_query_count += 1
    return (re_query_count / pairs) if pairs else 0.0


def wakeup_only_rate(events: list[dict[str, Any]]) -> float:
    """Fraction of sessions whose only events are wakeups (no queries).

    The positive signal for L0/L1 sufficiency: the agent woke up, received
    the cheap context, and never needed a query. Sessions with no wakeup are
    not eligible (the metric is about whether a wakeup was enough on its own).
    """
    sessions: dict[str, dict[str, int]] = {}
    for e in events:
        sid = e.get("session_id")
        if not sid:
            continue
        kind = e.get("event_type")
        if kind not in ("wakeup", "query"):
            continue
        slot = sessions.setdefault(sid, {"wakeup": 0, "query": 0})
        slot[kind] += 1

    eligible = [s for s in sessions.values() if s["wakeup"] >= 1]
    if not eligible:
        return 0.0
    wakeup_only = sum(1 for s in eligible if s["query"] == 0)
    return wakeup_only / len(eligible)
