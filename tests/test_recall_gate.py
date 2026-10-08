"""The recall_gate calibration harness compares what the hook compares."""

from __future__ import annotations

from types import SimpleNamespace

import neuralmind.core as core
import neuralmind.prompt_recall as prompt_recall
from tests.benchmark import recall_gate


class _FakeMind:
    def __init__(self, project):
        pass

    def _load_existing_index(self):
        return True


def test_the_sweep_uses_the_raw_similarity(monkeypatch):
    monkeypatch.setenv("NEURALMIND_NO_LEARN", "0")
    monkeypatch.setattr(core, "NeuralMind", _FakeMind)
    # Just under the default 0.35: rounding to 4 places would read 0.35.
    monkeypatch.setattr(
        prompt_recall, "recall", lambda mind, prompt: SimpleNamespace(similarity=0.34996, count=1)
    )
    report = recall_gate.measure(".", ["on topic"], ["off topic"])
    at_035 = next(s for s in report["sweep"] if s["threshold"] == 0.35)
    # The hook abstains below 0.35, so the harness mustn't count it as kept.
    assert at_035["on_topic_kept"] == 0
    assert at_035["off_topic_passed"] == 0
    assert report["rows"][0]["similarity"] == 0.34996


def test_the_sweep_counts_only_prompts_that_get_a_block(monkeypatch):
    monkeypatch.setenv("NEURALMIND_NO_LEARN", "0")
    monkeypatch.setattr(core, "NeuralMind", _FakeMind)
    # A strong match with nothing to name: format_block, and so the hook, adds nothing.
    monkeypatch.setattr(
        prompt_recall, "recall", lambda mind, prompt: SimpleNamespace(similarity=0.6, count=0)
    )
    report = recall_gate.measure(".", ["on topic"], ["off topic"])
    assert all(s["on_topic_kept"] == 0 and s["off_topic_passed"] == 0 for s in report["sweep"])
