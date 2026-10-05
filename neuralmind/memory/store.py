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
- ``decision_vectors`` caches an embedding of ``title + rationale`` per
  decision for semantic search (``semantic.py``), filled on first search
- Indexes on ``commit_sha``, ``status``, ``decision_type`` for fast filtering
- WAL mode + synchronous=NORMAL for concurrent-read safety (matches the
  SynapseStore / TraceStore pattern in this codebase)

Query strategy (``search()``; ``query()`` returns just the records):
- ``mode="keyword"``: the query's words, minus stopwords, are the search
  terms; any term can match, so a question finds what its keywords would.
  FTS5 MATCH ranks by ``bm25()`` (decisions matching more of the terms rank
  first); a LIKE scan stands in when FTS5 is unavailable (old SQLite builds)
- ``mode="semantic"``: cosine similarity between the question and each
  decision's embedded title + rationale, local MiniLM model (``semantic.py``)
- ``mode="hybrid"`` (default): both rankings fused by reciprocal rank
  fusion; keyword results alone, with a notice, when the model isn't on disk
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
import re
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from neuralmind.state_dir import ensure_parent_dir

from . import semantic

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

# The status-filter word that means "every status". Callers (the CLI's
# ``--status ALL``, MCP's ``status: "all"``) pass it as a string; the store
# itself spells "every status" as ``None``.
STATUS_FILTER_ALL = "ALL"


def normalize_status_filter(status: str | None) -> str | None:
    """Turn a caller's status filter into the store's form.

    Case-insensitive. ``None``, an empty string and ``"all"`` mean every
    status and return ``None``; a valid status returns its canonical
    upper-case spelling. Anything else raises ``ValueError`` — an unknown
    filter used to reach SQL as-is and silently match nothing.
    """
    if status is None:
        return None
    value = str(status).strip().upper()
    if not value or value == STATUS_FILTER_ALL:
        return None
    if value not in VALID_STATUSES:
        valid = ", ".join([*sorted(VALID_STATUSES), STATUS_FILTER_ALL])
        raise ValueError(f"unknown status filter {status!r}; expected one of {valid}")
    return value


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

# What each decision saw: the git blob id of every affected file, taken when
# the decision is recorded, amended or restored. `decisions scan` compares it
# with what a commit contains — an equal blob means the commit carries exactly
# the code the decision describes, so that commit leaves it ACTIVE. Additive
# (CREATE IF NOT EXISTS), so existing stores pick it up on open.
FINGERPRINTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS decision_fingerprints (
    decision_id TEXT NOT NULL,
    path TEXT NOT NULL,
    blob TEXT NOT NULL,
    PRIMARY KEY (decision_id, path)
);
"""

# One embedding per decision for semantic search: the title + rationale as of
# ``content_sha``, by ``model_id``. A vector whose text or model no longer
# matches is recomputed on the next search, so amending a decision or
# switching models never compares stale vectors. Additive, like the
# fingerprints table; the trigger drops a decision's vector with it.
VECTORS_SCHEMA = """
CREATE TABLE IF NOT EXISTS decision_vectors (
    decision_id TEXT PRIMARY KEY,
    model_id TEXT NOT NULL,
    content_sha TEXT NOT NULL,
    dim INTEGER NOT NULL,
    vector BLOB NOT NULL
);
CREATE TRIGGER IF NOT EXISTS decisions_vectors_ad AFTER DELETE ON decisions BEGIN
    DELETE FROM decision_vectors WHERE decision_id = old.id;
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


