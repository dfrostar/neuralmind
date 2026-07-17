"""
F3 — Tool-use metrics pipeline.

Continuous JSONL logging: per-query latency, retrieval reuse rate,
tool-call success rate, per-query token cost, synapse activation counts.
Bounded retention in `.neuralmind/metrics/`.
Feeds C1 fitness + E1 scoring.

Local-first. Stdlib-only. Fail-open.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

METRICS_DIR_NAME = "metrics"
METRICS_RETENTION_DAYS = 30
METRICS_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


def metrics_dir(project_path: str | Path) -> Path:
    """Return the metrics directory for a project."""
    return Path(project_path) / ".neuralmind" / METRICS_DIR_NAME


def _day_key(ts: float | None = None) -> str:
    """Return a YYYY-MM-DD key for metrics file naming."""
    ts = ts if ts is not None else time.time()
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


def _metrics_file(project_path: str | Path, day_key: str | None = None) -> Path:
    """Return the metrics file path for a given day."""
    key = day_key or _day_key()
    return metrics_dir(project_path) / f"metrics_{key}.jsonl"


class MetricsCollector:
    """
    Collects and persists per-query tool-use metrics to JSONL files
    under `.neuralmind/metrics/`. Files are named by UTC day for easy
    rotation and bounded retention.
    
    Fail-open: failed metric writes are silently dropped so a metrics
    failure never breaks the query path.
    """

    def __init__(
        self,
        project_path: str | Path | None = None,
        retention_days: float = METRICS_RETENTION_DAYS,
        max_bytes: int = METRICS_MAX_BYTES,
    ):
        self.project_path = Path(project_path) if project_path else None
        self.retention_days = retention_days
        self.max_bytes = max_bytes

    def _append(self, payload: dict[str, Any]) -> bool:
        """Append a JSONL record to today's metrics file. Fail-open."""
        if self.project_path is None:
            return False
        try:
            path = _metrics_file(self.project_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, sort_keys=True) + "\n")
            return True
        except Exception:
            return False

    def log_query_metrics(
        self,
        *,
        session_id: str,
        query: str,
        latency_ms: float,
        retrieval_reuse_rate: float,
        tool_calls: int,
        tool_successes: int,
        tokens_used: int,
        synapses_activated: int,
    ) -> bool:
        """Log metrics for a single query event."""
        return self._append({
            "event": "query",
            "ts": time.time(),
            "session_id": session_id,
            "query": query,
            "latency_ms": round(latency_ms, 2),
            "retrieval_reuse_rate": round(retrieval_reuse_rate, 4),
            "tool_calls": tool_calls,
            "tool_successes": tool_successes,
            "tokens_used": tokens_used,
            "synapses_activated": synapses_activated,
        })

    def log_build_metrics(
        self,
        *,
        duration_s: float,
        files_processed: int,
        synapse_edges: int,
        graph_edges: int,
    ) -> bool:
        """Log metrics for a build event."""
        return self._append({
            "event": "build",
            "ts": time.time(),
            "duration_s": round(duration_s, 2),
            "files_processed": files_processed,
            "synapse_edges": synapse_edges,
            "graph_edges": graph_edges,
        })

    def rotate(self) -> int:
        """
        Purge metrics files older than retention_days and truncate
        files exceeding max_bytes. Returns count of removed files.
        """
        if self.project_path is None:
            return 0
        metrics_path = metrics_dir(self.project_path)
        if not metrics_path.exists():
            return 0
        
        removed = 0
        cutoff_ts = time.time() - (self.retention_days * 86400)
        cutoff_day = time.strftime("%Y-%m-%d", time.gmtime(cutoff_ts))
        
        try:
            for f in sorted(metrics_path.glob("metrics_*.jsonl")):
                day_str = f.stem.replace("metrics_", "")
                if day_str < cutoff_day:
                    f.unlink()
                    removed += 1
                elif f.stat().st_size > self.max_bytes:
                    # Truncate to half max_bytes, keeping recent lines
                    lines = f.read_text(encoding="utf-8").splitlines()
                    keep = lines[-1000:] if len(lines) > 1000 else lines
                    f.write_text(
                        "\n".join(keep) + "\n" if keep else "",
                        encoding="utf-8",
                    )
        except Exception:
            pass
        return removed

    def summarize(
        self,
        days: int = 7,
        *,
        event_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Aggregate metrics from the last N days. Returns summary stats.
        Fail-open: returns zeros if no data available.
        """
        if self.project_path is None:
            return {}
        
        metrics_path = metrics_dir(self.project_path)
        if not metrics_path.exists():
            return {}
        
        cutoff = time.time() - (days * 86400)
        events: list[dict] = []
        
        try:
            for f in sorted(metrics_path.glob("metrics_*.jsonl")):
                with open(f, encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rec = json.loads(line)
                            if rec.get("ts", 0) >= cutoff:
                                if event_type is None or rec.get("event") == event_type:
                                    events.append(rec)
                        except (json.JSONDecodeError, TypeError):
                            continue
        except Exception:
            return {}
        
        if not events:
            return {"days": days, "n_events": 0}
        
        # Aggregate query events
        query_events = [e for e in events if e.get("event") == "query"]
        build_events = [e for e in events if e.get("event") == "build"]
        
        summary: dict[str, Any] = {"days": days, "n_events": len(events)}
        
        if query_events:
            latencies = [e["latency_ms"] for e in query_events if "latency_ms" in e]
            reuse = [e["retrieval_reuse_rate"] for e in query_events if "retrieval_reuse_rate" in e]
            tokens = [e["tokens_used"] for e in query_events if "tokens_used" in e]
            synapses_list = [e["synapses_activated"] for e in query_events if "synapses_activated" in e]
            
            summary["queries"] = {
                "n_queries": len(query_events),
                "mean_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0,
                "mean_retrieval_reuse_rate": round(sum(reuse) / len(reuse), 4) if reuse else 0,
                "mean_tokens_used": round(sum(tokens) / len(tokens)) if tokens else 0,
                "mean_synapses_activated": round(sum(synapses_list) / len(synapses_list), 1) if synapses_list else 0,
                "sum_tool_calls": sum(e.get("tool_calls", 0) for e in query_events),
                "sum_tool_successes": sum(e.get("tool_successes", 0) for e in query_events),
            }
        
        if build_events:
            durations = [e["duration_s"] for e in build_events if "duration_s" in e]
            summary["builds"] = {
                "n_builds": len(build_events),
                "mean_duration_s": round(sum(durations) / len(durations), 2) if durations else 0,
            }
        
        return summary
