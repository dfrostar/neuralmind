"""Tests for NeuralMind.synaptic_recall: seeding spreading activation.

Semantic search often matches a ``<id>__rationale`` node (the docstring) best,
but synapses form between code nodes. Recall must seed from the code node the
rationale belongs to, or it recalls nothing for exactly the prompts that match
the code best.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from neuralmind.core import NeuralMind, _rationale_owners, _synapse_node
from neuralmind.synapses import SynapseStore

GO_GRAPH = Path(__file__).parent / "fixtures" / "sample_project_go" / "graphify-out" / "graph.json"


class _Mind:
    """Just what synaptic_recall reads: a store, an embedder, _ensure_built."""

    def __init__(self, store, hits, edges=()):
        self.synapses = store
        self.embedder = SimpleNamespace(search=lambda query, n: hits, edges=list(edges))

    def _ensure_built(self):
        pass


def _store(tmp_path) -> SynapseStore:
    store = SynapseStore(tmp_path / "synapses.db")
    store.reinforce(["pkg_mod_py__load_fn", "pkg_mod_py__save_fn"])
    return store


def test_rationale_node_maps_to_its_code_node():
    assert _synapse_node("pkg_mod_py__load_fn__rationale") == "pkg_mod_py__load_fn"
    assert _synapse_node("pkg_mod_py__load_fn") == "pkg_mod_py__load_fn"
    assert _synapse_node("__rationale") == "__rationale"


def test_recall_seeds_from_the_code_node_behind_a_rationale(tmp_path):
    hits = [{"id": "pkg_mod_py__load_fn__rationale", "score": 0.6}]
    ranked, similarity = NeuralMind.synaptic_recall(_Mind(_store(tmp_path), hits), "q")
    assert [node for node, _ in ranked] == ["pkg_mod_py__save_fn"]
    assert similarity == 0.6


def test_a_code_node_and_its_rationale_are_one_seed(tmp_path):
    store = _store(tmp_path)
    hits = [
        {"id": "pkg_mod_py__load_fn", "score": 0.5},
        {"id": "pkg_mod_py__load_fn__rationale", "score": 0.6},
    ]
    ranked, similarity = NeuralMind.synaptic_recall(_Mind(store, hits), "q")
    # The better score seeds once; the two aren't summed.
    assert ranked == store.spread([("pkg_mod_py__load_fn", 0.6)], depth=2, top_k=10)
    assert similarity == 0.6


def test_edges_learned_on_a_rationale_id_still_recall(tmp_path):
    # Query feedback stores raw hit ids, rationale ids included: those edges
    # must stay reachable once recall also seeds from the owning code node.
    store = SynapseStore(tmp_path / "synapses.db")
    store.reinforce(["pkg_mod_py__load_fn__rationale", "docs_loading_md"])
    hits = [{"id": "pkg_mod_py__load_fn__rationale", "score": 0.6}]
    ranked, _ = NeuralMind.synaptic_recall(_Mind(store, hits), "q")
    assert "docs_loading_md" in [node for node, _ in ranked]


def test_a_rationale_and_its_code_node_dont_double_a_shared_neighbour(tmp_path):
    # Both ids carry an edge to the same neighbour: it gets the code node's
    # activation, not the sum of the two.
    store = SynapseStore(tmp_path / "synapses.db")
    store.reinforce(["pkg_mod_py__load_fn", "pkg_mod_py__save_fn"])
    store.reinforce(["pkg_mod_py__load_fn__rationale", "pkg_mod_py__save_fn"])
    hits = [{"id": "pkg_mod_py__load_fn__rationale", "score": 0.6}]
    ranked, _ = NeuralMind.synaptic_recall(_Mind(store, hits), "q")
    alone = dict(store.spread([("pkg_mod_py__load_fn", 0.6)], depth=2, top_k=10))
    assert dict(ranked)["pkg_mod_py__save_fn"] == alone["pkg_mod_py__save_fn"]


def test_a_rationale_hit_never_recalls_itself_or_its_code_node(tmp_path):
    store = SynapseStore(tmp_path / "synapses.db")
    store.reinforce(["pkg_mod_py__load_fn", "pkg_mod_py__save_fn"])
    store.reinforce(["pkg_mod_py__load_fn__rationale", "pkg_mod_py__save_fn"])
    hits = [{"id": "pkg_mod_py__load_fn__rationale", "score": 0.6}]
    ranked, _ = NeuralMind.synaptic_recall(_Mind(store, hits), "q")
    assert [node for node, _ in ranked] == ["pkg_mod_py__save_fn"]


def test_another_seeds_link_adds_to_a_rationales_link(tmp_path):
    # load's rationale and save both link to export; load itself doesn't.
    # export gets save's contribution plus the rationale's, not the larger.
    store = SynapseStore(tmp_path / "synapses.db")
    for _ in range(3):
        store.reinforce(["pkg_mod_py__load_fn__rationale", "pkg_mod_py__export_fn"])
    store.reinforce(["pkg_mod_py__save_fn", "pkg_mod_py__export_fn"])
    hits = [
        {"id": "pkg_mod_py__load_fn__rationale", "score": 0.6},
        {"id": "pkg_mod_py__save_fn", "score": 0.6},
    ]
    ranked, _ = NeuralMind.synaptic_recall(_Mind(store, hits), "q")

    def alone(seed):
        return dict(store.spread([(seed, 0.6)], depth=2, top_k=10))["pkg_mod_py__export_fn"]

    expected = alone("pkg_mod_py__load_fn__rationale") + alone("pkg_mod_py__save_fn")
    assert dict(ranked)["pkg_mod_py__export_fn"] == pytest.approx(expected)


def test_no_match_recalls_nothing(tmp_path):
    assert NeuralMind.synaptic_recall(_Mind(_store(tmp_path), []), "q") == ([], 0.0)


def test_synaptic_neighbors_is_the_recall_list(tmp_path):
    mind = _Mind(_store(tmp_path), [{"id": "pkg_mod_py__load_fn__rationale", "score": 0.6}])
    mind.synaptic_recall = lambda *a, **k: NeuralMind.synaptic_recall(mind, *a, **k)
    assert NeuralMind.synaptic_neighbors(mind, "q") == NeuralMind.synaptic_recall(mind, "q")[0]


def test_a_graphify_rationale_maps_through_its_rationale_for_edge(tmp_path):
    # graphify doesn't use the __rationale suffix; the edge says whose it is.
    edges = [
        {
            "relation": "rationale_for",
            "source": "pkg_mod_py_load_rationale",
            "target": "pkg_mod_py__load_fn",
        },
        {"relation": "calls", "source": "pkg_mod_py__load_fn", "target": "pkg_mod_py__save_fn"},
    ]
    hits = [{"id": "pkg_mod_py_load_rationale", "score": 0.6}]
    ranked, similarity = NeuralMind.synaptic_recall(_Mind(_store(tmp_path), hits, edges), "q")
    assert [node for node, _ in ranked] == ["pkg_mod_py__save_fn"]
    assert similarity == 0.6


def test_rationale_owners_reads_either_edge_shape():
    mind = SimpleNamespace(
        embedder=SimpleNamespace(
            edges=[
                {"relation": "rationale_for", "_src": "a_rationale", "_tgt": "a"},
                {"relation": "rationale_for", "source": "b_rationale_1", "target": "b"},
                {"relation": "contains", "source": "file", "target": "a"},
            ]
        )
    )
    owners = _rationale_owners(mind)
    assert owners == {"a_rationale": "a", "b_rationale_1": "b"}
    # Built once per loaded edge list.
    assert _rationale_owners(mind) is owners


def test_rationale_owners_accepts_a_code_to_rationale_edge():
    # The orientation probe.extract_rationales also accepts: the node data
    # says which end is the rationale.
    mind = SimpleNamespace(
        embedder=SimpleNamespace(
            nodes=[
                {"id": "a", "file_type": "code"},
                {"id": "a_rationale", "file_type": "rationale"},
            ],
            edges=[{"relation": "rationale_for", "source": "a", "target": "a_rationale"}],
        )
    )
    assert _rationale_owners(mind) == {"a_rationale": "a"}


def test_every_rationale_in_a_graphify_graph_maps_to_a_graph_node():
    graph = json.loads(GO_GRAPH.read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in graph["nodes"]}
    mind = SimpleNamespace(
        embedder=SimpleNamespace(nodes=graph["nodes"], edges=graph.get("links") or graph["edges"])
    )
    owners = _rationale_owners(mind)
    rationales = [nid for nid, n in nodes.items() if n.get("file_type") == "rationale"]
    assert rationales
    assert _synapse_node("db_connection_go_rationale_1", owners) == "db_connection_go"
    for rid in rationales:
        owner = _synapse_node(rid, owners)
        assert owner != rid and owner in nodes
        assert nodes[owner].get("file_type") != "rationale"
