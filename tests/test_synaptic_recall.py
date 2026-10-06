"""Tests for NeuralMind.synaptic_recall: seeding spreading activation.

Semantic search often matches a ``<id>__rationale`` node (the docstring) best,
but synapses form between code nodes. Recall must seed from the code node the
rationale belongs to, or it recalls nothing for exactly the prompts that match
the code best.
"""

from __future__ import annotations

from types import SimpleNamespace

from neuralmind.core import NeuralMind, _synapse_node
from neuralmind.synapses import SynapseStore


class _Mind:
    """Just what synaptic_recall reads: a store, an embedder, _ensure_built."""

    def __init__(self, store, hits):
        self.synapses = store
        self.embedder = SimpleNamespace(search=lambda query, n: hits)

    def _ensure_built(self):
        pass


def _store(tmp_path) -> SynapseStore:
    store = SynapseStore(tmp_path / "synapses.db")
    store.reinforce(["pkg_mod_py__load_fn", "pkg_mod_py__save_fn"])
    return store


def test_rationale_node_maps_to_its_code_node():
    assert _synapse_node("pkg_mod_py__load_fn__rationale") == "pkg_mod_py__load_fn"
    assert _synapse_node("pkg_mod_py__load_fn") == "pkg_mod_py__load_fn"
    assert _synapse_node("__rationale") == "__rationale"


def test_recall_seeds_from_the_code_node_behind_a_rationale(tmp_path):
    hits = [{"id": "pkg_mod_py__load_fn__rationale", "score": 0.6}]
    ranked, similarity = NeuralMind.synaptic_recall(_Mind(_store(tmp_path), hits), "q")
    assert [node for node, _ in ranked] == ["pkg_mod_py__save_fn"]
    assert similarity == 0.6


def test_a_code_node_and_its_rationale_are_one_seed(tmp_path):
    store = _store(tmp_path)
    hits = [
        {"id": "pkg_mod_py__load_fn", "score": 0.5},
        {"id": "pkg_mod_py__load_fn__rationale", "score": 0.6},
    ]
    ranked, similarity = NeuralMind.synaptic_recall(_Mind(store, hits), "q")
    # The better score seeds once; the two aren't summed.
    assert ranked == store.spread([("pkg_mod_py__load_fn", 0.6)], depth=2, top_k=10)
    assert similarity == 0.6


def test_no_match_recalls_nothing(tmp_path):
    assert NeuralMind.synaptic_recall(_Mind(_store(tmp_path), []), "q") == ([], 0.0)


def test_synaptic_neighbors_is_the_recall_list(tmp_path):
    mind = _Mind(_store(tmp_path), [{"id": "pkg_mod_py__load_fn__rationale", "score": 0.6}])
    mind.synaptic_recall = lambda *a, **k: NeuralMind.synaptic_recall(mind, *a, **k)
    assert NeuralMind.synaptic_neighbors(mind, "q") == NeuralMind.synaptic_recall(mind, "q")[0]
