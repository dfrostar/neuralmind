"""Ranking order must be a function of the data, not of the host.

Regression cover for the bimodality tracked in PR #484. The self-benchmark's
synapse gate failed on roughly one CI run in four, always by the same 5.26
points, on byte-identical code. What the artifacts eventually showed:

- ``graph.embedding_probe_sha256_16`` was IDENTICAL between passing and
  failing runs, so the embeddings were bit-identical and the embedding path
  was not the variable.
- ``cpu_count`` was 4 on both sides, retiring core count as the suspect.
- The vector-only baseline (``off_queries``) was identical on all 19 fixture
  queries.
- Exactly one query differed with synapse recall on: ``refund`` lost its one
  expected module, ``billing/stripe_client.py``, from the kept results.
  One query of nineteen flipping 1.0 -> 0.0 is 100/19 = 5.26 points, which is
  precisely the gap between the two observed modes.

The mechanism is that ``_apply_synapse_recall`` re-sorts the kept results by
boosted score and then drops the tail to stay inside a fixed displacement
budget. Sorting on a raw float lets a last-bit difference decide which node
falls off the end, and that difference varied by runner.

These tests pin the ordering contract itself rather than the benchmark
outcome, so a regression shows up here — deterministically, on any machine —
instead of as an intermittent red on an unrelated PR.

Stdlib-only by design: ``context_selector`` imports cleanly without ChromaDB
or numpy, and this file must keep running in the dependency-light test job.
"""

from __future__ import annotations

from neuralmind.context_selector import _RANK_QUANTUM, _rank_key


def _order(pairs):
    """Sort ``(node_id, score)`` pairs the way the ranking sites do."""
    return [nid for nid, _ in sorted(pairs, key=lambda x: _rank_key(x[1], x[0]))]


def test_higher_score_still_ranks_first():
    """The tie-break must not disturb genuine score ordering."""
    assert _order([("a", 0.1), ("b", 0.9), ("c", 0.5)]) == ["b", "c", "a"]


def test_ties_resolve_by_node_id_not_input_order():
    """Equal scores order by id, whichever way the input arrives.

    This is the property the old ``reverse=True`` sort lacked: Python's sort
    is stable, so equal scores simply preserved input order, and input order
    was not guaranteed to be the same on every host.
    """
    forward = [("beta", 0.5), ("alpha", 0.5), ("gamma", 0.5)]
    assert _order(forward) == ["alpha", "beta", "gamma"]
    assert _order(list(reversed(forward))) == ["alpha", "beta", "gamma"]


def test_float_noise_below_the_quantum_does_not_reorder():
    """Scores differing only in float noise must not swap places.

    This is the actual #484 failure: two candidates a few ULPs apart, where
    the loser is dropped by the displacement budget. A difference this small
    is not a ranking signal, and treating it as one made the result depend on
    which CPU summed the floats.
    """
    base = 0.7456140350877193
    noisy = base + _RANK_QUANTUM / 1000.0
    assert noisy != base, "test needs two distinct floats to be meaningful"
    # 'zeta' holds the fractionally larger score but must still lose to
    # 'alpha' on the id tie-break, rather than winning on noise.
    assert _order([("zeta", noisy), ("alpha", base)]) == ["alpha", "zeta"]


def test_real_score_difference_above_the_quantum_is_respected():
    """The quantum must not swallow differences that are genuine signal."""
    base = 0.5
    higher = base + _RANK_QUANTUM * 1000.0
    assert _order([("zzz", higher), ("aaa", base)]) == ["zzz", "aaa"]


def test_quantum_is_far_above_float_noise_and_far_below_real_differences():
    """Guard the constant itself against being tuned into uselessness.

    Too small and last-bit noise still reorders; too large and it starts
    merging scores that differ for real reasons.
    """
    assert 1e-12 <= _RANK_QUANTUM <= 1e-6


def test_non_numeric_score_degrades_instead_of_raising():
    """A malformed score must not take down context assembly."""
    assert _order([("a", None), ("b", 1.0)]) == ["b", "a"]
    assert _order([("a", "not-a-number"), ("b", 1.0)]) == ["b", "a"]


def test_missing_node_id_is_ordered_not_fatal():
    """Ties among id-less rows still produce a total order."""
    assert _rank_key(1.0, None) == _rank_key(1.0, "")
    assert _order([("", 0.5), ("a", 0.5)]) == ["", "a"]


def test_refund_case_two_hosts_keep_the_same_nodes():
    """The #484 signature: two hosts, same scores bar noise, same survivors.

    This models the failure as it actually happened. Both hosts see the same
    candidates in the same order; what differed was the last bits of the
    scores, because the summation order behind them was not identical. Under
    a raw float sort that is enough to swap two near-tied nodes, and the loser
    is dropped by the fixed displacement budget — which is how ``refund`` lost
    ``billing/stripe_client.py`` on some runners and not others.

    Note the earlier version of this test permuted the input order instead.
    That version passed against the *old* implementation too, so it proved
    nothing; a regression test that cannot fail on the unfixed code is worse
    than no test, because it reads as cover that is not there.
    """
    keep = 2
    host_a = [
        ("billing/stripe_client.py", 0.61),
        ("users/crud.py", 0.61),
        ("api/routes.py", 0.99),
    ]
    # Same computation on a different CPU: a few ULPs apart, no more.
    host_b = [
        ("billing/stripe_client.py", 0.61 - _RANK_QUANTUM / 500.0),
        ("users/crud.py", 0.61 + _RANK_QUANTUM / 500.0),
        ("api/routes.py", 0.99),
    ]
    kept_a = set(_order(host_a)[:keep])
    kept_b = set(_order(host_b)[:keep])
    assert kept_a == kept_b, (
        "displacement kept different nodes on two hosts whose scores differ "
        f"only by float noise: {sorted(kept_a)} vs {sorted(kept_b)}"
    )
    # And the expected module specifically must survive on both.
    assert "billing/stripe_client.py" in kept_a
    assert "billing/stripe_client.py" in kept_b
