"""Local-first memory scaffolding for opt-in continual learning."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONSENT_FILE_NAME = "memory_consent.json"
QUERY_EVENTS_FILE_NAME = "query_events.jsonl"


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


def log_query_event(project_path: str | Path, question: str, result: Any) -> bool:
    if not is_memory_logging_enabled():
        return False

    event = {
        "event_type": "query",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project_path": str(Path(project_path).resolve()),
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
