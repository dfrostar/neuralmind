"""G5 — Structural gap detection (InfraNodus-style betweenness).

Ports InfraNodus's betweenness-centrality gap detection into NeuralMind's
structural graph. Identifies cross-community bridge nodes and structural
blind spots where two communities should connect but don't.

Pure Python, stdlib-only. No NetworkX dependency.

Example:
    >>> import json
    >>> from neuralmind.structural_gaps import detect_gaps, format_structural_gaps
    >>> with open("graphify-out/graph.json") as f:
    ...     graph = json.load(f)
    >>> gaps = detect_gaps(graph, top_k=5)
    >>> print(format_structural_gaps(gaps))

See Also:
    - ``neuralmind.modularity`` — Louvain community detection
    - ``neuralmind.cli`` — CLI integration (``neuralmind gaps --structural``)
    - ``neuralmind.mcp_server`` — MCP tool (``neuralmind_structural_gaps``)
    - ``docs/specs/G5-BRD.md`` — business requirements
    - ``docs/specs/G5-TRD.md`` — technical specification
    - ``docs/specs/G5-TEST-PLAN.md`` — test cases

Version:
    1.9.0
"""

from __future__ import annotations

import heapq
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

# Default betweenness threshold for bridge candidates
GAP_THRESHOLD_DEFAULT = 0.005

# Maximum graph size before switching to approximate betweenness
MAX_BETWEENNESS_NODES = 2000

# Edge type weights by relation (from TRD §3).
# Higher weight = stronger relationship = shorter path distance.
EDGE_WEIGHTS: dict[str, float] = {
    "calls": 1.0,
    "inherits": 0.9,
    "imports_from": 0.8,
    "imports": 0.8,  # alias used in some graph.json files
    "contains": 0.3,
    "rationale_for": 0.2,
}


def _build_adjacency(
    graph: dict[str, Any],
    weight_field: str = "weight",
) -> tuple[list[str], dict[str, dict[str, float]]]:
    """Build adjacency list from graph.json.

    Returns ``(nodes, adj)`` where ``adj`` maps ``node_id -> {neighbor_id: distance}``.
    Distance is ``1 / weight`` so that stronger edges are "shorter" and
    more likely to carry shortest paths.

    Multiple links between the same pair collapse to the strongest (minimum distance).
    """
    raw_nodes = graph.get("nodes", [])
    nodes: list[str] = []
    node_set: set[str] = set()
    for n in raw_nodes:
        nid = n.get("id")
        if nid:
            nodes.append(nid)
            node_set.add(nid)

    adj: dict[str, dict[str, float]] = {n: {} for n in nodes}

    for link in graph.get("links", []):
        src = link.get("source")
        tgt = link.get("target")
        if src not in node_set or tgt not in node_set:
            continue

        # Resolve weight: explicit field → relation-based fallback
        w = link.get(weight_field)
        if w is None or not isinstance(w, (int, float)) or w <= 0:
            relation = link.get("relation", "calls")
            w = EDGE_WEIGHTS.get(relation, 0.5)

        # Distance = 1 / weight (higher weight = closer = preferred path)
        dist = 1.0 / w

        # Undirected: keep the minimum distance (maximum weight) per pair
        if tgt not in adj[src] or dist < adj[src][tgt]:
            adj[src][tgt] = dist
        if src not in adj[tgt] or dist < adj[tgt][src]:
            adj[tgt][src] = dist

    return nodes, adj


