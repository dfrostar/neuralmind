# Copyright (c) 2026 Cheval-Volant LLC (d/b/a NeuralMind).
# Source-available under the NeuralMind Commercial Modules License.
# Free 1-seat use included; see LICENSING.md.
"""cli.py — Memory Layer CLI commands (`neuralmind memory ...`).

Decision recording, retrieval, audit, and evaluation commands for the
NeuralMind memory layer.  Wired into the main CLI via
``build_memory_subparsers(subparsers)`` so the memory package stays isolated.

Storage: per-project SQLite at ``.neuralmind/memory/decisions.sqlite``.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

STATUS_ACTIVE = "active"
STATUS_STALE = "stale"
STATUS_INVALIDATED = "invalidated"

# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------


def _db_path(project_path: str | Path) -> Path:
    """Return the SQLite path for a project's memory store."""
    return Path(project_path) / ".neuralmind" / "memory" / "decisions.sqlite"


def _get_db(project_path: str | Path) -> sqlite3.Connection:
    """Open (creating schema if needed) the memory SQLite store."""
    db_path = _db_path(project_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS decisions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            rationale TEXT NOT NULL DEFAULT '',
            confidence REAL NOT NULL DEFAULT 1.0,
            decision_type TEXT NOT NULL DEFAULT 'architecture',
            status TEXT NOT NULL DEFAULT 'active',
            commit_sha TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            invalidated_at TEXT,
            invalidation_reason TEXT
        );

        CREATE TABLE IF NOT EXISTS decision_files (
            decision_id TEXT NOT NULL,
            file_path TEXT NOT NULL,
            FOREIGN KEY (decision_id) REFERENCES decisions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS rejected_alternatives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_id TEXT NOT NULL,
            option TEXT NOT NULL,
            rejection_reason TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (decision_id) REFERENCES decisions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_id TEXT NOT NULL,
            evidence_type TEXT NOT NULL DEFAULT 'supporting',
            content TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (decision_id) REFERENCES decisions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status);
        CREATE INDEX IF NOT EXISTS idx_decisions_commit ON decisions(commit_sha);
        CREATE INDEX IF NOT EXISTS idx_decisions_type ON decisions(decision_type);

        -- FTS5 index mapping decisions.id (TEXT) to an INTEGER rowid
        CREATE TABLE IF NOT EXISTS decisions_fts_map (
            decision_id TEXT PRIMARY KEY,
            rowid INTEGER UNIQUE
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS decisions_fts USING fts5(
            title, rationale, content='decisions_fts_map', content_rowid='rowid'
        );
        """)
    conn.commit()


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------


def _insert_decision(
    conn: sqlite3.Connection,
    title: str,
    rationale: str,
    confidence: float,
    decision_type: str,
    commit_sha: str | None,
    files: list[str] | None,
    rejected: list[dict[str, str]] | None,
    evidence_list: list[dict[str, Any]] | None,
) -> str:
    """Insert a decision record and return its ID."""
    decision_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO decisions
           (id, title, rationale, confidence, decision_type, status,
            commit_sha, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            decision_id,
            title,
            rationale,
            confidence,
            decision_type,
            STATUS_ACTIVE,
            commit_sha,
            now,
            now,
        ),
    )
    if files:
        conn.executemany(
            "INSERT INTO decision_files (decision_id, file_path) VALUES (?, ?)",
            [(decision_id, f) for f in files],
        )
    if rejected:
        conn.executemany(
            """INSERT INTO rejected_alternatives
               (decision_id, option, rejection_reason) VALUES (?, ?, ?)""",
            [(decision_id, r.get("option", ""), r.get("reason", "")) for r in rejected],
        )
    if evidence_list:
        conn.executemany(
            """INSERT INTO evidence
               (decision_id, evidence_type, content, source, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            [
                (
                    decision_id,
                    e.get("type", "supporting"),
                    e.get("content", ""),
                    e.get("source", ""),
                    now,
                )
                for e in evidence_list
            ],
        )
    # Update FTS index (use the mapping table for TEXT id → INTEGER rowid)
    conn.execute(
        "INSERT INTO decisions_fts_map(decision_id, rowid) VALUES (?, (SELECT COALESCE(MAX(rowid),0)+1 FROM decisions_fts_map))",
        (decision_id,),
    )
    conn.execute(
        "INSERT INTO decisions_fts(rowid, title, rationale) VALUES ((SELECT rowid FROM decisions_fts_map WHERE decision_id=?), ?, ?)",
        (decision_id, title, rationale),
    )
    conn.commit()
    return decision_id


def _get_decision(conn: sqlite3.Connection, decision_id: str) -> dict[str, Any] | None:
    """Fetch a single decision by ID."""
    row = conn.execute("SELECT * FROM decisions WHERE id = ?", (decision_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["files"] = [
        r["file_path"]
        for r in conn.execute(
            "SELECT file_path FROM decision_files WHERE decision_id = ?",
            (decision_id,),
        )
    ]
    d["rejected_alternatives"] = [
        {"option": r["option"], "rejection_reason": r["rejection_reason"]}
        for r in conn.execute(
            "SELECT option, rejection_reason FROM rejected_alternatives WHERE decision_id = ?",
            (decision_id,),
        )
    ]
    d["evidence"] = [
        {
            "type": r["evidence_type"],
            "content": r["content"],
            "source": r["source"],
            "created_at": r["created_at"],
        }
        for r in conn.execute(
            "SELECT evidence_type, content, source, created_at FROM evidence WHERE decision_id = ?",
            (decision_id,),
        )
    ]
    return d


def _query_decisions(
    conn: sqlite3.Connection,
    query_text: str,
    limit: int,
    status: str,
) -> list[dict[str, Any]]:
    """Search decisions by FTS or substring match."""
    if status == "all":
        status_clause = ""
        params: list[Any] = []
    else:
        status_clause = "WHERE d.status = ?"
        params = [status]

    # Try FTS first, fall back to LIKE
    try:
        if status_clause:
            fts_query = """
                SELECT d.*, 1.0 as score
                FROM decisions_fts f
                JOIN decisions_fts_map m ON m.rowid = f.rowid
                JOIN decisions d ON d.id = m.decision_id
                WHERE decisions_fts MATCH ? AND d.status = ?
                ORDER BY d.updated_at DESC
                LIMIT ?
            """
            rows = conn.execute(fts_query, (query_text, status, limit)).fetchall()
        else:
            fts_query = """
                SELECT d.*, 1.0 as score
                FROM decisions_fts f
                JOIN decisions_fts_map m ON m.rowid = f.rowid
                JOIN decisions d ON d.id = m.decision_id
                WHERE decisions_fts MATCH ?
                ORDER BY d.updated_at DESC
                LIMIT ?
            """
            rows = conn.execute(fts_query, (query_text, limit)).fetchall()
    except sqlite3.OperationalError:
        # FTS match failed, fall back to LIKE
        like_pattern = f"%{query_text}%"
        if status_clause:
            like_query = f"""
                SELECT d.*, 1.0 as score
                FROM decisions d
                {status_clause}
                AND (d.title LIKE ? OR d.rationale LIKE ?)
                ORDER BY d.updated_at DESC
                LIMIT ?
            """
            rows = conn.execute(like_query, (*params, like_pattern, like_pattern, limit)).fetchall()
        else:
            like_query = """
                SELECT d.*, 1.0 as score
                FROM decisions d
                WHERE d.title LIKE ? OR d.rationale LIKE ?
                ORDER BY d.updated_at DESC
                LIMIT ?
            """
            rows = conn.execute(like_query, (like_pattern, like_pattern, limit)).fetchall()

    results = []
    for row in rows:
        d = dict(row)
        d["files"] = [
            r["file_path"]
            for r in conn.execute(
                "SELECT file_path FROM decision_files WHERE decision_id = ?",
                (d["id"],),
            )
        ]
        d["rejected_alternatives"] = [
            {"option": r["option"], "rejection_reason": r["rejection_reason"]}
            for r in conn.execute(
                "SELECT option, rejection_reason FROM rejected_alternatives WHERE decision_id = ?",
                (d["id"],),
            )
        ]
        d["evidence"] = [
            {
                "type": r["evidence_type"],
                "content": r["content"],
                "source": r["source"],
                "created_at": r["created_at"],
            }
            for r in conn.execute(
                "SELECT evidence_type, content, source, created_at FROM evidence WHERE decision_id = ?",
                (d["id"],),
            )
        ]
        results.append(d)
    return results


def _list_decisions(
    conn: sqlite3.Connection,
    stale_only: bool = False,
    orphaned_only: bool = False,
) -> list[dict[str, Any]]:
    """List all decisions, optionally filtered."""
    where_clauses = []
    params: list[Any] = []
    if stale_only:
        where_clauses.append("status = ?")
        params.append(STATUS_STALE)
    if orphaned_only:
        where_clauses.append("commit_sha IS NOT NULL AND status = ?")
        params.append(STATUS_STALE)

    query = "SELECT * FROM decisions"
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    query += " ORDER BY created_at DESC"

    rows = conn.execute(query, params).fetchall()
    results = []
    for row in rows:
        d = dict(row)
        d["files"] = [
            r["file_path"]
            for r in conn.execute(
                "SELECT file_path FROM decision_files WHERE decision_id = ?",
                (d["id"],),
            )
        ]
        d["rejected_alternatives"] = [
            {"option": r["option"], "rejection_reason": r["rejection_reason"]}
            for r in conn.execute(
                "SELECT option, rejection_reason FROM rejected_alternatives WHERE decision_id = ?",
                (d["id"],),
            )
        ]
        d["evidence"] = [
            {
                "type": r["evidence_type"],
                "content": r["content"],
                "source": r["source"],
                "created_at": r["created_at"],
            }
            for r in conn.execute(
                "SELECT evidence_type, content, source, created_at FROM evidence WHERE decision_id = ?",
                (d["id"],),
            )
        ]
        results.append(d)
    return results


def _invalidate_decision(conn: sqlite3.Connection, decision_id: str, reason: str = "") -> bool:
    """Mark a decision as stale/invalidated. Returns True if found."""
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        """UPDATE decisions
           SET status = ?, invalidated_at = ?, invalidation_reason = ?, updated_at = ?
           WHERE id = ?""",
        (STATUS_STALE, now, reason, now, decision_id),
    )
    conn.commit()
    return cur.rowcount > 0


def _restore_decision(
    conn: sqlite3.Connection, decision_id: str, new_commit_sha: str | None = None
) -> bool:
    """Re-validate a stale decision. Returns True if found."""
    now = datetime.now(timezone.utc).isoformat()
    if new_commit_sha:
        cur = conn.execute(
            """UPDATE decisions
               SET status = ?, commit_sha = ?, invalidated_at = NULL,
                   invalidation_reason = NULL, updated_at = ?
               WHERE id = ?""",
            (STATUS_ACTIVE, new_commit_sha, now, decision_id),
        )
    else:
        cur = conn.execute(
            """UPDATE decisions
               SET status = ?, invalidated_at = NULL,
                   invalidation_reason = NULL, updated_at = ?
               WHERE id = ?""",
            (STATUS_ACTIVE, now, decision_id),
        )
    conn.commit()
    return cur.rowcount > 0


def _amend_decision(
    conn: sqlite3.Connection,
    decision_id: str,
    rationale: str | None = None,
    rejected: list[dict[str, str]] | None = None,
    evidence_list: list[dict[str, Any]] | None = None,
) -> bool:
    """Add to an existing decision. Returns True if found."""
    now = datetime.now(timezone.utc).isoformat()
    if rationale:
        conn.execute(
            "UPDATE decisions SET rationale = ?, updated_at = ? WHERE id = ?",
            (rationale, now, decision_id),
        )
    if rejected:
        conn.executemany(
            """INSERT INTO rejected_alternatives
               (decision_id, option, rejection_reason) VALUES (?, ?, ?)""",
            [(decision_id, r.get("option", ""), r.get("reason", "")) for r in rejected],
        )
    if evidence_list:
        conn.executemany(
            """INSERT INTO evidence
               (decision_id, evidence_type, content, source, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            [
                (
                    decision_id,
                    e.get("type", "supporting"),
                    e.get("content", ""),
                    e.get("source", ""),
                    now,
                )
                for e in evidence_list
            ],
        )

    # Update FTS index if rationale changed
    if rationale:
        conn.execute(
            "UPDATE decisions_fts SET title = (SELECT title FROM decisions WHERE id=?), rationale = ? WHERE rowid = (SELECT rowid FROM decisions_fts_map WHERE decision_id=?)",
            (decision_id, rationale, decision_id),
        )

    conn.commit()
    return True


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _status_badge(status: str) -> str:
    """Return a colored status indicator."""
    if status == STATUS_ACTIVE:
        return "ACTIVE 🟢"
    if status == STATUS_STALE:
        return "STALE 🔴"
    return "INVALIDATED ⚪"


def _format_table_plain(headers: list[str], rows: list[list[str]]) -> str:
    """Format data as a plain-text table."""
    if not rows:
        return ""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))
    sep = "─" * (sum(col_widths) + 3 * len(headers) + 1)
    lines = [sep]
    header_line = " │ ".join(h.ljust(w) for h, w in zip(headers, col_widths, strict=True))
    lines.append(f"│ {header_line} │")
    lines.append(sep)
    for row in rows:
        row_line = " │ ".join(cell.ljust(w) for cell, w in zip(row, col_widths, strict=True))
        lines.append(f"│ {row_line} │")
    lines.append(sep)
    return "\n".join(lines)


def _format_table_rich(headers: list[str], rows: list[list[str]]) -> str:
    """Format data as a rich table (fallback to plain)."""
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console(file=None)
        table = Table(title=None, show_header=True, header_style="bold")
        for h in headers:
            table.add_column(h)
        for row in rows:
            table.add_row(*row)
        with console.capture() as capture:
            console.print(table)
        return capture.get()
    except ImportError:
        return _format_table_plain(headers, rows)


def format_table(headers: list[str], rows: list[list[str]]) -> str:
    """Format data as a table, using rich if available."""
    try:
        import rich  # noqa: F401

        return _format_table_rich(headers, rows)
    except ImportError:
        return _format_table_plain(headers, rows)


# ---------------------------------------------------------------------------
# CLI command implementations
# ---------------------------------------------------------------------------


def cmd_memory_record(args: argparse.Namespace) -> None:
    """Store a new decision."""
    project_path = getattr(args, "project_path", ".") or "."
    title = getattr(args, "title", None)
    if not title:
        print("Error: --title is required", file=sys.stderr)
        sys.exit(1)

    rationale = getattr(args, "rationale", "") or ""
    commit = getattr(args, "commit", None)
    files_str = getattr(args, "files", None)
    files = [f.strip() for f in files_str.split(",") if f.strip()] if files_str else []
    decision_type = getattr(args, "type", "architecture") or "architecture"
    confidence = getattr(args, "confidence", 1.0) or 1.0

    # Parse rejected alternatives (JSON array of {option, reason})
    rejected: list[dict[str, str]] | None = None
    rejected_str = getattr(args, "rejected", None)
    if rejected_str:
        try:
            rejected = json.loads(rejected_str)
            if isinstance(rejected, str):
                rejected = [{"option": r.strip(), "reason": ""} for r in rejected.split(",")]
            elif isinstance(rejected, dict):
                rejected = [rejected]
            elif isinstance(rejected, list):
                # Handle list of strings
                rejected = [
                    {"option": r.strip(), "reason": ""} if isinstance(r, str) else r
                    for r in rejected
                ]
        except json.JSONDecodeError:
            rejected = [{"option": rejected_str, "reason": ""}]

    # Parse evidence (JSON array of {type, content, source})
    evidence: list[dict[str, Any]] | None = None
    evidence_str = getattr(args, "evidence", None)
    if evidence_str:
        try:
            evidence = json.loads(evidence_str)
            if isinstance(evidence, dict):
                evidence = [evidence]
        except json.JSONDecodeError:
            evidence = [{"type": "supporting", "content": evidence_str, "source": "cli"}]

    conn = _get_db(project_path)
    try:
        decision_id = _insert_decision(
            conn,
            title=title,
            rationale=rationale,
            confidence=confidence,
            decision_type=decision_type,
            commit_sha=commit,
            files=files,
            rejected=rejected,
            evidence_list=evidence,
        )
    finally:
        conn.close()

    print(f"Recorded decision: {decision_id}")
    print(f"  Title: {title}")
    if commit:
        print(f"  Commit: {commit}")
    print(f"  Status: {_status_badge(STATUS_ACTIVE)}")


def cmd_memory_query(args: argparse.Namespace) -> None:
    """Search decisions by natural language."""
    project_path = getattr(args, "project_path", ".") or "."
    query_text = getattr(args, "query", None)
    if not query_text:
        print("Error: QUERY is required", file=sys.stderr)
        sys.exit(1)

    limit = getattr(args, "limit", 10) or 10
    status = getattr(args, "status", "active") or "active"

    conn = _get_db(project_path)
    try:
        results = _query_decisions(conn, query_text, limit, status)
    finally:
        conn.close()

    if not results:
        print(f'No decisions found matching "{query_text}"')
        return

    print(f'NeuralMind Memory Query: "{query_text}"')
    print()
    headers = ["#", "Score", "Decision", "Commit", "Status"]
    rows = []
    for i, d in enumerate(results, 1):
        commit_display = d.get("commit_sha", "") or "-"
        if commit_display != "-" and len(commit_display) > 7:
            commit_display = commit_display[:7]
        rows.append(
            [
                str(i),
                f'{d.get("score", 0):.2f}',
                d.get("title", "")[:40],
                commit_display,
                _status_badge(d.get("status", STATUS_ACTIVE)),
            ]
        )
    print(format_table(headers, rows))


def cmd_memory_amend(args: argparse.Namespace) -> None:
    """Add to an existing decision."""
    project_path = getattr(args, "project_path", ".") or "."
    decision_id = getattr(args, "id", None)
    if not decision_id:
        print("Error: ID is required", file=sys.stderr)
        sys.exit(1)

    conn = _get_db(project_path)
    try:
        existing = _get_decision(conn, decision_id)
        if not existing:
            print(
                f"No decision found with ID {decision_id}. Run `neuralmind memory audit`.",
                file=sys.stderr,
            )
            sys.exit(1)

        # Build updates from flags
        new_rationale = getattr(args, "rationale", None)
        rejected_str = getattr(args, "rejected", None)
        rejected: list[dict[str, str]] | None = None
        if rejected_str:
            try:
                rejected = json.loads(rejected_str)
                if isinstance(rejected, str):
                    rejected = [{"option": r, "reason": ""} for r in rejected.split(",")]
            except json.JSONDecodeError:
                rejected = [{"option": rejected_str, "reason": ""}]

        evidence_str = getattr(args, "evidence", None)
        evidence: list[dict[str, Any]] | None = None
        if evidence_str:
            try:
                evidence = json.loads(evidence_str)
                if isinstance(evidence, dict):
                    evidence = [evidence]
            except json.JSONDecodeError:
                evidence = [{"type": "supporting", "content": evidence_str, "source": "cli"}]

        _amend_decision(
            conn,
            decision_id,
            rationale=new_rationale,
            rejected=rejected,
            evidence_list=evidence,
        )

        updated = _get_decision(conn, decision_id)
    finally:
        conn.close()

    print(f"Amended decision: {decision_id}")
    if updated:
        print(f"  Title: {updated.get('title', '')}")
        print(f"  Rationale: {updated.get('rationale', '')[:120]}")
        print(f"  Status: {_status_badge(updated.get('status', STATUS_ACTIVE))}")


def cmd_memory_audit(args: argparse.Namespace) -> None:
    """List all decisions."""
    project_path = getattr(args, "project_path", ".") or "."
    stale_only = getattr(args, "stale", False)
    orphaned_only = getattr(args, "orphaned", False)
    output_format = getattr(args, "format", "md")

    conn = _get_db(project_path)
    try:
        results = _list_decisions(conn, stale_only=stale_only, orphaned_only=orphaned_only)
    finally:
        conn.close()

    if output_format == "json":
        print(json.dumps(results, indent=2, default=str))
        return

    if not results:
        filter_desc = ""
        if stale_only:
            filter_desc = " (stale)"
        elif orphaned_only:
            filter_desc = " (orphaned)"
        print(f"No decisions found{filter_desc}")
        return

    filter_title = "All Decisions"
    if stale_only:
        filter_title = "Stale Decisions"
    elif orphaned_only:
        filter_title = "Orphaned Decisions"

    print(f"NeuralMind Memory Audit — {filter_title} ({len(results)} entries)")
    print()
    headers = ["ID", "Title", "Type", "Commit", "Status", "Created"]
    rows = []
    for d in results:
        commit_display = d.get("commit_sha", "") or "-"
        if commit_display != "-" and len(commit_display) > 7:
            commit_display = commit_display[:7]
        rows.append(
            [
                d["id"][:8],
                d.get("title", "")[:35],
                d.get("decision_type", ""),
                commit_display,
                _status_badge(d.get("status", STATUS_ACTIVE)),
                d.get("created_at", "")[:10],
            ]
        )
    print(format_table(headers, rows))


def cmd_memory_export(args: argparse.Namespace) -> None:
    """Dump all decisions to file or stdout."""
    project_path = getattr(args, "project_path", ".") or "."
    output_format = getattr(args, "format", "md")
    output_path = getattr(args, "output", None)

    conn = _get_db(project_path)
    try:
        results = _list_decisions(conn)
    finally:
        conn.close()

    output: str
    if output_format == "json":
        output = json.dumps(results, indent=2, default=str)
    else:
        # Markdown
        lines = ["# NeuralMind Memory Export", ""]
        lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        lines.append(f"Total decisions: {len(results)}")
        lines.append("")
        for d in results:
            lines.append(f"## {d.get('title', 'Untitled')}")
            lines.append(f"- **ID:** `{d['id']}`")
            lines.append(f"- **Type:** {d.get('decision_type', 'architecture')}")
            lines.append(f"- **Status:** {d.get('status', STATUS_ACTIVE)}")
            lines.append(f"- **Confidence:** {d.get('confidence', 1.0)}")
            if d.get("commit_sha"):
                lines.append(f"- **Commit:** `{d['commit_sha']}`")
            if d.get("files"):
                lines.append(f"- **Files:** {', '.join(d['files'])}")
            lines.append(f"- **Rationale:** {d.get('rationale', '')}")
            if d.get("rejected_alternatives"):
                lines.append("- **Rejected alternatives:**")
                for ra in d["rejected_alternatives"]:
                    lines.append(f"  - {ra['option']}: {ra.get('rejection_reason', '')}")
            if d.get("evidence"):
                lines.append("- **Evidence:**")
                for ev in d["evidence"]:
                    lines.append(f"  - [{ev.get('type', 'supporting')}] {ev.get('content', '')}")
            lines.append(f"- **Created:** {d.get('created_at', '')}")
            lines.append(f"- **Updated:** {d.get('updated_at', '')}")
            lines.append("")
        output = "\n".join(lines)

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(output, encoding="utf-8")
        print(f"Exported {len(results)} decisions to {output_path}")
    else:
        print(output)


def cmd_memory_restore(args: argparse.Namespace) -> None:
    """Re-validate a stale decision."""
    project_path = getattr(args, "project_path", ".") or "."
    decision_id = getattr(args, "id", None)
    if not decision_id:
        print("Error: ID is required", file=sys.stderr)
        sys.exit(1)

    new_commit = getattr(args, "commit", None)

    conn = _get_db(project_path)
    try:
        existing = _get_decision(conn, decision_id)
        if not existing:
            print(
                f"No decision found with ID {decision_id}. Run `neuralmind memory audit`.",
                file=sys.stderr,
            )
            sys.exit(1)

        _restore_decision(conn, decision_id, new_commit_sha=new_commit)
    finally:
        conn.close()

    print(f"Restored decision: {decision_id}")
    print(f"  Status: {_status_badge(STATUS_ACTIVE)}")
    if new_commit:
        print(f"  New commit: {new_commit}")


def cmd_memory_invalidate(args: argparse.Namespace) -> None:
    """Mark a decision as stale."""
    project_path = getattr(args, "project_path", ".") or "."
    decision_id = getattr(args, "id", None)
    if not decision_id:
        print("Error: ID is required", file=sys.stderr)
        sys.exit(1)

    reason = getattr(args, "reason", "") or ""

    conn = _get_db(project_path)
    try:
        existing = _get_decision(conn, decision_id)
        if not existing:
            print(
                f"No decision found with ID {decision_id}. Run `neuralmind memory audit`.",
                file=sys.stderr,
            )
            sys.exit(1)

        _invalidate_decision(conn, decision_id, reason=reason)
    finally:
        conn.close()

    print(f"Invalidated decision: {decision_id}")
    print(f"  Status: {_status_badge(STATUS_STALE)}")
    if reason:
        print(f"  Reason: {reason}")


def cmd_memory_eval(args: argparse.Namespace) -> None:
    """Run benchmark evaluation."""
    project_path = getattr(args, "project_path", ".") or "."
    tasks = getattr(args, "tasks", 10) or 10
    output_format = getattr(args, "format", "json") or "json"
    output_path = getattr(args, "output", None)

    conn = _get_db(project_path)
    try:
        all_decisions = _list_decisions(conn)
    finally:
        conn.close()

    # Simple eval: compute statistics
    total = len(all_decisions)
    active = sum(1 for d in all_decisions if d.get("status") == STATUS_ACTIVE)
    stale = sum(1 for d in all_decisions if d.get("status") == STATUS_STALE)
    invalidated = sum(1 for d in all_decisions if d.get("status") == STATUS_INVALIDATED)
    avg_confidence = sum(d.get("confidence", 1.0) for d in all_decisions) / total if total else 0.0
    with_commit = sum(1 for d in all_decisions if d.get("commit_sha"))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": str(Path(project_path).resolve()),
        "summary": {
            "total_decisions": total,
            "active": active,
            "stale": stale,
            "invalidated": invalidated,
            "avg_confidence": round(avg_confidence, 3),
            "with_commit_link": with_commit,
        },
        "tasks_run": min(tasks, total),
        "pass": active > 0 and (stale / max(total, 1)) < 0.3,
    }

    output: str
    if output_format == "md":
        lines = [
            "# NeuralMind Memory Eval Report",
            "",
            f"Generated: {report['generated_at']}",
            f"Project: {report['project']}",
            "",
            "## Summary",
            "",
            f"- Total decisions: {total}",
            f"- Active: {active}",
            f"- Stale: {stale}",
            f"- Invalidated: {invalidated}",
            f"- Average confidence: {avg_confidence:.2f}",
            f"- Linked to commits: {with_commit}",
            "",
            f"## Result: {'PASS' if report['pass'] else 'FAIL'}",
            "",
            f"Ran {report['tasks_run']} eval tasks.",
        ]
        output = "\n".join(lines)
    else:
        output = json.dumps(report, indent=2)

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(output, encoding="utf-8")
        print(f"Eval report written to {output_path}")
    else:
        print(output)

    sys.exit(0 if report["pass"] else 1)


# ---------------------------------------------------------------------------
# Subparser builder
# ---------------------------------------------------------------------------


def build_memory_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Add ``memory`` subcommands to the main argparse subparsers.

    Call this from ``neuralmind.cli.main()`` to wire memory commands.

    Parameters
    ----------
    subparsers : argparse._SubParsersAction
        The ``add_subparsers()`` action from the main parser.
    """
    memory = subparsers.add_parser(
        "memory",
        help="Memory layer: record, query, audit decisions",
    )
    memory_sub = memory.add_subparsers(dest="memory_command")
    memory_sub.required = True

    # --- record ---
    record_p = memory_sub.add_parser(
        "record",
        help="Store a new decision",
    )
    record_p.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Project root (default: current directory)",
    )
    record_p.add_argument(
        "--title",
        required=True,
        help="Decision title",
    )
    record_p.add_argument(
        "--rationale",
        default="",
        help="Decision rationale",
    )
    record_p.add_argument(
        "--commit",
        default=None,
        help="Associated git commit SHA",
    )
    record_p.add_argument(
        "--files",
        default=None,
        help="Comma-separated list of files affected",
    )
    record_p.add_argument(
        "--type",
        default="architecture",
        help="Decision type (default: architecture)",
    )
    record_p.add_argument(
        "--rejected",
        default=None,
        help='Rejected alternatives as JSON: \'{"option":"X","reason":"..."}\'',
    )
    record_p.add_argument(
        "--evidence",
        default=None,
        help='Evidence as JSON: \'{"type":"supporting","content":"...","source":"..."}\'',
    )
    record_p.add_argument(
        "--confidence",
        type=float,
        default=1.0,
        help="Confidence score 0.0-1.0 (default: 1.0)",
    )
    record_p.set_defaults(func=cmd_memory_record)

    # --- query ---
    query_p = memory_sub.add_parser(
        "query",
        help="Search decisions by natural language",
    )
    query_p.add_argument(
        "query",
        help="Search query text",
    )
    query_p.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Project root (default: current directory)",
    )
    query_p.add_argument(
        "--limit",
        "-l",
        type=int,
        default=10,
        help="Maximum results (default: 10)",
    )
    query_p.add_argument(
        "--status",
        choices=["active", "stale", "all"],
        default="active",
        help="Filter by status (default: active)",
    )
    query_p.set_defaults(func=cmd_memory_query)

    # --- amend ---
    amend_p = memory_sub.add_parser(
        "amend",
        help="Add to an existing decision",
    )
    amend_p.add_argument(
        "id",
        help="Decision ID (full or 8-char prefix)",
    )
    amend_p.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Project root (default: current directory)",
    )
    amend_p.add_argument(
        "--rejected",
        default=None,
        help="Rejected alternatives as JSON array",
    )
    amend_p.add_argument(
        "--evidence",
        default=None,
        help='Evidence as JSON: {"type":"...","content":"...","source":"..."}',
    )
    amend_p.add_argument(
        "--rationale",
        default=None,
        help="Updated rationale text",
    )
    amend_p.set_defaults(func=cmd_memory_amend)

    # --- audit ---
    audit_p = memory_sub.add_parser(
        "audit",
        help="List all decisions",
    )
    audit_p.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Project root (default: current directory)",
    )
    audit_p.add_argument(
        "--stale",
        action="store_true",
        help="Show only stale decisions",
    )
    audit_p.add_argument(
        "--orphaned",
        action="store_true",
        help="Show only orphaned decisions (have commit but stale)",
    )
    audit_p.add_argument(
        "--format",
        choices=["md", "json"],
        default="md",
        help="Output format (default: md)",
    )
    audit_p.set_defaults(func=cmd_memory_audit)

    # --- export ---
    export_p = memory_sub.add_parser(
        "export",
        help="Dump all decisions",
    )
    export_p.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Project root (default: current directory)",
    )
    export_p.add_argument(
        "--format",
        choices=["md", "json"],
        default="md",
        help="Output format (default: md)",
    )
    export_p.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output file path (default: stdout)",
    )
    export_p.set_defaults(func=cmd_memory_export)

    # --- restore ---
    restore_p = memory_sub.add_parser(
        "restore",
        help="Re-validate a stale entry",
    )
    restore_p.add_argument(
        "id",
        help="Decision ID",
    )
    restore_p.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Project root (default: current directory)",
    )
    restore_p.add_argument(
        "--commit",
        default=None,
        help="New commit SHA to link",
    )
    restore_p.set_defaults(func=cmd_memory_restore)

    # --- invalidate ---
    invalidate_p = memory_sub.add_parser(
        "invalidate",
        help="Mark a decision as stale",
    )
    invalidate_p.add_argument(
        "id",
        help="Decision ID",
    )
    invalidate_p.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Project root (default: current directory)",
    )
    invalidate_p.add_argument(
        "--reason",
        default="",
        help="Reason for invalidation",
    )
    invalidate_p.set_defaults(func=cmd_memory_invalidate)

    # --- eval ---
    eval_p = memory_sub.add_parser(
        "eval",
        help="Run benchmark evaluation",
    )
    eval_p.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Project root (default: current directory)",
    )
    eval_p.add_argument(
        "--tasks",
        "-t",
        type=int,
        default=10,
        help="Number of eval tasks (default: 10)",
    )
    eval_p.add_argument(
        "--format",
        choices=["json", "md"],
        default="json",
        help="Output format (default: json)",
    )
    eval_p.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output file path (default: stdout)",
    )
    eval_p.set_defaults(func=cmd_memory_eval)
