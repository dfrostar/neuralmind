#!/usr/bin/env python3
"""Generate deterministic test fixtures for G5 structural gap detection.

Run once to create synthetic graph.json files under
tests/fixtures/structural_gaps/. Deterministic — no randomness.
"""

from __future__ import annotations

import json
import os

OUT_ROOT = os.path.join(
    os.path.dirname(__file__),
    "..",
    "tests",
    "fixtures",
    "structural_gaps",
)


def write_fixture(name: str, graph: dict) -> None:
    """Write graph.json into <name>/graphify-out/."""
    fixture_dir = os.path.join(OUT_ROOT, name, "graphify-out")
    os.makedirs(fixture_dir, exist_ok=True)
    with open(os.path.join(fixture_dir, "graph.json"), "w") as f:
        json.dump(graph, f, indent=2)
    print(f"  wrote {name}/graphify-out/graph.json")


def make_node(nid: str, label: str, community: int) -> dict:
    return {"id": nid, "label": label, "community": community}


def make_link(
    src: str, tgt: str, relation: str = "calls", weight: float | None = None
) -> dict[str, object]:
    link: dict[str, object] = {"source": src, "target": tgt, "relation": relation}
    if weight is not None:
        link["weight"] = weight
    return link


# --- 1. Star graph: 1 center + 5 leaves ---
def star_graph() -> dict:
    nodes = [
        make_node("center", "Center", 0),
        make_node("leaf1", "Leaf1", 1),
        make_node("leaf2", "Leaf2", 1),
        make_node("leaf3", "Leaf3", 2),
        make_node("leaf4", "Leaf4", 2),
        make_node("leaf5", "Leaf5", 2),
    ]
    links = [make_link("center", f"leaf{i}") for i in range(1, 6)]
    return {"nodes": nodes, "links": links}


# --- 2. Two communities joined by one bridge node ---
def two_community() -> dict:
    nodes = [
        make_node("a1", "A1", 0),
        make_node("a2", "A2", 0),
        make_node("bridge", "Bridge", 0),
        make_node("b1", "B1", 1),
        make_node("b2", "B2", 1),
    ]
    links = [
        make_link("a1", "a2"),
        make_link("a2", "bridge"),
        make_link("bridge", "b1"),
        make_link("b1", "b2"),
    ]
    return {"nodes": nodes, "links": links}


# --- 3. Line graph A-B-C-D ---
def line_graph() -> dict:
    nodes = [
        make_node("a", "A", 0),
        make_node("b", "B", 0),
        make_node("c", "C", 1),
        make_node("d", "D", 1),
    ]
    links = [
        make_link("a", "b"),
        make_link("b", "c"),
        make_link("c", "d"),
    ]
    return {"nodes": nodes, "links": links}


# --- 4. Multi-bridge: 3 communities, 5 bridges ---
def multi_bridge() -> dict:
    nodes = [
        make_node("c0_a", "C0_A", 0),
        make_node("c0_b", "C0_B", 0),
        make_node("c1_a", "C1_A", 1),
        make_node("c1_b", "C1_B", 1),
        make_node("c2_a", "C2_A", 2),
        make_node("c2_b", "C2_B", 2),
        make_node("b1", "B1", 0),
        make_node("b2", "B2", 0),
        make_node("b3", "B3", 1),
        make_node("b4", "B4", 1),
        make_node("b5", "B5", 2),
    ]
    links = [
        # Community 0 internal
        make_link("c0_a", "c0_b"),
        # Community 1 internal
        make_link("c1_a", "c1_b"),
        # Community 2 internal
        make_link("c2_a", "c2_b"),
        # Bridges
        make_link("c0_a", "b1"),
        make_link("b1", "c1_a"),
        make_link("c0_b", "b2"),
        make_link("b2", "c2_a"),
        make_link("c1_b", "b3"),
        make_link("b3", "c2_b"),
        make_link("c1_a", "b4"),
        make_link("b4", "c2_a"),
        make_link("c0_a", "b5"),
        make_link("b5", "c2_b"),
    ]
    return {"nodes": nodes, "links": links}


# --- 5. Hub and spoke: hub should be filtered ---
def hub_and_spoke() -> dict:
    nodes = [
        make_node("hub", "Hub", 0),
        make_node("s1", "S1", 0),
        make_node("s2", "S2", 0),
        make_node("s3", "S3", 1),
        make_node("s4", "S4", 1),
        make_node("s5", "S5", 2),
        make_node("s6", "S6", 2),
    ]
    links = [
        make_link("hub", "s1"),
        make_link("hub", "s2"),
        make_link("hub", "s3"),
        make_link("hub", "s4"),
        make_link("hub", "s5"),
        make_link("hub", "s6"),
    ]
    return {"nodes": nodes, "links": links}


# --- 6. Disconnected: two components, no bridges ---
def disconnected() -> dict:
    nodes = [
        make_node("a1", "A1", 0),
        make_node("a2", "A2", 0),
        make_node("a3", "A3", 0),
        make_node("b1", "B1", 1),
        make_node("b2", "B2", 1),
        make_node("b3", "B3", 1),
    ]
    links = [
        make_link("a1", "a2"),
        make_link("a2", "a3"),
        make_link("a3", "a1"),
        make_link("b1", "b2"),
        make_link("b2", "b3"),
        make_link("b3", "b1"),
    ]
    return {"nodes": nodes, "links": links}


# --- 7. Single node ---
def single_node() -> dict:
    nodes = [make_node("solo", "Solo", 0)]
    return {"nodes": nodes, "links": []}


# --- 8. Empty ---
def empty() -> dict:
    return {"nodes": [], "links": []}


# --- 9. Large synthetic: 1000 nodes ---
def large_synthetic() -> dict:
    nodes = []
    links = []
    # 10 communities, 100 nodes each
    for c in range(10):
        for i in range(100):
            nid = f"c{c}_n{i}"
            nodes.append(make_node(nid, f"Node_{c}_{i}", c))
    # Intra-community chain links
    for c in range(10):
        for i in range(99):
            links.append(make_link(f"c{c}_n{i}", f"c{c}_n{i+1}"))
    # One bridge per consecutive pair of communities
    for c in range(9):
        links.append(make_link(f"c{c}_n50", f"c{c+1}_n50"))
    return {"nodes": nodes, "links": links}


# --- 10. Corrupt: invalid JSON ---
# Handled separately — writes a .json file with invalid content


def main() -> None:
    os.makedirs(OUT_ROOT, exist_ok=True)
    print("Generating G5 structural gap fixtures...")

    fixtures = {
        "star_graph": star_graph,
        "two_community": two_community,
        "line_graph": line_graph,
        "multi_bridge": multi_bridge,
        "hub_and_spoke": hub_and_spoke,
        "disconnected": disconnected,
        "single_node": single_node,
        "empty": empty,
        "large_synthetic": large_synthetic,
    }

    for name, fn in fixtures.items():
        write_fixture(name, fn())

    # Corrupt fixture: write invalid JSON
    corrupt_dir = os.path.join(OUT_ROOT, "corrupt", "graphify-out")
    os.makedirs(corrupt_dir, exist_ok=True)
    with open(os.path.join(corrupt_dir, "graph.json"), "w") as f:
        f.write("{ invalid json content")
    print("  wrote corrupt/graphify-out/graph.json (invalid)")

    print(f"\n{len(fixtures) + 1} fixtures generated.")


if __name__ == "__main__":
    main()
