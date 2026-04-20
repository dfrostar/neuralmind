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
