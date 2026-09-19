"""store.py — Decision Store (SQLite-backed rationale persistence).

A persistent, queryable store for architectural decisions made in a project.
Decisions capture *why* a codebase is shaped a way it is — the rationale that
otherwise lives only in a human's head or a scrolled-past chat. Storing them
means an agent touching that code later can recall the original reason instead
of re-deriving, re-asking, or silently undoing the decision.

Storage:
- SQLite at ``<project>/.neuralmind/memory.db``
- ``decisions`` table mirrors the ``DecisionRecord`` model
- FTS5 virtual table over ``title + rationale`` for full-text search
- Indexes on ``commit_sha``, ``status``, ``decision_type`` for fast filtering
- WAL mode + synchronous=NORMAL for concurrent-read safety (matches the
  SynapseStore / TraceStore pattern in this codebase)

Query strategy:
- FTS5 MATCH for text search (relevance-ranked via ``bm25()``)
- Fallback to LIKE-based scan when FTS5 is unavailable (old SQLite builds)
- Default filter excludes STALE and INVALIDATED decisions

Lifecycle:
- ``record()`` inserts a new ACTIVE decision
- ``query()`` searches by text with optional status / min-confidence filters
- ``audit()`` surfaces stale or orphaned decisions for review
- ``restore()`` re-anchors a decision to a new commit
- ``invalidate()`` marks a decision INVALIDATED (with reason logged)
- ``delete()`` hard-removes a record
- ``export()`` renders all decisions as Markdown (or returns JSON)

Fail-open: every read degrades gracefully on a missing/corrupt DB; writes are
best-effort so a DecisionStore failure never breaks the surrounding workflow.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from neuralmind.state_dir import ensure_parent_dir

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Data model (from TRD)
# --------------------------------------------------------------------------- #

VALID_DECISION_TYPES: frozenset[str] = frozenset(
    {
        "ARCHITECTURE",
        "DEPENDENCY",
        "TEST",
        "REFACTOR",
        "BUGFIX",
        "CONFIG",
    }
)

VALID_STATUSES: frozenset[str] = frozenset(
    {
        "ACTIVE",
        "STALE",
        "INVALIDATED",
    }
)

DEFAULT_DECISION_TYPE = "ARCHITECTURE"
DEFAULT_STATUS = "ACTIVE"


class DecisionRecord(BaseModel):
    """One persisted architectural decision.

    Mirrors the TRD data model exactly. All list fields default to empty
    lists (not shared references) so records are safe to mutate after
    construction.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    rationale: str
    commit_sha: str
    files_affected: list[str] = Field(default_factory=list)
    decision_type: str = Field(default=DEFAULT_DECISION_TYPE)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    status: str = Field(default=DEFAULT_STATUS)
    author: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evidence: list[str] = Field(default_factory=list)
    rejected_alternatives: list[str] = Field(default_factory=list)
    dependency_constraints: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    class Config:
        # Allow construction from dicts with datetime strings.
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #

# Schema version for this module. Bumped on additive schema changes.
SCHEMA_VERSION = 1

# Core decisions table — column order matches DecisionRecord fields so
# row → model mapping is positional in hot paths.
DECISIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    rationale TEXT NOT NULL,
    commit_sha TEXT NOT NULL,
    files_affected TEXT NOT NULL DEFAULT '[]',
    decision_type TEXT NOT NULL DEFAULT 'ARCHITECTURE',
    confidence REAL NOT NULL DEFAULT 1.0,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    author TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    evidence TEXT NOT NULL DEFAULT '[]',
    rejected_alternatives TEXT NOT NULL DEFAULT '[]',
    dependency_constraints TEXT NOT NULL DEFAULT '[]',
    tags TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_decisions_commit_sha ON decisions(commit_sha);
CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status);
CREATE INDEX IF NOT EXISTS idx_decisions_decision_type ON decisions(decision_type);
CREATE INDEX IF NOT EXISTS idx_decisions_created_at ON decisions(created_at);
"""

# FTS5 virtual table for full-text search over title + rationale.
# Non-content-linked: stores the decision `id` directly so we can join
# on it (works cleanly with TEXT PRIMARY KEY — content-linked FTS relies
# on integer rowid, which doesn't compose with text PKs).
FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS decisions_fts USING fts5(
    id UNINDEXED,
    title,
    rationale
);
"""

