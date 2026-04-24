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
from neuralmind.mcp_security import MCPSecurityManager, get_security_manager

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


def tool_query(project_path: str, question: str) -> dict[str, Any]:
    """Get optimized context for a specific question."""
    mind = get_mind(project_path)
    result = mind.query(question)
    return {
        "context": result.context,
        "tokens": result.budget.total,
        "reduction_ratio": round(result.reduction_ratio, 1),
        "layers": result.layers_used,
        "communities_loaded": result.communities_loaded,
        "search_hits": result.search_hits,
    }


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
]


def handle_tool_call(name: str, arguments: dict[str, Any]) -> str:
    """Handle a tool call and return the result as JSON string."""
    handlers = {
        "neuralmind_wakeup": lambda args: tool_wakeup(args["project_path"]),
        "neuralmind_query": lambda args: tool_query(args["project_path"], args["question"]),
        "neuralmind_search": lambda args: tool_search(
            args["project_path"], args["query"], args.get("n", 10)
        ),
        "neuralmind_build": lambda args: tool_build(args["project_path"], args.get("force", False)),
        "neuralmind_stats": lambda args: tool_stats(args["project_path"]),
        "neuralmind_benchmark": lambda args: tool_benchmark(args["project_path"]),
        "neuralmind_skeleton": lambda args: tool_skeleton(args["project_path"], args["file_path"]),
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
