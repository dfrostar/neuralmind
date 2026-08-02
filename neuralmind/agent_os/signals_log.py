"""signals_log.py — Persistent signal + insight storage for Agent OS tenants.

Stores signal records and correlator insights in JSONL files under the
tenant's directory. Thread-safe via a module-level lock.

Design:
    - Fail-open: any error degrades to no-op (never blocks signal pipeline).
    - Append-only: signals and insights are never overwritten.
    - Per-tenant isolation: each tenant has its own signals/insights files.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

_lock = threading.Lock()


def _tenant_dir(tenant_id: str, base_dir: Path | None = None) -> Path:
    """Get the directory for a tenant's signals log."""
    if base_dir is None:
        base_dir = Path.home() / ".neuralmind" / "tenants"
    return base_dir / tenant_id


def log_signal(tenant_id: str, signal: Any, base_dir: Path | None = None) -> None:
    """Log a signal to the tenant's signals log.

    Args:
        tenant_id: The tenant that owns this signal.
        signal: A Signal object (or any object with to_dict()).
        base_dir: Optional override for the tenants directory.
    """
    try:
        dir_ = _tenant_dir(tenant_id, base_dir)
        dir_.mkdir(parents=True, exist_ok=True)
        log_file = dir_ / "signals.jsonl"
        with _lock:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(signal.to_dict()) + "\n")
    except Exception:
        pass


def log_insight(tenant_id: str, insight: Any, base_dir: Path | None = None) -> None:
    """Log an insight to the tenant's insights log.

    Args:
        tenant_id: The tenant that owns this insight.
        insight: An Insight object (or any object with to_dict()).
        base_dir: Optional override for the tenants directory.
    """
    try:
        dir_ = _tenant_dir(tenant_id, base_dir)
        dir_.mkdir(parents=True, exist_ok=True)
        log_file = dir_ / "insights.jsonl"
        with _lock:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(insight.to_dict()) + "\n")
    except Exception:
        pass


def get_signals(tenant_id: str, base_dir: Path | None = None) -> list[dict]:
    """Get all signals for a tenant.

    Args:
        tenant_id: The tenant to query.
        base_dir: Optional override for the tenants directory.

    Returns:
        List of signal dicts, oldest first.
    """
    log_file = _tenant_dir(tenant_id, base_dir) / "signals.jsonl"
    if not log_file.exists():
        return []
    try:
        with open(log_file, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    except Exception:
        return []


def get_insights(tenant_id: str, base_dir: Path | None = None) -> list[dict]:
    """Get all insights for a tenant.

    Args:
        tenant_id: The tenant to query.
        base_dir: Optional override for the tenants directory.

    Returns:
        List of insight dicts, oldest first.
    """
    log_file = _tenant_dir(tenant_id, base_dir) / "insights.jsonl"
    if not log_file.exists():
        return []
    try:
        with open(log_file, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    except Exception:
        return []


def clear_tenant(tenant_id: str, base_dir: Path | None = None) -> None:
    """Clear all signals and insights for a tenant.

    Args:
        tenant_id: The tenant to clear.
        base_dir: Optional override for the tenants directory.
    """
    dir_ = _tenant_dir(tenant_id, base_dir)
    for name in ("signals.jsonl", "insights.jsonl"):
        f = dir_ / name
        if f.exists():
            try:
                f.unlink()
            except OSError:
                pass
