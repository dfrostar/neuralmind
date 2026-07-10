"""
querying.py — read-side query/search formatting
================================================

Presentation helpers over an already-built index: hybrid-highlight
prefixes for query results, the compact file skeleton view, and the
graph payload for the ``serve`` graph-view UI. Extracted from
``core.py``; each function takes the :class:`~neuralmind.core.NeuralMind`
instance and is read-only over its embedder/synapse state. Callers are
responsible for ``_ensure_built()`` — these functions assume a built
index.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .core import NeuralMind


def build_hybrid_highlights(
    mind: NeuralMind, question: str, cached_hits: list[dict] | None = None
) -> str:
    if cached_hits:
        results = cached_hits[: mind.MAX_HYBRID_HIGHLIGHT_RESULTS]
    else:
        results = mind.embedder.search(question, n=mind.MAX_HYBRID_HIGHLIGHT_RESULTS)
    if not results:
        return ""
    lines = ["## Hybrid Highlights"]
    for item in results:
        metadata = item.get("metadata", {})
        label = metadata.get("label", item.get("id", "unknown"))
        source = metadata.get("source_file", "")
        score = item.get("score", 0.0)
        source_suffix = f" ({source})" if source else ""
        lines.append(f"- {label}{source_suffix} — score {score:.2f}")
    return "\n".join(lines)


def skeleton(mind: NeuralMind, file_path: str) -> str:
    """Return a compact skeleton view of a file using graph data.

    The skeleton contains:
    - File header (community, function count)
    - Function list with line numbers and one-line rationale from the graph
    - Internal call graph (within the file)
    - Cross-file relationships (shares_data_with, imports_from edges)
    - Pointer to bypass for full source

    Args:
        mind: A built NeuralMind instance
        file_path: Path to the source file (absolute or project-relative)

    Returns:
        Formatted skeleton text, or empty string if file is not indexed
    """
    nodes = mind.embedder.get_file_nodes(file_path)
    if not nodes:
        return ""

    node_ids = {n["id"] for n in nodes}
    edges = mind.embedder.get_file_edges(file_path, node_ids=node_ids)

    # Partition nodes
    code_nodes = [n for n in nodes if n.get("file_type") == "code"]
    rationale_nodes = [n for n in nodes if n.get("file_type") == "rationale"]

    # Map code node id → rationale text (via rationale_for edges)
    # Edge shape: {relation: "rationale_for", _src: rationale_id, _tgt: code_id, ...}
    rationale_map: dict[str, str] = {}
    for e in edges:
        if e.get("relation") != "rationale_for":
            continue
        src = e.get("_src") or e.get("source")
        tgt = e.get("_tgt") or e.get("target")
        # Find the rationale node
        rationale_node = next(
            (rn for rn in rationale_nodes if rn["id"] in (src, tgt)),
            None,
        )
        code_node = next(
            (cn for cn in code_nodes if cn["id"] in (src, tgt)),
            None,
        )
        if rationale_node and code_node:
            label = rationale_node.get("label", "").strip()
            # Rationale labels are sometimes truncated docstrings; strip trailing ellipsis
            if label:
                rationale_map[code_node["id"]] = label[:120]

    # Separate the file-level node (source_location "L1" or label matching filename)
    file_node = next(
        (
            n
            for n in code_nodes
            if n.get("source_location") == "L1"
            or n.get("label", "").endswith((".py", ".ts", ".js", ".go", ".rs"))
        ),
        None,
    )
    function_nodes = [n for n in code_nodes if n is not file_node]

    # Sort functions by line number
    def _line_no(node: dict) -> int:
        loc = node.get("source_location", "L0")
        try:
            return int(loc.lstrip("L"))
        except ValueError:
            return 0

    function_nodes.sort(key=_line_no)

    # Build call graph (within-file calls)
    calls_map: dict[str, list[str]] = {}
    for e in edges:
        if e.get("relation") != "calls":
            continue
        # Graph stores calls as target calls source (reversed semantics per exploration)
        src = e.get("_src") or e.get("source")
        tgt = e.get("_tgt") or e.get("target")
        if src in node_ids and tgt in node_ids:
            # Display direction: caller → callee
            # Per graphify convention, _src is caller, _tgt is callee
            caller_id = src
            callee_id = tgt
            callee_node = next((n for n in function_nodes if n["id"] == callee_id), None)
            caller_node = next((n for n in function_nodes if n["id"] == caller_id), None)
            if caller_node and callee_node:
                calls_map.setdefault(caller_node.get("label", caller_id), []).append(
                    callee_node.get("label", callee_id)
                )

    # Cross-file edges
    cross_edges = [
        e
        for e in edges
        if e.get("relation") in ("shares_data_with", "imports_from", "implements", "uses")
        and (
            (e.get("_src") in node_ids) != (e.get("_tgt") in node_ids)
        )  # exactly one endpoint inside
    ]

    # Format output
    lines: list[str] = []
    community = nodes[0].get("community", "?")
    lines.append(f"# {file_path}  (community {community}, {len(function_nodes)} functions)")
    lines.append("")
    lines.append("## Functions")

    # Compute padding for nice alignment
    max_label = max((len(n.get("label", "")) for n in function_nodes), default=12)
    for n in function_nodes:
        loc = n.get("source_location", "L?")
        label = n.get("label", "?")
        rat = rationale_map.get(n["id"])
        if rat:
            lines.append(f"{loc:<5} {label:<{max_label}}  — {rat}")
        else:
            lines.append(f"{loc:<5} {label}")

    if calls_map:
        lines.append("")
        lines.append("## Call graph (within this file)")
        for caller, callees in calls_map.items():
            unique = sorted(set(callees))
            lines.append(f"{caller} → {', '.join(unique)}")

    if cross_edges:
        lines.append("")
        lines.append("## Cross-file")
        seen_pairs: set[tuple[str, str, str]] = set()
        for e in cross_edges[:10]:  # cap to avoid bloat
            rel = e.get("relation", "?")
            src = e.get("_src") or e.get("source")
            tgt = e.get("_tgt") or e.get("target")
            conf = e.get("confidence", "")
            score = e.get("confidence_score", "")
            pair = (src, tgt, rel)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            # Name the out-of-file endpoint
            our_ids = node_ids
            inside_id = src if src in our_ids else tgt
            outside_id = tgt if src in our_ids else src
            inside_label = next(
                (n.get("label", inside_id) for n in nodes if n["id"] == inside_id),
                inside_id,
            )
            score_str = f" {score}" if score else ""
            lines.append(f"{inside_label} {rel} → {outside_id} ({conf}{score_str})")

    lines.append("")
    lines.append("[Full source available: Read this file with NEURALMIND_BYPASS=1]")

    return "\n".join(lines)


def graph_data(
    mind: NeuralMind, synapse_min_weight: float = 0.05, synapse_limit: int = 2000
) -> dict:
    """Return the full code graph for the ``serve`` graph-view UI.

    Combines structural edges (calls/imports from graph.json) with the
    learned synapse overlay. Node ids are the embedder's graph ids so
    the overlay lines up with the structural nodes. Read-only — never
    mutates the index or the synapse store.
    """
    raw_nodes = list(getattr(mind.embedder, "nodes", []) or [])
    raw_edges = list(getattr(mind.embedder, "edges", []) or [])

    nodes = []
    for n in raw_nodes:
        nid = str(n.get("id", n.get("label", "")))
        if not nid:
            continue
        nodes.append(
            {
                "id": nid,
                "label": n.get("label", nid),
                "file_type": n.get("file_type", "unknown"),
                "source_file": n.get("source_file", ""),
                "source_location": n.get("source_location", ""),
                "community": int(n.get("community", -1)),
            }
        )
    node_ids = {n["id"] for n in nodes}

    edges = []
    for e in raw_edges:
        src = e.get("_src") or e.get("source")
        tgt = e.get("_tgt") or e.get("target")
        if src not in node_ids or tgt not in node_ids:
            continue
        edges.append(
            {
                "source": src,
                "target": tgt,
                "relation": e.get("relation", "related"),
            }
        )

    synapses = []
    store = mind.synapses
    if store is not None:
        try:
            for a, b, weight, count in store.edges(
                min_weight=synapse_min_weight, limit=synapse_limit
            ):
                # Synapse ids can include community_* pseudo-nodes that
                # aren't real graph nodes — keep only edges we can draw.
                if a in node_ids and b in node_ids:
                    synapses.append(
                        {
                            "source": a,
                            "target": b,
                            "weight": round(weight, 4),
                            "activation_count": count,
                        }
                    )
        except Exception:
            pass

    return {
        "project": mind.project_path.name,
        # Full absolute path so the UI can key per-project state (e.g.
        # saved canvas layouts) without collisions between two repos
        # that happen to share a basename.
        "project_path": str(mind.project_path.resolve()),
        "nodes": nodes,
        "edges": edges,
        "synapses": synapses,
        "stats": {
            "nodes": len(nodes),
            "edges": len(edges),
            "synapses": len(synapses),
        },
    }