# Dropped from a search before matching. Any term can match, so without
# this "how do we ..." would match nearly every decision ("we" is also a
# prefix of "weights"). This is NLTK's English stopword list: function words
# only, so a word that could name what a decision is about stays searchable.
# It includes contraction fragments ("what's" splits into "what" and "s"),
# which as prefixes would match every word starting with that letter.
_QUERY_STOPWORDS: frozenset[str] = frozenset("""
    i me my myself we our ours ourselves you your yours yourself yourselves
    he him his himself she her hers herself it its itself they them their
    theirs themselves what which who whom this that these those am is are was
    were be been being have has had having do does did doing a an the and but
    if or because as until while of at by for with about against between into
    through during before after above below to from up down in out on off
    over under again further then once here there when where why how all any
    both each few more most other some such no nor not only own same so than
    too very can will just should now
    s t d ll m o re ve y don ain aren couldn didn doesn hadn hasn haven isn
    ma mightn mustn needn shan shouldn wasn weren won wouldn
    """.split())


def _search_terms(text: str) -> list[str]:
    """The words a search matches on: lower-cased, de-duplicated, minus stopwords.

    A query made only of stopwords keeps them, so it still searches.
    """
    words = list(dict.fromkeys(w.lower() for w in re.findall(r"[A-Za-z0-9_]+", text)))
    return [w for w in words if w not in _QUERY_STOPWORDS] or words


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