# Triggers to keep the FTS index in sync with the decisions table.
# The FTS table is non-content-linked (stores `id UNINDEXED` directly)
# so the triggers manage the FTS rows explicitly.
FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS decisions_ai AFTER INSERT ON decisions BEGIN
    INSERT INTO decisions_fts(id, title, rationale)
    VALUES (new.id, new.title, new.rationale);
END;
CREATE TRIGGER IF NOT EXISTS decisions_ad AFTER DELETE ON decisions BEGIN
    DELETE FROM decisions_fts WHERE id = old.id;
END;
CREATE TRIGGER IF NOT EXISTS decisions_au AFTER UPDATE ON decisions BEGIN
    DELETE FROM decisions_fts WHERE id = old.id;
    INSERT INTO decisions_fts(id, title, rationale)
    VALUES (new.id, new.title, new.rationale);
END;
"""

# Meta table row for schema version tracking (shared with other .neuralmind modules).
META_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# Stale threshold: decisions not updated in this many days are considered stale.
STALE_DAYS = 90


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _row_to_record(row: tuple) -> DecisionRecord:
    """Convert a raw SQLite row tuple to a DecisionRecord.

    Column order matches DECISIONS_SCHEMA exactly. JSON-list columns are
    decoded; datetime columns are parsed from ISO-8601 strings.
    """
    return DecisionRecord(
        id=row[0],
        title=row[1],
        rationale=row[2],
        commit_sha=row[3],
        files_affected=json.loads(row[4]) if row[4] else [],
        decision_type=row[5],
        confidence=row[6],
        status=row[7],
        author=row[8],
        created_at=_parse_iso(row[9]),
        updated_at=_parse_iso(row[10]),
        evidence=json.loads(row[11]) if row[11] else [],
        rejected_alternatives=json.loads(row[12]) if row[12] else [],
        dependency_constraints=json.loads(row[13]) if row[13] else [],
        tags=json.loads(row[14]) if row[14] else [],
    )


def _parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 datetime string, tolerating trailing 'Z' and microsecond variants."""
    if not value:
        return datetime.now(timezone.utc)
    # Python 3.11+ handles Z suffix and most ISO variants natively.
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


