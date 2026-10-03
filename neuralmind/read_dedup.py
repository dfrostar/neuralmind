"""read_dedup.py — Replace a repeat read of an unchanged file with a short stub.

In a long session an agent often reads a file it already has in context. The
``compress-read`` PostToolUse hook action uses this module to shorten that
repeat read: Claude Code's ``updatedToolOutput`` field replaces a tool result
before the model sees it, provided the value matches the tool's output shape
(for Read, ``{"type": "text", "file": {"filePath", "content", ...}}``). A value
that doesn't match is ignored and the original result goes through, so a
schema change in Claude Code degrades to "no dedup", never to a broken read.

What counts as a repeat, and what keeps it safe:

- **Scope** — one Claude Code session and one agent: rows are keyed on the
  hook payload's ``session_id`` plus ``agent_id``, which Claude Code sets
  inside subagents (a subagent's reads never enter the main conversation's
  context, and vice versa). A payload without a session id is never deduped.
- **Identity** — the SHA-256 of the exact text the Read returned, plus the
  read's ``offset``/``limit``/``pages``: another range of the same file is a
  different read, and any change to the file is a different hash.
- **Liveness** — a stub is never followed by another stub for the same read.
  The next repeat passes through in full, so an agent whose earlier copy has
  left its context gets the file back by reading it again.
- **Context resets** — the ``session-start`` and ``pre-compact`` hook actions
  drop the session's rows (:meth:`ReadCache.clear_session`): after a
  compaction or ``/clear`` the earlier result is gone from the context.
- **Age** — a full read older than ``MAX_AGE_SECS`` doesn't count.
- **Size** — reads shorter than ``MIN_CHARS`` are never stubbed; the stub
  would cost about as much as the content it replaces.

Storage: ``<project>/.neuralmind/read_cache.db`` (stdlib SQLite). Each
check-and-record runs in one ``BEGIN IMMEDIATE`` transaction, so parallel
hook processes for the same session can't interleave a read's state.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Reads shorter than this are never stubbed (the stub is ~350 characters).
MIN_CHARS = 2000
# A full read older than this no longer counts as "already in context".
MAX_AGE_SECS = 3600
# prune() drops rows untouched for this long, and caps the table at MAX_ROWS.
PRUNE_AGE_SECS = 86400
MAX_ROWS = 5000

READ_CACHE_FILENAME = "read_cache.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reads (
    session_id TEXT NOT NULL,
    agent_id TEXT NOT NULL DEFAULT '',
    path TEXT NOT NULL,
    view TEXT NOT NULL DEFAULT '',
    content_hash TEXT NOT NULL,
    reads INTEGER NOT NULL DEFAULT 1,
    delivered_at REAL NOT NULL,
    last_seen REAL NOT NULL,
    stubbed INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (session_id, agent_id, path, view)
);
CREATE INDEX IF NOT EXISTS idx_reads_last_seen ON reads(last_seen);
"""


@dataclass(frozen=True)
class RepeatRead:
    """A read that repeats the last full read of the same content.

    Attributes:
        reads: Times this content has been read in this session, this one included.
        delivered_at: When the agent last received the content in full (epoch).
    """

    reads: int
    delivered_at: float


def read_cache_path(project_path: str | Path) -> Path:
    """Path of the project's read-dedup database."""
    return Path(project_path) / ".neuralmind" / READ_CACHE_FILENAME


def content_hash(text: str) -> str:
    """SHA-256 of the text a Read returned."""
    return hashlib.sha256(text.encode("utf-8", errors="surrogatepass")).hexdigest()


def read_view(tool_input: dict) -> str:
    """The part of a file a Read asked for, as a stable key ("" for a plain read)."""
    view = [tool_input.get(key) for key in ("offset", "limit", "pages")]
    if not any(v not in (None, "", 0) for v in view):
        return ""
    return json.dumps(view, sort_keys=True, default=str)


def find_read_text(tool_response: Any) -> str | None:
    """The text a Read returned, or None when there is no text to dedup.

    Claude Code nests a text read under ``file.content``; the older flat
    ``{"content": ...}`` shape is accepted too. Images, notebooks and PDFs
    carry no ``content`` string and are never deduped.
    """
    if not isinstance(tool_response, dict):
        return None
    file_part = tool_response.get("file")
    if isinstance(file_part, dict):
        text = file_part.get("content")
        return text if isinstance(text, str) else None
    text = tool_response.get("content")
    return text if isinstance(text, str) else None


