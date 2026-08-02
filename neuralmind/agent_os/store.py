"""store.py — Unified SQLite persistence for Agent OS.

Single-thread-safe SQLite database replacing the scattered JSONL stores.
Fixes: state loss on restart (D17), thread-safety (C21), cascade cleanup (D20),
and audit integrity (D19).

Schema:
    signals — Page-Hinkley signal records + detector state
    insights — correlator hypotheses
    proposals — improvement proposals
    experiments — A/B experiment results
    promotions — promotion/rollback records
    tuner_incumbents — current best-known tunable values
    adversarial_queries — generated stress cases
    audit_log — governance audit trail

Every table carries tenant_id for row-level isolation (F2/S32 fix).

Usage:
    store = AgentOSStore(Path.home() / ".neuralmind" / "agent-os.db")
    store.insert_signal("tenant_a", signal.to_dict())
    store.persist_signal_state("tenant_a", metric_name, state_dict)
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_SCHEMA_VERSION = 2

_SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    signal_ts REAL NOT NULL,
    metric_name TEXT NOT NULL,
    value REAL NOT NULL,
    baseline REAL NOT NULL,
    delta REAL NOT NULL,
    severity REAL NOT NULL,
    level TEXT NOT NULL DEFAULT 'info',
    acknowledged INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_signals_tenant ON signals (tenant_id);
CREATE INDEX IF NOT EXISTS idx_signals_metric ON signals (tenant_id, metric_name);
CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals (tenant_id, signal_ts);

CREATE TABLE IF NOT EXISTS signal_states (
    tenant_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    running_sum REAL NOT NULL DEFAULT 0.0,
    m2 REAL NOT NULL DEFAULT 0.0,
    min_cum_dev REAL NOT NULL DEFAULT 0.0,
    max_cum_dev REAL NOT NULL DEFAULT 0.0,
    lambda_threshold REAL NOT NULL DEFAULT 4.0,
    last_signal_at REAL NOT NULL DEFAULT 0.0,
    cooldown_seconds REAL NOT NULL DEFAULT 60.0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (tenant_id, metric_name)
);

CREATE TABLE IF NOT EXISTS insights (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    signal_id TEXT,
    insight_ts REAL NOT NULL,
    hypothesis TEXT NOT NULL,
    cause_type TEXT NOT NULL,
    cause_ref TEXT NOT NULL,
    confidence REAL NOT NULL,
    details TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_insights_tenant ON insights (tenant_id);
CREATE INDEX IF NOT EXISTS idx_insights_signal ON insights (signal_id);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    title TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    baseline_tag TEXT NOT NULL,
    candidate_tag TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    baseline_value REAL NOT NULL,
    candidate_value REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed',
    signal_count INTEGER NOT NULL DEFAULT 0,
    tags TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_proposals_tenant ON proposals (tenant_id);
CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals (tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_proposals_metric ON proposals (tenant_id, metric_name);

CREATE TABLE IF NOT EXISTS experiments (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    proposal_id TEXT,
    metric_name TEXT NOT NULL,
    baseline_value REAL NOT NULL,
    candidate_value REAL NOT NULL,
    delta REAL NOT NULL,
    p_value REAL,
    ci_lower REAL,
    ci_upper REAL,
    verdict TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT NOT NULL,
    details TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_experiments_tenant ON experiments (tenant_id);
CREATE INDEX IF NOT EXISTS idx_experiments_proposal ON experiments (proposal_id);
CREATE INDEX IF NOT EXISTS idx_experiments_verdict ON experiments (tenant_id, verdict);

CREATE TABLE IF NOT EXISTS promotions (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    experiment_id TEXT,
    status TEXT NOT NULL,
    delta REAL NOT NULL,
    message TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_promotions_tenant ON promotions (tenant_id);

CREATE TABLE IF NOT EXISTS tuner_incumbents (
    tenant_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    value REAL NOT NULL,
    tag TEXT NOT NULL,
    history TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (tenant_id, metric_name)
);

CREATE TABLE IF NOT EXISTS adversarial_queries (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    query TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    source_hypothesis TEXT,
    cause_type TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_adversarial_tenant ON adversarial_queries (tenant_id);

CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    details TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_log (tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log (created_at);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);
"""