def compute_betweenness(
    graph: dict[str, Any],
    *,
    normalized: bool = True,
    weight: str = "weight",
) -> dict[str, float]:
    """Compute betweenness centrality via Brandes algorithm (weighted).

    Runs Dijkstra from every node (O(VE + V² log V) for weighted graphs).
    For graphs larger than MAX_BETWEENNESS_NODES, samples k ≈ min(V, 1000)
    source nodes uniformly and scales the result back.

    Args:
        graph: graph.json dict with ``nodes`` and ``links``.
        normalized: If True, scale so a star-graph centre reaches 1.0.
        weight: Link field name for edge weight.

    Returns:
        ``{node_id: betweenness_centrality}`` — empty dict for empty graphs.
    """
    nodes, adj = _build_adjacency(graph, weight)
    n = len(nodes)

    if n < 3:
        return dict.fromkeys(nodes, 0.0)

    betweenness: dict[str, float] = dict.fromkeys(nodes, 0.0)

    # Determine source nodes: full computation for small graphs,
    # sampled approximation for large ones.
    if n <= MAX_BETWEENNESS_NODES:
        sources = nodes
    else:
        # Uniform sampling with deterministic seed for reproducibility
        import random

        rng = random.Random(42)
        k = min(n, 100)  # k-approximate betweenness
        sources = rng.sample(nodes, k)

    for s in sources:
        # --- Forward phase: Dijkstra from s ---
        dist: dict[str, float] = dict.fromkeys(nodes, math.inf)
        dist[s] = 0.0
        sigma: dict[str, float] = dict.fromkeys(nodes, 0.0)
        sigma[s] = 1.0
        pred: dict[str, list[str]] = {node: [] for node in nodes}

        pq: list[tuple[float, str]] = [(0.0, s)]

        while pq:
            d, v = heapq.heappop(pq)
            if d > dist[v] + 1e-12:
                continue
            for w_node, edge_dist in adj[v].items():
                new_dist = d + edge_dist
                if new_dist < dist[w_node] - 1e-12:
                    dist[w_node] = new_dist
                    heapq.heappush(pq, (new_dist, w_node))
                    pred[w_node] = [v]
                    sigma[w_node] = sigma[v]
                elif abs(new_dist - dist[w_node]) <= 1e-12:
                    pred[w_node].append(v)
                    sigma[w_node] += sigma[v]

        # --- Backward phase: accumulate dependencies ---
        delta: dict[str, float] = dict.fromkeys(nodes, 0.0)

        # Process in decreasing distance order (skip unreachable + source)
        reachable = [node for node in nodes if dist[node] < math.inf and node != s]
        reachable.sort(key=lambda n: dist[n], reverse=True)

        for w_node in reachable:
            for v in pred[w_node]:
                if sigma[w_node] > 0:
                    delta[v] += (sigma[v] / sigma[w_node]) * (1.0 + delta[w_node])
            betweenness[w_node] += delta[w_node]

    # Scale up from sample to population
    if n > MAX_BETWEENNESS_NODES:
        scale_up = n / len(sources)
        for node in betweenness:
            betweenness[node] *= scale_up

    # Normalize: star-graph centre → 1.0
    if normalized and n > 2:
        scale = 1.0 / ((n - 1) * (n - 2))
        for node in betweenness:
            betweenness[node] *= scale

    return betweenness


def find_bridge_candidates(
    graph: dict[str, Any],
    communities: dict[str, int],
    *,
    threshold: float = GAP_THRESHOLD_DEFAULT,
    min_communities: int = 2,
) -> list[str]:
    """Find nodes that bridge multiple communities.

    A node is a bridge candidate when:
    1. Its betweenness ≥ ``threshold``.
    2. Its neighbourhood (own community + neighbours' communities)
       spans ≥ ``min_communities`` distinct communities.
    3. Its degree ≤ ``median_degree × 2`` (hubs filtered out).

    Args:
        graph: graph.json dict.
        communities: ``{node_id: community_id}`` mapping.
        threshold: Minimum betweenness value.
        min_communities: Minimum distinct communities in neighbourhood.

    Returns:
        Node IDs sorted by betweenness descending.
    """
    betweenness = compute_betweenness(graph, normalized=True)
    nodes, adj = _build_adjacency(graph)

    if not adj:
        return []

    # Hub filter: median degree × 2
    degrees = [len(neighbors) for neighbors in adj.values() if neighbors]
    if not degrees:
        return []
    sorted_degrees = sorted(degrees)
    median_degree = sorted_degrees[len(sorted_degrees) // 2]
    max_degree = median_degree * 2

    candidates: list[str] = []
    for node in nodes:
        cb = betweenness.get(node, 0.0)
        if cb < threshold:
            continue

        # Distinct communities in this node's neighbourhood
        bridged: set[int] = set()
        own_c = communities.get(node)
        if own_c is not None:
            bridged.add(own_c)
        for neighbor in adj.get(node, {}):
            c = communities.get(neighbor)
            if c is not None:
                bridged.add(c)

        if len(bridged) < min_communities:
            continue

        # Filter high-degree hubs
        if len(adj.get(node, {})) > max_degree:
            continue

        candidates.append(node)

    candidates.sort(key=lambda n: betweenness.get(n, 0.0), reverse=True)
    return candidates


@dataclass(frozen=True)
class Gap:
    """A structural gap — a node that bridges communities but is under-connected.

    Ordering methods compare by ``gap_score`` only (higher = more critical).
    """

    node_id: str
    node_name: str
    communities: tuple[int, ...]  # sorted community labels this node bridges
    betweenness: float  # [0, 1] normalized
    degree: int  # number of direct neighbors
    gap_score: float  # betweenness * (1 / (degree + 1))
    suggested_connections: tuple[str, ...]  # node_ids this could connect to

    @property
    def is_significant(self) -> bool:
        """True when gap_score meets the default threshold."""
        return self.gap_score >= GAP_THRESHOLD_DEFAULT

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Gap):
            return NotImplemented
        return self.gap_score < other.gap_score

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Gap):
            return NotImplemented
        return self.gap_score > other.gap_score

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Gap):
            return NotImplemented
        return self.gap_score <= other.gap_score

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Gap):
            return NotImplemented
        return self.gap_score >= other.gap_score


