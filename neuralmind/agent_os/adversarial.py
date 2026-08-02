"""adversarial.py — Adversarial query generation from insights.

When a signal fires, generate adversarial queries that test the insight
hypothesis against edge cases and failure modes. Stored in JSONL for
audit trail and review.

Design:
    - Generate queries that test the hypothesis boundary conditions
    - Store in JSONL for fail-open persistence
    - Stdlib-only: no external dependencies
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_lock = threading.Lock()


def _store_path(base_dir: Path | None = None) -> Path:
    if base_dir is None:
        base_dir = Path.home() / ".neuralmind" / "agent-os"
    return base_dir / "adversarial_queries.jsonl"


def generate_adversarial_query(
    metric_name: str,
    hypothesis: str,
    cause_type: str = "unknown",
    base_dir: Path | None = None,
) -> str:
    """Generate an adversarial query from an insight hypothesis.

    Tests edge cases around the hypothesis by asking:
    1. Under what conditions would this hypothesis FAIL?
    2. What's the worst-case scenario if this hypothesis is WRONG?
    3. What's the boundary where this hypothesis breaks?

    Args:
        metric_name: The metric that triggered the signal.
        hypothesis: The insight hypothesis string.
        cause_type: The type of cause (code_change, config_change, etc.).
        base_dir: Optional override for the agent-os directory.

    Returns:
        The generated adversarial query string.
    """
    query = (
        f"ADVERSARIAL: Given the hypothesis '{hypothesis}' for metric "
        f"'{metric_name}' (cause_type={cause_type}), identify: "
        f"(1) The boundary conditions under which this hypothesis fails, "
        f"(2) The worst-case scenario if this change is applied incorrectly, "
        f"(3) The minimum viable test that would falsify this hypothesis."
    )

    _persist(query, metric_name, hypothesis, cause_type, base_dir)
    return query


def _persist(
    query: str,
    metric_name: str,
    hypothesis: str,
    cause_type: str,
    base_dir: Path | None = None,
) -> None:
    """Persist an adversarial query to JSONL."""
    try:
        path = _store_path(base_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "query_id": f"adv_{uuid.uuid4().hex[:12]}",
            "query": query,
            "metric_name": metric_name,
            "source_hypothesis": hypothesis,
            "cause_type": cause_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with _lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
    except Exception:
        pass


def get_adversarial_queries(
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Get all stored adversarial queries."""
    path = _store_path(base_dir)
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    except Exception:
        return []
