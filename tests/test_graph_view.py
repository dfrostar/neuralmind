"""Tests for the graph-view data layer (SynapseStore.edges + graph_data)."""

from __future__ import annotations

from neuralmind.core import NeuralMind
from neuralmind.synapses import SynapseStore


def test_synapse_edges_returns_sorted_filtered_view(tmp_path):
    store = SynapseStore(tmp_path / "synapses.db")
    store.reinforce(["a", "b"])  # one pair, weight = LEARNING_RATE
    store.reinforce(["a", "b"])  # reinforce same pair -> heavier
    store.reinforce(["c", "d"])  # lighter pair

    edges = store.edges()
    assert len(edges) == 2
    # strongest first
    assert edges[0][0:2] == ("a", "b")
    assert edges[0][2] > edges[1][2]
    # activation_count is carried through
    assert edges[0][3] == 2

    # min_weight filters out the lighter pair
    heavy = store.edges(min_weight=edges[0][2])
    assert [e[0:2] for e in heavy] == [("a", "b")]


def test_graph_data_shape_and_synapse_overlay(temp_project):
    mind = NeuralMind(str(temp_project), backend_type="in_memory")
    mind.build()

    # Learn an association so the overlay is non-empty.
    mind.activate(["node_1", "node_2"])

    data = mind.graph_data()

    assert data["project"] == temp_project.name
    assert data["stats"]["nodes"] == len(data["nodes"])
    assert data["stats"]["edges"] == len(data["edges"])
    assert data["stats"]["synapses"] == len(data["synapses"])

    # Nodes carry the fields the UI renders.
    node = data["nodes"][0]
    assert {"id", "label", "file_type", "source_file", "community"} <= node.keys()

    # Structural edges only reference real nodes.
    node_ids = {n["id"] for n in data["nodes"]}
    for edge in data["edges"]:
        assert edge["source"] in node_ids
        assert edge["target"] in node_ids

    # The reinforced pair shows up in the synapse overlay.
    pairs = {(s["source"], s["target"]) for s in data["synapses"]}
    assert ("node_1", "node_2") in pairs
    for syn in data["synapses"]:
        assert syn["weight"] > 0
        assert syn["source"] in node_ids and syn["target"] in node_ids
