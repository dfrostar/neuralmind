"""Displacement must evict the results the admission test approved.

`_apply_synapse_boost` is budget-neutral: to surface a co-activated node it
has to drop a vector hit. Which hit it drops is the whole game — evicting a
stronger result to make room for a weaker recall is exactly what regresses
top-k hit rate, and it is what the admission test exists to prevent.

The subtle failure is not in the test but in what happens after it: once any
candidate is rejected, the survivors are no longer a suffix of `results`, so
trimming a blind suffix evicts the wrong rows — dropping a result the
admission test just protected while keeping one it cleared for displacement.

Stdlib-only, like the rest of the synapse layer's tests.
"""

from __future__ import annotations

from neuralmind.context_selector import ContextSelector


class _StubEmbedder:
    def get_nodes_by_ids(self, ids: list[str]) -> list[dict]:
        return [{"id": i} for i in ids]


def _selector(energy: dict[str, float]) -> ContextSelector:
    sel = object.__new__(ContextSelector)
    sel._synapse_boost_weight = 1.0
    sel._synapse_pull_in_max = 5
    sel._synapse_pull_in_min_energy = 0.0
    sel._synapse_seed_k = 1
    sel._trace = None
    sel._synapse_disabled = lambda: False
    sel._recall_energy = lambda seeds: dict(energy)
    sel.embedder = _StubEmbedder()
    return sel


def test_rejected_pair_does_not_evict_the_result_it_protected() -> None:
    # One strong candidate (0.95) and one weak (0.10). The weak one cannot
    # outrank the 0.50 result, so that result must survive; the 0.20 result is
    # the one cleared for displacement.
    sel = _selector({"strong": 0.95, "weak": 0.10})
    results = [
        {"id": "top", "score": 0.90},
        {"id": "expendable", "score": 0.20},
        {"id": "gold", "score": 0.50},
    ]

    kept = {r["id"] for r in sel._apply_synapse_boost(results)}

    assert "gold" in kept, (
        "displacement evicted a result the admission test protected: 'gold' "
        "(0.50) outranks every rejected candidate, so it must survive."
    )
    assert "expendable" not in kept, (
        "displacement kept the result it had cleared for eviction: "
        "'expendable' (0.20) is what the strong candidate was admitted against."
    )


def test_no_admissible_candidate_leaves_results_untouched() -> None:
    # Every candidate is weaker than every result it could replace.
    sel = _selector({"weak_a": 0.01, "weak_b": 0.02})
    results = [
        {"id": "a", "score": 0.90},
        {"id": "b", "score": 0.80},
        {"id": "c", "score": 0.70},
    ]

    out = sel._apply_synapse_boost(results)

    assert [r["id"] for r in out] == ["a", "b", "c"]
    assert not any(r.get("_synapse_recalled") for r in out)


def test_displacement_is_budget_neutral() -> None:
    # The count must not grow: this is what keeps the token budget fixed.
    sel = _selector({"strong_a": 0.99, "strong_b": 0.98})
    results = [
        {"id": "a", "score": 0.90},
        {"id": "b", "score": 0.10},
        {"id": "c", "score": 0.05},
    ]

    out = sel._apply_synapse_boost(results)

    assert len(out) == len(results)
    # The strongest vector hit is never displaced.
    assert "a" in {r["id"] for r in out}
