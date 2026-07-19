"""Tests for the structural edge index (calls/inherits/imports layer).

Stdlib-only, like the synapse tests: :class:`StructuralIndex` is pure Python
and never touches ChromaDB or the embedder, so these build a tiny edge list
(or read a committed graph.json fixture) and assert on typed adjacency.
"""

from __future__ import annotations

import json
from pathlib import Path

from neuralmind.structural import (
    DEFAULT_VIEWS,
    RELATION_VIEWS,
    StructuralIndex,
)

FIXTURE = (
    Path(__file__).parent.parent
    / "neuralmind"
    / "demo_data"
    / "sample_project"
    / "graphify-out"
    / "graph.json"
)


def _edge(source, target, relation, confidence=1.0):
    return {
        "source": source,
        "target": target,
        "relation": relation,
        "confidence_score": confidence,
    }


def test_calls_edge_is_directional():
    idx = StructuralIndex().build_from_edges([_edge("a_fn", "b_fn", "calls")])
    # a --calls--> b : b is a callee of a, a is a caller of b.
    assert idx.neighbors("a_fn")["callees"] == ["b_fn"]
    assert idx.neighbors("b_fn")["callers"] == ["a_fn"]
    # And not the reverse.
    assert "callers" not in idx.neighbors("a_fn")
    assert "callees" not in idx.neighbors("b_fn")


def test_inherits_edge_maps_to_bases_and_subclasses():
    idx = StructuralIndex().build_from_edges([_edge("child_cls", "base_cls", "inherits")])
    assert idx.neighbors("child_cls")["bases"] == ["base_cls"]
    assert idx.neighbors("base_cls")["subclasses"] == ["child_cls"]


def test_imports_from_maps_to_importers():
    idx = StructuralIndex().build_from_edges([_edge("mod_a", "mod_b", "imports_from")])
    # importers is a default view: mod_b is imported by mod_a.
    assert idx.neighbors("mod_b")["importers"] == ["mod_a"]
    # "imports" (what mod_a imports) is off by default, reachable via relation.
    assert "imports" not in idx.neighbors("mod_a")
    assert idx.neighbors("mod_a", relations=["imports_from"])["imports"] == ["mod_b"]


def test_self_loops_and_unknown_relations_skipped():
    idx = StructuralIndex().build_from_edges(
        [
            _edge("x", "x", "calls"),  # self-loop
            _edge("x", "y", "mystery_relation"),  # unknown relation
            {"relation": "calls"},  # missing endpoints
        ]
    )
    assert idx.edge_count == 0
    assert idx.neighbors("x") == {}


def test_confidence_gating_drops_low_confidence_edges():
    edges = [
        _edge("a", "b", "calls", confidence=0.4),
        _edge("a", "c", "calls", confidence=0.9),
    ]
    idx = StructuralIndex().build_from_edges(edges, min_confidence=0.5)
    assert idx.neighbors("a")["callees"] == ["c"]  # 0.4 edge dropped


def test_graphify_underscore_endpoints_supported():
    # Real graphify graphs sometimes use _src/_tgt instead of source/target.
    idx = StructuralIndex().build_from_edges([{"_src": "a", "_tgt": "b", "relation": "calls"}])
    assert idx.neighbors("a")["callees"] == ["b"]


def test_relations_filter_expands_to_both_views():
    idx = StructuralIndex().build_from_edges(
        [
            _edge("file_a", "sym_a", "contains"),
            _edge("a_fn", "b_fn", "calls"),
        ]
    )
    # contains is off by default…
    assert "members" not in idx.neighbors("file_a")
    # …but reachable via an explicit relation, expanding to both views.
    got = idx.neighbors("file_a", relations=["contains"])
    assert got["members"] == ["sym_a"]


def test_dedup_repeated_edges():
    idx = StructuralIndex().build_from_edges([_edge("a", "b", "calls"), _edge("a", "b", "calls")])
    assert idx.neighbors("a")["callees"] == ["b"]  # not ["b", "b"]


def test_recall_prioritizes_callers_over_importers():
    edges = [
        _edge("caller", "target", "calls"),  # target's caller
        _edge("importer", "target", "imports_from"),  # target's importer
    ]
    idx = StructuralIndex().build_from_edges(edges)
    ranked = idx.recall(["target"])
    ids = [nid for nid, _ in ranked]
    assert "caller" in ids and "importer" in ids
    # Callers weigh more than importers.
    weights = dict(ranked)
    assert weights["caller"] > weights["importer"]


def test_recall_excludes_seeds():
    idx = StructuralIndex().build_from_edges([_edge("a", "b", "calls")])
    ranked = idx.recall(["a", "b"])
    assert all(nid not in {"a", "b"} for nid, _ in ranked)


def test_hub_downweights_runaway_degree():
    # 5 callers (> cap 2, but < the default top_k so none are truncated) →
    # each caller's recall weight is hub-normalized down, so one over-connected
    # utility can't dominate recall.
    capped = StructuralIndex(hub_degree=2)
    capped.build_from_edges([_edge(f"c{i}", "hub", "calls") for i in range(5)])
    capped_weights = dict(capped.recall(["hub"]))
    assert len(capped_weights) == 5  # all callers returned (no truncation)
    w_hub = capped_weights["c0"]
    # A node with a single caller isn't capped (full weight).
    single = StructuralIndex(hub_degree=2)
    single.build_from_edges([_edge("only", "leaf", "calls")])
    w_single = dict(single.recall(["leaf"]))["only"]
    assert w_hub < w_single


