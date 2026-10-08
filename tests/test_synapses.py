"""Tests for the associative synapse layer."""

from __future__ import annotations

import math
import threading
import time

import pytest

from neuralmind.synapses import (
    LEARNING_RATE,
    LTP_FLOOR,
    LTP_THRESHOLD,
    PRUNE_THRESHOLD,
    SHARED_NAMESPACE,
    STRUCTURAL_MAX_WEIGHT,
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


def test_repeated_decay_does_not_compound(tmp_path):
    """Decay is wall-clock, not per-call: the SessionStart hook runs decay()
    every session, and each tick must only charge the time since the last
    tick. Regression for #422 (weights collapsing to the floor / pruned)."""
    now = time.time()
    t0 = now - 30 * 86400

    once = _store(tmp_path / "once")
    once.reinforce(["a", "b"], now=t0)
    once.record_sequence(["a", "b"], now=t0)
    once.decay(now=now)
    expected = dict(once.neighbors("a"))["b"]
    expected_t = once.transitions()[0][2]

    many = _store(tmp_path / "many")
    many.reinforce(["a", "b"], now=t0)
    many.record_sequence(["a", "b"], now=t0)
    for step in (10, 20, 30, 30, 30):
        many.decay(now=t0 + step * 86400)

    # Relative tolerance: splitting the exponent across ticks rounds
    # differently per platform's SQLite EXP (~1e-8 relative on Windows).
    assert dict(many.neighbors("a"))["b"] == pytest.approx(expected, rel=1e-6)
    assert many.transitions()[0][2] == pytest.approx(expected_t, rel=1e-6)


def test_synapse_client_deactivate_decays_touching_edges(tmp_path):
    from neuralmind.synapse_client import SynapseClient

    s = _store(tmp_path)
    s.reinforce(["a", "b"], now=time.time() - 60 * 86400)
    before = dict(s.neighbors("a"))["b"]
    assert SynapseClient(s, tmp_path).deactivate(["a", "a"]) == 1
    assert dict(s.neighbors("a")).get("b", 0.0) < before


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


def test_degrees_count_distinct_neighbors_across_namespaces(tmp_path):
    s = _store(tmp_path)
    s.reinforce(["A", "B"])
    s.reinforce(["A", "C"])
    # The same pair in a second namespace is still one neighbor.
    s.reinforce(["A", "B"], namespace=SHARED_NAMESPACE)
    assert s.degrees(["A", "B", "C", "lonely"]) == {"A": 2, "B": 1, "C": 1}
    assert s.degrees(["A"], namespaces=[SHARED_NAMESPACE]) == {"A": 1}
    assert s.degrees([]) == {}


def test_degrees_takes_more_ids_than_sqlite_binds_at_once(tmp_path):
    s = _store(tmp_path)
    s.reinforce(["A", "B"])
    # 300,000 bound variables in one query: past SQLite's default 32,766 and
    # the 250,000 Debian and Ubuntu builds allow.
    ids = [f"n{i}" for i in range(150_000)] + ["A"]
    assert s.degrees(ids) == {"A": 1}


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


def test_stats_ltp_edges_counts_only_edges_decay_protects(tmp_path):
    # Regression: ltp_edges counted every row with enough activations, so an
    # edge penalized below LTP_FLOOR, or one in the ephemeral namespace (no
    # LTP exemption), was reported as LTP-protected although decay erodes it.
    db = tmp_path / "synapses.db"
    personal = SynapseStore(db)
    ephemeral = SynapseStore(db, namespace="ephemeral")
    for _ in range(LTP_THRESHOLD + 1):
        personal.reinforce(["ltp_a", "ltp_b"])
        personal.reinforce(["low_a", "low_b"])
        ephemeral.reinforce(["eph_a", "eph_b"])
    personal.reinforce(["young_a", "young_b"])  # too few activations
    personal.penalize(["low_a", "low_b"], penalty=0.9)  # 1.0 -> 0.1 < LTP_FLOOR

    stats = personal.stats()
    assert stats["edges"] == 4
    assert stats["ltp_edges"] == 1
    assert personal.stats_detailed()["ltp_protected"] == 1


def test_stats_ltp_edges_matches_the_synapse_memory_long_term_count(tmp_path):
    from neuralmind.synapse_memory import render_synapse_memory
    from neuralmind.synapses import default_db_path

    store = SynapseStore(default_db_path(tmp_path))
    for _ in range(LTP_THRESHOLD):
        store.reinforce(["a", "b"])
        store.reinforce(["c", "d"])
    store.penalize(["c", "d"], penalty=0.9)

    out = render_synapse_memory(tmp_path)
    assert store.stats()["ltp_edges"] == 1
    assert "Edges learned: 2 (1 long-term)" in out
    assert out.count("*(long-term)*") == 1


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
    from neuralmind.synapses import EPHEMERAL_HALF_LIFE_DAYS, HALF_LIFE_DAYS, SHARED_HALF_LIFE_DAYS

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
        conn.execute("UPDATE structural_edges SET call_count = 50000 WHERE caller = 'A'")
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
    """Re-seeding must neither add rows nor inflate activation_count.

    Seeding is not an activation: bumping the count on every build made an
    unchanged call path LTP-protected after LTP_THRESHOLD rebuilds.
    """
    s = _store(tmp_path)
    edges = [{"source": "A", "target": "B", "relation": "calls"}]
    s.persist_structural_edges(edges)
    s.seed_from_structural()
    s.seed_from_structural()
    assert len(s.edges()) == 1  # still one edge
    assert s.edges()[0][3] == 1  # activation_count not inflated by re-seeding


def test_seed_from_structural_uses_shared_namespace(tmp_path):
    """Seeded edges should land in 'shared' namespace."""
    s = _store(tmp_path)
    edges = [{"source": "A", "target": "B", "relation": "calls"}]
    s.persist_structural_edges(edges)
    s.seed_from_structural()
    # Check namespace via raw SQL
    with s._connect() as conn:
        ns = conn.execute("SELECT namespace FROM synapses WHERE node_a = 'A'").fetchone()[0]
    assert ns == "shared"


# --------------------------------------------------------------------------- #
# N-13: Document → synapse seeding tests
# --------------------------------------------------------------------------- #


def _make_store(tmp_path):
    """Create a SynapseStore with structural_edges populated."""
    return _store(tmp_path)


def _code_node(nid, label=None):
    """Helper: a code node dict."""
    return {
        "id": nid,
        "label": label or nid,
        "metadata": {"label": label or nid},
    }


def _biz_node(nid, text, tags=None, title=None):
    """Helper: a business context node dict."""
    meta = {"content_category": "business_context"}
    if title:
        meta["title"] = title
    if tags:
        meta["tags"] = tags
    return {
        "id": nid,
        "label": title or nid,
        "content_text": text,
        "metadata": meta,
    }


def test_T1_false_positive_control(tmp_path):
    """Generic words ('server', 'engine') must NOT create spurious edges."""
    s = _store(tmp_path)
    nodes = [
        _biz_node(
            "decision:test_decision.20260801",
            "We discussed the architecture. No specific code references.",
        ),
        _code_node("engine_server_py__cmd_ingest_fn", "cmd_ingest_fn"),
        _code_node("engine_core_py__main_fn", "main_fn"),
    ]
    count = s.seed_from_documents(nodes)
    # Generic "server"/"engine" are stopwords → no edges
    assert count == 0


def test_T2_idempotency_no_activation_inflation(tmp_path):
    """Re-running seed returns 0 new edges and must not inflate activation_count."""
    s = _store(tmp_path)
    nodes = [
        _biz_node(
            "decision:adopt_postgres.20260801",
            "Use PostgreSQL for CMMC audit logs.",
            tags=["infrastructure"],
            title="Adopt PostgreSQL",
        ),
        _code_node("engine_audit_py__log_fn", "audit_log_data"),
        _code_node("engine_db_pg__connect_fn", "postgres_connect"),
    ]
    count1 = s.seed_from_documents(nodes)
    assert count1 > 0
    count2 = s.seed_from_documents(nodes)
    # H3 fix: second run returns 0 new edges (not candidate count)
    assert count2 == 0
    # activation_count must be 1 (not incremented on re-run)
    with s._connect() as conn:
        max_act = conn.execute("SELECT MAX(activation_count) FROM synapses").fetchone()[0]
    assert max_act == 1


def test_T3_cross_process_determinism(tmp_path):
    """Seed in one store, reopen fresh store — same edges."""
    db = tmp_path / "synapses.db"
    s1 = SynapseStore(db)
    nodes = [
        _biz_node(
            "decision:security_review.20260801",
            "Conduct quarterly security review of auth module.",
            tags=["security", "compliance"],
        ),
        _code_node("engine_auth_py__login_fn", "auth_login"),
        _code_node("engine_security_py__check_fn", "security_check"),
    ]
    count1 = s1.seed_from_documents(nodes)
    s2 = SynapseStore(db)
    count2 = s2.seed_from_documents(nodes)
    # H3: second run returns 0 new edges
    assert count1 > 0
    assert count2 == 0
    # Edges identical
    edges1 = {(a, b) for a, b, _, _ in s1.edges(min_weight=0.0)}
    edges2 = {(a, b) for a, b, _, _ in s2.edges(min_weight=0.0)}
    assert edges1 == edges2


def test_T4_namespace_and_canonical_ordering(tmp_path):
    """New edges must be 'shared' namespace, stored with node_a < node_b."""
    s = _store(tmp_path)
    nodes = [
        _biz_node(
            "decision:important.20260801",
            "Important decision about audit logs.",
        ),
        _code_node("engine_audit_py__log_fn", "audit_log_data"),
    ]
    s.seed_from_documents(nodes)
    with s._connect() as conn:
        rows = conn.execute("SELECT node_a, node_b, namespace FROM synapses").fetchall()
    for node_a, node_b, ns in rows:
        assert ns == "shared"
        assert node_a < node_b, f"Canonical order violated: {node_a} !< {node_b}"


def test_T5_stoplist_specificity(tmp_path):
    """Specific symbol creates edge; generic word does not."""
    s = _store(tmp_path)
    # "audit" is specific → should match
    # "util" is a stopword → should NOT match even if present in text
    nodes = [
        _biz_node(
            "decision:specific.20260801",
            "The audit module needs refactoring.",
        ),
        _code_node("engine_audit_py__verify_fn", "audit_verify"),
        _code_node("engine_util_py__helper_fn", "util_helper"),
    ]
    count = s.seed_from_documents(nodes)
    # "audit" should match (specific component)
    assert count >= 1
    with s._connect() as conn:
        rows = conn.execute("SELECT node_a, node_b FROM synapses").fetchall()
    # No edge to the util node (util is a stopword)
    for node_a, node_b in rows:
        assert not node_a.endswith("__helper_fn")
        assert not node_b.endswith("__helper_fn")


def test_T6_business_to_business_shared_tag(tmp_path):
    """Shared specific tag creates 0.20 edge when frequency < 20%."""
    s = _store(tmp_path)
    # 11 business nodes: 2 share "rare_pair_tag" (18% < 20%), rest unique
    nodes = [
        _biz_node("decision:shared.20260801", "Text.", tags=["rare_pair_tag"]),
        _biz_node("decision:sharer.20260801", "Text.", tags=["rare_pair_tag"]),
    ] + [_biz_node(f"decision:f{i}.20260801", "Text.", tags=[f"tag{i}"]) for i in range(9)]
    count = s.seed_from_documents(nodes)
    assert count == 1
    with s._connect() as conn:
        row = conn.execute("SELECT node_a, node_b, weight FROM synapses").fetchone()
    assert row[2] == 0.20
    assert row[0] < row[1]  # canonical ordering


def test_T7_fail_open(tmp_path):
    """No business nodes → 0 edges, no exception; malformed metadata ok."""
    s = _store(tmp_path)
    # No business nodes
    nodes = [
        _code_node("engine_audit_py__fn", "audit_fn"),
        _code_node("engine_server_py__fn", "server_fn"),
    ]
    assert s.seed_from_documents(nodes) == 0
    # Empty list
    assert s.seed_from_documents([]) == 0
    # Malformed metadata (no metadata key)
    nodes_bad = [
        {"id": "bad:node.001", "label": "bad", "content_text": "text"},
    ]
    assert s.seed_from_documents(nodes_bad) == 0


def test_T8_canonical_none_skip(tmp_path):
    """_canonical returns None for self-pairs — must be handled gracefully."""
    s = _store(tmp_path)
    # Business node with same ID would cause a==b in _canonical
    nodes = [
        _biz_node(
            "decision:self.20260801",
            "Self-referential decision.",
        ),
        _code_node("decision:self.20260801", "different_label"),
    ]
    # Should not raise
    count = s.seed_from_documents(nodes)
    # All edges should have node_a != node_b
    with s._connect() as conn:
        rows = conn.execute("SELECT node_a, node_b FROM synapses").fetchall()
    for node_a, node_b in rows:
        assert node_a != node_b


# ---------------------------------------------------------------------------
# Adversarial QA regression tests (post-H1/H2/H3 fixes)
# ---------------------------------------------------------------------------


def test_H1_compound_match_requires_adjacency(tmp_path):
    """Compound match must require components to be adjacent in text, not just present."""
    s = _store(tmp_path)
    nodes = [
        _biz_node(
            "decision:engine_test.20260801",
            "The engine was discussed. Much later, audit was mentioned.",
        ),
        _code_node("engine_audit_py__fn", "some_unrelated_label"),
    ]
    count = s.seed_from_documents(nodes)
    # "engine" and "audit" appear but are NOT adjacent → no compound match
    # Single-component match still works (audit is present), weight = 0.20
    assert count == 1
    with s._connect() as conn:
        weight = conn.execute("SELECT weight FROM synapses").fetchone()[0]
    assert weight == 0.20  # single match, not compound


def test_H1_compound_match_adjacent_components(tmp_path):
    """Adjacent components in text create compound match (0.25)."""
    s = _store(tmp_path)
    nodes = [
        _biz_node(
            "decision:adjacent.20260801",
            "We need to implement engine audit logging for compliance.",
        ),
        _code_node("engine_audit_py__fn", "some_other_label"),
    ]
    count = s.seed_from_documents(nodes)
    assert count == 1
    with s._connect() as conn:
        weight = conn.execute("SELECT weight FROM synapses").fetchone()[0]
    assert weight == 0.25


def test_H2_title_reference_b2b_crosslink(tmp_path):
    """A business node referencing another's title creates a 0.25 edge."""
    s = _store(tmp_path)
    nodes = [
        _biz_node(
            "decision:adopt_postgres.20260801",
            "Adopt PostgreSQL for audit logging.",
            title="Adopt PostgreSQL",
            tags=["infrastructure"],
        ),
        _biz_node(
            "meeting:review.20260801",
            "In this meeting we discussed the Adopt PostgreSQL decision and next steps.",
            title="Review Meeting",
            tags=["infrastructure"],
        ),
        _code_node("engine_audit_py__fn", "audit_fn"),
    ]
    count = s.seed_from_documents(nodes)
    # Should have: title-ref b2b edge (0.25) + maybe some code edges
    assert count >= 1
    with s._connect() as conn:
        rows = conn.execute("SELECT node_a, node_b, weight FROM synapses").fetchall()
    # Find the b2b edge
    biz_edges = [
        (a, b, w)
        for a, b, w in rows
        if a.startswith(("decision:", "meeting:")) and b.startswith(("decision:", "meeting:"))
    ]
    assert len(biz_edges) == 1
    assert biz_edges[0][2] == 0.25


def test_M1_file_path_tokenization(tmp_path):
    """File paths with / separators are properly tokenized."""
    s = _store(tmp_path)
    nodes = [
        _biz_node(
            "decision:filepath.20260801",
            "Update the engine/server.py file for better logging.",
        ),
        _code_node("engine_server_py__handler_fn", "server_handler"),
    ]
    count = s.seed_from_documents(nodes)
    # "server" should match (not "engine/server" jammed together)
    assert count >= 1


def test_T9_compound_vs_single_distinction(tmp_path):
    """Compound match (0.25) takes priority over single match (0.20)."""
    s = _store(tmp_path)
    nodes = [
        _biz_node(
            "decision:compound.20260801",
            "We use postgres connect for the database.",
        ),
        _code_node("engine_postgres_py__connect_fn", "some_other_label"),
    ]
    count = s.seed_from_documents(nodes)
    assert count == 1
    with s._connect() as conn:
        weight = conn.execute("SELECT weight FROM synapses").fetchone()[0]
    # "postgres" + "connect" are adjacent in text → compound match = 0.25
    assert weight == 0.25


def test_T10_exact_label_match_weight(tmp_path):
    """Exact full label match yields 0.40."""
    s = _store(tmp_path)
    nodes = [
        _biz_node(
            "decision:exact.20260801",
            "The audit_log_data function needs updating.",
        ),
        _code_node("engine_audit_py__log_fn", "audit_log_data"),
    ]
    count = s.seed_from_documents(nodes)
    assert count == 1
    with s._connect() as conn:
        weight = conn.execute("SELECT weight FROM synapses").fetchone()[0]
    assert weight == 0.40


# --------------------------------------------------------------------------- #
# Decay never raises a weight (LTP floor only holds edges at/above it)
# --------------------------------------------------------------------------- #


def _raw_edge(s, a, b, namespace="personal"):
    with s._connect() as conn:
        return conn.execute(
            "SELECT weight, activation_count FROM synapses "
            "WHERE node_a = ? AND node_b = ? AND namespace = ?",
            (a, b, namespace),
        ).fetchone()


@pytest.mark.parametrize("namespace", ["personal", SHARED_NAMESPACE])
@pytest.mark.parametrize("learned_half_life", [True, False])
def test_decay_does_not_lift_penalized_ltp_edge_back_to_floor(
    tmp_path, namespace, learned_half_life
):
    """An LTP edge penalized below LTP_FLOOR must stay below it on decay.

    The floor protects an established association from *fading*; it must
    not undo an explicit penalty. Decay is one-way: it never raises a weight.
    """
    s = _store(tmp_path)
    now = time.time()
    for _ in range(LTP_THRESHOLD):
        s.reinforce(["a", "b"], now=now, namespace=namespace)
    if not learned_half_life:
        with s._connect() as conn:
            conn.execute("UPDATE synapses SET half_life_days = NULL")
    s.penalize(["a", "b"], penalty=1.0, namespace=namespace)
    assert _raw_edge(s, "a", "b", namespace) == (0.0, LTP_THRESHOLD)

    s.decay(now=now)  # zero elapsed time
    assert _raw_edge(s, "a", "b", namespace)[0] == 0.0

    # Partially penalized (0.15 < floor): decays freely, never lifted to 0.2.
    s2 = SynapseStore(tmp_path / "second.db")
    for _ in range(LTP_THRESHOLD):
        s2.reinforce(["a", "b"], now=now, namespace=namespace)
    if not learned_half_life:
        with s2._connect() as conn:
            conn.execute("UPDATE synapses SET half_life_days = NULL")
    s2.penalize(["a", "b"], penalty=WEIGHT_CAP - 0.15, namespace=namespace)
    before = _raw_edge(s2, "a", "b", namespace)[0]
    assert before == pytest.approx(0.15)
    s2.decay(now=now + 10 * 86400)
    after = _raw_edge(s2, "a", "b", namespace)[0]
    assert after < before < LTP_FLOOR


def test_decay_still_floors_ltp_edges_that_were_above_floor(tmp_path):
    """The fix must keep the floor for edges that sit at or above it."""
    s = _store(tmp_path)
    now = time.time()
    for _ in range(LTP_THRESHOLD):
        s.reinforce(["a", "b"], now=now)
    s.decay(now=now + 3650 * 86400)  # ten years idle
    assert _raw_edge(s, "a", "b")[0] == pytest.approx(LTP_FLOOR)


def test_decay_never_increases_any_weight(tmp_path):
    s = _store(tmp_path)
    now = time.time()
    for _ in range(LTP_THRESHOLD + 1):
        s.reinforce(["h", "i"], now=now)
        s.reinforce(["j", "k"], now=now, namespace=SHARED_NAMESPACE)
    s.reinforce(["l", "m"], now=now)
    s.penalize(["h", "i"], penalty=0.95)
    s.penalize(["j", "k"], penalty=0.9, namespace=SHARED_NAMESPACE)
    sql = "SELECT node_a, node_b, namespace, weight FROM synapses"
    with s._connect() as conn:
        before = {(a, b, ns): w for a, b, ns, w in conn.execute(sql)}
    for days in (0, 1, 30, 400):
        s.decay(now=now + days * 86400)
        with s._connect() as conn:
            for a, b, ns, w in conn.execute(sql):
                assert w <= before[(a, b, ns)] + 1e-12, (a, b, ns, w, before[(a, b, ns)])
                before[(a, b, ns)] = w


# --------------------------------------------------------------------------- #
# decay_node: a fixed multiplicative tick per call (explicit negative signal)
# --------------------------------------------------------------------------- #


def test_decay_node_softens_a_freshly_reinforced_edge(tmp_path):
    """One negative signal must visibly weaken an edge used seconds ago.

    The old time-based formula decayed by the edge's idle time, so an edge
    reinforced moments before ``neuralmind_feedback signal=negative`` barely
    moved (0.3 to 0.29999998 after ten calls).
    """
    from neuralmind.synapses import NODE_DECAY_FACTOR

    s = _store(tmp_path)
    s.reinforce(["x", "y"])
    s.reinforce(["u", "v"])  # untouched by decay_node("x")
    s.decay_node("x")
    assert _raw_edge(s, "x", "y")[0] == pytest.approx(LEARNING_RATE * NODE_DECAY_FACTOR)
    assert _raw_edge(s, "u", "v")[0] == pytest.approx(LEARNING_RATE)


def test_decay_node_prunes_non_ltp_edges_below_threshold(tmp_path):
    s = _store(tmp_path)
    s.reinforce(["x", "y"])
    pruned = 0
    for _ in range(10):
        pruned = s.decay_node("y")["pruned"]
        if pruned:
            break
    assert pruned == 1
    assert _raw_edge(s, "x", "y") is None


def test_decay_node_keeps_ltp_floor_but_never_raises_a_weight(tmp_path):
    s = _store(tmp_path)
    for _ in range(LTP_THRESHOLD):
        s.reinforce(["x", "y"])
        s.reinforce(["x", "z"])
    for _ in range(20):
        s.decay_node("x")
    # Established association: floored, not pruned.
    assert _raw_edge(s, "x", "y")[0] == pytest.approx(LTP_FLOOR)
    # An LTP edge already penalized below the floor keeps falling.
    s.penalize(["x", "z"], penalty=1.0)
    s.decay_node("x")
    assert _raw_edge(s, "x", "z")[0] == 0.0


def test_decay_node_ticks_outgoing_transitions(tmp_path):
    from neuralmind.synapses import NODE_DECAY_FACTOR

    s = _store(tmp_path)
    for _ in range(4):
        s.record_sequence(["x", "y"])
    s.decay_node("x")
    with s._connect() as conn:
        w = conn.execute(
            "SELECT weight FROM synapse_transitions WHERE from_node='x' AND to_node='y'"
        ).fetchone()[0]
    assert w == pytest.approx(4.0 * NODE_DECAY_FACTOR)


# --------------------------------------------------------------------------- #
# Ephemeral edges keep the documented 1-day half-life
# --------------------------------------------------------------------------- #


def test_ephemeral_edges_use_documented_half_life(tmp_path):
    """Session scratch decays at EPHEMERAL_HALF_LIFE_DAYS, not DECAY_RATE_MIN.

    The learned per-edge rate used to clamp every edge to DECAY_RATE_MIN
    (3 days), so an ephemeral edge kept ~79% of its weight after a day
    instead of half.
    """
    from neuralmind.synapses import EPHEMERAL_HALF_LIFE_DAYS, EPHEMERAL_NAMESPACE

    s = SynapseStore(tmp_path / "synapses.db", namespace=EPHEMERAL_NAMESPACE)
    t0 = time.time()
    s.reinforce(["p", "q"], now=t0)
    s.reinforce(["p", "q"], now=t0)
    with s._connect() as conn:
        hl = conn.execute("SELECT half_life_days FROM synapses").fetchone()[0]
    assert hl == pytest.approx(EPHEMERAL_HALF_LIFE_DAYS)

    s.decay(now=t0 + EPHEMERAL_HALF_LIFE_DAYS * 86400)
    weight = _raw_edge(s, "p", "q", EPHEMERAL_NAMESPACE)[0]
    assert weight == pytest.approx(2 * LEARNING_RATE / 2)


# --------------------------------------------------------------------------- #
# normalize_hubs is idempotent (runs on every PreCompact hook)
# --------------------------------------------------------------------------- #


def _all_weights(s):
    with s._connect() as conn:
        return {
            (a, b, ns): w
            for a, b, ns, w in conn.execute(
                "SELECT node_a, node_b, namespace, weight FROM synapses"
            )
        }


@pytest.mark.parametrize("strength", [1.0, 2.0])
def test_normalize_hubs_is_idempotent(tmp_path, strength):
    """Repeated calls on an unchanged graph must leave weights unchanged.

    Each call used to multiply hub edges by sqrt(max_degree/degree) again,
    so a saturated hub fell 1.0 -> 0.5 -> 0.25 -> ... one PreCompact at a
    time until its edges were pruned.
    """
    s = _store(tmp_path)
    for i in range(200):
        s.reinforce(["utils", f"n{i}"], strength=strength)
        s.reinforce(["utils", f"n{i}"], strength=strength)
    before = _all_weights(s)
    assert s.normalize_hubs() == 1
    once = _all_weights(s)
    assert all(once[k] < before[k] for k in before)  # still trims a runaway hub
    for _ in range(6):
        assert s.normalize_hubs() == 0
    assert _all_weights(s) == pytest.approx(once, rel=1e-12)


def test_normalize_hubs_idempotent_with_adjacent_hubs(tmp_path):
    """Two hubs sharing an edge settle in one pass; later passes are no-ops."""
    s = _store(tmp_path)
    for i in range(120):
        s.reinforce(["hub_a", f"a{i}"], strength=2.0)
        s.reinforce(["hub_b", f"b{i}"], strength=2.0)
    for _ in range(4):
        s.reinforce(["hub_a", "hub_b"], strength=2.0)
    assert s.normalize_hubs() == 2
    once = _all_weights(s)
    assert s.normalize_hubs() == 0
    assert _all_weights(s) == pytest.approx(once, rel=1e-12)


def test_normalize_hubs_retrims_after_new_reinforcement(tmp_path):
    """Learning after a trim is trimmed back to the same budget, not below."""
    s = _store(tmp_path)
    for i in range(200):
        s.reinforce(["utils", f"n{i}"], strength=2.0)
    s.normalize_hubs()
    budget = sum(_all_weights(s).values())
    for i in range(200):
        s.reinforce(["utils", f"n{i}"], strength=2.0)
    assert sum(_all_weights(s).values()) > budget
    assert s.normalize_hubs() == 1
    assert sum(_all_weights(s).values()) == pytest.approx(budget, rel=1e-9)


# --------------------------------------------------------------------------- #
# Structural seeding mirrors the current build, not the build history
# --------------------------------------------------------------------------- #


def _structural_rows(s):
    with s._connect() as conn:
        return conn.execute(
            "SELECT caller, callee, edge_type, call_count FROM structural_edges ORDER BY caller"
        ).fetchall()


def test_rebuilds_do_not_make_structural_edges_ltp(tmp_path):
    """Rebuilding the same graph must not inflate call_count or LTP-protect.

    Every build used to add 1 to both ``call_count`` and the seeded edge's
    ``activation_count``, so after LTP_THRESHOLD builds an unchanged call
    path became LTP-protected (contradicting the docstring) and its weight
    crept up as if it had more call sites.
    """
    from neuralmind.synapses import STRUCTURAL_BASE_WEIGHT, STRUCTURAL_LOG_SCALE

    s = _store(tmp_path)
    edge = [{"source": "billing.charge", "target": "stripe.call", "relation": "calls"}]
    for _ in range(LTP_THRESHOLD + 1):
        s.persist_structural_edges(edge)
        s.seed_from_structural()
    assert _structural_rows(s) == [("billing.charge", "stripe.call", "call", 1)]
    with s._connect() as conn:
        weight, count = conn.execute(
            "SELECT weight, activation_count FROM synapses WHERE namespace = ?",
            (SHARED_NAMESPACE,),
        ).fetchone()
    assert count == 1 < LTP_THRESHOLD
    assert weight == pytest.approx(STRUCTURAL_BASE_WEIGHT + STRUCTURAL_LOG_SCALE * math.log(2))


def test_call_count_counts_call_sites_within_one_build(tmp_path):
    s = _store(tmp_path)
    edge = {"source": "a", "target": "b", "relation": "calls"}
    assert s.persist_structural_edges([edge, edge, edge]) == 1
    assert _structural_rows(s) == [("a", "b", "call", 3)]
    s.persist_structural_edges([edge, edge, edge])
    assert _structural_rows(s) == [("a", "b", "call", 3)]


def test_removed_call_path_is_not_reseeded(tmp_path):
    """A call deleted from the code drops out of structural_edges on rebuild."""
    s = _store(tmp_path)
    t0 = time.time() - 86400
    s.persist_structural_edges(
        [{"source": "billing.charge", "target": "stripe.call", "relation": "calls"}], now=t0
    )
    s.seed_from_structural(now=t0)

    s.persist_structural_edges([{"source": "other.a", "target": "other.b", "relation": "calls"}])
    s.seed_from_structural()

    assert _structural_rows(s) == [("other.a", "other.b", "call", 1)]
    with s._connect() as conn:
        last = conn.execute(
            "SELECT last_activated FROM synapses WHERE node_a = 'billing.charge'"
        ).fetchone()[0]
    # The stale seeded synapse is left to decay and prune; it is not refreshed.
    assert last == pytest.approx(t0)


def test_empty_graph_does_not_wipe_structural_edges(tmp_path):
    """A failed/empty graph load must not erase the last good snapshot."""
    s = _store(tmp_path)
    s.persist_structural_edges([{"source": "a", "target": "b", "relation": "calls"}])
    assert s.persist_structural_edges([]) == 0
    assert _structural_rows(s) == [("a", "b", "call", 1)]


# --------------------------------------------------------------------------- #
# Read-then-write transactions take the write lock up front (BEGIN IMMEDIATE)
# --------------------------------------------------------------------------- #


class _CommitAfterFirstRead:
    """Connection proxy: after the first SELECT inside a transaction, let a
    concurrent writer (another thread, another connection) commit.

    A deferred ``BEGIN`` whose first statement is a read pins a WAL snapshot;
    when another connection commits before the first write, SQLite fails the
    read->write upgrade at once with "database is locked" (SQLITE_BUSY_SNAPSHOT)
    instead of waiting out the busy timeout.
    """

    def __init__(self, conn, writer_go, writer_done):
        self._c = conn
        self._in_txn = False
        self._fired = False
        self._go = writer_go
        self._done = writer_done

    def execute(self, sql, *args):
        cur = self._c.execute(sql, *args)
        head = sql.lstrip().upper()
        if head.startswith("BEGIN"):
            self._in_txn = True
        elif self._in_txn and not self._fired and head.startswith("SELECT"):
            self._fired = True
            self._go.set()
            # With BEGIN IMMEDIATE the writer blocks on our lock, so don't
            # wait for it forever — it finishes after we commit.
            self._done.wait(timeout=0.5)
        return cur

    def __getattr__(self, name):
        return getattr(self._c, name)


def _run_with_concurrent_writer(monkeypatch, tmp_path, store, op):
    from contextlib import contextmanager

    other = SynapseStore(store.db_path)
    go, done = threading.Event(), threading.Event()
    errors: list[BaseException] = []

    def writer():
        go.wait(timeout=10)
        try:
            other.reinforce(["concurrent_c", "concurrent_d"])
        except BaseException as exc:  # pragma: no cover - surfaced below
            errors.append(exc)
        finally:
            done.set()

    original = SynapseStore._connect

    @contextmanager
    def patched(self):
        with original(self) as conn:
            yield _CommitAfterFirstRead(conn, go, done) if self is store else conn

    monkeypatch.setattr(SynapseStore, "_connect", patched)
    t = threading.Thread(target=writer)
    t.start()
    try:
        op()
    finally:
        go.set()
        t.join(timeout=30)
        monkeypatch.setattr(SynapseStore, "_connect", original)
    assert not errors, errors
    assert other.neighbors("concurrent_c", namespaces=["personal"])  # writer landed


def test_decay_waits_for_a_concurrent_writer(monkeypatch, tmp_path):
    s = _store(tmp_path)
    s.reinforce(["a", "b"])
    _run_with_concurrent_writer(monkeypatch, tmp_path, s, s.decay)


def test_seed_from_documents_waits_for_a_concurrent_writer(monkeypatch, tmp_path):
    s = _store(tmp_path)
    nodes = [
        _biz_node("decision:exact.20260801", "The audit_log_data function needs updating."),
        _code_node("engine_audit_py__log_fn", "audit_log_data"),
    ]
    result: list[int] = []
    _run_with_concurrent_writer(
        monkeypatch, tmp_path, s, lambda: result.append(s.seed_from_documents(nodes))
    )
    assert result == [1]


def test_normalize_hubs_waits_for_a_concurrent_writer(monkeypatch, tmp_path):
    s = _store(tmp_path)
    for i in range(60):
        s.reinforce(["hub", f"spoke_{i}"], strength=2.0)
    _run_with_concurrent_writer(monkeypatch, tmp_path, s, s.normalize_hubs)
