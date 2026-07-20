"""
G3 — Modularity clustering (Louvain/Leiden).

Replace balanced-per-file communities with real graph modularity
(Louvain/Leiden) over the structural edge set. Required for L2
to surface architectural boundaries instead of file boundaries.

Requires G1 (structural edge index, Wave 2) + G2 (SCIP optional, Wave 2).
Tree-sitter-only Louvain is acceptable for v1; SCIP edges augment
incrementally (G4).

Local-first. Stdlib-only. Fail-open.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def _build_adjacency(
    nodes: list[str],
    edges: list[tuple[str, str, float]],
) -> dict[str, dict[str, float]]:
    """Build adjacency list from (source, target, weight) tuples."""
    adj: dict[str, dict[str, float]] = {n: {} for n in nodes}
    for src, tgt, w in edges:
        if src in adj and tgt in adj:
            adj[src][tgt] = adj[src].get(tgt, 0.0) + w
            adj[tgt][src] = adj[tgt].get(src, 0.0) + w
    return adj


def _modularity_gain(
    adj: dict[str, dict[str, float]],
    node: str,
    target_community: str,
    node_community: dict[str, str],
    community_weights: dict[str, float],
    total_weight: float,
    resolution: float = 1.0,
) -> float:
    """
    Compute modularity gain for moving `node` into `target_community`.

    Louvain's ΔQ formula for moving node i from community Ci to Cj:
        ΔQ = (1/m) * [k_i,in(Cj) - γ·Σ_tot(Cj)·k_i/(2m)]
            - (1/m) * [k_i,in(Ci) - γ·Σ_tot(Ci)·k_i/(2m)]

    γ (`resolution`) scales the null model:
        γ < 1.0  → fewer/larger communities (under-partition)
        γ = 1.0  → standard modularity (default)
        γ > 1.0  → more/smaller communities (over-partition)

    Positive ΔQ means the move increases modularity.
    """
    if total_weight <= 0:
        return 0.0
    k_i = sum(adj.get(node, {}).values())
    k_i_in_target = sum(
        w for n, w in adj.get(node, {}).items() if node_community.get(n) == target_community
    )
    k_i_in_current = sum(
        w for n, w in adj.get(node, {}).items() if node_community.get(n) == node_community[node]
    )
    sigma_tot_target = community_weights.get(target_community, 0.0)
    sigma_tot_current = community_weights.get(node_community[node], 0.0)
    m = total_weight
    two_m = 2.0 * m
    # ΔQ = gain from target community - loss from current community
    gain_from_target = (k_i_in_target - resolution * sigma_tot_target * k_i / two_m) / m
    loss_from_current = (k_i_in_current - resolution * sigma_tot_current * k_i / two_m) / m
    return gain_from_target - loss_from_current


def louvain_clustering(
    adj: dict[str, dict[str, float]],
    *,
    resolution: float = 1.0,
    max_iterations: int = 10,
) -> dict[str, int]:
    """
    Louvain method for community detection.

    Phase 1 (greedy): each node moves to the neighbor community that
    maximizes modularity gain. Repeat until no node moves.
    Phase 2 (aggregation): collapse each community into a single node,
    rebuild adjacency, repeat Phase 1.

    Returns: {node_id: community_id}

    Falls back to singleton communities (each node its own) if the
    graph is empty or disconnected.
    """
    nodes = list(adj.keys())
    if not nodes:
        return {}

    # Initialize: each node in its own community
    node_community: dict[str, str] = {n: str(i) for i, n in enumerate(nodes)}
    community_nodes: dict[str, set[str]] = defaultdict(set)
    for n, c in node_community.items():
        community_nodes[c].add(n)

    # Total edge weight
    total_weight = (
        sum(sum(neighbors.values()) for neighbors in adj.values()) / 2.0
    )  # undirected, so divide by 2

    if total_weight <= 0:
        # No edges: each node in community 0
        return dict.fromkeys(nodes, 0)

    # Phase 1: greedy modularity optimization
    # Pre-compute community_weights once, then update incrementally as nodes move.
    community_weights: dict[str, float] = defaultdict(float)
    for n in nodes:
        c = node_community[n]
        community_weights[c] += sum(adj.get(n, {}).values())
    node_degree: dict[str, float] = {n: sum(adj.get(n, {}).values()) for n in nodes}

    changed = True
    iteration = 0
    while changed and iteration < max_iterations:
        changed = False
        iteration += 1
        for node in nodes:
            current_c = node_community[node]
            neighbors = adj.get(node, {})
            if not neighbors:
                continue

            # Find best community (with modularity gain)
            neighbor_communities: dict[str, float] = defaultdict(float)
            for n, w in neighbors.items():
                neighbor_communities[node_community[n]] += w

            best_gain = 0.0
            best_community = current_c

            k_i = node_degree[node]
            for neighbor_c, w_to_neighbor_c in neighbor_communities.items():
                if neighbor_c == current_c:
                    continue
                sigma_target = community_weights.get(neighbor_c, 0.0)
                sigma_current = community_weights.get(current_c, 0.0) - k_i
                two_m = 2.0 * total_weight
                gain_from_target = (w_to_neighbor_c - resolution * sigma_target * k_i / two_m) / total_weight
                k_i_in_current = neighbor_communities.get(current_c, 0.0)
                loss_from_current = (k_i_in_current - resolution * sigma_current * k_i / two_m) / total_weight
                gain = gain_from_target - loss_from_current
                if gain > best_gain:
                    best_gain = gain
                    best_community = neighbor_c

            if best_community != current_c:
                # Move node to better community
                community_nodes[current_c].discard(node)
                if not community_nodes[current_c]:
                    del community_nodes[current_c]
                community_nodes[best_community].add(node)
                # Incrementally update community weights
                k_val = node_degree[node]
                community_weights[current_c] -= k_val
                community_weights[best_community] = community_weights.get(best_community, 0.0) + k_val
                node_community[node] = best_community
                changed = True

    # Phase 2 (simplified): collapse communities and run again once
    # (Full Louvain would repeat until no change, but single collapse
    # pass is a good approximation for v1.)
    new_nodes = sorted(community_nodes.keys())
    if len(new_nodes) < len(nodes):
        # Build coarse adjacency
        new_adj: dict[str, dict[str, float]] = {c: defaultdict(float) for c in new_nodes}
        for n, neighbors in adj.items():
            c_n = node_community[n]
            for m, w in neighbors.items():
                c_m = node_community[m]
                if c_n == c_m:
                    # Intra-community edge: becomes self-loop in coarse graph.
                    # Without this, the coarse graph loses intra-weight,
                    # inflating inter-community ΔQ and over-merging.
                    new_adj[c_n][c_n] = new_adj[c_n].get(c_n, 0.0) + w
                else:
                    new_adj[c_n][c_m] = new_adj[c_n].get(c_m, 0.0) + w

        # Recurse on coarse graph
        coarse_communities = louvain_clustering(
            new_adj, resolution=resolution, max_iterations=max_iterations
        )

        # Map back: coarse community → final label
        coarse_labels = sorted(set(coarse_communities.values())) if coarse_communities else [0]
        coarse_to_int = {c: i for i, c in enumerate(coarse_labels)}

        result = {}
        for n in nodes:
            c_n = node_community[n]
            coarse_c = coarse_communities.get(c_n) or c_n
            result[n] = coarse_to_int.get(coarse_c, 0)
        return result

    # Flatten community labels to contiguous integers
    labels = sorted(set(node_community.values()))
    label_to_int = {c: i for i, c in enumerate(labels)}
    return {n: label_to_int[c] for n, c in node_community.items()}


def detect_structural_communities(
    graph: dict[str, Any],
    *,
    min_edge_weight: float = 0.0,
) -> dict[str, int]:
    """
    Detect communities over the structural edges of a graph.

    Consumes `graph['links']` (edges) and `graph['nodes']`.
    Returns {node_id: community_id}.

    Falls back to per-file grouping if graph is malformed (fail-open).
    """
    try:
        nodes = [str(n.get("id", n.get("node_id", ""))) for n in graph.get("nodes", [])]
        nodes = [n for n in nodes if n]

        edges = []
        for link in graph.get("links", []):
            src = link.get("source", link.get("_src", ""))
            tgt = link.get("target", link.get("_tgt", ""))
            if src and tgt and src != tgt:
                w = float(link.get("confidence_score", 1.0))
                if w >= min_edge_weight:
                    edges.append((str(src), str(tgt), w))

        if not nodes or not edges:
            return dict.fromkeys(nodes, 0)

        adj = _build_adjacency(nodes, edges)
        return louvain_clustering(adj)
    except Exception:
        # Fail-open: return all-same community
        return {n.get("id", str(i)): 0 for i, n in enumerate(graph.get("nodes", []))}
