"""
structural.py — Typed structural edge index over the code graph.

NeuralMind's recall runs on two *soft* signals: semantic similarity
(vector + BM25) and learned co-activation (the Hebbian synapse layer). This
module adds the *hard*, precise signal the graph has carried all along —
how the code is actually wired.

``graphify`` (and the in-repo :mod:`neuralmind.graphgen`) already emit typed
structural edges into ``graph.json`` — ``calls``, ``inherits``,
``imports_from``, ``contains`` and friends — and the embedder loads them
into ``embedder.edges``. Until now they were consumed only by the graph-view
UI and the IR. :class:`StructuralIndex` turns them into a queryable,
agent-visible layer that sits *beside* the synapse store:

- **structural** = innate wiring: precise, known on day one, non-decaying.
- **synaptic** = learned potentiation: earned from how you actually work.

The two fuse in retrieval (see ``context_selector._apply_structural_expansion``)
without competing: structure says what *can* be related; synapses say what
*actually* gets used together.

Design:
- Pure-Python, stdlib-only (no ChromaDB / numpy) so it tests like the
  synapse layer and stays importable in the ChromaDB-free base package.
- References node ids **verbatim** from the loaded graph — it never mints or
  reconstructs ids, so it is correct for both the real graphify id scheme
  and the in-repo graphgen one.
- Direction-aware: every edge contributes a *forward* view (from its
  ``source``) and a *reverse* view (from its ``target``). ``A --calls--> B``
  makes ``B`` a callee of ``A`` and ``A`` a caller of ``B``.
- Hub-normalized: a utility called by hundreds of sites can't flood recall
  or a blast radius; high-degree views are down-weighted / truncated.
"""

from __future__ import annotations

import math
from collections import defaultdict, deque
from collections.abc import Iterable

# Raw graph ``relation`` → (forward_view, reverse_view). The forward view is
# named from the edge's ``source`` node; the reverse view from its ``target``.
RELATION_VIEWS: dict[str, tuple[str, str]] = {
    "calls": ("callees", "callers"),
    "inherits": ("bases", "subclasses"),
    "implements": ("interfaces", "implementers"),
    "imports_from": ("imports", "importers"),
    "imports": ("imports", "importers"),
    "contains": ("members", "container"),
    "uses": ("uses", "used_by"),
    "references": ("uses", "used_by"),
}

# All view names known to the index (both directions of every relation).
ALL_VIEWS: tuple[str, ...] = tuple(
    dict.fromkeys(v for pair in RELATION_VIEWS.values() for v in pair)
)

# Views surfaced in the default ``neighbors()`` result and used to seed
# recall. ``contains``/``members``/``container`` and ``uses``/``used_by`` are
# indexed but off by default — structurally real, but noisy in the common
# "what does editing this touch?" question. Reach them via explicit relations.
DEFAULT_VIEWS: tuple[str, ...] = (
    "callers",
    "callees",
    "bases",
    "subclasses",
    "importers",
)

# Reverse-dependency views: "who depends on this node?" — the blast radius of
# a change. Callers, importers, subclasses, and implementers all break if the
# node's contract changes.
BLAST_VIEWS: tuple[str, ...] = ("callers", "importers", "subclasses", "implementers")

# Reverse view -> the raw relation reported on a blast-radius row (see
# blast_radius_detail). Where two relations share a view pair ("imports_from"
# and "imports" both -> "importers"), the more specific one is reported —
# fidelity beyond "some kind of import" isn't tracked per-edge, only per-view.
BLAST_VIEW_RELATION: dict[str, str] = {
    "callers": "calls",
    "subclasses": "inherits",
    "implementers": "implements",
    "importers": "imports_from",
}

# Per-view recall weight. Callers/callees dominate because signature and
# behavior changes propagate along the call graph; importers are weakest
# (module-level, coarse). Feeds the budget-neutral L3 expansion.
VIEW_RECALL_WEIGHT: dict[str, float] = {
    "callers": 1.0,
    "callees": 0.9,
    "bases": 0.8,
    "subclasses": 0.7,
    "importers": 0.5,
}

DEFAULT_HUB_DEGREE = 50
DEFAULT_RECALL_TOP_K = 8


