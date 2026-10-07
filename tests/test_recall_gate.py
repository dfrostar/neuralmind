"""The recall_gate calibration harness compares what the hook compares."""

from __future__ import annotations

import neuralmind.core as core
from tests.benchmark import recall_gate


class _FakeMind:
    def __init__(self, project):
        pass

    def _load_existing_index(self):
        return True

    def synaptic_recall(self, prompt, depth=2, top_k=8):
        # Just under the default 0.35: rounding to 4 places would read 0.35.
        return [("node", 1.0)], 0.34996


def test_the_sweep_uses_the_raw_similarity(monkeypatch):
    monkeypatch.setenv("NEURALMIND_NO_LEARN", "0")
    monkeypatch.setattr(core, "NeuralMind", _FakeMind)
    report = recall_gate.measure(".", ["on topic"], ["off topic"])
    at_035 = next(s for s in report["sweep"] if s["threshold"] == 0.35)
    # The hook abstains below 0.35, so the harness mustn't count it as kept.
    assert at_035["on_topic_kept"] == 0
    assert at_035["off_topic_passed"] == 0
    assert report["rows"][0]["similarity"] == 0.34996


class _NothingToName(_FakeMind):
    def synaptic_recall(self, prompt, depth=2, top_k=8):
        # A strong match, but no synapse edges around it: the hook adds nothing.
        return [], 0.6


def test_the_sweep_counts_only_prompts_that_get_a_block(monkeypatch):
    monkeypatch.setenv("NEURALMIND_NO_LEARN", "0")
    monkeypatch.setattr(core, "NeuralMind", _NothingToName)
    report = recall_gate.measure(".", ["on topic"], ["off topic"])
    assert all(s["on_topic_kept"] == 0 and s["off_topic_passed"] == 0 for s in report["sweep"])
