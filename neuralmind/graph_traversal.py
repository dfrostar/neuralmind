"""graph_traversal.py — Learned co-access edges for the code graph.

NeuralMind's vector index records structural edges (calls, imports, inherits)
from static analysis. This module adds *traversal edges* learned from how the
agent actually moves through the codebase: whenever two files appear together
in a query result or are read in the same session, a co-access edge is
reinforced (Hebbian). Over time this captures "to understand X, you also
need Y" relationships that static analysis misses.

Design:
- Stdlib only.
- Edges are stored in the synapses table with namespace='traversal'.
- Co-access edges decay faster than structural edges (they're noisier).
- Spreading activation can then route through learned traversal paths.

The module hooks into the query pipeline: after a query returns its top hits,
every pair of hit files is reinforced via the synapse store. A decay rate
higher than the structural default reflects that these relationships are
ephemeral (a refactoring can break them).
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

# Co-access edges decay faster than structural edges
TRAVERSAL_DECAY_RATE = 1.5  # vs structural default ~0.6
TRAVERSAL_LTP_THRESHOLD = 8  # takes longer to become durable
TRAVERSAL_LTP_FLOOR = 0.15


def _file_of(node: dict) -> str:
    """Extract the source file from a search hit node."""
    meta = node.get("metadata") or {}
    return str(meta.get("source_file") or node.get("id") or "")


def reinforce_coaccess(store, hits: list[dict], namespace: str = "traversal") -> int:
    """Reinforce co-access edges between files that appeared together.

    Every pair of file hits gets a Hebbian reinforcement. The weight is
    small (0.30 = LEARNING_RATE), so repeated co-activation is needed
    before the edge is durable.

    Args:
        store: SynapseStore instance.
        hits: List of search hit dicts (from L3 search results).
        namespace: Synapse namespace (default 'traversal').

    Returns:
        Number of edge updates.
    """
    if len(hits) < 2:
        return 0

    files: list[str] = []
    for hit in hits:
        f = _file_of(hit)
        if f and f not in files:
            files.append(f)

    updated = 0
    # Reinforce every pair in the result set
    # Use store.reinforce() with a list of node_ids per pair
    for i in range(len(files)):
        for j in range(i + 1, len(files)):
            store.reinforce([files[i], files[j]], namespace=namespace, strength=0.30)
            updated += 1

    if updated:
        logger.debug(
            "[graph_traversal] reinforced %d co-access edges across %d files", updated, len(files)
        )

    return updated


def get_related_files(
    store,
    node_id: str,
    namespace: str = "traversal",
    k: int = 5,
) -> list[tuple[str, float]]:
    """Get the top-k files most strongly connected to a node via traversal.

    Useful for "auto-preload related files" and "where else might I need to
    look?" suggestions.

    Args:
        store: SynapseStore instance.
        node_id: The node to query (file path or symbol id).
        namespace: Traversal namespace.
        k: Max results.

    Returns:
        List of (related_node, weight) tuples.
    """
    rows = store.spread_activation_from(
        node_id, namespaces=[namespace], depth=1, top_k=k, spread_decay=TRAVERSAL_DECAY_RATE
    )
    return [(r["node"], r["energy"]) for r in rows]


def decay_traversal_edges(
    store, rate: float = TRAVERSAL_DECAY_RATE, min_created_days: float = 0.0
) -> int:
    """Decay traversal edges more aggressively than structural edges.

    Args:
        store: SynapseStore instance.
        rate: Multiplicative decay per day.
        min_created_days: Don't decay edges newer than this.

    Returns:
        Number of edges decayed.
    """
    cutoff = time.time() - (min_created_days * 86400)
    with store._connect() as conn:
        cur = conn.execute(
            "SELECT node_a, node_b, weight FROM synapses WHERE namespace = 'traversal' AND created_at < ?",
            (cutoff,),
        )
        rows = cur.fetchall()
        for node_a, node_b, weight in rows:
            new_weight = weight * (1.0 - rate)
            if new_weight <= 0.01:
                conn.execute(
                    "DELETE FROM synapses WHERE namespace = 'traversal' AND ((node_a = ? AND node_b = ?) OR (node_a = ? AND node_b = ?))",
                    (node_a, node_b, node_b, node_a),
                )
            else:
                conn.execute(
                    "UPDATE synapses SET weight = ? WHERE namespace = 'traversal' AND ((node_a = ? AND node_b = ?) OR (node_a = ? AND node_b = ?))",
                    (new_weight, node_a, node_b, node_b, node_a),
                )
        return len(rows)