def _views_for_relations(relations: Iterable[str] | None) -> list[str]:
    """Resolve a caller's ``relations`` request to a list of view names.

    ``None`` → :data:`DEFAULT_VIEWS`. Each raw relation name (``"calls"``)
    expands to both of its views; a view name (``"callers"``) passed directly
    is honored as-is. Unknown tokens are ignored. Order-preserving + deduped.
    """
    if relations is None:
        return list(DEFAULT_VIEWS)
    views: list[str] = []
    for token in relations:
        if token in RELATION_VIEWS:
            views.extend(RELATION_VIEWS[token])
        elif token in ALL_VIEWS:
            views.append(token)
        elif token == "all":
            views.extend(ALL_VIEWS)
    return list(dict.fromkeys(views))


class StructuralIndex:
    """In-memory typed adjacency over the code graph's structural edges.

    Built once from ``embedder.edges`` (the ``links`` array of ``graph.json``)
    and cached on the :class:`~neuralmind.core.NeuralMind` instance. There is
    no persisted database — unlike synapses, structural edges are fully
    determined by the current graph, so the index is rebuilt from the graph
    rather than accumulated across sessions.
    """

    def __init__(self, hub_degree: int = DEFAULT_HUB_DEGREE) -> None:
        self.hub_degree = max(1, int(hub_degree))
        # view name -> node_id -> set of neighbor node ids
        self._views: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        self._edge_count = 0
        self._built = False

    # ----------------------------------------------------------------- #
    # Build
    # ----------------------------------------------------------------- #

    def build_from_edges(
        self, edges: Iterable[dict], *, min_confidence: float = 0.0
    ) -> StructuralIndex:
        """Populate the index from graph edge dicts.

        Reads ``source``/``target`` (falling back to graphify's ``_src``/
        ``_tgt``) and ``relation`` (falling back to ``label``/``kind``)
        verbatim. Edges whose ``relation`` isn't in :data:`RELATION_VIEWS`,
        whose ``confidence_score`` is below ``min_confidence``, or that are
        self-loops are skipped. Idempotent per call — safe to rebuild.
        """
        self._views = defaultdict(lambda: defaultdict(set))
        self._edge_count = 0
        for edge in edges or ():
            src = edge.get("source", edge.get("_src"))
            tgt = edge.get("target", edge.get("_tgt"))
            if not src or not tgt or src == tgt:
                continue
            relation = edge.get("relation", edge.get("label", edge.get("kind", "")))
            views = RELATION_VIEWS.get(relation)
            if views is None:
                continue
            try:
                confidence = float(edge.get("confidence_score", 1.0))
            except (TypeError, ValueError):
                confidence = 1.0
            if confidence < min_confidence:
                continue
            forward_view, reverse_view = views
            # forward view names the relationship from the source node;
            # reverse view names it from the target node.
            self._views[forward_view][str(src)].add(str(tgt))
            self._views[reverse_view][str(tgt)].add(str(src))
            self._edge_count += 1
        self._built = True
        return self

    @property
    def edge_count(self) -> int:
        return self._edge_count

    def __bool__(self) -> bool:
        return self._edge_count > 0

    # ----------------------------------------------------------------- #
    # Reads
    # ----------------------------------------------------------------- #

    def neighbors(
        self, node_id: str, relations: Iterable[str] | None = None
    ) -> dict[str, list[str]]:
        """Return the typed structural neighbors of ``node_id``.

        Keys are view names (``callers``, ``callees``, ``bases``,
        ``subclasses``, ``importers`` by default; more via ``relations``).
        Empty views are omitted, so an unknown or leaf node returns ``{}``.
        Each list is sorted for deterministic output.
        """
        out: dict[str, list[str]] = {}
        for view in _views_for_relations(relations):
            members = self._views.get(view, {}).get(node_id)
            if members:
                out[view] = sorted(members)
        return out

    def recall(
        self, seed_ids: Iterable[str], top_k: int = DEFAULT_RECALL_TOP_K
    ) -> list[tuple[str, float]]:
        """Flat weighted structural neighbors of ``seed_ids`` for recall.

        Unions the :data:`DEFAULT_VIEWS` neighbors of every seed, weights each
        by :data:`VIEW_RECALL_WEIGHT`, hub-normalizes seeds with runaway
        degree (``sqrt(hub_degree / degree)``, matching the synapse layer),
        and drops the seeds themselves. Returns ``[(node_id, weight), ...]``
        strongest first, capped at ``top_k``. Feeds the budget-neutral L3
        expansion in the context selector.
        """
        seeds = [s for s in dict.fromkeys(seed_ids) if s]
        if not seeds or top_k <= 0:
            return []
        seed_set = set(seeds)
        scores: dict[str, float] = defaultdict(float)
        for seed in seeds:
            for view in DEFAULT_VIEWS:
                members = self._views.get(view, {}).get(seed)
                if not members:
                    continue
                degree = len(members)
                hub_factor = (
                    math.sqrt(self.hub_degree / degree) if degree > self.hub_degree else 1.0
                )
                weight = VIEW_RECALL_WEIGHT.get(view, 0.3) * hub_factor
                for other in members:
                    if other in seed_set:
                        continue
                    scores[other] = max(scores[other], weight)
        # Sort by weight desc, then node id asc as a stable tie-break — members
        # come from sets (non-deterministic iteration order), so without the
        # secondary key the top_k cut would drop different tied neighbors from
        # run to run.
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return ranked[:top_k]

    def blast_radius_detail(self, node_id: str, depth: int = 2) -> list[dict]:
        """Transitive reverse-dependency rows for ``node_id`` (its blast radius).

        Same breadth-first traversal as :meth:`blast_radius`, but returns one
        row per dependent — ``{"id", "relation", "hop", "depends_on"}`` —
        instead of a flat id list, so a caller can see *how* each dependent
        depends on the node and how many hops away it is, not just that it
        does. Nearest-hop-wins: BFS visits a node the first time via its
        shortest path, so ``hop``/``depends_on`` always reflect that. Sorted
        by ``(hop, id)``. Cycle-safe (visited set) and hub-capped per node (a
        hub's dependents are truncated so one utility can't explode the
        radius).
        """
        if depth < 1:
            return []
        visited: set[str] = {node_id}
        frontier: deque[tuple[str, int]] = deque([(node_id, 0)])
        rows: dict[str, dict] = {}
        while frontier:
            current, hop = frontier.popleft()
            if hop >= depth:
                continue
            for view in BLAST_VIEWS:
                members = self._views.get(view, {}).get(current)
                if not members:
                    continue
                dependents = sorted(members)
                if len(dependents) > self.hub_degree:
                    dependents = dependents[: self.hub_degree]
                relation = BLAST_VIEW_RELATION.get(view, view)
                for dep in dependents:
                    if dep in visited:
                        continue
                    visited.add(dep)
                    rows[dep] = {
                        "id": dep,
                        "relation": relation,
                        "hop": hop + 1,
                        "depends_on": current,
                    }
                    frontier.append((dep, hop + 1))
        return sorted(rows.values(), key=lambda r: (r["hop"], r["id"]))

    def blast_radius(self, node_id: str, depth: int = 2) -> list[str]:
        """Transitive reverse-dependency set of ``node_id`` (its blast radius).

        Breadth-first over :data:`BLAST_VIEWS` — everything that calls,
        imports, subclasses, or implements the node, then everything that
        depends on *those*, up to ``depth`` hops. Cycle-safe (visited set) and
        hub-capped per node (a hub's dependents are truncated so one utility
        can't explode the radius). Returns ids sorted, excluding the node.

        Thin wrapper over :meth:`blast_radius_detail` for callers that only
        need the id set, not per-dependent hop/relation attribution.
        """
        return sorted(row["id"] for row in self.blast_radius_detail(node_id, depth))

    # ----------------------------------------------------------------- #
    # Stats
    # ----------------------------------------------------------------- #

    def stats(self) -> dict:
        """Coverage summary: edge count, per-view counts, node coverage, hubs."""
        per_view = {
            view: sum(len(v) for v in nodes.values()) for view, nodes in self._views.items()
        }
        covered = {nid for nodes in self._views.values() for nid in nodes}
        # Top hubs by total structural degree across all views.
        degree: dict[str, int] = defaultdict(int)
        for nodes in self._views.values():
            for nid, members in nodes.items():
                degree[nid] += len(members)
        top_hubs = sorted(degree.items(), key=lambda kv: kv[1], reverse=True)[:5]
        return {
            "edges": self._edge_count,
            "nodes_covered": len(covered),
            "per_view": {k: per_view.get(k, 0) for k in ALL_VIEWS if per_view.get(k)},
            "top_hubs": [(nid, deg) for nid, deg in top_hubs],
            "hub_degree": self.hub_degree,
        }
