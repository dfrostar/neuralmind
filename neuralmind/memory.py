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
    uuid so programmatic / CLI callers still get session grouping.
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
    """Log a wakeup (L0+L1) event.

    Distinct from query events because wakeups have no question and a
    fixed layer set; the value is in the *absence* of a follow-up query
    in the same session — that's the "L0/L1 was sufficient" signal the
    selector tuner reads.
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
    """Read all events (query + wakeup) from JSONL file.

    Unlike read_query_events, this does not filter by event_type, so
    aggregation helpers can compute cross-event-type signals like
    wakeup_only_rate.
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
    """Slice an event list by ISO timestamp window and/or trailing count."""
    out = events
    if since_ts is not None:
        out = [e for e in out if (e.get("timestamp") or "") >= since_ts]
    if last_n is not None:
        out = out[-last_n:]
    return out


def escalation_rate(events: list[dict[str, Any]]) -> float:
    """Fraction of *query* events whose layers_used includes L3.

    L3 is the deep-search layer; high escalation suggests L2 community
    summaries are under-recalling for the query distribution.
    """
    queries = [e for e in events if e.get("event_type") == "query"]
    if not queries:
        return 0.0
    escalated = sum(
        1
        for e in queries
        if "L3" in (e.get("retrieval_summary") or {}).get("layers_used", [])
    )
    return escalated / len(queries)


def re_query_rate(events: list[dict[str, Any]]) -> float:
    """Fraction of consecutive same-session queries with high overlap.

    Two queries in the same session whose communities_loaded sets
    overlap by >=50% (of the smaller set) suggest the first query
    under-disclosed and the agent had to come back. Computed only over
    consecutive query pairs, indexed by session_id.
    """
    queries_by_session: dict[str, list[dict[str, Any]]] = {}
    for e in events:
        if e.get("event_type") != "query":
            continue
        sid = e.get("session_id") or ""
        queries_by_session.setdefault(sid, []).append(e)

    re_query_count = 0
    pairs = 0
    for qs in queries_by_session.values():
        for i in range(1, len(qs)):
            pairs += 1
            prev = set(
                (qs[i - 1].get("retrieval_summary") or {}).get("communities_loaded", [])
            )
            cur = set(
                (qs[i].get("retrieval_summary") or {}).get("communities_loaded", [])
            )
            denom = min(len(prev), len(cur))
            if denom == 0:
                continue
            if len(prev & cur) / denom >= 0.5:
                re_query_count += 1
    return (re_query_count / pairs) if pairs else 0.0


def wakeup_only_rate(events: list[dict[str, Any]]) -> float:
    """Fraction of sessions whose only events are wakeups (no queries).

    The positive signal for L0/L1 sufficiency: the agent woke up,
    received the cheap context, and never needed a query.
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


def extract_module_ids_from_event(event: dict[str, Any]) -> list[str]:
    """Extract module IDs from a query event.

    Returns module names from communities_loaded in retrieval summary.

    Args:
        event: Query event dictionary

    Returns:
        List of module identifiers
    """
    modules = []
    summary = event.get("retrieval_summary", {})
    communities = summary.get("communities_loaded", [])

    for comm_id in communities:
        if comm_id >= 0:
            modules.append(f"community_{comm_id}")

    return modules


def build_cooccurrence_index(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Build cooccurrence patterns from query events.

    Analyzes which modules appear together in successful queries.
    Patterns are stored as module_pair → count mappings.

    Args:
        events: List of query events

    Returns:
        Index dict with cooccurrence patterns and metadata
    """
    cooccurrence: dict[str, int] = {}
    module_frequency: dict[str, int] = {}

    for event in events:
        modules = extract_module_ids_from_event(event)
        if not modules:
            continue

        # Count module frequencies
        for mod in modules:
            module_frequency[mod] = module_frequency.get(mod, 0) + 1

        # Count pairwise cooccurrences
        for i, mod_a in enumerate(modules):
            for mod_b in modules[i + 1 :]:
                # Canonicalize pair (alphabetical order)
                pair = "|".join(sorted([mod_a, mod_b]))
                cooccurrence[pair] = cooccurrence.get(pair, 0) + 1

    return {
        "metadata": {
            "version": "1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "events_analyzed": len(events),
            "patterns_learned": len(cooccurrence),
        },
        "cooccurrence": cooccurrence,
        "module_frequency": module_frequency,
    }


def write_learned_patterns(project_path: str | Path, index: dict[str, Any]) -> Path:
    """Write learned patterns to project's patterns file.

    Args:
        project_path: Path to project root
        index: Cooccurrence index from build_cooccurrence_index()

    Returns:
        Path to written patterns file
    """
    project_path = Path(project_path)
    patterns_dir = project_path / ".neuralmind"
    patterns_dir.mkdir(parents=True, exist_ok=True)

    patterns_file = patterns_dir / "learned_patterns.json"
    with patterns_file.open("w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    return patterns_file
