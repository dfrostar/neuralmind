"""Tests for the associative synapse layer."""

from __future__ import annotations

import threading
import time

import pytest

from neuralmind.synapses import (
    LEARNING_RATE,
    LTP_FLOOR,
    LTP_THRESHOLD,
    PRUNE_THRESHOLD,
    STRUCTURAL_BASE_WEIGHT,
    STRUCTURAL_LOG_SCALE,
    STRUCTURAL_MAX_WEIGHT,
    TRANSITION_PRUNE_THRESHOLD,
    TRANSITION_WEIGHT_CAP,
    WEIGHT_CAP,
    SHARED_NAMESPACE,
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
    # weak edge: one activation, old — will decay below prune threshold
    old_ts = time.time() - 200 * 86400  # 200 days ago
    s.reinforce(["weak_a", "weak_b"], now=old_ts)
    # strong edge: cross LTP threshold, old — decays but floor preserves it
    for _ in range(LTP_THRESHOLD + 2):
        s.reinforce(["strong_a", "strong_b"], now=old_ts)
    s.decay()
    weak = dict(s.neighbors("weak_a"))
    strong = dict(s.neighbors("strong_a"))
    assert "weak_b" not in weak  # pruned
    assert strong.get("strong_b", 0.0) >= LTP_FLOOR - 1e-9


def test_decay_fresh_edges_preserved(tmp_path):
    """Freshly-activated edges should not be pruned by a decay tick."""
    s = _store(tmp_path)
    s.reinforce(["fresh_a", "fresh_b"], now=time.time())
    s.decay()
    assert "fresh_b" in dict(s.neighbors("fresh_a"))


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
    # With time-based half-life decay, a fresh edge barely moves on one tick.
    # The real guard: half-life constants are positive.
    from neuralmind.synapses import HALF_LIFE_DAYS, SHARED_HALF_LIFE_DAYS, EPHEMERAL_HALF_LIFE_DAYS
    assert HALF_LIFE_DAYS > 0
    assert SHARED_HALF_LIFE_DAYS > 0
    assert EPHEMERAL_HALF_LIFE_DAYS > 0


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
    # old transition: one observation, 200 days ago — decays below threshold
    old_ts = time.time() - 200 * 86400
    s.record_sequence(["weak_a", "weak_b"], now=old_ts)
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
    assert WEIGHT_CAP > TRANSITION_PRUNE_THRESHOLD


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
    observed. Guards against accidentally cranking the decay half-life
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
    old_ts = time.time() - 200 * 86400  # 200 days ago
    s.record_sequence(["weak_a", "weak_b"], now=old_ts)  # one obs, old → prunes
    for _ in range(10):
        s.record_sequence(["strong_a", "strong_b"])  # fresh → survives
    # Drive enough decay to prune the weak edge.
    pruned_transitions = 0
    result = s.decay()
    pruned_transitions += result.get("pruned_transitions", 0)
    assert pruned_transitions >= 1
    remaining = s.decay()["remaining_transitions"]
    assert remaining >= 1  # strong pair survives


def test_concurrent_reinforce(tmp_path):
    """Two threads calling reinforce() on overlapping node IDs must produce
    the expected final weight (LEARNING_RATE summed per call, clamped to
    WEIGHT_CAP)."""
    s = _store(tmp_path)
    # Each run shares node "a" so that the edge (a, b) and (a, c) get
    # reinforced concurrently by both threads.
    set1 = ["a", "b", "c"]
    set2 = ["a", "b", "new_d"]

    errors: list[Exception] = []

    def reinforce_set(node_set):
        try:
            for _ in range(5):
                s.reinforce(node_set)
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=reinforce_set, args=(set1,))
    t2 = threading.Thread(target=reinforce_set, args=(set2,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert not errors, f"Concurrent reinforce raised: {errors}"

    # (a, b) is reinforced by both threads 5 times each => 10 LEARNING_RATE.
    a_neighbors = dict(s.neighbors("a"))
    expected_a_b = min(WEIGHT_CAP, 10 * LEARNING_RATE)
    assert (
        abs(a_neighbors["b"] - expected_a_b) < 1e-9
    ), f"expected (a,b) weight {expected_a_b}, got {a_neighbors['b']}"

    # (a, c) is only in set1, reinforced 5 times.
    expected_a_c = min(WEIGHT_CAP, 5 * LEARNING_RATE)
    assert abs(a_neighbors["c"] - expected_a_c) < 1e-9

    # (a, new_d) is only in set2, reinforced 5 times.
    assert abs(a_neighbors.get("new_d", 0.0) - expected_a_c) < 1e-9


def _count_connect_calls(store, fn):
    """Run ``fn()`` while counting how many times ``store._connect`` is
    entered. Returns (result, connect_count)."""
    import contextlib

    real_connect = store._connect
    count = {"n": 0}

    @contextlib.contextmanager
    def counting_connect():
        count["n"] += 1
        with real_connect() as conn:
            yield conn

    store._connect = counting_connect  # type: ignore[method-assign]
    try:
        result = fn()
    finally:
        store._connect = real_connect  # type: ignore[method-assign]
    return result, count["n"]


def test_reinforce_writes_in_single_transaction(tmp_path):
    """Regression: activation bumps and synapse upserts must share ONE
    transaction so a partial failure can't leave counters ahead of edges."""
    s = _store(tmp_path)
    _, connects = _count_connect_calls(s, lambda: s.reinforce(["a", "b", "c"]))
    assert (
        connects == 1
    ), f"reinforce should open exactly one connection/transaction, opened {connects}"


def test_reinforce_rolls_back_activations_on_synapse_failure(tmp_path):
    """If the synapse write fails, the activation-count bump must roll back
    too — reinforce() is all-or-nothing."""
    import contextlib
    import sqlite3

    s = _store(tmp_path)
    real_connect = s._connect

    class _FailingConn:
        def __init__(self, conn):
            self._conn = conn

        def executemany(self, sql, rows):
            if "INTO synapses(" in sql:
                raise sqlite3.OperationalError("induced synapse-write failure")
            return self._conn.executemany(sql, rows)

        def __getattr__(self, name):
            return getattr(self._conn, name)

    @contextlib.contextmanager
    def failing_connect():
        with real_connect() as conn:
            yield _FailingConn(conn)

    s._connect = failing_connect  # type: ignore[method-assign]
    try:
        raised = False
        try:
            s.reinforce(["a", "b", "c"])
        except sqlite3.OperationalError:
            raised = True
        assert raised, "reinforce should propagate the synapse-write failure"
    finally:
        s._connect = real_connect  # type: ignore[method-assign]

    # The activation bump for "a" must have rolled back with the synapses.
    with s._connect() as conn:
        cur = conn.execute("SELECT COUNT(*) FROM node_activations WHERE node_id = ?", ("a",))
        assert cur.fetchone()[0] == 0
    assert s.neighbors("a") == []


def test_decay_commits_in_single_transaction(tmp_path):
    """Regression: decay is not idempotent, so the whole tick must commit in
    ONE transaction — a partial commit + retry would double-decay."""
    s = _store(tmp_path)
    s.reinforce(["a", "b", "c"])  # personal namespace
    s.reinforce(["x", "y"], namespace="shared")

    # Pre-compute namespaces so the read scan isn't counted as a write txn.
    ns = s._default_namespaces()
    s._default_namespaces = lambda: ns  # type: ignore[method-assign]

    _, connects = _count_connect_calls(s, lambda: s.decay())
    assert connects == 1, f"decay should commit in exactly one transaction, opened {connects}"


# --------------------------------------------------------------------------- #
# Structural → synapse seeding tests
# --------------------------------------------------------------------------- #


def test_seed_from_structural_basic(tmp_path):
    """Structural edges in the table should seed synapse edges."""
    s = _store(tmp_path)
    edges = [
        {"source": "A", "target": "B", "relation": "calls"},
        {"source": "B", "target": "C", "relation": "imports_from"},
    ]
    s.persist_structural_edges(edges)
    count = s.seed_from_structural()
    assert count == 2
    all_edges = s.edges()
    assert len(all_edges) == 2
    for _, _, weight, _ in all_edges:
        assert 0.0 < weight <= STRUCTURAL_MAX_WEIGHT


def test_seed_from_structural_weight_capped(tmp_path):
    """Very high call_count should still cap at STRUCTURAL_MAX_WEIGHT."""

    s = _store(tmp_path)
    edges = [{"source": "A", "target": "B", "relation": "calls"}]
    s.persist_structural_edges(edges)
    # call_count=50000 → raw = 0.10 + 0.05*ln(50001) ≈ 0.641, capped to 0.60
    with s._connect() as conn:
        conn.execute(
            "UPDATE structural_edges SET call_count = 50000 WHERE caller = 'A'"
        )
    count = s.seed_from_structural()
    assert count == 1
    # Read shared namespace raw so we test the stored weight, not the merged
    # view (which scales by W_SHARED=0.5).
    with s._connect() as conn:
        raw_weight = conn.execute(
            "SELECT weight FROM synapses WHERE namespace = ?",
            (SHARED_NAMESPACE,),
        ).fetchone()[0]
    assert raw_weight == pytest.approx(STRUCTURAL_MAX_WEIGHT)


def test_seed_from_structural_idempotent(tmp_path):
    """Re-seeding should increment activation_count, not add rows."""
    s = _store(tmp_path)
    edges = [{"source": "A", "target": "B", "relation": "calls"}]
    s.persist_structural_edges(edges)
    s.seed_from_structural()
    s.seed_from_structural()
    assert len(s.edges()) == 1  # still one edge
    assert s.edges()[0][3] == 2  # activation_count incremented


def test_seed_from_structural_uses_shared_namespace(tmp_path):
    """Seeded edges should land in 'shared' namespace."""
    s = _store(tmp_path)
    edges = [{"source": "A", "target": "B", "relation": "calls"}]
    s.persist_structural_edges(edges)
    s.seed_from_structural()
    # Check namespace via raw SQL
    with s._connect() as conn:
        ns = conn.execute(
            "SELECT namespace FROM synapses WHERE node_a = 'A'"
        ).fetchone()[0]
    assert ns == "shared"
