"""proposal_store.py — Persistent proposal storage for Agent OS.

DEPRECATED: This module is a compatibility shim over the unified SQLite store.
All new code should use AgentOSStore directly.

Retained for backward compatibility with existing imports.
Thread-safe via a module-level lock.
"""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any

from .store import get_store

log = logging.getLogger(__name__)

_lock = threading.Lock()

# Module-level flag: if True, fall back to legacy JSONL behavior
# If False (default), use the unified store
_USE_LEGACY_JSONL = os.environ.get("NEURALMIND_AGENTOS_LEGACY_JSONL", "0") == "1"


def _store_path(base_dir: Path | None = None) -> Path:
    if base_dir is None:
        env_dir = os.environ.get("NEURALMIND_AGENTOS_DIR")
        base_dir = Path(env_dir) if env_dir else Path.home() / ".neuralmind" / "agent-os"
    return base_dir / "proposals.jsonl"


def create_proposal(
    title: str,
    hypothesis: str,
    baseline_tag: str,
    candidate_tag: str,
    metric_name: str,
    baseline_value: float,
    candidate_value: float,
    tags: list[str] | None = None,
    signal_count: int = 0,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Create a new proposal and persist it."""
    store = get_store()
    return store.create_proposal(
        tenant_id="default",
        title=title,
        hypothesis=hypothesis,
        baseline_tag=baseline_tag,
        candidate_tag=candidate_tag,
        metric_name=metric_name,
        baseline_value=baseline_value,
        candidate_value=candidate_value,
        tags=tags,
        signal_count=signal_count,
    )


def list_proposals(base_dir: Path | None = None) -> list[dict[str, Any]]:
    """Return the latest state of each proposal (newest first)."""
    store = get_store()
    return store.list_proposals(tenant_id="default")


def get_proposal(proposal_id: str, base_dir: Path | None = None) -> dict[str, Any] | None:
    """Get the latest state of a specific proposal."""
    store = get_store()
    return store.get_proposal("default", proposal_id)


def update_proposal(proposal_id: str, changes: dict[str, Any], base_dir: Path | None = None) -> dict[str, Any] | None:
    """Update a proposal and persist the change."""
    store = get_store()
    return store.update_proposal("default", proposal_id, changes)


def increment_signal_count(proposal_id: str, base_dir: Path | None = None) -> dict[str, Any] | None:
    """Increment signal_count on a proposal."""
    store = get_store()
    return store.increment_signal_count("default", proposal_id)


def _persist(proposal: dict[str, Any], base_dir: Path | None = None) -> None:
    """Legacy JSONL append — kept for reference, not used by default."""
    try:
        path = _store_path(base_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        with _lock:
            with open(path, "a", encoding="utf-8") as f:
                import json
                f.write(json.dumps(proposal) + "\n")
    except Exception:
        pass


def history(proposal_id: str | None = None, base_dir: Path | None = None) -> list[dict[str, Any]]:
    """Return full history from the store."""
    store = get_store()
    if proposal_id:
        # Return the current state of the proposal (store doesn't version records)
        proposal = store.get_proposal("default", proposal_id)
        return [proposal] if proposal else []
    return []
