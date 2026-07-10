"""
recent_queries.py — the recent-queries JSONL replay log
========================================================

Persistence for the graph-view UI's 'Replay last query' panel: each
query appends one JSON line describing the retrieval state the agent
actually received. Extracted from ``core.py``; the consent gate
(``NEURALMIND_MEMORY``) stays with the caller in
:meth:`neuralmind.core.NeuralMind._record_recent_query`, so this module
only ever sees writes the user has opted into.

Stdlib-only, like the rest of the synapse layer's support modules.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .context_selector import ContextResult

# Serializes recent-queries appends within this process. POSIX O_APPEND
# already makes single-line appends atomic, but Windows' CRT implements
# append mode as a separate seek-to-end + write, so two handles writing
# concurrently can interleave and lose lines.
_APPEND_LOCK = threading.Lock()

try:
    import msvcrt  # Windows-only: cross-process advisory lock below.
except ImportError:  # pragma: no cover - POSIX
    msvcrt = None  # type: ignore[assignment]


def _lock_byte0(fd: int) -> bool:
    """Best-effort cross-process mutex on byte 0 of *fd* (Windows only).

    POSIX writers don't need it (O_APPEND is atomic) and use flock for
    compaction instead; on Windows both the appender and the compactor
    take this same region so a compaction's read-truncate-rewrite can't
    drop a concurrent process's append. Non-blocking with a short retry
    so a stuck holder can never stall a query.
    """
    if msvcrt is None:
        return False
    import time as _time

    for _ in range(50):  # ~50ms worst case
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            _time.sleep(0.001)
    return False


def _unlock_byte0(fd: int) -> None:
    if msvcrt is None:
        return
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    except OSError:
        pass


def append_query_record(
    log_path: Path,
    question: str,
    result: ContextResult,
    *,
    max_entries: int,
    compact_bytes: int,
) -> None:
    """Append the last query's retrieval state to the recent-queries log.

    Powers the graph-view UI's 'Replay last query' panel: a human can
    see which nodes the agent actually received, including ids the
    UI can highlight on the canvas. Always on (local-only data,
    readable only through the auth-gated server).

    The hot path is a single-line O_APPEND write. On POSIX that is
    atomic across processes by itself (writes < PIPE_BUF don't
    tear); Windows' CRT implements append as seek-to-end + write,
    so writes are additionally serialized by a process-local lock
    and a best-effort cross-process byte-range lock. Trimming back
    to ``max_entries`` is a lazy compaction step gated by file
    size and protected by the same locks — see :func:`compact_log`.
    """
    try:
        hits = []
        for hit in (getattr(result, "top_search_hits", []) or [])[:12]:
            meta = hit.get("metadata") or {}
            hits.append(
                {
                    "id": str(hit.get("id", "")),
                    "label": meta.get("label", hit.get("id", "")),
                    "source_file": meta.get("source_file", ""),
                    "score": round(float(hit.get("score", 0.0)), 3),
                }
            )
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "question": question,
            "tokens": int(getattr(getattr(result, "budget", None), "total", 0)),
            "reduction_ratio": round(float(getattr(result, "reduction_ratio", 0.0)), 2),
            "layers_used": list(getattr(result, "layers_used", [])),
            "communities_loaded": list(getattr(result, "communities_loaded", [])),
            "top_hits": hits,
        }
        log_path.parent.mkdir(parents=True, exist_ok=True)
        encoded = (json.dumps(record, sort_keys=True) + "\n").encode("utf-8")
        with _APPEND_LOCK:
            fd = os.open(str(log_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
            locked = False
            try:
                locked = _lock_byte0(fd)
                os.write(fd, encoded)
            finally:
                if locked:
                    _unlock_byte0(fd)
                os.close(fd)
    except Exception:
        # Recording must never block the actual query.
        return
    try:
        compact_log(log_path, max_entries=max_entries, compact_bytes=compact_bytes)
    except Exception:
        pass


def compact_log(log_path: Path, *, max_entries: int, compact_bytes: int) -> None:
    """Trim the recent-queries log back to ``max_entries`` entries.

    Only runs when the file has grown past ``compact_bytes``, so the
    hot path stays append-only. The read-truncate-rewrite is guarded
    against another process's append by flock on POSIX and by the
    byte-0 region lock shared with :func:`append_query_record` on
    Windows; both are best-effort — worst case is a slightly
    oversized log file (no data loss).
    """
    try:
        size = log_path.stat().st_size
    except OSError:
        return
    if size <= compact_bytes:
        return
    try:
        import fcntl
    except ImportError:
        fcntl = None  # type: ignore[assignment]
    with _APPEND_LOCK, log_path.open("r+", encoding="utf-8") as f:
        if fcntl is not None:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            except OSError:
                pass
        locked = _lock_byte0(f.fileno())
        try:
            lines = [ln for ln in f if ln.strip()]
            if len(lines) <= max_entries:
                return
            f.seek(0)
            f.truncate()
            f.writelines(lines[-max_entries:])
            f.flush()
        finally:
            if locked:
                _unlock_byte0(f.fileno())
            if fcntl is not None:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass


def read_recent(log_path: Path, n: int = 20) -> list[dict]:
    """Return the N most-recent recorded queries, newest first."""
    if not log_path.exists():
        return []
    try:
        with log_path.open(encoding="utf-8") as f:
            lines = [line for line in f if line.strip()]
    except OSError:
        return []
    out: list[dict] = []
    for line in lines[-max(1, n) :]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    out.reverse()
    return out
