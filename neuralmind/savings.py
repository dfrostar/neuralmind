"""Savings report computation, shared by the CLI, MCP server, and daemon.

Reads the same event logs `neuralmind savings` always has — the project's
audit_events.jsonl (always written) with a fallback to the opt-in memory
query_events.jsonl — and aggregates them into one report dict. Extracted from
the CLI so every surface an agent talks to (MCP tool, daemon route) can answer
"how much is NeuralMind saving?" without shelling out.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from neuralmind import memory

# NeuralMind's internal reference baseline per query (tokens a naive
# "load everything relevant" turn would spend). Kept identical to the CLI's
# historical constant so numbers don't shift between surfaces.
BASELINE_TOKENS_PER_QUERY = 50_000


def _events_file(project_path: Path, use_global: bool) -> Path:
    audit_file = project_path / ".neuralmind" / "audit_events.jsonl"
    if use_global:
        return memory.global_query_events_file()
    if audit_file.exists():
        return audit_file
    return memory.project_query_events_file(project_path)


def compute_savings(
    project_path: str | Path = ".",
    *,
    use_global: bool = False,
    cost: bool = False,
    model: str | None = None,
    queries_per_day: int = 100,
) -> dict[str, Any]:
    """Aggregate logged query/wakeup events into a savings report.

    Returns a dict shaped like the CLI's ``savings --json`` output. Missing
    log or zero events are reported in-band (``error`` / zero counts) rather
    than raised, so server surfaces can return the dict as-is.
    """
    project_path = Path(project_path).resolve()
    events_file = _events_file(project_path, use_global)

    if not events_file.exists():
        return {"error": "no event log found", "path": str(events_file)}

    est_full = BASELINE_TOKENS_PER_QUERY
    queries: list[dict[str, Any]] = []
    wakeups: list[dict[str, Any]] = []
    try:
        with events_file.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue

                # Handle two event log formats:
                # 1. audit_events.jsonl: {category, action, details: {tokens, ...}}
                # 2. query_events.jsonl: {event_type, retrieval_summary: {...}, ...}
                if "details" in rec and "action" in rec:
                    details = rec.get("details", {})
                    tokens = details.get("tokens", 0)
                    search_hits = details.get("search_hits", 0)
                    # Audit log doesn't store reduction_ratio; estimate from tokens
                    ratio = est_full / tokens if tokens > 0 else 0.0
                    if rec.get("action") == "wakeup":
                        wakeups.append({"tokens": tokens, "ratio": ratio})
                    else:
                        queries.append(
                            {
                                "query": details.get("question", ""),
                                "tokens": tokens,
                                "ratio": ratio,
                                "ts": rec.get("timestamp", ""),
                                "search_hits": search_hits,
                            }
                        )
                else:
                    rs = rec.get("retrieval_summary", {})
                    tokens = rs.get("tokens", 0)
                    ratio = rs.get("reduction_ratio", 0.0)
                    if rec.get("event_type") == "wakeup":
                        wakeups.append({"tokens": tokens, "ratio": ratio})
                    else:
                        queries.append(
                            {
                                "query": rec.get("query", ""),
                                "tokens": tokens,
                                "ratio": ratio,
                                "ts": rec.get("timestamp", ""),
                            }
                        )
    except OSError as exc:
        return {"error": f"could not read {events_file}: {exc}", "path": str(events_file)}

    total_events = len(queries) + len(wakeups)
    if total_events == 0:
        return {"queries": 0, "total_tokens_saved": 0, "log": str(events_file)}

    total_tokens_used = sum(e["tokens"] for e in queries + wakeups)
    total_full_cost = total_events * est_full
    total_saved = total_full_cost - total_tokens_used
    avg_ratio = sum(e["ratio"] for e in queries) / len(queries) if queries else 0.0

    out: dict[str, Any] = {
        "project": project_path.name,
        "scope": "global" if use_global else project_path.name,
        "log": str(events_file),
        "total_queries": len(queries),
        "total_wakeups": len(wakeups),
        "total_tokens_used": total_tokens_used,
        "est_total_full_cost": total_full_cost,
        "total_tokens_saved": total_saved,
        "avg_reduction_ratio": round(avg_ratio, 1),
        "baseline_disclosure": "Reduction ratios are calculated against a hardcoded assumed baseline of 50,000 tokens per query (the 'full codebase' estimate), not a measured value. Real baselines vary by codebase size.",
        "recent_queries": queries[-5:],
    }

    if cost:
        # --queries-per-day is a *query* volume assumption; scale it by the
        # per-query average, not the per-event one, so a log with wakeups
        # mixed in doesn't dilute the projection (wakeups log ~0 tokens
        # saved, so counting them in the average understates $/day).
        query_tokens_used = sum(e["tokens"] for e in queries)
        query_tokens_baseline = len(queries) * est_full
        dollar_info = memory.estimate_dollar_savings(
            tokens_used=total_tokens_used,
            tokens_baseline=total_full_cost,
            events=total_events,
            model=model or memory.DEFAULT_PRICING_MODEL,
            queries_per_day=queries_per_day,
            query_tokens_saved=query_tokens_baseline - query_tokens_used,
            query_count=len(queries),
        )
        # Make the estimate basis machine-readable: only the with-NM cost is
        # measured from logged tokens; without-NM — and therefore
        # saved/projected — is estimated from the fixed per-query baseline.
        out["dollar_savings"] = {
            **dollar_info,
            "baseline_tokens_per_query": est_full,
            "estimated": True,
            "basis": (
                "with-NM cost is measured from logged tokens; without-NM (and "
                "saved/projected) is estimated from the fixed per-query baseline"
            ),
        }

    return out
