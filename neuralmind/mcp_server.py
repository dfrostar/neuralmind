#!/usr/bin/env python3
"""
mcp_server.py — Model Context Protocol Server for NeuralMind
=============================================================

Exposes NeuralMind capabilities via MCP for use with Claude, Cursor, and other
MCP-compatible tools.

Features:
- wakeup: Get minimal context for starting conversations
- query: Get optimized context for specific questions
- search: Direct semantic search
- build: Build/rebuild neural index
- stats: Get index statistics

Usage:
    # Run as MCP server
    python -m neuralmind.mcp_server

    # Or with uvx/npx
    uvx neuralmind-mcp
"""

import json
import sys
from pathlib import Path
from typing import Any

# MCP SDK imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("Warning: MCP SDK not installed. Install with: pip install mcp", file=sys.stderr)

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from neuralmind.core import NeuralMind
from neuralmind.mcp_security import MCPSecurityManager

# Cache for NeuralMind instances per project
_mind_cache: dict[str, NeuralMind] = {}
_security_cache: dict[str, MCPSecurityManager] = {}


def get_mind(project_path: str, auto_build: bool = True) -> NeuralMind:
    """Get or create a cached NeuralMind instance for a project."""
    abs_path = str(Path(project_path).resolve())
    if abs_path not in _mind_cache:
        _mind_cache[abs_path] = NeuralMind(abs_path)
        if auto_build:
            _mind_cache[abs_path].build()
    return _mind_cache[abs_path]


def get_security_manager(project_path: str) -> MCPSecurityManager:
    """Get or create security manager for project."""
    abs_path = str(Path(project_path).resolve())
    if abs_path not in _security_cache:
        _security_cache[abs_path] = MCPSecurityManager(abs_path)
    return _security_cache[abs_path]


def tool_wakeup(project_path: str) -> dict[str, Any]:
    """Get wake-up context for starting a conversation."""
    mind = get_mind(project_path)
    result = mind.wakeup()
    return {
        "context": result.context,
        "tokens": result.budget.total,
        "reduction_ratio": round(result.reduction_ratio, 1),
        "layers": result.layers_used,
    }


def tool_query(project_path: str, question: str, include_relevance: bool = False) -> dict[str, Any]:
    """Get optimized context for a specific question.

    When ``include_relevance`` is set, attach a structured relevance sidecar
    (per-file, per-node score / synapse-boost / recall + line spans) so a
    downstream compressor can protect the load-bearing spans instead of
    shrinking them away. Off by default to keep responses small.
    """
    mind = get_mind(project_path)
    result = mind.query(question)
    out: dict[str, Any] = {
        "context": result.context,
        "tokens": result.budget.total,
        "reduction_ratio": round(result.reduction_ratio, 1),
        "layers": result.layers_used,
        "communities_loaded": result.communities_loaded,
        "search_hits": result.search_hits,
    }
    if include_relevance:
        from .relevance import build_relevance_sidecar

        out["relevance"] = build_relevance_sidecar(result.top_search_hits, mind)
    return out


def tool_search(project_path: str, query: str, n: int = 10) -> list[dict[str, Any]]:
    """Direct semantic search for code entities."""
    mind = get_mind(project_path)
    results = mind.search(query, n=n)
    return [
        {
            "id": r.get("id"),
            "label": r.get("metadata", {}).get("label"),
            "file_type": r.get("metadata", {}).get("file_type"),
            "source_file": r.get("metadata", {}).get("source_file"),
            "score": round(r.get("score", 0), 3),
        }
        for r in results
    ]


def tool_build(project_path: str, force: bool = False) -> dict[str, Any]:
    """Build or rebuild the neural knowledge base."""
    # Clear cache to force rebuild
    abs_path = str(Path(project_path).resolve())
    if abs_path in _mind_cache:
        del _mind_cache[abs_path]

    mind = NeuralMind(project_path)
    result = mind.build(force=force)
    _mind_cache[abs_path] = mind
    return result