class AgentOSStore:
    """Thread-safe SQLite-backed persistence for Agent OS.

    Replaces JSONL stores with atomic, crash-safe operations.
    All writes go through a single lock (daemon is single-process).
    """

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            env_path = os.environ.get("NEURALMIND_AGENTOS_DIR")
            if env_path:
                db_path = Path(env_path) / "agent-os.db"
            else:
                # Use daemon home as base directory
                daemon_home = os.environ.get("NEURALMIND_DAEMON_HOME")
                if daemon_home:
                    db_path = Path(daemon_home) / "agent-os.db"
                else:
                    db_path = Path.home() / ".neuralmind" / "agent-os.db"
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self._db_path), timeout=30, check_same_thread=False
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    @contextmanager
    def _tx(self) -> Any:
        """Transactional context — atomic commit/rollback."""
        conn = self._get_conn()
        with self._lock:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def _init_db(self) -> None:
        """Create schema if needed."""
        # Ensure parent directory exists
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._tx() as conn:
            conn.executescript(_SCHEMA)
            # Check/set schema version
            row = conn.execute("SELECT version FROM schema_version").fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (_SCHEMA_VERSION,),
                )

    # ── signals ────────────────────────────────────────────────────

    def insert_signal(self, tenant_id: str, signal_dict: dict[str, Any]) -> None:
        with self._tx() as conn:
            conn.execute(
                """INSERT INTO signals
                   (id, tenant_id, signal_ts, metric_name, value, baseline,
                    delta, severity, level, acknowledged)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    signal_dict["signal_id"],
                    tenant_id,
                    signal_dict["timestamp"],
                    signal_dict["metric_name"],
                    signal_dict["value"],
                    signal_dict["baseline"],
                    signal_dict["delta"],
                    signal_dict["severity"],
                    signal_dict["level"],
                    int(signal_dict.get("acknowledged", False)),
                ),
            )

    def get_signals(self, tenant_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT * FROM signals WHERE tenant_id = ? ORDER BY signal_ts",
                (tenant_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_signals_by_metric(
        self, tenant_id: str, metric_name: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._get_conn().execute(
                """SELECT * FROM signals
                   WHERE tenant_id = ? AND metric_name = ?
                   ORDER BY signal_ts DESC LIMIT ?""",
                (tenant_id, metric_name, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── signal state (Page-Hinkley persistence) ───────────────────

    def persist_signal_state(
        self, tenant_id: str, metric_name: str, state: dict[str, Any]
    ) -> None:
        """Save Page-Hinkley state after every push. Crash-safe."""
        with self._tx() as conn:
            conn.execute(
                """INSERT INTO signal_states
                   (tenant_id, metric_name, count, running_sum, m2,
                    min_cum_dev, max_cum_dev, lambda_threshold,
                    last_signal_at, cooldown_seconds, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                   ON CONFLICT(tenant_id, metric_name) DO UPDATE SET
                   count = excluded.count,
                   running_sum = excluded.running_sum,
                   m2 = excluded.m2,
                   min_cum_dev = excluded.min_cum_dev,
                   max_cum_dev = excluded.max_cum_dev,
                   lambda_threshold = excluded.lambda_threshold,
                   last_signal_at = excluded.last_signal_at,
                   cooldown_seconds = excluded.cooldown_seconds,
                   updated_at = excluded.updated_at""",
                (
                    tenant_id,
                    metric_name,
                    state["count"],
                    state["running_sum"],
                    state["m2"],
                    state["min_cum_dev"],
                    state["max_cum_dev"],
                    state["lambda_threshold"],
                    state["last_signal_at"],
                    state["cooldown_seconds"],
                ),
            )

    def get_signal_state(self, tenant_id: str, metric_name: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._get_conn().execute(
                "SELECT * FROM signal_states WHERE tenant_id = ? AND metric_name = ?",
                (tenant_id, metric_name),
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def get_all_signal_states(
        self, tenant_id: str
    ) -> dict[str, dict[str, Any]]:
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT * FROM signal_states WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchall()
        return {r["metric_name"]: dict(r) for r in rows}

    # ── insights ───────────────────────────────────────────────────

    def insert_insight(
        self, tenant_id: str, insight_dict: dict[str, Any]
    ) -> None:
        with self._tx() as conn:
            conn.execute(
                """INSERT INTO insights
                   (id, tenant_id, signal_id, insight_ts, hypothesis,
                    cause_type, cause_ref, confidence, details)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    insight_dict["insight_id"],
                    tenant_id,
                    insight_dict["signal_id"],
                    datetime.fromisoformat(insight_dict["ts"]).timestamp(),
                    insight_dict["hypothesis"],
                    insight_dict["cause_type"],
                    insight_dict["cause_ref"],
                    insight_dict["confidence"],
                    json.dumps(insight_dict.get("details", {})),
                ),
            )

    def get_insights(self, tenant_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT * FROM insights WHERE tenant_id = ? ORDER BY insight_ts",
                (tenant_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── proposals ──────────────────────────────────────────────────

    def create_proposal(
        self,
        tenant_id: str,
        title: str,
        hypothesis: str,
        baseline_tag: str,
        candidate_tag: str,
        metric_name: str,
        baseline_value: float,
        candidate_value: float,
        tags: list[str] | None = None,
        signal_count: int = 0,
    ) -> dict[str, Any]:
        proposal = {
            "proposal_id": f"prop_{uuid.uuid4().hex[:12]}",
            "tenant_id": tenant_id,
            "title": title,
            "hypothesis": hypothesis,
            "baseline_tag": baseline_tag,
            "candidate_tag": candidate_tag,
            "metric_name": metric_name,
            "baseline_value": baseline_value,
            "candidate_value": candidate_value,
            "status": "proposed",
            "signal_count": signal_count,
            "tags": tags or [],
        }
        with self._tx() as conn:
            conn.execute(
                """INSERT INTO proposals
                   (id, tenant_id, title, hypothesis, baseline_tag,
                    candidate_tag, metric_name, baseline_value,
                    candidate_value, status, signal_count, tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    proposal["proposal_id"],
                    tenant_id,
                    title,
                    hypothesis,
                    baseline_tag,
                    candidate_tag,
                    metric_name,
                    baseline_value,
                    candidate_value,
                    "proposed",
                    signal_count,
                    json.dumps(tags or []),
                ),
            )
        return proposal

    def list_proposals(
        self,
        tenant_id: str,
        status: str | None = None,
        metric_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """O(1) per call — uses indexed query, not O(n) scan."""
        query = "SELECT * FROM proposals WHERE tenant_id = ?"
        params: list[Any] = [tenant_id]
        if status:
            query += " AND status = ?"
            params.append(status)
        if metric_name:
            query += " AND metric_name = ?"
            params.append(metric_name)
        query += " ORDER BY created_at DESC"
        with self._lock:
            rows = self._get_conn().execute(query, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["proposal_id"] = d.pop("id")
            result.append(d)
        return result

    def get_proposal(self, tenant_id: str, proposal_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._get_conn().execute(
                "SELECT * FROM proposals WHERE tenant_id = ? AND id = ?",
                (tenant_id, proposal_id),
            ).fetchone()
        if row is None:
            return None
        d = dict(row)
        # Rename id → proposal_id for API compatibility
        d["proposal_id"] = d.pop("id")
        return d

    def update_proposal(
        self, tenant_id: str, proposal_id: str, changes: dict[str, Any]
    ) -> dict[str, Any] | None:
        # Read-modify-write inside the lock
        with self._tx() as conn:
            row = conn.execute(
                "SELECT * FROM proposals WHERE tenant_id = ? AND id = ?",
                (tenant_id, proposal_id),
            ).fetchone()
            if row is None:
                return None
            current = dict(row)
            current.update(changes)
            current["updated_at"] = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """UPDATE proposals SET
                   title=?, hypothesis=?, baseline_tag=?, candidate_tag=?,
                   metric_name=?, baseline_value=?, candidate_value=?,
                   status=?, signal_count=?, tags=?, updated_at=?
                   WHERE tenant_id=? AND id=?""",
                (
                    current["title"],
                    current["hypothesis"],
                    current["baseline_tag"],
                    current["candidate_tag"],
                    current["metric_name"],
                    current["baseline_value"],
                    current["candidate_value"],
                    current["status"],
                    current["signal_count"],
                    json.dumps(current.get("tags", [])),
                    current["updated_at"],
                    tenant_id,
                    proposal_id,
                ),
            )
        return current

    def increment_signal_count(
        self, tenant_id: str, proposal_id: str
    ) -> dict[str, Any] | None:
        with self._tx() as conn:
            row = conn.execute(
                "SELECT signal_count FROM proposals WHERE tenant_id = ? AND id = ?",
                (tenant_id, proposal_id),
            ).fetchone()
            if row is None:
                return None
            new_count = row["signal_count"] + 1
            conn.execute(
                """UPDATE proposals SET signal_count = ?, updated_at = datetime('now')
                   WHERE tenant_id = ? AND id = ?""",
                (new_count, tenant_id, proposal_id),
            )
            return self.get_proposal(tenant_id, proposal_id)

    # ── experiments ────────────────────────────────────────────────

    def insert_experiment(
        self, tenant_id: str, result_dict: dict[str, Any]
    ) -> None:
        with self._tx() as conn:
            conn.execute(
                """INSERT INTO experiments
                   (id, tenant_id, proposal_id, metric_name, baseline_value,
                    candidate_value, delta, p_value, ci_lower, ci_upper,
                    verdict, started_at, ended_at, details)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result_dict["experiment_id"],
                    tenant_id,
                    result_dict["proposal_id"],
                    result_dict["metric_name"],
                    result_dict["baseline_value"],
                    result_dict["candidate_value"],
                    result_dict["delta"],
                    result_dict.get("p_value"),
                    result_dict.get("ci_lower"),
                    result_dict.get("ci_upper"),
                    result_dict["verdict"],
                    result_dict["started_at"],
                    result_dict["ended_at"],
                    json.dumps(result_dict.get("details", {})),
                ),
            )

    def get_experiments(self, tenant_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT * FROM experiments WHERE tenant_id = ? ORDER BY created_at DESC",
                (tenant_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_experiment_history_for_metric(
        self, tenant_id: str, metric_name: str
    ) -> list[dict[str, Any]]:
        """Get historical deltas for a metric (used by p-value calculation)."""
        with self._lock:
            rows = self._get_conn().execute(
                """SELECT * FROM experiments
                   WHERE tenant_id = ? AND metric_name = ?
                   ORDER BY created_at""",
                (tenant_id, metric_name),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── promotions ─────────────────────────────────────────────────

    def insert_promotion(
        self, tenant_id: str, record_dict: dict[str, Any]
    ) -> None:
        with self._tx() as conn:
            conn.execute(
                """INSERT INTO promotions
                   (id, tenant_id, experiment_id, status, delta, message)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    record_dict["promotion_id"],
                    tenant_id,
                    record_dict["experiment_id"],
                    record_dict["status"],
                    record_dict["delta"],
                    record_dict.get("message", ""),
                ),
            )

    def get_promotions(self, tenant_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT * FROM promotions WHERE tenant_id = ? ORDER BY created_at DESC",
                (tenant_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── tuner incumbents ───────────────────────────────────────────

    def persist_incumbent(
        self,
        tenant_id: str,
        metric_name: str,
        value: float,
        tag: str,
        history: list[dict[str, Any]],
    ) -> None:
        with self._tx() as conn:
            conn.execute(
                """INSERT INTO tuner_incumbents
                   (tenant_id, metric_name, value, tag, history, updated_at)
                   VALUES (?, ?, ?, ?, ?, datetime('now'))
                   ON CONFLICT(tenant_id, metric_name) DO UPDATE SET
                   value = excluded.value,
                   tag = excluded.tag,
                   history = excluded.history,
                   updated_at = excluded.updated_at""",
                (tenant_id, metric_name, value, tag, json.dumps(history)),
            )

    def get_incumbent(
        self, tenant_id: str, metric_name: str
    ) -> dict[str, Any] | None:
        with self._lock:
            row = self._get_conn().execute(
                "SELECT * FROM tuner_incumbents WHERE tenant_id = ? AND metric_name = ?",
                (tenant_id, metric_name),
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    # ── adversarial queries ────────────────────────────────────────

    def insert_adversarial_query(
        self, tenant_id: str, record: dict[str, Any]
    ) -> None:
        with self._tx() as conn:
            conn.execute(
                """INSERT INTO adversarial_queries
                   (id, tenant_id, query, metric_name, source_hypothesis,
                    cause_type)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    record.get("query_id", f"adv_{uuid.uuid4().hex[:12]}"),
                    tenant_id,
                    record["query"],
                    record.get("metric_name", ""),
                    record.get("source_hypothesis", ""),
                    record.get("cause_type", "unknown"),
                ),
            )

    def get_adversarial_queries(
        self, tenant_id: str
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT * FROM adversarial_queries WHERE tenant_id = ? ORDER BY created_at DESC",
                (tenant_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── audit log ──────────────────────────────────────────────────

    def audit(
        self,
        tenant_id: str,
        actor: str,
        action: str,
        target: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Append to audit log. Fail-closed: raises on error."""
        try:
            with self._tx() as conn:
                conn.execute(
                    """INSERT INTO audit_log
                       (id, tenant_id, actor, action, target, details)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        f"aud_{uuid.uuid4().hex[:12]}",
                        tenant_id,
                        actor,
                        action,
                        target,
                        json.dumps(details or {}),
                    ),
                )
        except Exception as exc:
            # Audit failures must surface, not silently drop
            log.error("AUDIT FAILURE: actor=%s action=%s target=%s error=%s", actor, action, target, exc)
            raise  # fail-closed: audit logging must never silently fail

    def get_audit_log(self, tenant_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT * FROM audit_log WHERE tenant_id = ? ORDER BY created_at DESC",
                (tenant_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── cascade cleanup (D20 fix) ──────────────────────────────────

    def delete_tenant(self, tenant_id: str) -> int:
        """Delete all data for a tenant. Returns rows deleted."""
        with self._tx() as conn:
            tables = [
                "signals", "signal_states", "insights", "proposals",
                "experiments", "promotions", "tuner_incumbents",
                "adversarial_queries", "audit_log",
            ]
            total = 0
            for table in tables:
                cursor = conn.execute(
                    f"DELETE FROM {table} WHERE tenant_id = ?", (tenant_id,)
                )
                total += cursor.rowcount
        return total

    # ── close ──────────────────────────────────────────────────────

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


# Module-level singleton for process-wide use
_store: AgentOSStore | None = None


def get_store(db_path: Path | None = None) -> AgentOSStore:
    """Get the module-level store singleton."""
    global _store
    if db_path is None:
        import os
        env_path = os.environ.get("NEURALMIND_AGENTOS_DIR")
        if env_path:
            db_path = Path(env_path) / "agent-os.db"
        else:
            daemon_home = os.environ.get("NEURALMIND_DAEMON_HOME")
            if daemon_home:
                db_path = Path(daemon_home) / "agent-os.db"
            else:
                db_path = Path.home() / ".neuralmind" / "agent-os.db"
    if _store is None:
        _store = AgentOSStore(db_path)
    elif db_path is not None and _store._db_path != db_path:
        _store.close()
        _store = AgentOSStore(db_path)
    return _store


def reset_store() -> None:
    """Reset the singleton (for tests)."""
    global _store
    if _store is not None:
        _store.close()
    _store = None