@dataclass
class DecisionSearch:
    """What a search returned, and which mode produced it.

    ``mode`` is the mode that ranked ``records``; it differs from
    ``requested`` only when hybrid search fell back to keyword results, and
    then ``notice`` says why.
    """

    records: list[DecisionRecord]
    mode: str
    requested: str
    notice: str | None = None


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
        embedder: What semantic and hybrid search embed with. Defaults to
            the local MiniLM model, loaded on the first such search.
    """

    def __init__(
        self, project_path: str, *, embedder: semantic.DecisionEmbedder | None = None
    ) -> None:
        self.project_path = Path(project_path).resolve()
        db_path = self.project_path / ".neuralmind" / "memory.db"
        self.db_path: Path = db_path
        self._embedder = embedder
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
            conn.executescript(FINGERPRINTS_SCHEMA)
            conn.executescript(VECTORS_SCHEMA)
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
        self._capture_fingerprints(rec.id, rec.files_affected)
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
            return
        # An amended decision was re-read against the code as it is now.
        self._capture_fingerprints(decision.id, decision.files_affected)

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

    def mark_stale(self, decision_id: str, reason: str = "") -> bool:
        """Mark a decision STALE, keeping why in its evidence list.

        Used by the InvalidationEngine when a commit changes a decision's
        files: the note (e.g. "commit 1a2b3c4 changed auth.py after this
        decision was recorded") travels with the record, so ``audit`` and
        ``restore`` users can see what moved.

        Returns True only when the row was updated. A missing id, or a locked
        or corrupt store, returns False (logged), so the engine never reports
        a decision as STALE that the store still holds as ACTIVE.
        """
        reason = reason.strip()
        note = f"Marked STALE: {reason}" if reason else "Marked STALE"
        try:
            with self._connect() as conn:
                cur = conn.execute(
                    """UPDATE decisions
                       SET status = 'STALE',
                           updated_at = ?,
                           evidence = json_insert(evidence, '$[#]', ?)
                       WHERE id = ?""",
                    (_now_iso(), note, decision_id),
                )
                return bool(cur.rowcount > 0)
        except Exception:
            logger.exception("[memory] mark_stale(%s) failed — status unchanged", decision_id)
            return False

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
        # Restoring says "this still holds for the code as it is now".
        self._capture_fingerprints(restored.id, restored.files_affected)
        return restored

    def delete(self, decision_id: str) -> None:
        """Hard-remove a decision. No-op if the id doesn't exist."""
        try:
            with self._connect() as conn:
                conn.execute("DELETE FROM decisions WHERE id = ?", (decision_id,))
                conn.execute(
                    "DELETE FROM decision_fingerprints WHERE decision_id = ?", (decision_id,)
                )
        except Exception:
            logger.exception("[memory] delete(%s) failed — record still present", decision_id)

    # ------------------------------------------------------------------ #
    # File fingerprints (what a decision saw)
    # ------------------------------------------------------------------ #

    def _capture_fingerprints(self, decision_id: str, files: list[str]) -> None:
        """Record the git blob id of each affected file as it is right now.

        Replaces any earlier fingerprints for the decision. Files that don't
        exist, or a project git can't hash, simply get none — and a decision
        without a fingerprint for a changed file is never exempt from going
        STALE. Fail-open: a capture failure never breaks the write it follows.
        """
        try:
            from .invalidate import file_blob_ids

            blobs = file_blob_ids(self.project_path, files)
            with self._connect() as conn:
                conn.execute(
                    "DELETE FROM decision_fingerprints WHERE decision_id = ?", (decision_id,)
                )
                conn.executemany(
                    "INSERT INTO decision_fingerprints(decision_id, path, blob) VALUES (?, ?, ?)",
                    [(decision_id, path, blob) for path, blob in blobs.items()],
                )
        except Exception:
            logger.warning(
                "[memory] could not fingerprint files for decision %s — the commit that "
                "carries it will mark it STALE",
                decision_id,
            )

    def fingerprints(self, decision_id: str) -> dict[str, str]:
        """``{project-relative path: git blob id}`` captured for a decision."""
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT path, blob FROM decision_fingerprints WHERE decision_id = ?",
                    (decision_id,),
                ).fetchall()
        except Exception:
            return {}
        return dict(rows)

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
        status: str | None = "ACTIVE",
        min_score: float = 0.0,
        mode: str | None = None,
    ) -> list[DecisionRecord]:
        """Search decisions by keywords, a question, or meaning.

        ``search()`` without the report of which mode ran; see it for the
        modes, arguments and errors.
        """
        return self.search(text, limit=limit, status=status, min_score=min_score, mode=mode).records

    def search(
        self,
        text: str,
        limit: int = 5,
        status: str | None = "ACTIVE",
        min_score: float = 0.0,
        mode: str | None = None,
    ) -> DecisionSearch:
        """Search decisions' titles and rationales; say which mode ranked them.

        Modes:

        - ``keyword``: the query's words, minus stopwords ("how", "do",
          "the", …), are matched against title and rationale, and a
          decision needs only one of them, so a question works as well as
          keywords. FTS5 ranks by bm25() (decisions matching more of the
          words rank first); a LIKE scan stands in without FTS5.
        - ``semantic``: decisions ranked by cosine similarity between the
          question and their embedded title + rationale (local MiniLM
          model); those below ``semantic.MIN_SIMILARITY`` are left out, so
          a question can find a decision that shares none of its words.
        - ``hybrid``: both rankings fused by reciprocal rank fusion. When
          semantic ranking can't run (the model isn't on disk), keyword
          results alone, and ``notice`` says why.

        By default only ACTIVE decisions are returned; pass ``status=None``
        (or ``"ALL"``) to include all statuses.

        Args:
            text: Keywords or a question (title + rationale are searched).
            limit: Maximum records to return.
            status: Filter by status ("ACTIVE", "STALE", "INVALIDATED",
                case-insensitive), or None / "ALL" to include all.
            min_score: Minimum confidence threshold (0.0–1.0). Records below
                this confidence are excluded.
            mode: "keyword", "semantic" or "hybrid", case-insensitive. None
                means ``$NEURALMIND_DECISION_SEARCH``, else
                ``semantic.DEFAULT_MODE``.

        Raises:
            ValueError: ``status`` or ``mode`` is not a known value.
            semantic.SemanticSearchUnavailableError: ``mode`` is "semantic" and
                semantic ranking can't run.
        """
        status = normalize_status_filter(status)
        requested = semantic.resolve_mode(mode)
        if not text or not text.strip():
            return DecisionSearch([], requested, requested)
        text = text.strip()

        if requested == "keyword":
            return DecisionSearch(
                self._keyword_search(text, limit, status, min_score), "keyword", requested
            )
        if requested == "semantic":
            return DecisionSearch(
                self._semantic_search(text, limit, status, min_score), "semantic", requested
            )

        # Hybrid: fuse deeper lists than the caller asked for, so a decision
        # ranked moderately by both signals can rise into the top `limit`.
        pool = max(limit * 4, 20)
        by_words = self._keyword_search(text, pool, status, min_score)
        try:
            by_meaning = self._semantic_search(text, pool, status, min_score)
        except semantic.SemanticSearchUnavailableError as e:
            return DecisionSearch(
                by_words[:limit],
                "keyword",
                requested,
                notice=f"semantic ranking unavailable ({e}); keyword results only",
            )
        records = {r.id: r for r in [*by_words, *by_meaning]}
        fused = semantic.rrf([[r.id for r in by_words], [r.id for r in by_meaning]])
        return DecisionSearch([records[i] for i in fused[:limit]], "hybrid", requested)

    def _keyword_search(
        self, text: str, limit: int, status: str | None, min_score: float
    ) -> list[DecisionRecord]:
        """FTS5 search, or the LIKE scan without FTS5. [] on a database error."""
        try:
            with self._connect() as conn:
                if _fts_available(conn):
                    return self._query_fts(conn, text, limit, status, min_score)
                return self._query_like(conn, text, limit, status, min_score)
        except Exception:
            logger.exception(
                "[memory] query(%r) failed — returning [] (agent will not see "
                "any decisions for this query)",
                text,
            )
            return []

    def _get_embedder(self) -> semantic.DecisionEmbedder:
        """The embedder for semantic ranking, loaded on first use.

        Raises:
            semantic.SemanticSearchUnavailableError: it can't be loaded.
        """
        if self._embedder is None:
            self._embedder = semantic.load_default_embedder()
        return self._embedder

    def _semantic_search(
        self, text: str, limit: int, status: str | None, min_score: float
    ) -> list[DecisionRecord]:
        """Decisions ranked by cosine similarity to ``text``.

        Embeds, in one pass, the question and any decision whose
        cached vector is missing or out of date, then caches the new
        vectors. [] on a database error, like keyword search.

        Raises:
            semantic.SemanticSearchUnavailableError: no embedder, or embedding
                failed.
        """
        embedder = self._get_embedder()  # checks numpy is installed
        import numpy as np

        clauses: list[str] = []
        params: list[Any] = []
        if status is not None:
            clauses.append("d.status = ?")
            params.append(status)
        if min_score > 0.0:
            clauses.append("d.confidence >= ?")
            params.append(min_score)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    f"""SELECT d.id, d.title, d.rationale, d.commit_sha, d.files_affected,
                               d.decision_type, d.confidence, d.status, d.author,
                               d.created_at, d.updated_at, d.evidence,
                               d.rejected_alternatives, d.dependency_constraints, d.tags,
                               v.model_id, v.content_sha, v.vector
                        FROM decisions d
                        LEFT JOIN decision_vectors v ON v.decision_id = d.id
                        {where}
                        ORDER BY d.created_at DESC""",
                    params,
                ).fetchall()
        except Exception:
            logger.exception("[memory] semantic search(%r) failed — returning []", text)
            return []
        if not rows:
            return []

        records = [_row_to_record(row[:15]) for row in rows]
        shas = [semantic.content_sha(semantic.decision_text(r.title, r.rationale)) for r in records]
        vectors: dict[str, Any] = {}
        to_embed: list[int] = []
        for i, row in enumerate(rows):
            model_id, sha, blob = row[15], row[16], row[17]
            if blob is not None and model_id == embedder.model_id and sha == shas[i]:
                vectors[records[i].id] = np.frombuffer(blob, dtype=np.float32)
            else:
                to_embed.append(i)

        texts = [semantic.decision_text(records[i].title, records[i].rationale) for i in to_embed]
        try:
            matrix = semantic.embed_texts(embedder, [*texts, text])
        except Exception as e:
            logger.exception("[memory] embedding failed during decision search")
            raise semantic.SemanticSearchUnavailableError(f"embedding failed: {e}") from e
        question = matrix[-1]
        for row_index, vector in zip(to_embed, matrix[:-1], strict=True):
            vectors[records[row_index].id] = vector
        if to_embed:
            self._cache_vectors(
                embedder.model_id,
                [(records[i].id, shas[i], matrix[n]) for n, i in enumerate(to_embed)],
            )

        candidates = [
            (r.id, vectors[r.id]) for r in records if vectors[r.id].shape == question.shape
        ]
        by_id = {r.id: r for r in records}
        ranked = semantic.rank_by_similarity(question, candidates)
        return [by_id[decision_id] for decision_id, _ in ranked[:limit]]

    def _cache_vectors(self, model_id: str, entries: list[tuple[str, str, Any]]) -> None:
        """Store freshly computed vectors. Best-effort: a failure costs a re-embed."""
        try:
            with self._connect() as conn:
                conn.execute("BEGIN")
                # The EXISTS guard skips a decision deleted since it was read,
                # whose vector the delete trigger could no longer remove.
                conn.executemany(
                    """INSERT OR REPLACE INTO decision_vectors
                           (decision_id, model_id, content_sha, dim, vector)
                       SELECT ?, ?, ?, ?, ?
                       WHERE EXISTS (SELECT 1 FROM decisions WHERE id = ?)""",
                    [
                        (
                            did,
                            model_id,
                            sha,
                            int(vec.shape[0]),
                            vec.astype("float32").tobytes(),
                            did,
                        )
                        for did, sha, vec in entries
                    ],
                )
                conn.execute("COMMIT")
        except Exception:
            logger.warning(
                "[memory] could not cache %d decision vector(s) — the next search embeds "
                "them again",
                len(entries),
            )

    def _query_fts(
        self,
        conn: sqlite3.Connection,
        text: str,
        limit: int,
        status: str | None,
        min_score: float,
    ) -> list[DecisionRecord]:
        """FTS5-backed relevance-ranked search.

        Any search term can match (OR), so a question works as well as a
        few keywords. bm25() sums each matched term's weight, so decisions
        that match more of the terms, and rarer ones, rank first; it returns
        lower-is-better, hence ASC. Each term is prefix-matched so partial
        words work, and double-quoted to escape FTS5 special characters
        (hyphens, etc.).
        """
        terms = _search_terms(text)
        if not terms:
            return []
        match_query = " OR ".join(f'"{t}"*' for t in terms)

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

        Same terms as the FTS path, each matched as a substring of the title
        or rationale; any term can match. Decisions containing more of the
        terms rank first, then the most recent, as a rough stand-in for
        bm25.
        """
        terms = _search_terms(text)
        if not terms:
            return []
        # One 0/1 per term: does the title or rationale contain it?
        hits = " + ".join(
            "(title LIKE ? ESCAPE '\\' OR rationale LIKE ? ESCAPE '\\')" for _ in terms
        )
        params: list[Any] = []
        for term in terms:
            pattern = "%" + re.sub(r"([\\%_])", r"\\\1", term) + "%"
            params += [pattern, pattern]

        clauses: list[str] = ["hits > 0"]
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
                FROM (SELECT *, {hits} AS hits FROM decisions)
                WHERE {where}
                ORDER BY hits DESC, created_at DESC
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
            status: Optional status filter ("ACTIVE", "STALE", "INVALIDATED",
                case-insensitive). If None or "ALL", returns decisions of all
                statuses.

        Returns:
            All matching decisions ordered by created_at DESC.

        Raises:
            ValueError: ``status`` is not a known status or "ALL".
        """
        status = normalize_status_filter(status)
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