def replace_read_text(tool_response: dict, new_text: str) -> dict:
    """Copy of ``tool_response`` with its text swapped for ``new_text``.

    Only the text (and, in Claude Code's shape, the line count that describes
    it) changes, so the value keeps the shape of the tool's own output.
    """
    updated = copy.deepcopy(tool_response)
    file_part = updated.get("file")
    if isinstance(file_part, dict):
        file_part["content"] = new_text
        if isinstance(file_part.get("numLines"), int):
            file_part["numLines"] = new_text.count("\n") + 1
    else:
        updated["content"] = new_text
    return updated


def dedup_stub(file_path: str, repeat: RepeatRead, project_path: str | Path | None = None) -> str:
    """The text an agent sees in place of a repeat read."""
    shown = str(file_path)
    if project_path:
        try:
            shown = str(Path(file_path).resolve().relative_to(Path(project_path).resolve()))
        except (ValueError, OSError):
            pass
    at = time.strftime("%H:%M:%S", time.localtime(repeat.delivered_at))
    return (
        f"[neuralmind read-dedup] {shown} is unchanged since you read it at {at} in "
        "this session, so that earlier result is still current and this repeat "
        "read was shortened. If the earlier result is no longer in your context, "
        "read the file again: the next read returns it in full."
    )


class ReadCache:
    """Per-project record of which reads each session has already received."""

    def __init__(self, project_path: str | Path):
        self.db_path = read_cache_path(project_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        # A short busy timeout: a hook must never stall a tool call. On
        # contention the caller's try/except treats the read as a miss.
        conn = sqlite3.connect(self.db_path, timeout=1.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def observe(
        self,
        session_id: str,
        agent_id: str,
        path: str,
        view: str,
        digest: str,
        now: float | None = None,
    ) -> RepeatRead | None:
        """Record a read and say whether it repeats the last full delivery.

        Returns a :class:`RepeatRead` when the same agent in the same session
        already received this exact content less than ``MAX_AGE_SECS`` ago and
        that delivery wasn't itself followed by a stub. Otherwise records the
        read as a full delivery and returns None.
        """
        ts = time.time() if now is None else now
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT content_hash, reads, delivered_at, stubbed FROM reads "
                "WHERE session_id = ? AND agent_id = ? AND path = ? AND view = ?",
                (session_id, agent_id, path, view),
            ).fetchone()
            key = (session_id, agent_id, path, view)
            if row is None or row[0] != digest or ts - row[2] > MAX_AGE_SECS:
                conn.execute(
                    "INSERT OR REPLACE INTO reads (session_id, agent_id, path, view, "
                    "content_hash, reads, delivered_at, last_seen, stubbed) "
                    "VALUES (?, ?, ?, ?, ?, 1, ?, ?, 0)",
                    (*key, digest, ts, ts),
                )
                repeat = None
            elif row[3]:
                # The previous repeat was stubbed: this one goes through in
                # full, so re-reading always recovers the content.
                conn.execute(
                    "UPDATE reads SET reads = reads + 1, delivered_at = ?, last_seen = ?, "
                    "stubbed = 0 WHERE session_id = ? AND agent_id = ? AND path = ? "
                    "AND view = ?",
                    (ts, ts, *key),
                )
                repeat = None
            else:
                conn.execute(
                    "UPDATE reads SET reads = reads + 1, last_seen = ?, stubbed = 1 "
                    "WHERE session_id = ? AND agent_id = ? AND path = ? AND view = ?",
                    (ts, *key),
                )
                repeat = RepeatRead(reads=int(row[1]) + 1, delivered_at=float(row[2]))
            conn.execute("COMMIT")
            return repeat
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def clear_session(self, session_id: str) -> int:
        """Forget every read in a session (all its agents). Returns rows removed."""
        conn = self._connect()
        try:
            return conn.execute("DELETE FROM reads WHERE session_id = ?", (session_id,)).rowcount
        finally:
            conn.close()

    def prune(self, now: float | None = None) -> int:
        """Drop rows untouched for ``PRUNE_AGE_SECS``, then cap at ``MAX_ROWS``."""
        ts = time.time() if now is None else now
        conn = self._connect()
        try:
            removed = conn.execute(
                "DELETE FROM reads WHERE last_seen < ?", (ts - PRUNE_AGE_SECS,)
            ).rowcount
            removed += conn.execute(
                "DELETE FROM reads WHERE rowid IN (SELECT rowid FROM reads "
                "ORDER BY last_seen DESC LIMIT -1 OFFSET ?)",
                (MAX_ROWS,),
            ).rowcount
            return removed
        finally:
            conn.close()

    def stats(self) -> dict:
        """Row and session counts, for diagnostics."""
        conn = self._connect()
        try:
            rows, sessions = conn.execute(
                "SELECT COUNT(*), COUNT(DISTINCT session_id) FROM reads"
            ).fetchone()
        finally:
            conn.close()
        return {"rows": int(rows), "sessions": int(sessions), "db_path": str(self.db_path)}
