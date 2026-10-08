"""
F3 — Tool-use metrics pipeline.

Continuous JSONL logging: per-query latency, retrieval reuse rate,
tool-call success rate, per-query token cost, synapse activation counts,
and how often prompt-time recall injected or abstained.
Bounded retention in `.neuralmind/metrics/`.
Feeds C1 fitness + E1 scoring.

Local-first. Stdlib-only. Fail-open.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from .recent_queries import _lock_byte0, _unlock_byte0

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]

METRICS_DIR_NAME = "metrics"
METRICS_RETENTION_DAYS = 30
METRICS_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
# One record's limit. The size check and the append share a best-effort
# cross-process lock; if it can't be had in time the record is appended
# anyway, so this bounds how far concurrent hook processes can overshoot the
# daily cap.
METRICS_MAX_RECORD_BYTES = 64 * 1024

# Serializes appends within this process. Every hook process appends to the
# same daily file, and Windows' CRT implements append mode as seek-to-end +
# write, so two handles writing at once can interleave and lose records.
_APPEND_LOCK = threading.Lock()


def _lock_file(fd: int) -> bool:
    """Best-effort cross-process lock on *fd*: flock on POSIX, byte 0 on Windows.

    Non-blocking with a short retry, so a stuck holder never stalls a hook.
    """
    if fcntl is None:
        return _lock_byte0(fd)
    for _ in range(50):  # ~50ms worst case
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            time.sleep(0.001)
    return False


def _unlock_file(fd: int) -> None:
    if fcntl is None:
        _unlock_byte0(fd)
        return
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass


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
            encoded = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
            if len(encoded) > min(METRICS_MAX_RECORD_BYTES, self.max_bytes):
                return False
            new_day = not path.exists()
            with _APPEND_LOCK:
                # O_BINARY: Windows would otherwise write "\r\n", past the bytes counted.
                flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0)
                fd = os.open(str(path), flags, 0o644)
                locked = False
                try:
                    locked = _lock_file(fd)
                    # Checked under the lock, against what other processes
                    # have committed. A record that would take today's file
                    # past the cap is dropped rather than rewrite a file
                    # other hook processes are appending to.
                    if os.fstat(fd).st_size + len(encoded) > self.max_bytes:
                        return False
                    os.write(fd, encoded)
                finally:
                    if locked:
                        _unlock_file(fd)
                    os.close(fd)
        except Exception:
            return False
        if new_day:
            # Once a day, when its file is started: the retention limits
            # apply without a separate cleanup step.
            self.rotate()
        return True

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
        return self._append(
            {
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
            }
        )

    def log_recall_metrics(
        self,
        *,
        outcome: str,
        injected: int,
        similarity: float,
    ) -> bool:
        """Log one prompt-time recall: ``injected``, or why it abstained.

        ``outcome`` is ``injected``, ``low_similarity`` (the prompt didn't
        match the code well enough) or ``no_neighbors`` (it matched, but no
        match had a file to name). No prompt text is kept.
        """
        return self._append(
            {
                "event": "recall",
                "ts": time.time(),
                "outcome": outcome,
                "injected": injected,
                "similarity": round(similarity, 4),
            }
        )

    def log_build_metrics(
        self,
        *,
        duration_s: float,
        files_processed: int,
        synapse_edges: int,
        graph_edges: int,
    ) -> bool:
        """Log metrics for a build event."""
        return self._append(
            {
                "event": "build",
                "ts": time.time(),
                "duration_s": round(duration_s, 2),
                "files_processed": files_processed,
                "synapse_edges": synapse_edges,
                "graph_edges": graph_edges,
            }
        )

    def rotate(self) -> int:
        """
        Purge metrics files older than retention_days and truncate
        files exceeding max_bytes. Returns count of removed files.

        Today's file is never rewritten: hook processes append to it
        concurrently, so it is capped by ``_append`` refusing records instead.
        """
        if self.project_path is None:
            return 0
        metrics_path = metrics_dir(self.project_path)
        if not metrics_path.exists():
            return 0

        removed = 0
        today = _metrics_file(self.project_path).name
        cutoff_ts = time.time() - (self.retention_days * 86400)
        cutoff_day = time.strftime("%Y-%m-%d", time.gmtime(cutoff_ts))

        try:
            for f in sorted(metrics_path.glob("metrics_*.jsonl")):
                day_str = f.stem.replace("metrics_", "")
                if day_str < cutoff_day:
                    f.unlink()
                    removed += 1
                elif f.name != today and f.stat().st_size > self.max_bytes:
                    self._truncate(f)
        except Exception:
            pass
        return removed

    def _truncate(self, path: Path) -> None:
        """Keep the newest whole records that fit in half the cap (at most 1,000).

        The file ends up well under the cap even when single records are
        large. The read and the rewrite hold the append lock, so a hook still
        appending to yesterday's file at midnight can't land a record between
        them. Without the lock it isn't truncated; the next rotation tries again.
        """
        with _APPEND_LOCK:
            fd = os.open(str(path), os.O_RDWR | getattr(os, "O_BINARY", 0))
            locked = False
            try:
                locked = _lock_file(fd)
                if not locked:
                    return
                with os.fdopen(fd, "r+b", closefd=False) as f:
                    text = f.read().decode("utf-8")
                    budget = self.max_bytes // 2
                    keep: list[str] = []
                    for line in reversed(text.splitlines()):
                        size = len(line.encode("utf-8")) + 1
                        if size > budget or len(keep) >= 1000:
                            break
                        keep.append(line)
                        budget -= size
                    keep.reverse()
                    f.seek(0)
                    f.truncate()
                    f.write(("\n".join(keep) + "\n" if keep else "").encode("utf-8"))
            finally:
                if locked:
                    _unlock_file(fd)
                os.close(fd)

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
        recall_events = [e for e in events if e.get("event") == "recall"]

        summary: dict[str, Any] = {"days": days, "n_events": len(events)}

        if query_events:
            latencies = [e["latency_ms"] for e in query_events if "latency_ms" in e]
            reuse = [e["retrieval_reuse_rate"] for e in query_events if "retrieval_reuse_rate" in e]
            tokens = [e["tokens_used"] for e in query_events if "tokens_used" in e]
            synapses_list = [
                e["synapses_activated"] for e in query_events if "synapses_activated" in e
            ]

            summary["queries"] = {
                "n_queries": len(query_events),
                "mean_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0,
                "mean_retrieval_reuse_rate": round(sum(reuse) / len(reuse), 4) if reuse else 0,
                "mean_tokens_used": round(sum(tokens) / len(tokens)) if tokens else 0,
                "mean_synapses_activated": (
                    round(sum(synapses_list) / len(synapses_list), 1) if synapses_list else 0
                ),
                "sum_tool_calls": sum(e.get("tool_calls", 0) for e in query_events),
                "sum_tool_successes": sum(e.get("tool_successes", 0) for e in query_events),
            }

        if build_events:
            durations = [e["duration_s"] for e in build_events if "duration_s" in e]
            summary["builds"] = {
                "n_builds": len(build_events),
                "mean_duration_s": round(sum(durations) / len(durations), 2) if durations else 0,
            }

        if recall_events:
            outcomes: dict[str, int] = {}
            for e in recall_events:
                key = str(e.get("outcome", "unknown"))
                outcomes[key] = outcomes.get(key, 0) + 1
            injected = outcomes.get("injected", 0)
            summary["recall"] = {
                "n_prompts": len(recall_events),
                "n_injected": injected,
                "abstain_rate": round(1 - injected / len(recall_events), 4),
                "outcomes": outcomes,
            }

        return summary