def test_recall_tie_break_is_deterministic():
    # Many equal-weight neighbors truncated to top_k must be stable across runs:
    # sorted by id, so the lowest ids survive deterministically.
    idx = StructuralIndex()
    idx.build_from_edges([_edge(f"c{i:02d}", "target", "calls") for i in range(20)])
    first = [nid for nid, _ in idx.recall(["target"], top_k=8)]
    second = [nid for nid, _ in idx.recall(["target"], top_k=8)]
    assert first == second
    assert first == [f"c{i:02d}" for i in range(8)]  # lowest ids kept


def test_blast_radius_transitive_reverse_deps():
    # c1 --calls--> mid --calls--> target ; importer --imports--> target
    edges = [
        _edge("mid", "target", "calls"),
        _edge("c1", "mid", "calls"),
        _edge("importer", "target", "imports_from"),
    ]
    idx = StructuralIndex().build_from_edges(edges)
    depth1 = idx.blast_radius("target", depth=1)
    assert set(depth1) == {"mid", "importer"}  # direct dependents only
    depth2 = idx.blast_radius("target", depth=2)
    assert set(depth2) == {"mid", "importer", "c1"}  # c1 reached transitively


def test_blast_radius_cycle_safe():
    edges = [_edge("a", "b", "calls"), _edge("b", "a", "calls")]
    idx = StructuralIndex().build_from_edges(edges)
    # Cycle must terminate and not include the seed itself.
    out = idx.blast_radius("a", depth=5)
    assert out == ["b"]


def test_blast_radius_detail_reports_hop_and_relation():
    # c1 --calls--> mid --calls--> target ; importer --imports_from--> target
    edges = [
        _edge("mid", "target", "calls"),
        _edge("c1", "mid", "calls"),
        _edge("importer", "target", "imports_from"),
    ]
    idx = StructuralIndex().build_from_edges(edges)
    rows = {row["id"]: row for row in idx.blast_radius_detail("target", depth=2)}

    assert rows["mid"] == {"id": "mid", "relation": "calls", "hop": 1, "depends_on": "target"}
    assert rows["importer"] == {
        "id": "importer",
        "relation": "imports_from",
        "hop": 1,
        "depends_on": "target",
    }
    assert rows["c1"] == {"id": "c1", "relation": "calls", "hop": 2, "depends_on": "mid"}


def test_blast_radius_detail_nearest_hop_wins():
    # target has two direct callers; one of them (mid) is itself a 2-hop
    # dependent via a different path. mid must be recorded at hop 1, not 2.
    edges = [
        _edge("mid", "target", "calls"),
        _edge("other", "target", "calls"),
        _edge("mid", "other", "calls"),
    ]
    idx = StructuralIndex().build_from_edges(edges)
    rows = {row["id"]: row for row in idx.blast_radius_detail("target", depth=2)}
    assert rows["mid"]["hop"] == 1


def test_blast_radius_is_a_thin_wrapper_over_detail():
    edges = [
        _edge("mid", "target", "calls"),
        _edge("c1", "mid", "calls"),
        _edge("importer", "target", "imports_from"),
    ]
    idx = StructuralIndex().build_from_edges(edges)
    assert idx.blast_radius("target", depth=2) == sorted(
        row["id"] for row in idx.blast_radius_detail("target", depth=2)
    )


def test_empty_index_is_falsy_and_safe():
    idx = StructuralIndex()
    assert not idx
    assert idx.neighbors("anything") == {}
    assert idx.recall(["anything"]) == []
    assert idx.blast_radius("anything") == []
    assert idx.blast_radius_detail("anything") == []


# --- real graph.json fixture: ids read verbatim, real relations present ----


def test_fixture_builds_and_covers_expected_relations():
    graph = json.loads(FIXTURE.read_text())
    edges = graph.get("edges", graph.get("links", []))
    idx = StructuralIndex().build_from_edges(edges)
    assert idx  # non-empty
    stats = idx.stats()
    # The demo graph is known to carry calls / inherits / imports edges.
    per_view = stats["per_view"]
    assert per_view.get("callers", 0) > 0 or per_view.get("callees", 0) > 0
    # Node ids in the index must be exactly those in the graph (no minting).
    graph_ids = {n["id"] for n in graph.get("nodes", [])}
    covered = {nid for nodes in idx._views.values() for nid in nodes}
    assert covered  # something covered
    assert covered <= graph_ids  # every covered id is a real graph node id


def test_fixture_stats_shape():
    graph = json.loads(FIXTURE.read_text())
    edges = graph.get("edges", graph.get("links", []))
    stats = StructuralIndex().build_from_edges(edges).stats()
    assert set(stats) >= {"edges", "nodes_covered", "per_view", "top_hubs", "hub_degree"}
    assert stats["edges"] > 0


def test_default_views_are_subset_of_known_views():
    known = {v for pair in RELATION_VIEWS.values() for v in pair}
    assert set(DEFAULT_VIEWS) <= known
