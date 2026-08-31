"""Displacement must not spend both slots on one module.

Regression cover for the bimodality tracked through PR #484 and #492, and for
the product defect underneath it.

``_apply_synapse_boost`` and ``_apply_structural_expansion`` are budget-neutral:
recalled neighbours take the slots of existing hits rather than adding to them.
They used to take those slots from the plain tail of the ranked list, which has
two problems.

The product problem: when several hits come from the same file, tail-drop can
evict a module's only representatives while keeping two of another's. The
context loses a whole file and gains nothing. On the ``refund`` fixture query
that is exactly what happened — two api/routes.py rows survived and both
billing/stripe_client.py rows were dropped, so the query lost its single
expected module and scored 0.0.

The determinism problem follows from it: which pair sat in the tail depended on
a ~0.8% score difference that varies by host, so the same commit measured
-1.75 points on AVX-512 runners and +3.5 on others, bit-stably, for months.

``_displace`` prefers a victim whose module another survivor still covers. That
makes the surviving *module set* independent of orderings within a module, which
is what the host-dependent scores were perturbing.

Stdlib-only by design: ``context_selector`` imports cleanly without ChromaDB or
numpy, so this keeps running in the dependency-light test job.
"""

from __future__ import annotations

from neuralmind.context_selector import _COVERAGE_MARGIN, _displace, _module_of


def _hit(node_id, module, score):
    return {"id": node_id, "score": score, "metadata": {"source_file": module}}


def _modules(results):
    return sorted({_module_of(r) for r in results})


# The four L3 hits for `refund`, as measured. Two files, two rows each.
def _refund_hits(avx512: bool):
    """The same four hits as scored on each host class.

    Not invented: these are the values recorded in graph.refund_decision_probe
    on a failing and a passing CI job.
    """
    if avx512:
        return [
            _hit("api_routes_rationale_86", "api/routes.py", 1.000000000000),
            _hit("api_routes_refund_endpoint", "api/routes.py", 0.948110951698),
            _hit("billing_stripe_client_rationale_44", "billing/stripe_client.py", 0.946987863624),
            _hit("billing_stripe_client_rationale_132", "billing/stripe_client.py", 0.946315287017),
        ]
    return [
        _hit("api_routes_rationale_86", "api/routes.py", 1.000000000000),
        _hit("billing_stripe_client_rationale_44", "billing/stripe_client.py", 0.954859847106),
        _hit("billing_stripe_client_rationale_132", "billing/stripe_client.py", 0.946315287017),
        _hit("api_routes_refund_endpoint", "api/routes.py", 0.940238968216),
    ]


def test_refund_keeps_its_expected_module_on_the_host_that_used_to_fail():
    """The AVX-512 ordering must not evict billing/stripe_client.py.

    Tail-drop kept results[:2] here — both api/routes.py — which is how the
    query scored 0.0 despite the expected module being present in the hits.
    """
    kept, dropped = _displace(_refund_hits(avx512=True), 2)
    assert len(kept) == 2 and len(dropped) == 2
    assert "billing/stripe_client.py" in _modules(
        kept
    ), f"expected module evicted; kept {[r['id'] for r in kept]}"


def test_both_host_orderings_keep_the_same_modules():
    """The surviving module set must not depend on the host's scores.

    This is the bimodality itself. Both lists hold the same four nodes; only
    the scores differ, by ~0.8% — far too small to be a ranking signal and far
    too large for a tie-break to absorb.
    """
    kept_avx, _ = _displace(_refund_hits(avx512=True), 2)
    kept_other, _ = _displace(_refund_hits(avx512=False), 2)
    assert (
        _modules(kept_avx)
        == _modules(kept_other)
        == [
            "api/routes.py",
            "billing/stripe_client.py",
        ]
    )


def test_tail_drop_would_have_failed_the_case_above():
    """Pin that these fixtures actually discriminate.

    An earlier regression test on this bug passed against the unfixed code and
    so proved nothing. This asserts the old behaviour really does lose the
    module, so the two tests above cannot quietly become vacuous.
    """
    hits = _refund_hits(avx512=True)
    tail_dropped_kept = hits[: len(hits) - 2]
    assert "billing/stripe_client.py" not in _modules(tail_dropped_kept)


def test_all_unique_modules_falls_back_to_weakest_first():
    """With nothing redundant to drop, behaviour is the plain weakest-first."""
    hits = [
        _hit("a", "one.py", 0.9),
        _hit("b", "two.py", 0.5),
        _hit("c", "three.py", 0.1),
    ]
    kept, dropped = _displace(hits, 1)
    assert [r["id"] for r in dropped] == ["c"]
    assert [r["id"] for r in kept] == ["a", "b"]


def test_kept_preserves_input_order():
    """Callers concatenate kept + fetched, so ranking order must survive."""
    hits = [
        _hit("a", "one.py", 0.900),
        _hit("b", "one.py", 0.702),
        _hit("c", "two.py", 0.700),
    ]
    kept, _ = _displace(hits, 1)
    assert [r["id"] for r in kept] == ["a", "c"]


def test_a_materially_better_hit_is_not_sacrificed_for_coverage():
    """Coverage only decides inside the band where ranking cannot separate.

    Here the redundant hit scores 0.8 against the unique hit's 0.7 — well
    outside the margin — so the score is real signal and stands. Dropping it
    to keep one more file costs more facts than the file is worth: measured,
    an unbounded coverage preference took the parity gate's faithfulness delta
    from +0.041 to -0.006 and failed its floor.
    """
    hits = [
        _hit("a", "one.py", 0.9),
        _hit("b", "one.py", 0.8),
        _hit("c", "two.py", 0.7),
    ]
    kept, dropped = _displace(hits, 1)
    assert [r["id"] for r in dropped] == ["c"]
    assert [r["id"] for r in kept] == ["a", "b"]


def test_margin_is_wide_enough_for_host_variance_and_no_wider():
    """Guard the constant against being tuned into either uselessness.

    Below the ~0.8% host-to-host score variation it stops curing the
    bimodality; far above it, coverage starts overriding real ranking signal
    and fact coverage regresses.
    """
    assert 0.01 <= _COVERAGE_MARGIN <= 0.05


def test_equal_scores_break_on_id_not_input_order():
    """Two equally-weak redundant rows resolve the same way either way round."""
    forward = [
        _hit("keep", "one.py", 0.9),
        _hit("zeta", "dup.py", 0.5),
        _hit("alpha", "dup.py", 0.5),
    ]
    a, _ = _displace(forward, 1)
    b, _ = _displace(list(reversed(forward)), 1)
    assert sorted(r["id"] for r in a) == sorted(r["id"] for r in b)


def test_drop_count_is_honoured_and_never_negative():
    """Budget neutrality: exactly drop_count go, and a zero/negative is a no-op."""
    hits = [_hit(str(i), f"m{i % 2}.py", 1.0 - i / 10) for i in range(5)]
    for n in (0, -3):
        kept, dropped = _displace(hits, n)
        assert len(kept) == 5 and dropped == []
    kept, dropped = _displace(hits, 3)
    assert len(kept) == 2 and len(dropped) == 3


def test_missing_metadata_degrades_instead_of_raising():
    """A malformed row must not take down context assembly."""
    hits = [{"id": "a", "score": 0.9}, {"id": "b", "score": 0.1}, {"score": 0.5}]
    kept, dropped = _displace(hits, 1)
    assert len(kept) == 2 and len(dropped) == 1
