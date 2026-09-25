"""MCP tools for the decision memory layer.

Exposes the DecisionStore via MCP so agents can query, audit, record,
and invalidate architectural decisions.  Integrates with the existing
NeuralMind MCP server by providing a TOOLS list and handle_tool_call()
function that follows the same pattern as ``neuralmind.mcp_server``.

Tools:
- neuralmind_query_decisions: Search decisions by natural language
- neuralmind_audit_decisions: List all decisions with status
- neuralmind_record_decision: Store a new architecture decision
- neuralmind_invalidate_decision: Mark a decision as stale/invalid
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .store import DecisionStore

# ---------------------------------------------------------------------------
# Store accessor
# ---------------------------------------------------------------------------


def get_decision_store(project_path: str) -> DecisionStore:
    """Get or create a DecisionStore for a project.

    The store lives at ``<project>/.neuralmind/memory.db`` and is created
    lazily on first access.  Fail-open: a corrupt or missing DB returns
    empty results rather than raising.
    """
    return DecisionStore(str(Path(project_path).resolve()))


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


def tool_query_decisions(project_path: str, query: str, limit: int = 5) -> dict[str, Any]:
    """Search project decisions by natural language.

    Uses FTS5 when available (relevance-ranked via bm25), falling back to
    a LIKE scan otherwise.  By default only ACTIVE decisions are returned.

    Args:
        project_path: Path to the project root directory.
        query: Natural language search query (searches title + rationale).
        limit: Maximum number of results to return (default: 5).

    Returns:
        Dict with ``query``, ``count``, and ``decisions`` (list of
        DecisionRecord dicts ordered by relevance).
    """
    store = get_decision_store(project_path)
    records = store.query(query, limit=limit)
    return {
        "query": query,
        "count": len(records),
        "decisions": [json.loads(r.json()) for r in records],
    }


def tool_audit_decisions(project_path: str, stale_only: bool = False) -> dict[str, Any]:
    """List all decisions with status (active/stale/invalidated).

    Args:
        project_path: Path to the project root directory.
        stale_only: When True, return only STALE and orphaned decisions.
            When False (default), returns ALL decisions regardless of status.

    Returns:
        Dict with ``count`` and ``decisions`` (list of DecisionRecord dicts).
    """
    store = get_decision_store(project_path)
    if stale_only:
        records = store.audit(stale_only=True)
    else:
        records = store.list_all()
    return {
        "count": len(records),
        "decisions": [json.loads(r.json()) for r in records],
    }


def tool_record_decision(
    project_path: str,
    title: str,
    rationale: str,
    commit_sha: str = "",
    files: list[str] | None = None,
) -> dict[str, Any]:
    """Store a new architecture decision with commit linkage.

    Args:
        project_path: Path to the project root directory.
        title: Short summary of the decision (e.g. "Use per-handler auth").
        rationale: The *why* — the reasoning that won't be obvious later.
        commit_sha: Git SHA anchoring the decision to a specific state.
        files: Paths of files this decision concerns.

    Returns:
        The created DecisionRecord as a dict.
    """
    store = get_decision_store(project_path)
    record = store.record(
        title=title,
        rationale=rationale,
        commit_sha=commit_sha,
        files_affected=files,
    )
    return json.loads(record.json())


def tool_invalidate_decision(
    project_path: str,
    decision_id: str,
    reason: str = "",
) -> dict[str, Any]:
    """Mark a decision as stale/invalid.

    The reason is appended to the decision's evidence list so the
    invalidation itself carries context.

    Args:
        project_path: Path to the project root directory.
        decision_id: UUID of the decision to invalidate.
        reason: Why the decision is being retired.

    Returns:
        Confirmation dict with the decision_id and new status.
    """
    store = get_decision_store(project_path)
    store.invalidate(decision_id, reason=reason)
    return {
        "decision_id": decision_id,
        "status": "INVALIDATED",
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# 3-layer progressive retrieval (Memory Layer v4.3, build spec Component B)
#
# Layer 1 — memory_search: compact index rows (~50-100 tokens each).
# Layer 2 — memory_timeline: chronological context around an anchor.
# Layer 3 — memory_get: full decision records by ID (batch-capped).
#
# The pattern is L0-L3 discipline applied to the MCP tool surface: agents
# filter on cheap index rows first and pay for full records only where
# needed (the claude-mem search -> timeline -> get_observations workflow).
# ---------------------------------------------------------------------------

# Layer-3 batch cap: forces filtering before fetching (build spec B.3).
MEMORY_GET_MAX_IDS = 20


def _compact_row(r) -> dict[str, Any]:
    """Render a decision as a compact index row (Layer 1).

    Kept deliberately small — roughly 50-100 tokens per row — so an agent
    can scan 10-20 candidates before committing to full-record fetches.
    """
    return {
        "id": r.id,
        "title": r.title[:120],
        "status": r.status,
        "type": r.decision_type,
        "commit": (r.commit_sha or "")[:10],
        "updated": r.updated_at.date().isoformat(),
        "files": len(r.files_affected),
    }


def tool_memory_search(
    project_path: str,
    query: str,
    limit: int = 10,
    status: str | None = "ACTIVE",
) -> dict[str, Any]:
    """Layer 1: search decisions, return compact index rows.

    Cheap first call in the 3-layer workflow. Returns id/title/status/
    type/commit/date/counts only — no rationale, no evidence. Use
    memory_timeline for context around a hit, memory_get for full records.

    Args:
        project_path: Path to the project root directory.
        query: Natural language query (title + rationale are searched).
        limit: Maximum rows to return (default: 10, capped at 25).
        status: Filter by status ("ACTIVE" default; None = all).

    Returns:
        Dict with ``query``, ``count``, ``results`` (compact rows), and
        ``next`` — a hint describing the follow-up call.
    """
    limit = max(1, min(int(limit), 25))
    store = get_decision_store(project_path)
    records = store.query(query, limit=limit, status=status)
    return {
        "query": query,
        "count": len(records),
        "results": [_compact_row(r) for r in records],
        "next": (
            "Use memory_timeline with an id for chronological context, or "
            "memory_get with batched ids (max 20) for full records."
        ),
    }


def tool_memory_timeline(
    project_path: str,
    decision_id: str = "",
    query: str = "",
    before: int = 3,
    after: int = 3,
) -> dict[str, Any]:
    """Layer 2: chronological context around a decision or query.

    Given an anchor decision (by id, or the top hit for a query), return
    the decisions recorded immediately before and after it — compact rows
    ordered oldest to newest. This answers "what else was being decided
    around then?" without paying for full records.

    Args:
        project_path: Path to the project root directory.
        decision_id: Anchor decision id (mutually exclusive with query).
        query: If no id given, anchor on the top query hit.
        before/after: How many neighbors each side (default 3, capped 10).

    Returns:
        Dict with ``anchor`` (compact row), ``before`` and ``after``
        lists (compact rows, chronological), and ``next`` hint.
    """
    before = max(0, min(int(before), 10))
    after = max(0, min(int(after), 10))
    store = get_decision_store(project_path)

    anchor = store.get(decision_id) if decision_id else None
    if anchor is None:
        if not query:
            return {"error": "Provide decision_id or query"}
        hits = store.query(query, limit=1, status=None)
        if not hits:
            return {"error": f"No decision found for query: {query!r}"}
        anchor = hits[0]
    if anchor is None:
        return {"error": f"No decision with id: {decision_id}"}

    # All decisions ordered by creation time; slice around the anchor.
    all_records = sorted(store.list_all(status=None), key=lambda r: r.created_at)
    idx = next((i for i, r in enumerate(all_records) if r.id == anchor.id), None)
    if idx is None:
        # Anchor not in list_all (e.g. filtered); degrade to anchor-only.
        return {
            "anchor": _compact_row(anchor),
            "before": [],
            "after": [],
            "next": "Use memory_get for the full anchor record.",
        }
    return {
        "anchor": _compact_row(anchor),
        "before": [_compact_row(r) for r in all_records[max(0, idx - before) : idx]],
        "after": [_compact_row(r) for r in all_records[idx + 1 : idx + 1 + after]],
        "next": (
            "Use memory_get with batched ids (max 20) for full records of " "any row shown here."
        ),
    }


def tool_memory_get(project_path: str, ids: list[str]) -> dict[str, Any]:
    """Layer 3: fetch full decision records by id, batch-capped.

    The expensive layer — rationale, rejected alternatives, evidence, and
    invalidation status. Capped at MEMORY_GET_MAX_IDS (20) per call so
    agents must filter via memory_search first.

    Args:
        project_path: Path to the project root directory.
        ids: Decision ids to fetch (max 20; excess ids are rejected).

    Returns:
        Dict with ``count``, ``decisions`` (full records), and ``missing``
        (ids that could not be found).
    """
    if not ids:
        return {"error": "ids must be a non-empty list"}
    if len(ids) > MEMORY_GET_MAX_IDS:
        return {
            "error": (
                f"Batch cap is {MEMORY_GET_MAX_IDS} ids per call — got "
                f"{len(ids)}. Filter with memory_search first."
            )
        }
    store = get_decision_store(project_path)
    records: list[dict[str, Any]] = []
    missing: list[str] = []
    for did in ids:
        r = store.get(did)
        if r is None:
            missing.append(did)
        else:
            records.append(json.loads(r.json()))
    return {"count": len(records), "decisions": records, "missing": missing}


# ---------------------------------------------------------------------------
# MCP tool definitions (for integration with neuralmind.mcp_server)
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "neuralmind_query_decisions",
        "description": (
            "Search project decisions by natural language. Returns top "
            "matching decisions with scores, commit SHAs, and file references."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to the project root directory",
                },
                "query": {
                    "type": "string",
                    "description": "Natural language search query",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results to return (default: 5)",
                    "default": 5,
                },
            },
            "required": ["project_path", "query"],
        },
    },
    {
        "name": "neuralmind_audit_decisions",
        "description": (
            "List all decisions with status (active/stale/invalidated). "
            "Use to audit memory state."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to the project root directory",
                },
                "stale_only": {
                    "type": "boolean",
                    "description": "Return only stale/invalidated decisions",
                },
            },
            "required": ["project_path"],
        },
    },
    {
        "name": "neuralmind_record_decision",
        "description": "Store a new architecture decision with commit linkage.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to the project root directory",
                },
                "title": {
                    "type": "string",
                    "description": "Short summary of the decision",
                },
                "rationale": {
                    "type": "string",
                    "description": "The reasoning behind the decision",
                },
                "commit_sha": {
                    "type": "string",
                    "description": "Git SHA anchoring the decision",
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Files affected by this decision",
                },
            },
            "required": ["project_path", "title", "rationale"],
        },
    },
    {
        "name": "neuralmind_invalidate_decision",
        "description": "Mark a decision as stale/invalid.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to the project root directory",
                },
                "decision_id": {
                    "type": "string",
                    "description": "ID of the decision to invalidate",
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for invalidation",
                },
            },
            "required": ["project_path", "decision_id"],
        },
    },
    {
        "name": "neuralmind_memory_search",
        "description": (
            "Layer 1 of progressive decision retrieval: search decisions "
            "and return compact index rows (~50-100 tokens each: id, title, "
            "status, type, commit, date). Cheap first call — filter here, "
            "then use neuralmind_memory_timeline for context or "
            "neuralmind_memory_get for full records."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to the project root directory",
                },
                "query": {
                    "type": "string",
                    "description": "Natural language search query",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum rows (default 10, capped 25)",
                    "default": 10,
                },
                "status": {
                    "type": "string",
                    "description": "Filter: ACTIVE (default), STALE, INVALIDATED, or all",
                },
            },
            "required": ["project_path", "query"],
        },
    },
    {
        "name": "neuralmind_memory_timeline",
        "description": (
            "Layer 2 of progressive decision retrieval: chronological "
            "context around a decision. Given an anchor id (or a query "
            "whose top hit becomes the anchor), return the decisions "
            "recorded immediately before and after it as compact rows. "
            "Answers 'what else was being decided around then?'"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to the project root directory",
                },
                "decision_id": {
                    "type": "string",
                    "description": "Anchor decision id (or use query)",
                },
                "query": {
                    "type": "string",
                    "description": "Anchor on the top hit for this query",
                },
                "before": {
                    "type": "integer",
                    "description": "Neighbors before the anchor (default 3)",
                    "default": 3,
                },
                "after": {
                    "type": "integer",
                    "description": "Neighbors after the anchor (default 3)",
                    "default": 3,
                },
            },
            "required": ["project_path"],
        },
    },
    {
        "name": "neuralmind_memory_get",
        "description": (
            "Layer 3 of progressive decision retrieval: fetch full "
            "decision records (rationale, rejected alternatives, evidence, "
            "invalidation status) by id. Batch-capped at 20 ids per call — "
            "filter with neuralmind_memory_search first."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to the project root directory",
                },
                "ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Decision ids to fetch (max 20 per call)",
                },
            },
            "required": ["project_path", "ids"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool call dispatcher (for integration with neuralmind.mcp_server)
# ---------------------------------------------------------------------------


def handle_tool_call(name: str, arguments: dict[str, Any]) -> str:
    """Handle a decision memory tool call and return the result as JSON.

    This function follows the same pattern as
    ``neuralmind.mcp_server.handle_tool_call`` so it can be merged into
    the main server's handler dict.

    Args:
        name: Tool name (e.g. "neuralmind_query_decisions").
        arguments: Tool arguments dict.

    Returns:
        JSON string with the tool result.
    """
    handlers = {
        "neuralmind_query_decisions": lambda args: tool_query_decisions(
            args["project_path"],
            args["query"],
            args.get("limit", 5),
        ),
        "neuralmind_audit_decisions": lambda args: tool_audit_decisions(
            args["project_path"],
            args.get("stale_only", False),
        ),
        "neuralmind_record_decision": lambda args: tool_record_decision(
            args["project_path"],
            args["title"],
            args["rationale"],
            args.get("commit_sha", ""),
            args.get("files"),
        ),
        "neuralmind_invalidate_decision": lambda args: tool_invalidate_decision(
            args["project_path"],
            args["decision_id"],
            args.get("reason", ""),
        ),
        "neuralmind_memory_search": lambda args: tool_memory_search(
            args["project_path"],
            args["query"],
            args.get("limit", 10),
            args.get("status", "ACTIVE"),
        ),
        "neuralmind_memory_timeline": lambda args: tool_memory_timeline(
            args["project_path"],
            args.get("decision_id", ""),
            args.get("query", ""),
            args.get("before", 3),
            args.get("after", 3),
        ),
        "neuralmind_memory_get": lambda args: tool_memory_get(
            args["project_path"],
            args.get("ids", []),
        ),
    }

    if name not in handlers:
        return json.dumps({"error": f"Unknown tool: {name}"})

    try:
        result = handlers[name](arguments)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})
