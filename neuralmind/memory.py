"""Local-first implicit continual-learning scaffolding."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONSENT_SENTINEL = "continual_learning_consent.json"
GLOBAL_MEMORY_FILE = "implicit_learning.jsonl"
PROJECT_MEMORY_FILE = "implicit_learning.jsonl"


def global_neuralmind_home() -> Path:
    """Resolve the global NeuralMind data directory."""
    return Path(os.environ.get("NEURALMIND_HOME", "~/.neuralmind")).expanduser()


def project_neuralmind_home(project_path: str | Path) -> Path:
    """Resolve the project-local NeuralMind data directory."""
    return Path(project_path).resolve() / ".neuralmind"


def consent_sentinel_path() -> Path:
    """Return the global consent sentinel path."""
    return global_neuralmind_home() / CONSENT_SENTINEL


def _read_consent_state(path: Path) -> bool | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    opted_in = payload.get("opted_in")
    if isinstance(opted_in, bool):
        return opted_in
    return None


def _write_consent_state(path: Path, opted_in: bool, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "opted_in": opted_in,
        "source": source,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def ensure_implicit_learning_consent() -> bool:
    """Get/record one-time user consent for implicit learning logs.

    Returns:
        True when logging is allowed, False otherwise.
    """
    sentinel = consent_sentinel_path()
    saved = _read_consent_state(sentinel)
    if saved is not None:
        return saved

    env_choice = os.environ.get("NEURALMIND_IMPLICIT_LEARNING_OPT_IN")
    if env_choice is not None:
        normalized = env_choice.strip().lower()
        opted_in = normalized in {"1", "true", "yes", "y", "on"}
        _write_consent_state(sentinel, opted_in=opted_in, source="env")
        return opted_in

    stdin = getattr(sys, "stdin", None)
    stdout = getattr(sys, "stdout", None)
    if not (stdin and stdout and stdin.isatty() and stdout.isatty()):
        return False

    print("\nNeuralMind can optionally log local interaction memory for continual learning.")
    print(f"Stored only on this machine in: {global_neuralmind_home()} and <project>/.neuralmind")
    answer = input("Enable implicit continual-learning memory logging? [y/N]: ").strip().lower()
    opted_in = answer in {"y", "yes"}
    _write_consent_state(sentinel, opted_in=opted_in, source="prompt")
    return opted_in


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, default=str))
        handle.write("\n")


def log_implicit_learning_event(
    project_path: str | Path,
    event: str,
    details: dict[str, Any] | None = None,
) -> bool:
    """Append one local-first implicit learning event to global + project logs."""
    if not ensure_implicit_learning_consent():
        return False

    project_root = Path(project_path).resolve()
    payload: dict[str, Any] = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project": project_root.name,
        "project_path": str(project_root),
        "details": details or {},
    }

    try:
        _append_jsonl(global_neuralmind_home() / "memory" / GLOBAL_MEMORY_FILE, payload)
        _append_jsonl(
            project_neuralmind_home(project_root) / "memory" / PROJECT_MEMORY_FILE, payload
        )
        return True
    except Exception:
        return False
