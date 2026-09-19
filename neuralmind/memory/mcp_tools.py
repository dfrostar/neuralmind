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
    }

    if name not in handlers:
        return json.dumps({"error": f"Unknown tool: {name}"})

    try:
        result = handlers[name](arguments)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})
