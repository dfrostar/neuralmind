"""Tests for the graph-view data layer (SynapseStore.edges + graph_data)."""

from __future__ import annotations

import json

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


def test_recent_queries_records_top_hit_ids_and_caps(temp_project, monkeypatch):
    # The replay log gates on the same consent flag as the learning log,
    # which defaults to off in tests — force it on so the recording
    # actually happens.
    monkeypatch.setattr("neuralmind.core.is_memory_logging_enabled", lambda: True)

    mind = NeuralMind(str(temp_project), backend_type="in_memory")
    mind.build()

    # Run a few queries; each one should be appended.
    mind.query("authentication flow")
    mind.query("billing tasks")

    recent = mind.recent_queries(n=5)
    assert len(recent) == 2
    # Newest first.
    assert recent[0]["question"] == "billing tasks"
    assert recent[1]["question"] == "authentication flow"

    # Every record carries every field the UI consumes — including the
    # `layers_used` and `communities_loaded` shown in the replay detail.
    for rec in recent:
        assert {
            "ts",
            "question",
            "tokens",
            "reduction_ratio",
            "layers_used",
            "communities_loaded",
            "top_hits",
        } <= rec.keys()
        for hit in rec["top_hits"]:
            assert {"id", "label", "score"} <= hit.keys()

    # Lazy compaction trims the file once it crosses the byte threshold.
    # Lower the threshold so we don't have to write a megabyte of fixture
    # to exercise it.
    log = mind._recent_queries_path()
    log.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(NeuralMind, "RECENT_QUERIES_COMPACT_BYTES", 256)
    with log.open("a", encoding="utf-8") as f:
        for i in range(NeuralMind.RECENT_QUERIES_MAX + 25):
            f.write(f'{{"question": "stale {i}", "ts": "2026-01-01T00:00:00Z"}}\n')
    mind.query("fresh")
    with log.open(encoding="utf-8") as f:
        lines = [line for line in f if line.strip()]
    assert len(lines) == NeuralMind.RECENT_QUERIES_MAX
    # Compaction must keep the newest records (including this turn's
    # "fresh" query) and drop the earliest stale records — not the other
    # way around.
    questions = [json.loads(line)["question"] for line in lines]
    assert questions[-1] == "fresh"
    assert "stale 0" not in questions
    assert "stale 1" not in questions


def test_recent_queries_append_is_concurrency_safe(temp_project, monkeypatch):
    # Verify that two writers appending in parallel each land an entry —
    # the previous read-modify-write implementation could have lost one
    # of them. With single-line atomic appends both must survive.
    import threading

    monkeypatch.setattr("neuralmind.core.is_memory_logging_enabled", lambda: True)
    mind = NeuralMind(str(temp_project), backend_type="in_memory")
    mind.build()

    barrier = threading.Barrier(8)

    def fire(label):
        barrier.wait()
        for i in range(5):
            mind.query(f"{label}-{i}")

    threads = [threading.Thread(target=fire, args=(name,)) for name in "abcdefgh"]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    recent = mind.recent_queries(n=NeuralMind.RECENT_QUERIES_MAX)
    assert len(recent) == 8 * 5


def test_recent_queries_respects_memory_consent_optout(temp_project, monkeypatch):
    # Users who opted out of query logging must not get a parallel
    # persistence path through the replay log — gating the recorder on
    # the same consent flag closes that loophole.
    monkeypatch.setattr("neuralmind.core.is_memory_logging_enabled", lambda: False)
    mind = NeuralMind(str(temp_project), backend_type="in_memory")
    mind.build()
    mind.query("would normally be recorded")
    assert mind.recent_queries() == []
    assert not mind._recent_queries_path().exists()


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
