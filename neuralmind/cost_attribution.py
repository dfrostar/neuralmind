"""cost_attribution.py — CFO-facing ROI artifact from query event logs.

Reads the JSONL query events written by ``neuralmind.memory`` and the
metrics written by ``neuralmind.metrics_pipeline``, then computes a
per-repo, per-seat modeled cost savings figure.

The model is deliberately conservative:
  - Only queries with a measured reduction_ratio > 1.0 count as savings.
  - The baseline (no NeuralMind) token count is reconstructed from the
    reduction_ratio and the actual tokens_used.
  - Cost is modeled at a flat $0.01 per 1K tokens (OpenRouter-scale
    pricing for a mid-tier model — configurable via COST_PER_1K_TOKENS).

This is a *modeled* savings figure, not a measured one — the baseline is
reconstructed, not observed. The output says so explicitly.

Local-first. Stdlib-only. Fail-open.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default cost model: $0.01 per 1K tokens (OpenRouter mid-tier).
# Override via NEURALMIND_COST_PER_1K_TOKENS env var.
DEFAULT_COST_PER_1K_TOKENS = 0.01

# Reduction ratio below which a query is not counted as savings.
# (A ratio of 1.0 means NeuralMind used the same tokens as baseline.)
MIN_SAVINGS_RATIO = 1.0


def _cost_per_1k_tokens() -> float:
    """Read cost model from environment, falling back on default."""
    try:
        return float(os.environ.get("NEURALMIND_COST_PER_1K_TOKENS", DEFAULT_COST_PER_1K_TOKENS))
    except (KeyError, ValueError):
        return DEFAULT_COST_PER_1K_TOKENS


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL file, returning a list of dicts. Fail-open."""
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception:
        logger.exception("[cost_attribution] failed reading %s", path)
    return events


def _baseline_tokens(tokens_used: int, reduction_ratio: float) -> int:
    """Reconstruct the baseline (no-NeuralMind) token count.

    baseline = tokens_used * reduction_ratio
    (reduction_ratio = baseline / tokens_used, so baseline = ratio * tokens_used)
    """
    if reduction_ratio <= 0:
        return tokens_used
    return int(tokens_used * reduction_ratio)


def compute_cost_attribution(
    project_path: str | Path,
    *,
    days: int = 30,
    cost_per_1k_tokens: float | None = None,
) -> dict[str, Any]:
    """Compute cost attribution for a project from its query event logs.

    Returns a dict with:
        - project: project name
        - days: analysis window
        - cost_model: cost per 1K tokens
        - total_queries: total query events
        - savings_queries: queries with reduction_ratio > MIN_SAVINGS_RATIO
        - total_tokens_used: actual tokens consumed
        - total_baseline_tokens: reconstructed baseline tokens
        - total_savings_tokens: baseline - actual
        - savings_ratio: total_savings_tokens / total_baseline_tokens
        - modeled_cost_savings_usd: modeled dollar savings
        - per_session: breakdown by session_id
        - daily: breakdown by day
    """
    from .memory import project_query_events_file

    project_path = Path(project_path)
    project_name = project_path.name
    cost_per_1k = cost_per_1k_tokens if cost_per_1k_tokens is not None else _cost_per_1k_tokens()

    events = _read_jsonl(project_query_events_file(project_path))
    if not events:
        return {
            "project": project_name,
            "days": days,
            "cost_model": cost_per_1k,
            "total_queries": 0,
            "savings_queries": 0,
            "total_tokens_used": 0,
            "total_baseline_tokens": 0,
            "total_savings_tokens": 0,
            "savings_ratio": 0.0,
            "modeled_cost_savings_usd": 0.0,
            "per_session": {},
            "daily": {},
        }

    cutoff = time.time() - (days * 86400)
    recent_events = [
        e for e in events if e.get("timestamp", "") and _parse_ts(e["timestamp"]) >= cutoff
    ]

    if not recent_events:
        return {
            "project": project_name,
            "days": days,
            "cost_model": cost_per_1k,
            "total_queries": 0,
            "savings_queries": 0,
            "total_tokens_used": 0,
            "total_baseline_tokens": 0,
            "total_savings_tokens": 0,
            "savings_ratio": 0.0,
            "modeled_cost_savings_usd": 0.0,
            "per_session": {},
            "daily": {},
        }

    total_tokens_used = 0
    total_baseline_tokens = 0
    savings_queries = 0
    per_session: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"queries": 0, "tokens_used": 0, "baseline_tokens": 0, "savings_tokens": 0}
    )
    daily: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"queries": 0, "tokens_used": 0, "baseline_tokens": 0, "savings_tokens": 0}
    )

    for event in recent_events:
        retrieval = event.get("retrieval_summary", {})
        tokens_used = int(retrieval.get("tokens", 0))
        reduction_ratio = float(retrieval.get("reduction_ratio", 0.0))
        session_id = event.get("session_id", "unknown")
        ts = event.get("timestamp", "")
        day_key = ts[:10] if len(ts) >= 10 else "unknown"

        baseline = _baseline_tokens(tokens_used, reduction_ratio)
        savings = max(0, baseline - tokens_used)

        total_tokens_used += tokens_used
        total_baseline_tokens += baseline
        if reduction_ratio > MIN_SAVINGS_RATIO:
            savings_queries += 1

        # Per-session
        per_session[session_id]["queries"] += 1
        per_session[session_id]["tokens_used"] += tokens_used
        per_session[session_id]["baseline_tokens"] += baseline
        per_session[session_id]["savings_tokens"] += savings

        # Daily
        daily[day_key]["queries"] += 1
        daily[day_key]["tokens_used"] += tokens_used
        daily[day_key]["baseline_tokens"] += baseline
        daily[day_key]["savings_tokens"] += savings

    total_savings_tokens = max(0, total_baseline_tokens - total_tokens_used)
    savings_ratio = (
        total_savings_tokens / total_baseline_tokens if total_baseline_tokens > 0 else 0.0
    )
    modeled_cost_savings = (total_savings_tokens / 1000) * cost_per_1k

    # Convert defaultdicts to regular dicts for JSON serialization
    per_session_dict = dict(per_session)
    daily_dict = dict(daily)

    return {
        "project": project_name,
        "days": days,
        "cost_model": cost_per_1k,
        "total_queries": len(recent_events),
        "savings_queries": savings_queries,
        "total_tokens_used": total_tokens_used,
        "total_baseline_tokens": total_baseline_tokens,
        "total_savings_tokens": total_savings_tokens,
        "savings_ratio": round(savings_ratio, 4),
        "modeled_cost_savings_usd": round(modeled_cost_savings, 4),
        "per_session": per_session_dict,
        "daily": daily_dict,
    }


