"""
traces.py — Immutable reasoning trace store (PRD 2 A1).

An immutable `reasoning_traces` table in synapses.db:
  (session_id, timestamp, query_fingerprint, strategy, tools_used, outcome, success_signal)

Powers "the agent learned what works." Queryable by the synapse recall path
so retrieval can favor nodes from successful past strategies. Schema-versioned
alongside the existing meta table. **Fail-open**: traces are observational,
never load-bearing — a failure here must never break query/build/search.

Pure and stdlib-only: uses the same SQLite-backed SynapseStore connection
pattern as the synapse layer itself.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Schema additions for the traces table (added to the existing SCHEMA in synapses.py)
TRACES_SCHEMA = """
CREATE TABLE IF NOT EXISTS reasoning_traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    query_fingerprint TEXT NOT NULL,
    strategy TEXT NOT NULL DEFAULT 'unknown',
    tools_used TEXT NOT NULL DEFAULT '[]',
    outcome TEXT NOT NULL DEFAULT 'unknown',
    success_signal REAL NOT NULL DEFAULT 0.0
);
CREATE INDEX IF NOT EXISTS idx_traces_session ON reasoning_traces(session_id);
CREATE INDEX IF NOT EXISTS idx_traces_fingerprint ON reasoning_traces(query_fingerprint);
CREATE INDEX IF NOT EXISTS idx_traces_timestamp ON reasoning_traces(timestamp);
CREATE INDEX IF NOT EXISTS idx_traces_success ON reasoning_traces(success_signal);
"""


def _fingerprint(query: str) -> str:
    """Stable fingerprint for a query string (short hash for grouping)."""
    return hashlib.sha256(query.encode("utf-8", "replace")).hexdigest()[:16]


@dataclass
class ReasoningTrace:
    """A single immutable reasoning trace record."""

    session_id: str
    timestamp: float
    query_fingerprint: str
    strategy: str = "unknown"
    tools_used: list[str] = field(default_factory=list)
    outcome: str = "unknown"
    success_signal: float = 0.0
    id: int | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "query_fingerprint": self.query_fingerprint,
            "strategy": self.strategy,
            "tools_used": list(self.tools_used),
            "outcome": self.outcome,
            "success_signal": round(self.success_signal, 4),
        }


class TraceStore:
    """Immutable reasoning trace store over the synapses.db connection.

    Writes are append-only (no update/delete API). Reads are queryable by
    session, fingerprint, or time window. Uses the same SQLite WAL pattern
    as SynapseStore.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0, isolation_level=None)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(TRACES_SCHEMA)

    def record(
        self,
        session_id: str,
        query: str,
        *,
        strategy: str = "unknown",
        tools_used: list[str] | None = None,
        outcome: str = "unknown",
        success_signal: float = 0.0,
        timestamp: float | None = None,
    ) -> ReasoningTrace:
        """Append a reasoning trace. Append-only: never raises on write."""
        ts = timestamp if timestamp is not None else time.time()
        fp = _fingerprint(query)
        tools = json.dumps(list(tools_used or []))
        try:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO reasoning_traces
                       (session_id, timestamp, query_fingerprint, strategy,
                        tools_used, outcome, success_signal)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (session_id, ts, fp, strategy, tools, outcome, success_signal),
                )
        except Exception:
            # Fail-open: trace recording must never break the query path.
            pass
        return ReasoningTrace(
            session_id=session_id,
            timestamp=ts,
            query_fingerprint=fp,
            strategy=strategy,
            tools_used=list(tools_used or []),
            outcome=outcome,
            success_signal=success_signal,
        )

    def query(
        self,
        *,
        session_id: str | None = None,
        fingerprint: str | None = None,
        strategy: str | None = None,
        outcome: str | None = None,
        since: float | None = None,
        until: float | None = None,
        min_success: float | None = None,
        limit: int = 100,
        order: str = "desc",
    ) -> list[ReasoningTrace]:
        """Query traces with optional filters. Returns newest-first by default."""
        clauses: list[str] = []
        params: list[Any] = []
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if fingerprint is not None:
            clauses.append("query_fingerprint = ?")
            params.append(fingerprint)
        if strategy is not None:
            clauses.append("strategy = ?")
            params.append(strategy)
        if outcome is not None:
            clauses.append("outcome = ?")
            params.append(outcome)
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since)
        if until is not None:
            clauses.append("timestamp <= ?")
            params.append(until)
        if min_success is not None:
            clauses.append("success_signal >= ?")
            params.append(min_success)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        direction = "DESC" if order == "desc" else "ASC"
        traces: list[ReasoningTrace] = []
        try:
            with self._connect() as conn:
                cur = conn.execute(
                    f"""SELECT id, session_id, timestamp, query_fingerprint,
                               strategy, tools_used, outcome, success_signal
                        FROM reasoning_traces
                        {where}
                        ORDER BY timestamp {direction}
                        LIMIT ?""",
                    (*params, limit),
                )
                for row in cur.fetchall():
                    traces.append(
                        ReasoningTrace(
                            id=row[0],
                            session_id=row[1],
                            timestamp=row[2],
                            query_fingerprint=row[3],
                            strategy=row[4],
                            tools_used=json.loads(row[5]) if row[5] else [],
                            outcome=row[6],
                            success_signal=row[7],
                        )
                    )
        except Exception:
            pass
        return traces

    def count(self, *, session_id: str | None = None) -> int:
        """Total trace count, optionally filtered by session."""
        try:
            with self._connect() as conn:
                if session_id:
                    cur = conn.execute(
                        "SELECT COUNT(*) FROM reasoning_traces WHERE session_id = ?",
                        (session_id,),
                    )
                else:
                    cur = conn.execute("SELECT COUNT(*) FROM reasoning_traces")
                return cur.fetchone()[0]
        except Exception:
            return 0

    def successful_fingerprints(
        self,
        *,
        min_success: float = 0.7,
        session_id: str | None = None,
        limit: int = 50,
    ) -> list[str]:
        """Return fingerprints of successful past queries (for recall boosting).

        Deduplicated — a fingerprint appearing N times in the traces still
        returns once in this list, so popular queries don't overweight recall.
        """
        seen: set[str] = set()
        results: list[str] = []
        for t in self.query(
            session_id=session_id,
            min_success=min_success,
            limit=limit * 2,  # fetch extra to cover dedup shrinkage
        ):
            if t.query_fingerprint not in seen:
                seen.add(t.query_fingerprint)
                results.append(t.query_fingerprint)
                if len(results) >= limit:
                    break
        return results
