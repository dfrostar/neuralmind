"""Tests for the associative synapse layer."""

from __future__ import annotations

from neuralmind.synapses import (
    DECAY_RATE,
    LEARNING_RATE,
    LTP_FLOOR,
    LTP_THRESHOLD,
    PRUNE_THRESHOLD,
    WEIGHT_CAP,
    SynapseStore,
)


def _store(tmp_path):
    return SynapseStore(tmp_path / "synapses.db")


def test_reinforce_creates_undirected_canonical_edges(tmp_path):
    s = _store(tmp_path)
    pairs = s.reinforce(["b", "a", "c"])
    # 3 nodes => 3 unique pairs
    assert pairs == 3
    # querying either direction returns the same neighbors
    a_neighbors = dict(s.neighbors("a"))
    b_neighbors = dict(s.neighbors("b"))
    assert "b" in a_neighbors and "c" in a_neighbors
    assert "a" in b_neighbors and "c" in b_neighbors
    # weights match the configured learning rate on first reinforce
    assert abs(a_neighbors["b"] - LEARNING_RATE) < 1e-9


def test_reinforce_self_pairs_and_duplicates_are_ignored(tmp_path):
    s = _store(tmp_path)
    pairs = s.reinforce(["a", "a", "a"])
    assert pairs == 0
    assert s.neighbors("a") == []


def test_repeated_reinforce_accumulates_up_to_cap(tmp_path):
    s = _store(tmp_path)
    for _ in range(50):
        s.reinforce(["x", "y"])
    weight = dict(s.neighbors("x"))["y"]
    assert weight <= WEIGHT_CAP + 1e-9
    assert weight >= WEIGHT_CAP - 1e-9


def test_decay_prunes_weak_edges_but_keeps_ltp_floor(tmp_path):
    s = _store(tmp_path)
    # weak edge: one activation, will decay below prune threshold
    s.reinforce(["weak_a", "weak_b"])
    # strong edge: cross LTP threshold
    for _ in range(LTP_THRESHOLD + 2):
        s.reinforce(["strong_a", "strong_b"])
    # heavy decay: many ticks
    for _ in range(500):
        s.decay()
    weak = dict(s.neighbors("weak_a"))
    strong = dict(s.neighbors("strong_a"))
    assert "weak_b" not in weak  # pruned
    assert strong.get("strong_b", 0.0) >= LTP_FLOOR - 1e-9


def test_spreading_activation_finds_indirect_neighbors(tmp_path):
    s = _store(tmp_path)
    # build a chain: A — B — C, with A and C never co-activated
    for _ in range(3):
        s.reinforce(["A", "B"])
        s.reinforce(["B", "C"])
    ranked = dict(s.spread([("A", 1.0)], depth=2, top_k=10))
    # B is a direct neighbor and should rank above C
    assert "B" in ranked and "C" in ranked
    assert ranked["B"] > ranked["C"]
    # A itself is excluded from results
    assert "A" not in ranked


def test_spread_with_no_seeds_returns_empty(tmp_path):
    s = _store(tmp_path)
    assert s.spread([]) == []


def test_spread_skips_seeds_without_edges(tmp_path):
    s = _store(tmp_path)
    s.reinforce(["A", "B"])
    # unknown seed has no edges; spread should still return A/B's relationship
    ranked = dict(s.spread(["unknown_node"], depth=2, top_k=10))
    assert ranked == {}


def test_normalize_hubs_scales_runaway_central_nodes(tmp_path):
    s = _store(tmp_path)
    # make HUB the center of a star with many spokes
    spokes = [f"spoke_{i}" for i in range(200)]
    for spoke in spokes:
        s.reinforce(["HUB", spoke])
    # hub now has degree 200, well above HUB_DEGREE
    before = dict(s.neighbors("HUB", k=5))
    adjusted = s.normalize_hubs()
    assert adjusted >= 1
    after = dict(s.neighbors("HUB", k=5))
    # all sampled weights should drop after normalization
    for node, before_w in before.items():
        assert after[node] < before_w


def test_stats_reports_edge_and_node_counts(tmp_path):
    s = _store(tmp_path)
    s.reinforce(["a", "b", "c"])
    stats = s.stats()
    assert stats["edges"] == 3
    assert stats["nodes"] == 3
    assert stats["total_weight"] > 0.0
    assert stats["db_path"].endswith("synapses.db")


def test_reset_clears_everything(tmp_path):
    s = _store(tmp_path)
    s.reinforce(["a", "b"])
    s.reset()
    stats = s.stats()
    assert stats["edges"] == 0
    assert stats["nodes"] == 0


def test_persistence_across_instances(tmp_path):
    db = tmp_path / "synapses.db"
    s1 = SynapseStore(db)
    s1.reinforce(["x", "y"])
    s2 = SynapseStore(db)
    assert dict(s2.neighbors("x")).get("y", 0.0) > 0.0


def test_weak_decay_does_not_prune_above_threshold(tmp_path):
    s = _store(tmp_path)
    # Reinforce enough so first decay leaves us above PRUNE_THRESHOLD.
    for _ in range(3):
        s.reinforce(["a", "b"])
    s.decay()
    assert dict(s.neighbors("a")).get("b", 0.0) > PRUNE_THRESHOLD


def test_decay_constant_is_sane():
    # Sanity: a single decay tick on a max-weight non-LTP edge must not
    # immediately delete it. This guards against accidental config changes.
    assert WEIGHT_CAP * (1.0 - DECAY_RATE) > PRUNE_THRESHOLD