def _parse_ts(ts_str: str) -> float:
    """Parse an ISO timestamp to epoch seconds. Fail-open: returns 0."""
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.timestamp()
    except (ValueError, TypeError):
        return 0.0


def format_cost_report(attribution: dict[str, Any]) -> str:
    """Format a cost attribution dict as a human-readable report."""
    lines: list[str] = []
    lines.append(f"Cost Attribution — {attribution['project']}")
    lines.append(f"  Analysis window: {attribution['days']} days")
    lines.append(f"  Cost model: ${attribution['cost_model']:.4f} per 1K tokens")
    lines.append("")
    lines.append(f"  Total queries: {attribution['total_queries']}")
    lines.append(f"  Queries with savings: {attribution['savings_queries']}")
    lines.append("")
    lines.append(f"  Tokens used (NeuralMind): {attribution['total_tokens_used']:,}")
    lines.append(f"  Baseline tokens (no NeuralMind): {attribution['total_baseline_tokens']:,}")
    lines.append(f"  Savings tokens: {attribution['total_savings_tokens']:,}")
    lines.append(f"  Savings ratio: {attribution['savings_ratio']:.1%}")
    lines.append("")
    lines.append(f"  Modeled cost savings: ${attribution['modeled_cost_savings_usd']:.2f}")
    lines.append("")

    per_session = attribution.get("per_session", {})
    if per_session:
        lines.append("  Per-session breakdown:")
        for session_id, stats in sorted(per_session.items()):
            lines.append(f"    {session_id}:")
            lines.append(f"      Queries: {stats['queries']}")
            lines.append(f"      Tokens used: {stats['tokens_used']:,}")
            lines.append(f"      Baseline tokens: {stats['baseline_tokens']:,}")
            lines.append(f"      Savings tokens: {stats['savings_tokens']:,}")
        lines.append("")

    daily = attribution.get("daily", {})
    if daily:
        lines.append("  Daily breakdown:")
        for day, stats in sorted(daily.items()):
            lines.append(
                f"    {day}: {stats['queries']} queries, {stats['savings_tokens']:,} tokens saved"
            )
        lines.append("")

    lines.append("  Note: Modeled savings — baseline reconstructed from reduction_ratio,")
    lines.append("  not measured directly. Conservative: only counts queries with ratio > 1.0.")

    return "\n".join(lines)
