"""Tests for the associative synapse layer."""

from __future__ import annotations

from neuralmind.synapses import (
    DECAY_RATE,
    LEARNING_RATE,
    LTP_FLOOR,
    LTP_THRESHOLD,
    PRUNE_THRESHOLD,
    TRANSITION_DECAY_RATE,
    TRANSITION_PRUNE_THRESHOLD,
    TRANSITION_WEIGHT_CAP,
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


# ---------------------------------------------------------------------------
# Directional transitions (v0.11.0+)
# ---------------------------------------------------------------------------


def test_record_sequence_creates_directional_edges(tmp_path):
    s = _store(tmp_path)
    pairs = s.record_sequence(["a", "b", "c"])
    # 3-node ordered sequence → 2 consecutive pairs
    assert pairs == 2
    # next_likely returns successors with normalized probabilities
    nxt = dict(s.next_likely("a"))
    assert "b" in nxt
    assert abs(sum(nxt.values()) - 1.0) < 1e-9
    # 'c' is not a successor of 'a' (only consecutive pairs count)
    assert "c" not in nxt


def test_record_sequence_is_directional(tmp_path):
    s = _store(tmp_path)
    s.record_sequence(["a", "b"])
    # a -> b recorded; the reverse is not
    assert dict(s.next_likely("a")) == {"b": 1.0}
    assert s.next_likely("b") == []


def test_record_sequence_skips_self_transitions(tmp_path):
    s = _store(tmp_path)
    # Consecutive duplicates should be collapsed.
    pairs = s.record_sequence(["a", "a", "a", "b", "b", "c"])
    assert pairs == 2
    nxt = dict(s.next_likely("a"))
    assert nxt == {"b": 1.0}


def test_next_likely_probabilities_normalize(tmp_path):
    s = _store(tmp_path)
    # 'a' transitions to 'b' three times and to 'c' once.
    for _ in range(3):
        s.record_sequence(["a", "b"])
    s.record_sequence(["a", "c"])
    nxt = dict(s.next_likely("a"))
    assert abs(nxt["b"] - 0.75) < 1e-9
    assert abs(nxt["c"] - 0.25) < 1e-9


def test_next_likely_unknown_node_returns_empty(tmp_path):
    s = _store(tmp_path)
    s.record_sequence(["a", "b"])
    assert s.next_likely("unknown") == []


def test_transitions_filters_by_source(tmp_path):
    s = _store(tmp_path)
    s.record_sequence(["a", "b", "c"])
    all_rows = s.transitions()
    from_a = s.transitions(from_node="a")
    assert len(all_rows) == 2
    assert len(from_a) == 1
    assert from_a[0][:2] == ("a", "b")


def test_transition_decay_prunes_weak_transitions(tmp_path):
    s = _store(tmp_path)
    s.record_sequence(["weak_a", "weak_b"])  # one observation
    # Many decay ticks should drop it below TRANSITION_PRUNE_THRESHOLD.
    for _ in range(500):
        s.decay()
    assert s.next_likely("weak_a") == []


def test_stats_reports_transition_counts(tmp_path):
    s = _store(tmp_path)
    s.record_sequence(["a", "b", "c"])
    stats = s.stats()
    assert stats["transitions"] == 2
    assert stats["transition_weight"] > 0.0


def test_reset_clears_transitions(tmp_path):
    s = _store(tmp_path)
    s.record_sequence(["a", "b"])
    s.reset()
    assert s.next_likely("a") == []
    assert s.stats()["transitions"] == 0


def test_transition_decay_constant_is_sane():
    # A single decay tick on a single-observation transition must not
    # immediately delete it.
    assert (1.0 - TRANSITION_DECAY_RATE) > TRANSITION_PRUNE_THRESHOLD


def test_persistence_carries_transitions(tmp_path):
    db = tmp_path / "synapses.db"
    s1 = SynapseStore(db)
    s1.record_sequence(["x", "y", "z"])
    s2 = SynapseStore(db)
    assert dict(s2.next_likely("x")) == {"y": 1.0}
    assert dict(s2.next_likely("y")) == {"z": 1.0}


def test_record_sequence_empty_and_single_input_are_noops(tmp_path):
    s = _store(tmp_path)
    assert s.record_sequence([]) == 0
    assert s.record_sequence(["solo"]) == 0
    assert s.record_sequence(["", "", ""]) == 0  # empty strings filtered
    assert s.stats()["transitions"] == 0


def test_transition_weight_caps_under_repeated_observations(tmp_path):
    """Repeated A→B observations must clamp at TRANSITION_WEIGHT_CAP. Without
    a cap a hot transition pair could overflow the float weight and starve
    other successors in the probability distribution."""
    s = _store(tmp_path)
    for _ in range(int(TRANSITION_WEIGHT_CAP) + 50):
        s.record_sequence(["a", "b"])
    rows = s.transitions(from_node="a")
    assert len(rows) == 1
    _, _, weight, count = rows[0]
    assert weight <= TRANSITION_WEIGHT_CAP + 1e-9
    # Count must still increment past the cap so LTP-style heuristics
    # can distinguish hot pairs from merely-saturated ones.
    assert count == int(TRANSITION_WEIGHT_CAP) + 50


def test_next_likely_top_k_zero_returns_empty(tmp_path):
    s = _store(tmp_path)
    s.record_sequence(["a", "b"])
    assert s.next_likely("a", top_k=0) == []


def test_next_likely_top_k_larger_than_successors_returns_all(tmp_path):
    s = _store(tmp_path)
    s.record_sequence(["a", "b"])
    s.record_sequence(["a", "c"])
    nxt = s.next_likely("a", top_k=100)
    assert len(nxt) == 2
    assert {n for n, _ in nxt} == {"b", "c"}


def test_next_likely_full_distribution_sums_to_one(tmp_path):
    """Top-K may sum to less than 1.0 by truncation, but the *full*
    distribution must sum to exactly 1.0 — that's what makes it a
    probability distribution rather than just a ranked score."""
    s = _store(tmp_path)
    # 5 successors with skewed weights so truncation matters.
    for _ in range(5):
        s.record_sequence(["src", "a"])
    for _ in range(3):
        s.record_sequence(["src", "b"])
    s.record_sequence(["src", "c"])
    s.record_sequence(["src", "d"])
    s.record_sequence(["src", "e"])

    full = s.next_likely("src", top_k=100)
    assert len(full) == 5
    assert abs(sum(p for _, p in full) - 1.0) < 1e-9

    # Top-3 should sum to less than 1.0 (we truncated) but each individual
    # probability must match its share of the full sum.
    top3 = s.next_likely("src", top_k=3)
    assert len(top3) == 3
    full_map = dict(full)
    for node, p in top3:
        assert abs(p - full_map[node]) < 1e-9


def test_record_sequence_strength_zero_is_noop_on_weight(tmp_path):
    """strength=0.0 records the pair (count bumps) but adds no weight.
    Useful for callers that want to track an observation without yet
    trusting it."""
    s = _store(tmp_path)
    s.record_sequence(["a", "b"], strength=0.0)
    rows = s.transitions(from_node="a")
    assert len(rows) == 1
    _, _, weight, count = rows[0]
    assert weight == 0.0
    assert count == 1
    # And: a zero-weight row contributes nothing to next_likely.
    assert s.next_likely("a") == []


def test_transitions_min_weight_filter(tmp_path):
    s = _store(tmp_path)
    # Strong: 5 observations
    for _ in range(5):
        s.record_sequence(["a", "b"])
    # Weak: 1 observation
    s.record_sequence(["a", "c"])
    all_rows = s.transitions(from_node="a")
    strong_only = s.transitions(from_node="a", min_weight=2.0)
    assert len(all_rows) == 2
    assert len(strong_only) == 1
    assert strong_only[0][1] == "b"


def test_decay_does_not_prune_high_count_transition_below_threshold(tmp_path):
    """A single decay tick must not erase a transition that's been heavily
    observed. Guards against accidentally cranking TRANSITION_DECAY_RATE
    to a value that decimates the table on every tick."""
    s = _store(tmp_path)
    for _ in range(20):
        s.record_sequence(["a", "b"])
    weight_before = s.transitions(from_node="a")[0][2]
    s.decay()
    weight_after = s.transitions(from_node="a")[0][2]
    assert weight_after > TRANSITION_PRUNE_THRESHOLD
    assert weight_after < weight_before


def test_decay_returns_transition_counts(tmp_path):
    """decay()'s return dict must report transition prune/remaining counts
    so monitoring callers (the watch loop, the SessionStart hook) can
    surface them."""
    s = _store(tmp_path)
    s.record_sequence(["weak_a", "weak_b"])  # one obs, will prune
    for _ in range(10):
        s.record_sequence(["strong_a", "strong_b"])  # survives
    # Drive enough decay to prune the weak edge.
    pruned_transitions = 0
    for _ in range(200):
        result = s.decay()
        pruned_transitions += result.get("pruned_transitions", 0)
    assert pruned_transitions >= 1
    remaining = s.decay()["remaining_transitions"]
    assert remaining >= 1  # strong pair survives
