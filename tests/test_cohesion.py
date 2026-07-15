"""Tests for cluster-cohesion outlier detection (prototype).

Stdlib-only, like the rest of the synapse-layer tests: the detector is a
pure function over a ``neighbors(node)`` callable, so a plain dict stands
in for the synapse store.
"""

from __future__ import annotations

from neuralmind.cohesion import find_outliers, format_outliers


def _neighbors_from(graph):
    """Adapt a ``{node: [(other, weight), ...]}`` dict to a NeighborFn."""

    def neighbors(node):
        return graph.get(node, [])

    return neighbors


def test_flags_the_eleventh_handler():
    # Ten handlers route orgId through resolveOrgId; validateSession does
    # not — it is the odd one out that shipped a bug in the real story.
    handlers = [f"handler_{i}" for i in range(10)] + ["validateSession"]
    graph = {h: [("resolveOrgId", 1.0)] for h in handlers[:10]}
    graph["validateSession"] = [("someOtherHelper", 1.0)]

    findings = find_outliers(handlers, _neighbors_from(graph))

    assert findings, "expected the outlier to be flagged"
    top = findings[0]
    assert top.node == "validateSession"
    assert top.associate == "resolveOrgId"
    assert top.peers == 10
    assert top.cluster_size == 11
    assert top.share == 1.0  # every one of its 10 peers uses it


def test_consistent_cluster_is_quiet():
    # All eleven share the associate — nothing anomalous, no findings.
    handlers = [f"handler_{i}" for i in range(11)]
    graph = {h: [("resolveOrgId", 1.0)] for h in handlers}

    assert find_outliers(handlers, _neighbors_from(graph)) == []


def test_small_cluster_is_quiet():
    # Below the min-peers majority we cannot claim a pattern exists.
    handlers = ["a", "b", "c"]
    graph = {"a": [("x", 1.0)], "b": [("x", 1.0)], "c": [("y", 1.0)]}

    assert find_outliers(handlers, _neighbors_from(graph)) == []


def test_intra_cluster_links_do_not_count_as_shared_pattern():
    # Members linking to each other is cohesion, not a shared *external*
    # associate, so it must not manufacture an outlier finding.
    members = ["a", "b", "c", "d", "e"]
    graph = {m: [(other, 1.0) for other in members if other != m] for m in members}

    assert find_outliers(members, _neighbors_from(graph)) == []


def test_weak_edges_are_ignored():
    handlers = [f"handler_{i}" for i in range(5)]
    # Peers link strongly; the dissenter links only weakly to the same
    # associate — treated as "does not share" under the weight floor.
    graph = {h: [("resolveOrgId", 1.0)] for h in handlers[:4]}
    graph["handler_4"] = [("resolveOrgId", 0.05)]

    findings = find_outliers(handlers, _neighbors_from(graph), min_peers=4, min_weight=0.5)

    assert findings
    assert findings[0].node == "handler_4"


def test_format_is_empty_when_nothing_found():
    assert format_outliers([]) == ""


def test_format_names_node_and_associate():
    handlers = [f"handler_{i}" for i in range(10)] + ["validateSession"]
    graph = {h: [("resolveOrgId", 1.0)] for h in handlers[:10]}
    graph["validateSession"] = [("someOtherHelper", 1.0)]

    text = format_outliers(find_outliers(handlers, _neighbors_from(graph)))

    assert "validateSession" in text
    assert "resolveOrgId" in text
    assert "cohesion check" in text.lower()


if __name__ == "__main__":
    # Runnable without pytest so the prototype can be demonstrated directly.
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