def _format_iso(dt: datetime) -> str:
    """Format a datetime as ISO-8601 UTC string."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _fts_available(conn: sqlite3.Connection) -> bool:
    """Check whether FTS5 is available in this SQLite build."""
    try:
        conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='decisions_fts'")
        # The above only confirms the table exists; actually test FTS5 works:
        conn.execute("SELECT * FROM decisions_fts LIMIT 0")
        return True
    except Exception:
        return False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# DecisionStore
# --------------------------------------------------------------------------- #


class DecisionStore:
    """SQLite-backed store for project-level architectural decisions.

    Construct once per project path. Safe to share across threads/hooks;
    each call opens a short-lived connection (WAL mode allows concurrent
    readers + a single writer). Fail-open: a read returns [] on any DB
    error; a write silently no-ops rather than crashing the caller.

    Args:
        project_path: Root of the project. The DB lives at
            ``<project_path>/.neuralmind/memory.db``.
    """

    def __init__(self, project_path: str) -> None:
        self.project_path = Path(project_path).resolve()
        db_path = self.project_path / ".neuralmind" / "memory.db"
        self.db_path: Path = db_path
        ensure_parent_dir(self.db_path)
        self._init_schema()

    # ------------------------------------------------------------------ #
    # Connection management
    # ------------------------------------------------------------------ #

    @contextmanager
    def _connect(self):
        """Open a SQLite connection with WAL + synchronous=NORMAL.

        Matches the SynapseStore / TraceStore pattern so concurrent readers
        (hooks + MCP server + CLI) don't block each other.
        """
        conn = sqlite3.connect(self.db_path, timeout=30.0, isolation_level=None)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            yield conn
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Schema
    # ------------------------------------------------------------------ #

    def _init_schema(self) -> None:
        """Create tables, indexes, FTS virtual table, and triggers.

        Idempotent: every statement uses IF NOT EXISTS. Only creates the
        FTS5 virtual table when the SQLite build supports it.
        """
        with self._connect() as conn:
            conn.executescript(META_SCHEMA)
            conn.executescript(DECISIONS_SCHEMA)
            # FTS5 may not be available in all SQLite builds (some minimal
            # Docker / Alpine images ship without it). Fail open: skip FTS
            # if the CREATE VIRTUAL TABLE raises, and the query() method
            # falls back to LIKE.
            try:
                conn.executescript(FTS_SCHEMA)
                conn.executescript(FTS_TRIGGERS)
            except sqlite3.OperationalError:
                pass  # FTS5 unavailable — LIKE fallback handles queries.
            self._stamp_schema_version(conn)

    @staticmethod
    def _stamp_schema_version(conn: sqlite3.Connection) -> None:
        """Record the schema version in the meta table (read-only upsert)."""
        cur = conn.execute("SELECT value FROM meta WHERE key='decision_store_schema_version'")
        row = cur.fetchone()
        try:
            recorded = int(row[0]) if row is not None else 0
        except (TypeError, ValueError):
            recorded = 0
        if recorded < SCHEMA_VERSION:
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES ('decision_store_schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #

    def record(
        self,
        title: str,
        rationale: str,
        commit_sha: str,
        *,
        files_affected: list[str] | None = None,
        decision_type: str = DEFAULT_DECISION_TYPE,
        confidence: float = 1.0,
        status: str = DEFAULT_STATUS,
        author: str | None = None,
        evidence: list[str] | None = None,
        rejected_alternatives: list[str] | None = None,
        dependency_constraints: list[str] | None = None,
        tags: list[str] | None = None,
        id: str | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> DecisionRecord:
        """Insert a new decision. Returns the constructed DecisionRecord.

        Args:
            title: Short summary of the decision (e.g. "Use per-handler auth").
            rationale: The *why* — the reasoning that won't be obvious later.
            commit_sha: Git SHA anchoring the decision to a specific state.
            files_affected: Paths of files this decision concerns.
            decision_type: One of VALID_DECISION_TYPES.
            confidence: 0.0–1.0 certainty that this decision is correct.
            status: One of VALID_STATUSES.
            author: Optional identifier for who made the decision.
            evidence: URLs / refs / doc lines supporting the decision.
            rejected_alternatives: Brief descriptions of paths not taken.
            dependency_constraints: Hard constraints this decision depends on.
            tags: Free-form labels for filtering.
            id: Optional explicit UUID (auto-generated if not provided).
            created_at: Optional explicit timestamp (defaults to now).
            updated_at: Optional explicit timestamp (defaults to now).
        """
        now = datetime.now(timezone.utc)
        files_affected_norm = [f.replace("\\", "/") for f in (files_affected or [])]
        rec = DecisionRecord(
            id=id or str(uuid.uuid4()),
            title=title,
            rationale=rationale,
            commit_sha=commit_sha,
            files_affected=files_affected_norm,
            decision_type=(
                decision_type if decision_type in VALID_DECISION_TYPES else DEFAULT_DECISION_TYPE
            ),
            confidence=max(0.0, min(1.0, confidence)),
            status=status if status in VALID_STATUSES else DEFAULT_STATUS,
            author=author,
            created_at=created_at or now,
            updated_at=updated_at or now,
            evidence=list(evidence or []),
            rejected_alternatives=list(rejected_alternatives or []),
            dependency_constraints=list(dependency_constraints or []),
            tags=list(tags or []),
        )
        try:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO decisions
                       (id, title, rationale, commit_sha, files_affected,
                        decision_type, confidence, status, author,
                        created_at, updated_at, evidence, rejected_alternatives,
                        dependency_constraints, tags)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        rec.id,
                        rec.title,
                        rec.rationale,
                        rec.commit_sha,
                        json.dumps(rec.files_affected),
                        rec.decision_type,
                        rec.confidence,
                        rec.status,
                        rec.author,
                        _format_iso(rec.created_at),
                        _format_iso(rec.updated_at),
                        json.dumps(rec.evidence),
                        json.dumps(rec.rejected_alternatives),
                        json.dumps(rec.dependency_constraints),
                        json.dumps(rec.tags),
                    ),
                )
        except Exception:
            # Fail-open: a write failure must never crash the caller, but it
            # MUST be visible — the update() silent-no-op bug (066a48b) hid
            # here. Log with traceback for diagnosis.
            logger.exception("[memory] record() failed for decision %s — not persisted", rec.id)
        return rec

    # ------------------------------------------------------------------ #
    # Status updates
    # ------------------------------------------------------------------ #

    def update_status(self, decision_id: str, status: str) -> None:
        """Update a decision's status."""
        if status not in VALID_STATUSES:
            return
        try:
            with self._connect() as conn:
                conn.execute(
                    """UPDATE decisions
                       SET status = ?, updated_at = ?
                       WHERE id = ?""",
                    (status, _now_iso(), decision_id),
                )
        except Exception:
            logger.exception(
                "[memory] update_status(%s, %s) failed — status unchanged",
                decision_id,
                status,
            )

    def update(self, decision: DecisionRecord) -> None:
        """Update all fields of a decision record."""
        try:
            with self._connect() as conn:
                conn.execute(
                    """UPDATE decisions
                       SET title = ?, rationale = ?, commit_sha = ?,
                           files_affected = ?, decision_type = ?,
                           confidence = ?, status = ?, author = ?,
                           updated_at = ?, evidence = ?,
                           rejected_alternatives = ?,
                           dependency_constraints = ?, tags = ?
                       WHERE id = ?""",
                    (
                        decision.title,
                        decision.rationale,
                        decision.commit_sha,
                        json.dumps(decision.files_affected),
                        decision.decision_type,
                        decision.confidence,
                        decision.status,
                        decision.author,
                        _now_iso(),
                        json.dumps(decision.evidence),
                        json.dumps(decision.rejected_alternatives),
                        json.dumps(decision.dependency_constraints),
                        json.dumps(decision.tags),
                        decision.id,
                    ),
                )
        except Exception:
            logger.exception("[memory] update(%s) failed — decision not persisted", decision.id)

    def invalidate(self, decision_id: str, reason: str = "") -> None:
        """Mark a decision INVALIDATED.

        The reason is appended to the decision's evidence list so the
        invalidation itself carries context — future readers can see *why*
        a decision was retired. No-op if the id doesn't exist.
        """
        reason = reason.strip()
        note = f"Invalidated: {reason}" if reason else "Invalidated"
        try:
            with self._connect() as conn:
                conn.execute(
                    """UPDATE decisions
                       SET status = 'INVALIDATED',
                           updated_at = ?,
                           evidence = json_insert(evidence, '$[#]', ?)
                       WHERE id = ?""",
                    (_now_iso(), note, decision_id),
                )
        except Exception:
            logger.exception("[memory] invalidate(%s) failed — decision still active", decision_id)

    def restore(self, decision_id: str, new_commit_sha: str) -> DecisionRecord:
        """Re-anchor a decision to a new commit and reset its status to ACTIVE.

        Useful after a cherry-pick / rebase where the original commit no
        longer exists in the current history but the decision still applies.
        Returns the updated record, or raises KeyError if not found.
        """
        now = _now_iso()
        try:
            with self._connect() as conn:
                conn.execute(
                    """UPDATE decisions
                       SET commit_sha = ?,
                           status = 'ACTIVE',
                           updated_at = ?,
                           evidence = json_insert(evidence, '$[#]', ?)
                       WHERE id = ?""",
                    (
                        new_commit_sha,
                        now,
                        f"Restored at commit {new_commit_sha}",
                        decision_id,
                    ),
                )
        except Exception:
            logger.exception("[memory] restore(%s) failed — decision not re-anchored", decision_id)
        restored = self.get(decision_id)
        if restored is None:
            raise KeyError(f"Decision not found: {decision_id}")
        return restored

    def delete(self, decision_id: str) -> None:
        """Hard-remove a decision. No-op if the id doesn't exist."""
        try:
            with self._connect() as conn:
                conn.execute("DELETE FROM decisions WHERE id = ?", (decision_id,))
        except Exception:
            logger.exception("[memory] delete(%s) failed — record still present", decision_id)

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #

    def get(self, decision_id: str) -> DecisionRecord | None:
        """Fetch a single decision by id, or None if not found."""
        try:
            with self._connect() as conn:
                cur = conn.execute(
                    """SELECT id, title, rationale, commit_sha, files_affected,
                              decision_type, confidence, status, author,
                              created_at, updated_at, evidence,
                              rejected_alternatives, dependency_constraints, tags
                       FROM decisions WHERE id = ?""",
                    (decision_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return _row_to_record(row)
        except Exception:
            logger.exception("[memory] get(%s) failed — returning None", decision_id)
            return None

    # ------------------------------------------------------------------ #
    # Invalidation Engine support
    # ------------------------------------------------------------------ #

    def find_by_files(
        self, files: list[str], include_invalidated: bool = False
    ) -> list[DecisionRecord]:
        """Return decisions whose files_affected overlap the given paths.

        Used by the InvalidationEngine to find decisions that may be
        stale after a file change. The files_affected column is stored
        as a JSON array, so we use json_each for efficient overlap
        detection.

        Args:
            files: List of file paths to check.
            include_invalidated: If True, include INVALIDATED decisions
                in the result. The invalidation engine sets this to False
                (already-handled decisions are irrelevant), but the
                stale-guard sets it True so it can surface all non-ACTIVE
                decisions before an edit.
        """
        if not files:
            return []
        records: list[DecisionRecord] = []
        try:
            with self._connect() as conn:
                # Use json_each to expand files_affected and match
                # against the changed files list.
                placeholders = ", ".join(["?"] * len(files))
                invalidated_clause = "" if include_invalidated else "AND d.status != 'INVALIDATED'"
                cur = conn.execute(
                    f"""SELECT DISTINCT d.id, d.title, d.rationale, d.commit_sha, d.files_affected,
                              d.decision_type, d.confidence, d.status, d.author,
                              d.created_at, d.updated_at, d.evidence,
                              d.rejected_alternatives, d.dependency_constraints, d.tags
                       FROM decisions d, json_each(d.files_affected) je
                       WHERE je.value IN ({placeholders})
                       {invalidated_clause}
                       ORDER BY d.created_at DESC""",
                    files,
                )
                records = [_row_to_record(row) for row in cur.fetchall()]
        except Exception:
            logger.exception(
                "[memory] find_by_files() failed — returning [] (invalidation "
                "may miss decisions for: %s)",
                files,
            )
        return records

    def find_dependents(self, decision_id: str) -> list[DecisionRecord]:
        """Return decisions that depend on the given decision_id.

        A dependent is a decision whose dependency_constraints includes
        the given decision_id. Used by the InvalidationEngine to cascade
        invalidation through the decision graph.
        """
        records: list[DecisionRecord] = []
        try:
            with self._connect() as conn:
                cur = conn.execute(
                    """SELECT DISTINCT d.id, d.title, d.rationale, d.commit_sha, d.files_affected,
                              d.decision_type, d.confidence, d.status, d.author,
                              d.created_at, d.updated_at, d.evidence,
                              d.rejected_alternatives, d.dependency_constraints, d.tags
                       FROM decisions d, json_each(d.dependency_constraints) je
                       WHERE je.value = ?
                       AND d.status != 'INVALIDATED'
                       ORDER BY d.created_at DESC""",
                    (decision_id,),
                )
                records = [_row_to_record(row) for row in cur.fetchall()]
        except Exception:
            logger.exception(
                "[memory] find_dependents(%s) failed — returning [] (cascade "
                "invalidation may miss dependents)",
                decision_id,
            )
        return records

    def find_stale(self) -> list[DecisionRecord]:
        """Return all decisions with status STALE."""
        try:
            with self._connect() as conn:
                cur = conn.execute("""SELECT id, title, rationale, commit_sha, files_affected,
                              decision_type, confidence, status, author,
                              created_at, updated_at, evidence,
                              rejected_alternatives, dependency_constraints, tags
                       FROM decisions
                       WHERE status = 'STALE'
                       ORDER BY updated_at ASC""")
                return [_row_to_record(row) for row in cur.fetchall()]
        except Exception:
            return []

    def query(
        self,
        text: str,
        limit: int = 5,
        status: str = "ACTIVE",
        min_score: float = 0.0,
    ) -> list[DecisionRecord]:
        """Search decisions by full-text query.

        Uses FTS5 when available (relevance-ranked via bm25()), falling back
        to a LIKE scan otherwise. By default only ACTIVE decisions are
        returned; pass ``status=None`` to include all statuses.

        Args:
            text: Search query (title + rationale are searched).
            limit: Maximum records to return.
            status: Filter by status ("ACTIVE", "STALE", "INVALIDATED"),
                or None to include all.
            min_score: Minimum confidence threshold (0.0–1.0). Records below
                this confidence are excluded.
        """
        if not text or not text.strip():
            return []

        text = text.strip()
        records: list[DecisionRecord] = []

        try:
            with self._connect() as conn:
                if _fts_available(conn):
                    records = self._query_fts(conn, text, limit, status, min_score)
                else:
                    records = self._query_like(conn, text, limit, status, min_score)
        except Exception:
            logger.exception(
                "[memory] query(%r) failed — returning [] (agent will not see "
                "any decisions for this query)",
                text,
            )
            return []
        return records

    def _query_fts(
        self,
        conn: sqlite3.Connection,
        text: str,
        limit: int,
        status: str | None,
        min_score: float,
    ) -> list[DecisionRecord]:
        """FTS5-backed relevance-ranked search.

        bm25() returns lower-is-better; we use ASC ordering so the most
        relevant result comes first. The MATCH query uses prefix matching so
        partial words work; tokens are double-quoted to escape FTS5 special
        characters (hyphens, etc.).
        """
        import re

        # Extract alphanumeric tokens (preserve original case for search).
        tokens = re.findall(r"[A-Za-z0-9_]+", text)
        if not tokens:
            return []
        # Quote each token to escape FTS5 special chars, then add prefix.
        match_query = " ".join(f'"{t}"*' for t in tokens)

        clauses: list[str] = ["d.id = f.id"]
        params: list[Any] = []

        clauses.append("decisions_fts MATCH ?")
        params.append(match_query)

        if status is not None:
            clauses.append("d.status = ?")
            params.append(status)

        if min_score > 0.0:
            clauses.append("d.confidence >= ?")
            params.append(min_score)

        where = " AND ".join(clauses)

        cur = conn.execute(
            f"""SELECT d.id, d.title, d.rationale, d.commit_sha, d.files_affected,
                       d.decision_type, d.confidence, d.status, d.author,
                       d.created_at, d.updated_at, d.evidence,
                       d.rejected_alternatives, d.dependency_constraints, d.tags
                FROM decisions_fts f
                JOIN decisions d ON d.id = f.id
                WHERE {where}
                ORDER BY bm25(decisions_fts) ASC
                LIMIT ?""",
            (*params, limit),
        )

        return [_row_to_record(row) for row in cur.fetchall()]

    def _query_like(
        self,
        conn: sqlite3.Connection,
        text: str,
        limit: int,
        status: str | None,
        min_score: float,
    ) -> list[DecisionRecord]:
        """LIKE-based fallback for SQLite builds without FTS5.

        Orders by created_at DESC (most recent first) as a rough proxy for
        relevance when we can't rank by text match.
        """
        clauses: list[str] = ["(title LIKE ? OR rationale LIKE ?)"]
        like_pattern = f"%{text}%"
        params: list[Any] = [like_pattern, like_pattern]

        if status is not None:
            clauses.append("status = ?")
            params.append(status)

        if min_score > 0.0:
            clauses.append("confidence >= ?")
            params.append(min_score)

        where = " AND ".join(clauses)

        cur = conn.execute(
            f"""SELECT id, title, rationale, commit_sha, files_affected,
                       decision_type, confidence, status, author,
                       created_at, updated_at, evidence,
                       rejected_alternatives, dependency_constraints, tags
                FROM decisions
                WHERE {where}
                ORDER BY created_at DESC
                LIMIT ?""",
            (*params, limit),
        )

        return [_row_to_record(row) for row in cur.fetchall()]

    def audit(
        self,
        stale_only: bool = False,
        orphaned_only: bool = False,
    ) -> list[DecisionRecord]:
        """Review decisions that may need attention.

        Args:
            stale_only: Return only STALE decisions (past STALE_DAYS since
                last update).
            orphaned_only: Return ACTIVE decisions whose commit_sha does
                not exist in the current git history (requires git).

        Returns:
            Matching decisions ordered by updated_at DESC (oldest first).
        """
        records: list[DecisionRecord] = []
        try:
            with self._connect() as conn:
                if stale_only:
                    records = self._audit_stale(conn)
                elif orphaned_only:
                    records = self._audit_orphaned(conn)
                else:
                    # Return both stale + orphaned when neither flag is set.
                    records = self._audit_stale(conn) + self._audit_orphaned(conn)
        except Exception:
            logger.exception(
                "[memory] audit() failed — returning [] (stale/orphaned "
                "decisions will not be surfaced)"
            )
            return []
        # Deduplicate (a decision could be both stale and orphaned).
        seen: set[str] = set()
        deduped: list[DecisionRecord] = []
        for rec in records:
            if rec.id not in seen:
                seen.add(rec.id)
                deduped.append(rec)
        return deduped

    def list_all(self, status: str | None = None) -> list[DecisionRecord]:
        """List all decisions, optionally filtered by status.

        Unlike ``audit()``, this returns every decision (including healthy ACTIVE ones).

        Args:
            status: Optional status filter ("ACTIVE", "STALE", "INVALIDATED").
                If None, returns decisions of all statuses.

        Returns:
            All matching decisions ordered by created_at DESC.
        """
        try:
            with self._connect() as conn:
                if status is not None:
                    cur = conn.execute(
                        """SELECT id, title, rationale, commit_sha, files_affected,
                                  decision_type, confidence, status, author,
                                  created_at, updated_at, evidence,
                                  rejected_alternatives, dependency_constraints, tags
                           FROM decisions
                           WHERE status = ?
                           ORDER BY created_at DESC""",
                        (status,),
                    )
                else:
                    cur = conn.execute("""SELECT id, title, rationale, commit_sha, files_affected,
                                  decision_type, confidence, status, author,
                                  created_at, updated_at, evidence,
                                  rejected_alternatives, dependency_constraints, tags
                           FROM decisions
                           ORDER BY created_at DESC""")
                return [_row_to_record(row) for row in cur.fetchall()]
        except Exception:
            logger.exception(
                "[memory] list_all(status=%s) failed — returning []",
                status,
            )
            return []

    def _audit_stale(self, conn: sqlite3.Connection) -> list[DecisionRecord]:
        """Find decisions whose updated_at is older than STALE_DAYS."""

        cutoff = (
            datetime.now(timezone.utc) - __import__("datetime").timedelta(days=STALE_DAYS)
        ).isoformat()
        cur = conn.execute(
            """SELECT id, title, rationale, commit_sha, files_affected,
                       decision_type, confidence, status, author,
                       created_at, updated_at, evidence,
                       rejected_alternatives, dependency_constraints, tags
                FROM decisions
                WHERE status = 'ACTIVE' AND updated_at < ?
                ORDER BY updated_at ASC""",
            (cutoff,),
        )
        return [_row_to_record(row) for row in cur.fetchall()]

    def _audit_orphaned(self, conn: sqlite3.Connection) -> list[DecisionRecord]:
        """Find ACTIVE decisions whose commit_sha is not in git history.

        Requires git to be available and the project to be a git repo.
        Silently returns empty list when git is unavailable (fail-open).
        """
        import subprocess

        # Collect all commit SHAs in the project.
        try:
            result = subprocess.run(
                ["git", "rev-list", "--all"],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return []

        if result.returncode != 0:
            return []

        valid_shas: set[str] = set(result.stdout.splitlines())

        # Find ACTIVE decisions with commit_sha not in the valid set.
        cur = conn.execute(
            """SELECT id, title, rationale, commit_sha, files_affected,
                       decision_type, confidence, status, author,
                       created_at, updated_at, evidence,
                       rejected_alternatives, dependency_constraints, tags
                FROM decisions
                WHERE status = 'ACTIVE'""",
        )

        orphaned: list[DecisionRecord] = []
        for row in cur.fetchall():
            rec = _row_to_record(row)
            if rec.commit_sha not in valid_shas:
                orphaned.append(rec)
        return orphaned

    # ------------------------------------------------------------------ #
    # Export
    # ------------------------------------------------------------------ #

    def export(self, format: str = "md", output: str | None = None) -> str:
        """Render all ACTIVE decisions as Markdown or JSON.

        Args:
            format: "md" (default) or "json".
            output: Optional file path to write to. If None, returns the
                rendered string directly.

        Returns:
            The rendered string (Markdown or JSON).
        """
        records = self._get_all_active()

        if format == "json":
            payload = [json.loads(rec.json()) for rec in records]
            content = json.dumps(payload, indent=2, default=str)
        else:
            content = self._render_markdown(records)

        if output:
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            Path(output).write_text(content, encoding="utf-8")

        return content

    def _get_all_active(self) -> list[DecisionRecord]:
        """Fetch all ACTIVE decisions ordered by created_at DESC."""
        try:
            with self._connect() as conn:
                cur = conn.execute("""SELECT id, title, rationale, commit_sha, files_affected,
                               decision_type, confidence, status, author,
                               created_at, updated_at, evidence,
                               rejected_alternatives, dependency_constraints, tags
                        FROM decisions
                        WHERE status = 'ACTIVE'
                        ORDER BY created_at DESC""")
                return [_row_to_record(row) for row in cur.fetchall()]
        except Exception:
            return []

    def _render_markdown(self, records: list[DecisionRecord]) -> str:
        """Render a list of DecisionRecords as Markdown."""
        if not records:
            return "# Decision Store\n\nNo active decisions.\n"

        lines: list[str] = ["# Decision Store", ""]
        lines.append(f"_{len(records)} active decision(s)._")
        lines.append("")

        for rec in records:
            lines.append(f"## {rec.title}")
            lines.append("")
            lines.append(f"- **Type**: `{rec.decision_type}`")
            lines.append(f"- **Confidence**: {rec.confidence:.0%}")
            lines.append(f"- **Commit**: `{rec.commit_sha[:7] if rec.commit_sha else '—'}`")
            if rec.author:
                lines.append(f"- **Author**: {rec.author}")
            if rec.tags:
                tag_str = " ".join(f"`{t}`" for t in rec.tags)
                lines.append(f"- **Tags**: {tag_str}")
            if rec.files_affected:
                lines.append(f"- **Files**: {', '.join(f'`{f}`' for f in rec.files_affected)}")
            lines.append("")
            lines.append(rec.rationale)
            lines.append("")

            if rec.evidence:
                lines.append("**Evidence:**")
                for e in rec.evidence:
                    lines.append(f"- {e}")
                lines.append("")

            if rec.rejected_alternatives:
                lines.append("**Rejected alternatives:**")
                for alt in rec.rejected_alternatives:
                    lines.append(f"- {alt}")
                lines.append("")

            if rec.dependency_constraints:
                lines.append("**Constraints:**")
                for c in rec.dependency_constraints:
                    lines.append(f"- {c}")
                lines.append("")

            lines.append(f"*Created: {rec.created_at.strftime('%Y-%m-%d')}*")
            lines.append("")

        return "\n".join(lines)