def detect_gaps(
    graph: dict[str, Any],
    communities: dict[str, int] | None = None,
    *,
    top_k: int = 10,
    threshold: float = GAP_THRESHOLD_DEFAULT,
) -> list[Gap]:
    """Detect structural gaps — ranked cross-community bridge candidates.

    Args:
        graph: graph.json dict.
        communities: ``{node_id: community_id}``. If None, reads from
            ``graph["nodes"][*]["community"]``; falls back to Louvain
            inline when no community field is present.
        top_k: Maximum number of gaps to return.
        threshold: Minimum betweenness for bridge candidates.

    Returns:
        List of :class:`Gap` objects sorted by ``gap_score`` descending.
    """
    # --- Resolve communities ---
    if communities is None:
        communities = {}
        for node in graph.get("nodes", []):
            nid = node.get("id")
            c = node.get("community")
            if nid and c is not None:
                communities[nid] = c

    # Fallback: run Louvain inline when graph lacks community assignments
    nodes, adj = _build_adjacency(graph)
    if not communities and len(nodes) >= 3:
        try:
            from .modularity import louvain_clustering

            # Convert distance back to weight for Louvain
            weight_adj: dict[str, dict[str, float]] = {node: {} for node in nodes}
            for node in nodes:
                for neighbor, dist in adj[node].items():
                    weight_adj[node][neighbor] = 1.0 / dist if dist > 0 else 1.0
            communities = louvain_clustering(weight_adj)
        except ImportError:
            pass

    betweenness = compute_betweenness(graph, normalized=True)
    bridge_candidates = find_bridge_candidates(graph, communities, threshold=threshold)

    # Build community → nodes mapping for suggested-connection search
    community_nodes: dict[int, list[str]] = defaultdict(list)
    for nid, c in communities.items():
        community_nodes[c].append(nid)

    # Build node-id → label mapping for human-readable names
    id_to_label: dict[str, str] = {}
    for node in graph.get("nodes", []):
        nid = node.get("id")
        if nid:
            id_to_label[nid] = node.get("label", nid)

    gaps: list[Gap] = []
    for node in bridge_candidates:
        cb = betweenness.get(node, 0.0)
        degree = len(adj.get(node, {}))
        gap_score = cb * (1.0 / (degree + 1))

        # Communities this node bridges
        bridged: set[int] = set()
        own_c = communities.get(node)
        if own_c is not None:
            bridged.add(own_c)
        neighbors = adj.get(node, {})
        for neighbor in neighbors:
            c = communities.get(neighbor)
            if c is not None:
                bridged.add(c)

        # Suggested connections: highest-degree non-neighbor per other community
        neighbors_set = set(neighbors.keys())
        suggested: list[str] = []
        for c in sorted(bridged):
            if c == own_c:
                continue
            # Candidates: nodes in community c, not already connected
            cands = [n for n in community_nodes.get(c, []) if n != node and n not in neighbors_set]
            if cands:
                cands.sort(key=lambda n: len(adj.get(n, {})), reverse=True)
                suggested.append(cands[0])

        gap = Gap(
            node_id=node,
            node_name=id_to_label.get(node, node),
            communities=tuple(sorted(bridged)),
            betweenness=round(cb, 6),
            degree=degree,
            gap_score=round(gap_score, 6),
            suggested_connections=tuple(suggested),
        )
        gaps.append(gap)

    gaps.sort(key=lambda g: g.gap_score, reverse=True)
    return gaps[:top_k]


def format_structural_gaps(gaps: list[Gap]) -> str:
    """Render gaps as a human-readable report.

    Output includes community pairs, betweenness, degree, and gap_score
    for each structural gap found.
    """
    if not gaps:
        return "## Structural Gaps — betweenness × inverse-degree\n\nNo structural gaps found."

    lines = ["## Structural Gaps — betweenness × inverse-degree", ""]

    for i, gap in enumerate(gaps, 1):
        community_str = ", ".join(str(c) for c in gap.communities)
        lines.append(
            f"{i}. {gap.node_name} (communities: {community_str})  "
            f"betweenness={gap.betweenness:.3f}  degree={gap.degree}  "
            f"gap_score={gap.gap_score:.3f}"
        )
        if gap.suggested_connections:
            lines.append(f"   suggested connections: {', '.join(gap.suggested_connections)}")

    return "\n".join(lines)
