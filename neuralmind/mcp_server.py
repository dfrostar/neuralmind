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

import asyncio
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


def clear_all_caches() -> None:
    """Clear all global caches. Used for testing and graceful shutdown."""
    _mind_cache.clear()
    _security_cache.clear()


def get_cache_stats() -> dict[str, int]:
    """Return current cache sizes for observability."""
    return {"minds": len(_mind_cache), "security": len(_security_cache)}


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


def tool_health(project_path: str) -> dict[str, Any]:
    """Lightweight health check for CI/CD, Docker, systemd."""
    import time
    from pathlib import Path
    
    nm_dir = Path(project_path) / ".neuralmind"
    ir_path = nm_dir / "index_ir.json"
    
    if not ir_path.exists():
        return {"status": "no_index", "healthy": False, "exit_code": 2}
    
    try:
        ir_meta = json.loads(ir_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        ir_meta = {}
    
    last_build = ir_meta.get("built_at", 0) or ir_path.stat().st_mtime
    age_hours = (time.time() - last_build) / 3600 if last_build else float("inf")
    
    disk_mb = sum(f.stat().st_size for f in nm_dir.rglob("*") if f.is_file()) / (1024 * 1024)
    
    synapse_count = 0
    synapse_path = nm_dir / "synapses.db"
    if synapse_path.exists():
        try:
            from neuralmind.synapses import SynapseStore
            synapse_count = SynapseStore(synapse_path).stats().get("edges", 0)
        except Exception:
            pass
    
    return {
        "status": "stale" if age_hours >= 24 else "healthy",
        "healthy": age_hours < 24,
        "exit_code": 1 if age_hours >= 24 else 0,
        "index_age_hours": round(age_hours, 1),
        "node_count": ir_meta.get("node_count", len(ir_meta.get("nodes", []))),
        "disk_mb": round(disk_mb, 2),
        "synapse_edges": synapse_count,
    }


def tool_benchmark(project_path: str) -> dict[str, Any]:
    """Run token reduction benchmark."""
    mind = get_mind(project_path)
    return mind.benchmark()


def tool_savings(
    project_path: str,
    cost: bool = False,
    model: str | None = None,
    queries_per_day: int = 100,
) -> dict[str, Any]:
    """Report cumulative measured token savings from the query event log."""
    from neuralmind.savings import compute_savings

    return compute_savings(
        project_path,
        cost=cost,
        model=model,
        queries_per_day=queries_per_day,
    )


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


def tool_structural_neighbors(
    project_path: str,
    query: str,
    relations: list[str] | None = None,
    blast_radius: bool = False,
    depth: int = 2,
) -> dict[str, Any]:
    """How a symbol is wired into the codebase, from the static code graph.

    Returns the symbol's callers, callees, base/sub classes, and importers —
    the precise structural relationships graphify extracts, distinct from the
    learned synapse graph. Use before editing a function's signature (to find
    every caller) or a class (to find overrides/subclasses). Pass
    ``blast_radius=true`` for the transitive set of code a change would affect.
    ``query`` may be a symbol name or a natural-language description; it is
    resolved to the closest graph node.
    """
    mind = get_mind(project_path)
    if blast_radius:
        return mind.blast_radius(query, depth=depth)
    return mind.structural_neighbors(query, relations=relations)


def tool_impact(project_path: str, symbol: str, depth: int = 1) -> dict[str, Any]:
    """What depends on ``symbol`` — reverse-dependency ("blast radius") lookup.

    Friendlier-named, richer-output sibling of
    ``neuralmind_structural_neighbors(blast_radius=true)``: each dependent
    carries which hop and which relation (calls/inherits/imports_from/
    implements) connects it, not just its id. Use before renaming, re-
    signing, or deleting a symbol to see everything a change would touch.
    ``symbol`` may be an exact node id or a natural-language description.
    """
    mind = get_mind(project_path)
    return mind.impact(symbol, depth=depth)


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


def tool_compliance_report(project_path: str, format: str = "json") -> dict[str, Any]:
    """Generate a validated compliance saving report via the running daemon.

    Scans the project for compliance annotations (CMMC, NIST, SOX, HIPAA,
    ISO), cross-references against ingested practice content nodes, and
    returns a structured report suitable for auditor evidence. Can be
    called via MCP while the daemon is running — no CLI export needed.

    Args:
        project_path: path to the project root
        format: ``json`` (default) returns structured data, ``markdown``
            returns a human-readable report

    Returns:
        dict with: timestamp, compliance_annotations (list of matched
        controls with source files/lines), practices_ingested (count),
        evidence_map (control → code mapping), synapse_linked (boolean
        indicating whether compliance annotations are synaptically linked)
    """
    import time
    from pathlib import Path

    from neuralmind.compliance_matcher import (
        compliance_synapse_key,
        find_compliance_annotations_in_file,
    )

    mind = get_mind(project_path, auto_build=False)
    project_root = Path(project_path).resolve()

    annotations = []
    control_ids_found = set()

    # Scan Python source files in the project for compliance annotations
    for fpath in sorted(project_root.rglob("*.py")):
        if ".neuralmind" in fpath.parts or "__pycache__" in fpath.parts:
            continue
        try:
            results = find_compliance_annotations_in_file(str(fpath))
            for r in results:
                annotations.append(
                    {
                        "file": str(fpath.relative_to(project_root)),
                        "line": r.get("span", (0, 0))[0],
                        "control_id": r.get("control_id", ""),
                        "framework": r.get("framework", ""),
                        "text": r.get("match_text", ""),
                    }
                )
                control_ids_found.add(r.get("control_id", ""))
        except Exception:
            continue

    # Check which controls are synaptically linked to code nodes
    synapse_store = mind.synapses
    synapse_linked = False
    linked_controls = []
    if synapse_store is not None:
        for ctrl_id in sorted(control_ids_found):
            # Find the framework for this control_id from annotations
            framework = next(
                (a["framework"] for a in annotations if a["control_id"] == ctrl_id), "UNKNOWN"
            )
            sk = compliance_synapse_key(ctrl_id, framework)
            try:
                with synapse_store._connect() as conn:
                    row = conn.execute(
                        "SELECT COUNT(*) FROM synapses WHERE node_a = ? OR node_b = ?",
                        (sk, sk),
                    ).fetchone()
                    if row and row[0] > 0:
                        synapse_linked = True
                        linked_controls.append({"control_id": ctrl_id, "edge_count": row[0]})
            except Exception:
                continue

    # Check CMMC practice ingestion via content nodes
    try:
        import sqlite3

        meta_path = project_root / ".neuralmind" / "neuralmind.db"
        practices_ingested = 0
        if meta_path.exists():
            conn = sqlite3.connect(str(meta_path))
            row = conn.execute(
                "SELECT COUNT(*) FROM meta WHERE key LIKE 'cmmc_practice:%'"
            ).fetchone()
            practices_ingested = row[0] if row else 0
            conn.close()
    except Exception:
        practices_ingested = 0

    report = {
        "timestamp": time.time(),
        "project": project_root.name,
        "compliance_annotations": annotations,
        "total_annotations": len(annotations),
        "unique_controls": len(control_ids_found),
        "practices_ingested": practices_ingested,
        "synapse_linked": synapse_linked,
        "linked_controls": linked_controls,
        "evidence_map": {
            c: [a["file"] for a in annotations if a["control_id"] == c]
            for c in sorted(control_ids_found)
        },
    }

    if format == "markdown":
        lines = [
            f"# Compliance Saving Report — {project_root.name}",
            f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
            "",
            "## Summary",
            f"- **Total compliance annotations found:** {len(annotations)}",
            f"- **Unique controls referenced:** {len(control_ids_found)}",
            f"- **CMMC practices ingested:** {practices_ingested}",
            f"- **Synapse-linked controls:** {len(linked_controls) if synapse_linked else 0}",
            "",
        ]
        for ctrl in sorted(control_ids_found):
            files = [a for a in annotations if a["control_id"] == ctrl]
            lines.append(f"### {ctrl}")
            for f in files[:10]:
                lines.append(f"- `{f['file']}:{f['line']}` — {f['text'][:80]}")
            if len(files) > 10:
                lines.append(f"- *... and {len(files) - 10} more*")
            lines.append("")
        report["markdown"] = "\n".join(lines)

    return report


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


def tool_structural_gaps(
    project_path: str,
    threshold: float = 0.1,
    top_k: int = 10,
) -> dict[str, Any]:
    """Detect structural gaps in a codebase using betweenness centrality.

    Reads graph.json, computes betweenness centrality via Brandes algorithm,
    identifies cross-community bridge nodes, and scores gaps as
    ``betweenness × (1 / (degree + 1))``.

    Args:
        project_path: Path to the project root directory.
        threshold: Minimum betweenness for bridge candidates (default: 0.1).
        top_k: Maximum number of gaps to return (default: 10).

    Returns:
        Dict with ``gaps`` (list of gap dicts), ``total_nodes``, ``total_edges``,
        and ``num_communities``.
    """
    import json
    import os

    from neuralmind.structural_gaps import detect_gaps

    graph_path = os.path.join(project_path, "graphify-out", "graph.json")
    if not os.path.exists(graph_path):
        return {"error": "No graph found. Run `neuralmind build` first.", "gaps": []}

    with open(graph_path, encoding="utf-8") as f:
        graph = json.load(f)

    gaps = detect_gaps(graph, top_k=top_k, threshold=threshold)

    # Count distinct communities
    communities = set()
    for node in graph.get("nodes", []):
        c = node.get("community")
        if c is not None:
            communities.add(c)

    return {
        "gaps": [
            {
                "node_id": g.node_id,
                "node_name": g.node_name,
                "communities": list(g.communities),
                "betweenness": g.betweenness,
                "degree": g.degree,
                "gap_score": g.gap_score,
                "suggested_connections": list(g.suggested_connections),
            }
            for g in gaps
        ],
        "total_nodes": len(graph.get("nodes", [])),
        "total_edges": len(graph.get("links", [])),
        "num_communities": len(communities),
    }


def tool_ingest_document(
    project_path: str, file_path: str, content_type: str = "auto"
) -> dict[str, Any]:
    """Ingest a document into the project's neural index.

    Parses PDF/Markdown/text into ContentNode objects that embed alongside
    code in the same vector space. Documents are chunked automatically for
    finer-grained retrieval. After ingestion, the document's contents
    surface in query() and search() alongside code.

    Synapse edges are seeded from documentation prose into the Hebbian
    graph when NEURALMIND_LLM_SEED=1 is set — connecting documented
    architectural relationships to code nodes.
    """
    mind = get_mind(project_path)
    return mind.ingest_document(file_path, content_type=content_type)


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
        "description": "Get optimized context for answering a question about a codebase. Achieves 12-50x typical token reduction by only loading relevant code clusters.",
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
        "name": "neuralmind_savings",
        "description": (
            "Report cumulative measured token savings from the project's query "
            "event log — how many tokens NeuralMind has actually saved across "
            "logged queries and wakeups, with an optional dollar estimate."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to the project root directory",
                },
                "cost": {
                    "type": "boolean",
                    "description": "Also estimate dollar savings priced on input tokens",
                },
                "model": {
                    "type": "string",
                    "description": "Pricing model for the cost estimate (e.g. claude-opus-4-8)",
                },
                "queries_per_day": {
                    "type": "integer",
                    "description": "Assumed queries/day for the monthly projection (default 100)",
                },
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
        "name": "neuralmind_structural_neighbors",
        "description": (
            "How a symbol is wired into the codebase, from the static code graph: "
            "its callers, callees, base/sub classes, and importers. Use before "
            "editing a function's signature (find all callers) or a class (find "
            "overrides), or pass blast_radius=true for the transitive set of code a "
            "change would affect. Precise and available day-one — complements the "
            "learned synapse graph."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {"type": "string"},
                "query": {
                    "type": "string",
                    "description": "Symbol name or NL description; resolved to a graph node.",
                },
                "relations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Optional filter: calls, inherits, imports, contains, or all. "
                        "Default surfaces callers/callees/bases/subclasses/importers."
                    ),
                },
                "blast_radius": {
                    "type": "boolean",
                    "default": False,
                    "description": "Return the transitive reverse-dependency set instead.",
                },
                "depth": {"type": "integer", "default": 2},
            },
            "required": ["project_path", "query"],
        },
    },
    {
        "name": "neuralmind_impact",
        "description": (
            "What depends on a symbol — reverse-dependency (blast-radius) lookup. "
            "Friendlier-named, richer-output sibling of "
            "neuralmind_structural_neighbors(blast_radius=true): each dependent "
            "carries which hop and which relation (calls/inherits/imports_from/"
            "implements) connects it, not just its id. Use before renaming, "
            "re-signing, or deleting a symbol to see everything a change would touch."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {"type": "string"},
                "symbol": {
                    "type": "string",
                    "description": "Symbol name, NL description, or exact node id.",
                },
                "depth": {
                    "type": "integer",
                    "default": 1,
                    "description": "How many hops of transitive dependents to include.",
                },
            },
            "required": ["project_path", "symbol"],
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
        "name": "neuralmind_health",
        "description": (
            "Lightweight health check for CI/CD and orchestrators. Returns "
            "index age, node count, last build time, disk usage, synapse edges. "
            "Exit code 0=healthy, 1=stale, 2=no index."
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
    {
        "name": "neuralmind_structural_gaps",
        "description": "Detect structural gaps using betweenness centrality. Identifies cross-community bridge nodes and structural blind spots in the codebase.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to the project root directory",
                },
                "threshold": {
                    "type": "number",
                    "description": "Minimum betweenness for bridge candidates (default: 0.1)",
                    "default": 0.1,
                },
                "top_k": {
                    "type": "integer",
                    "description": "Maximum number of gaps to return (default: 10)",
                    "default": 10,
                },
            },
            "required": ["project_path"],
        },
    },
    {
        "name": "neuralmind_compliance_report",
        "description": (
            "Generate a validated compliance saving report from the running "
            "daemon. Scans the project for compliance annotations (CMMC, NIST, "
            "SOX, HIPAA, ISO), cross-references against ingested practices, "
            "and returns an auditor-ready evidence map with synapse linkage "
            "information. No CLI export needed — call directly via MCP."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to the project root directory",
                },
                "format": {
                    "type": "string",
                    "enum": ["json", "markdown"],
                    "default": "json",
                    "description": "Output format — json (structured) or markdown (human-readable)",
                },
            },
            "required": ["project_path"],
        },
    },
    {
        "name": "neuralmind_ingest_document",
        "description": (
            "Ingest a document (PDF, Markdown, text) into the project's "
            "neural index. Parses and chunks the file into content nodes that "
            "embed alongside code in the same vector space — query() and "
            "search() will surface the document's content alongside code. "
            "Synapse edges are seeded from documentation prose when "
            "NEURALMIND_LLM_SEED=1 is set, connecting documented "
            "architectural relationships to code nodes."
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
                    "description": "Path to the document file (absolute or project-relative)",
                },
                "content_type": {
                    "type": "string",
                    "enum": ["auto", "pdf", "markdown", "text"],
                    "default": "auto",
                    "description": (
                        "Content type hint. 'auto' sniffs from file magic "
                        "bytes and extension. Use 'pdf', 'markdown', or "
                        "'text' to override."
                    ),
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
        "neuralmind_query": lambda args: tool_query(
            args["project_path"], args["question"], args.get("include_relevance", False)
        ),
        "neuralmind_search": lambda args: tool_search(
            args["project_path"], args["query"], args.get("n", 10)
        ),
        "neuralmind_build": lambda args: tool_build(args["project_path"], args.get("force", False)),
        "neuralmind_stats": lambda args: tool_stats(args["project_path"]),
        "neuralmind_health": lambda args: tool_health(args["project_path"]),
        "neuralmind_benchmark": lambda args: tool_benchmark(args["project_path"]),
        "neuralmind_savings": lambda args: tool_savings(
            args["project_path"],
            args.get("cost", False),
            args.get("model"),
            args.get("queries_per_day", 100),
        ),
        "neuralmind_skeleton": lambda args: tool_skeleton(args["project_path"], args["file_path"]),
        "neuralmind_synaptic_neighbors": lambda args: tool_synaptic_neighbors(
            args["project_path"],
            args["query"],
            args.get("depth", 2),
            args.get("top_k", 10),
        ),
        "neuralmind_structural_neighbors": lambda args: tool_structural_neighbors(
            args["project_path"],
            args["query"],
            args.get("relations"),
            args.get("blast_radius", False),
            args.get("depth", 2),
        ),
        "neuralmind_impact": lambda args: tool_impact(
            args["project_path"], args["symbol"], args.get("depth", 1)
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
        "neuralmind_structural_gaps": lambda args: tool_structural_gaps(
            args["project_path"],
            args.get("threshold", 0.1),
            args.get("top_k", 10),
        ),
        "neuralmind_feedback": lambda args: tool_feedback(
            args["project_path"],
            args["node_id"],
            args["signal"],
            args.get("context_node_ids"),
        ),
        "neuralmind_compliance_report": lambda args: tool_compliance_report(
            args["project_path"],
            args.get("format", "json"),
        ),
        "neuralmind_ingest_document": lambda args: tool_ingest_document(
            args["project_path"],
            args["file_path"],
            args.get("content_type", "auto"),
        ),
    }

    if name not in handlers:
        return json.dumps({"error": f"Unknown tool: {name}"})

    project_path_raw = arguments.get("project_path")
    project_path = str(project_path_raw) if project_path_raw else None
    actor = str(arguments.get("actor", "anonymous"))
    role = str(arguments.get("role", "builder"))

    if not project_path:
        return json.dumps({"error": "project_path is required", "code": "invalid_request"})

    try:
        security = get_security_manager(project_path)
        result = security.secure_call(actor, role, name, lambda: handlers[name](arguments))
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
        result = await asyncio.to_thread(handle_tool_call, name, arguments)
        return [TextContent(type="text", text=result)]

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    """Main entry point.

    Transport selection (F1): if NEURALMIND_MCP_TRANSPORT=streamable_http
    and deps are available, the Starlette app is served via uvicorn.
    Otherwise falls back to stdio (byte-compatible).
    """
    import asyncio

    transport_raw = __import__("os").environ.get("NEURALMIND_MCP_TRANSPORT", "")
    if transport_raw == "streamable_http":
        from .mcp_http import select_transport

        shared_memory = _get_shared_memory()
        transport = select_transport(shared_memory)
        if transport is not None:
            app = transport.get_starlette_app()
            if app is not None:
                import uvicorn

                uvicorn.run(app, host="127.0.0.1", port=8765)
                return
    asyncio.run(run_mcp_server())


# F2: Shared daemon memory registry (process-level).
_shared_memory: Any = None


def _get_shared_memory() -> Any:
    """Get or create the shared daemon memory for this process."""
    global _shared_memory
    if _shared_memory is None:
        from .daemon_memory import SharedDaemonMemory

        _shared_memory = SharedDaemonMemory()
    return _shared_memory


if __name__ == "__main__":
    main()