def tool_stats(project_path: str) -> dict[str, Any]:
    """Get index statistics for a project."""
    mind = get_mind(project_path, auto_build=False)
    try:
        stats = mind.embedder.get_stats()
        stats["project"] = Path(project_path).name
        stats["built"] = stats.get("total_nodes", 0) > 0
        return stats
    except Exception as e:
        return {"project": Path(project_path).name, "built": False, "error": str(e)}


def tool_benchmark(project_path: str) -> dict[str, Any]:
    """Run token reduction benchmark."""
    mind = get_mind(project_path)
    return mind.benchmark()


def tool_skeleton(project_path: str, file_path: str) -> dict[str, Any]:
    """Return a graph-backed skeleton of a file (functions + rationales + call graph)."""
    mind = get_mind(project_path)
    skeleton = mind.skeleton(file_path)
    return {
        "file": file_path,
        "skeleton": skeleton,
        "chars": len(skeleton),
        "indexed": bool(skeleton),
    }


def tool_synaptic_neighbors(
    project_path: str, query: str, depth: int = 2, top_k: int = 10
) -> dict[str, Any]:
    """Spreading-activation recall over the learned synapse graph.

    Seeds the activation pulse at the top semantic matches for ``query``
    and propagates through weighted edges that NeuralMind has learned
    from co-activation. Empty list when the graph hasn't accumulated
    edges yet — typical for the first few sessions on a project.
    """
    mind = get_mind(project_path)
    ranked = mind.synaptic_neighbors(query, depth=depth, top_k=top_k)
    return {
        "query": query,
        "depth": depth,
        "neighbors": [
            {"node_id": node_id, "activation": round(energy, 4)} for node_id, energy in ranked
        ],
    }


def tool_synapse_stats(project_path: str) -> dict[str, Any]:
    """Inspect the synapse graph: edge count, LTP edges, top hubs."""
    mind = get_mind(project_path, auto_build=False)
    store = mind.synapses
    if store is None:
        return {"enabled": False}
    return {"enabled": True, **store.stats()}


def tool_next_likely(project_path: str, from_node: str, top_k: int = 5) -> dict[str, Any]:
    """Predict what typically follows ``from_node`` from learned
    directional transitions.

    Returns ``(to_node, probability)`` pairs normalized over all outgoing
    transitions from ``from_node``. ``from_node`` is whatever string the
    transition recorder used — file paths from the watcher, node ids
    from direct calls. Empty when the node has no recorded transitions.
    """
    mind = get_mind(project_path, auto_build=False)
    store = mind.synapses
    if store is None:
        return {"enabled": False, "from_node": from_node, "next": []}
    ranked = store.next_likely(from_node, top_k=top_k)
    return {
        "enabled": True,
        "from_node": from_node,
        "next": [{"to_node": to_node, "probability": round(prob, 4)} for to_node, prob in ranked],
    }


def tool_synapse_decay(project_path: str) -> dict[str, Any]:
    """Manually run a decay tick. Normally fired by the SessionStart hook."""
    mind = get_mind(project_path, auto_build=False)
    store = mind.synapses
    if store is None:
        return {"enabled": False}
    return {"enabled": True, **store.decay()}


def tool_feedback(
    project_path: str,
    node_id: str,
    signal: str,
    context_node_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Record explicit retrieval feedback to strengthen or weaken synapse weights.

    ``signal`` is ``"positive"`` or ``"negative"``.

    Positive: reinforces co-activation between ``node_id`` and every node
    in ``context_node_ids`` (the other results the agent saw in the same
    retrieval round).  Use this when a result was genuinely helpful.

    Negative: applies one decay tick to all edges touching ``node_id`` so
    it surfaces less often in spreading-activation recall.  Use this when
    a result was irrelevant — the weight drifts down over time rather than
    being hard-removed, preserving LTP-protected edges.

    Both no-op gracefully when the synapse store is absent (cold graph).
    """
    mind = get_mind(project_path, auto_build=False)
    store = mind.synapses
    if store is None:
        return {"enabled": False, "node_id": node_id, "signal": signal}

    if signal == "positive" and context_node_ids:
        all_ids = [node_id] + [c for c in context_node_ids if c != node_id]
        store.reinforce(all_ids)
        return {
            "enabled": True,
            "signal": "positive",
            "node_id": node_id,
            "reinforced_with": context_node_ids,
        }
    if signal == "negative":
        store.decay_node(node_id)
        return {
            "enabled": True,
            "signal": "negative",
            "node_id": node_id,
        }
    return {
        "enabled": True,
        "signal": signal,
        "node_id": node_id,
        "note": "no-op: positive requires context_node_ids; negative requires only node_id",
    }


def tool_export_synapse_memory(project_path: str) -> dict[str, Any]:
    """Render the synapse store as markdown for Claude Code auto-memory.

    Writes <project>/.neuralmind/SYNAPSE_MEMORY.md plus, when present,
    ~/.claude/projects/<slug>/memory/synapse-activations.md so the
    associations surface in agents that don't call the MCP tools.
    """
    from neuralmind.synapse_memory import export_synapse_memory

    mind = get_mind(project_path, auto_build=False)
    if mind.synapses is None:
        return {"enabled": False, "written": []}
    paths = export_synapse_memory(project_path, embedder=mind.embedder)
    return {"enabled": True, "written": [str(p) for p in paths]}


def tool_review(
    project_path: str,
    changed_files: list[str],
    top_k: int = 10,
) -> dict[str, Any]:
    """Warn about likely co-breakage given a set of changed files.

    Runs spreading activation through the learned synapse graph seeded at
    the provided changed files. Returns files NOT in ``changed_files`` that
    are strongly associated — historical co-edit partners that may also need
    to change. Use before committing or as part of a code-review workflow.

    ``changed_files`` should be project-relative paths or absolute paths.
    Use the CLI ``neuralmind review`` to derive them automatically from
    ``git diff``.
    """
    mind = get_mind(project_path)
    abs_project = Path(project_path).resolve()
    changed_set = {str(abs_project / f) if not Path(f).is_absolute() else f for f in changed_files}

    # Resolve file paths to node IDs
    seed_ids: list[tuple[str, float]] = []
    for fpath in changed_set:
        try:
            for node in mind.embedder.get_file_nodes(fpath):
                nid = node.get("id")
                if nid:
                    seed_ids.append((str(nid), 1.0))
        except Exception:
            continue

    at_risk: list[dict] = []
    if seed_ids and mind.synapses is not None:
        try:
            neighbors = mind.synapses.spread(seed_ids, depth=2, top_k=top_k * 2)
            seen_files: set[str] = set()
            all_nodes = getattr(mind.embedder, "nodes", []) or []
            node_file_map = {
                str(n.get("id", "")): (
                    n.get("metadata", {}).get("source_file") or n.get("source_file", "")
                )
                for n in all_nodes
            }
            for node_id, weight in neighbors:
                node_file = node_file_map.get(node_id)
                if not node_file:
                    continue
                abs_file = (
                    str(abs_project / node_file) if not Path(node_file).is_absolute() else node_file
                )
                if abs_file in changed_set or abs_file in seen_files:
                    continue
                seen_files.add(abs_file)
                rel = str(Path(abs_file).relative_to(abs_project))
                at_risk.append({"file": rel, "synapse_weight": round(weight, 3)})
                if len(at_risk) >= top_k:
                    break
        except Exception:
            pass

    return {
        "changed_files": [str(Path(f).relative_to(abs_project)) for f in sorted(changed_set)],
        "at_risk": at_risk,
        "synapse_graph_available": mind.synapses is not None,
    }


# Tool definitions for MCP
TOOLS = [
    {
        "name": "neuralmind_wakeup",
        "description": "Get minimal wake-up context (~600 tokens) for starting a conversation about a codebase. Returns project identity and architecture overview.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to the project root directory",
                }
            },
            "required": ["project_path"],
        },
    },
    {
        "name": "neuralmind_query",
        "description": "Get optimized context for answering a question about a codebase. Achieves 40-70x token reduction by only loading relevant code clusters.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to the project root directory",
                },
                "question": {
                    "type": "string",
                    "description": "Natural language question about the codebase",
                },
                "include_relevance": {
                    "type": "boolean",
                    "description": "Attach a structured relevance sidecar (per-file, per-node "
                    "score / synapse-boost / recall + line spans) so a downstream compressor "
                    "can protect the load-bearing spans. Default false.",
                },
            },
            "required": ["project_path", "question"],
        },
    },
    {
        "name": "neuralmind_search",
        "description": "Semantic search for code entities (functions, classes, files). Returns top matches with relevance scores.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to the project root directory",
                },
                "query": {"type": "string", "description": "Search query"},
                "n": {
                    "type": "integer",
                    "description": "Number of results to return (default: 10)",
                    "default": 10,
                },
            },
            "required": ["project_path", "query"],
        },
    },
    {
        "name": "neuralmind_build",
        "description": "Build or rebuild the neural knowledge base for a project. Requires graphify-out/graph.json to exist.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to the project root directory",
                },
                "force": {
                    "type": "boolean",
                    "description": "Force rebuild all embeddings even if unchanged",
                    "default": False,
                },
            },
            "required": ["project_path"],
        },
    },
    {
        "name": "neuralmind_stats",
        "description": "Get statistics about the neural index for a project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to the project root directory",
                }
            },
            "required": ["project_path"],
        },
    },
    {
        "name": "neuralmind_benchmark",
        "description": "Run a benchmark to measure token reduction. Tests wake-up and several query patterns.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to the project root directory",
                }
            },
            "required": ["project_path"],
        },
    },
    {
        "name": "neuralmind_skeleton",
        "description": (
            "Return a compact graph-backed view of a file (functions, rationales, "
            "call graph, cross-file edges). Use INSTEAD of Read when exploring "
            "how a file is structured — typically 5-15x cheaper than the raw source."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to the project root directory",
                },
                "file_path": {
                    "type": "string",
                    "description": "File path (absolute or project-relative) to skeleton",
                },
            },
            "required": ["project_path", "file_path"],
        },
    },
    {
        "name": "neuralmind_synaptic_neighbors",
        "description": (
            "Spreading-activation recall over the learned synapse graph. Returns "
            "nodes that NeuralMind has learned to associate with the query through "
            "co-activation — complements vector search with usage-based recall."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {"type": "string"},
                "query": {"type": "string", "description": "Seed query for spreading activation"},
                "depth": {"type": "integer", "default": 2},
                "top_k": {"type": "integer", "default": 10},
            },
            "required": ["project_path", "query"],
        },
    },
    {
        "name": "neuralmind_synapse_stats",
        "description": "Stats on the learned synapse graph: edges, LTP edges, top hubs.",
        "inputSchema": {
            "type": "object",
            "properties": {"project_path": {"type": "string"}},
            "required": ["project_path"],
        },
    },
    {
        "name": "neuralmind_synapse_decay",
        "description": (
            "Run one decay tick on the synapse graph. Usually fired automatically "
            "from the SessionStart hook; exposed here for manual control."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"project_path": {"type": "string"}},
            "required": ["project_path"],
        },
    },
    {
        "name": "neuralmind_next_likely",
        "description": (
            "Predict what typically follows a node (file path or node id) from "
            "learned directional transitions. Returns successors ranked by "
            "probability, normalized over all outgoing transitions. Useful for "
            "prefetching context the agent is likely to ask about next."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {"type": "string"},
                "from_node": {
                    "type": "string",
                    "description": "Source node (file path or node id) to look up successors for.",
                },
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["project_path", "from_node"],
        },
    },
    {
        "name": "neuralmind_feedback",
        "description": (
            "Record explicit retrieval feedback to strengthen or weaken synapse weights. "
            "Use signal='positive' with context_node_ids (the other results from the same "
            "query) to reinforce co-activation for a helpful node. Use signal='negative' to "
            "apply a targeted decay tick to an unhelpful node. LTP-protected edges (heavily "
            "co-activated) are never fully removed by a single negative signal."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to the project root directory",
                },
                "node_id": {
                    "type": "string",
                    "description": "ID of the node to give feedback on (from search results)",
                },
                "signal": {
                    "type": "string",
                    "enum": ["positive", "negative"],
                    "description": "'positive' to reinforce co-activation; 'negative' to decay",
                },
                "context_node_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Other node IDs from the same retrieval round (required for positive signal)",
                },
            },
            "required": ["project_path", "node_id", "signal"],
        },
    },
    {
        "name": "neuralmind_export_synapse_memory",
        "description": (
            "Render the learned synapse graph as markdown and write it to "
            "<project>/.neuralmind/SYNAPSE_MEMORY.md and (when present) "
            "Claude Code's auto-memory directory. Used to surface learned "
            "associations to agents that don't call NeuralMind tools directly."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"project_path": {"type": "string"}},
            "required": ["project_path"],
        },
    },
    {
        "name": "neuralmind_review",
        "description": (
            "Warn about likely co-breakage before a commit or code review. "
            "Given a list of changed files, runs spreading activation through "
            "the learned synapse graph and returns files NOT in the diff that "
            "have historically been edited together with the changed files. "
            "Use this to catch forgotten test files, tightly-coupled modules, "
            "or config updates that should accompany the current change."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to the project root directory",
                },
                "changed_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Project-relative or absolute paths of files being changed",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Maximum number of at-risk files to return (default: 10)",
                    "default": 10,
                },
            },
            "required": ["project_path", "changed_files"],
        },
    },
]


def handle_tool_call(name: str, arguments: dict[str, Any]) -> str:
    """Handle a tool call and return the result as JSON string."""
    handlers = {
        "neuralmind_wakeup": lambda args: tool_wakeup(args["project_path"]),
        "neuralmind_query": lambda args: tool_query(
            args["project_path"], args["question"], args.get("include_relevance", False)
        ),
        "neuralmind_search": lambda args: tool_search(
            args["project_path"], args["query"], args.get("n", 10)
        ),
        "neuralmind_build": lambda args: tool_build(args["project_path"], args.get("force", False)),
        "neuralmind_stats": lambda args: tool_stats(args["project_path"]),
        "neuralmind_benchmark": lambda args: tool_benchmark(args["project_path"]),
        "neuralmind_skeleton": lambda args: tool_skeleton(args["project_path"], args["file_path"]),
        "neuralmind_synaptic_neighbors": lambda args: tool_synaptic_neighbors(
            args["project_path"],
            args["query"],
            args.get("depth", 2),
            args.get("top_k", 10),
        ),
        "neuralmind_synapse_stats": lambda args: tool_synapse_stats(args["project_path"]),
        "neuralmind_synapse_decay": lambda args: tool_synapse_decay(args["project_path"]),
        "neuralmind_next_likely": lambda args: tool_next_likely(
            args["project_path"],
            args["from_node"],
            args.get("top_k", 5),
        ),
        "neuralmind_export_synapse_memory": lambda args: tool_export_synapse_memory(
            args["project_path"]
        ),
        "neuralmind_review": lambda args: tool_review(
            args["project_path"],
            args["changed_files"],
            args.get("top_k", 10),
        ),
        "neuralmind_feedback": lambda args: tool_feedback(
            args["project_path"],
            args["node_id"],
            args["signal"],
            args.get("context_node_ids"),
        ),
    }

    if name not in handlers:
        return json.dumps({"error": f"Unknown tool: {name}"})

    project_path_raw = arguments.get("project_path")
    project_path = str(project_path_raw) if project_path_raw else None
    actor = str(arguments.get("actor", "anonymous"))
    role = str(arguments.get("role", "builder"))

    try:
        if project_path is not None:
            security = get_security_manager(project_path)
            result = security.secure_call(actor, role, name, lambda: handlers[name](arguments))
        else:
            result = handlers[name](arguments)
        return json.dumps(result, indent=2, default=str)
    except (PermissionError, RuntimeError) as e:
        return json.dumps({"error": str(e), "code": "security_denied"})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def run_mcp_server():
    """Run the MCP server."""
    if not MCP_AVAILABLE:
        print(
            "Error: MCP SDK not available. Install with: pip install mcp",
            file=sys.stderr,
        )
        sys.exit(1)

    server = Server("neuralmind")

    @server.list_tools()
    async def list_tools():
        return [Tool(**t) for t in TOOLS]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        result = handle_tool_call(name, arguments)
        return [TextContent(type="text", text=result)]

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    """Main entry point."""
    import asyncio

    asyncio.run(run_mcp_server())


if __name__ == "__main__":
    main()
