"""Hermetic tests for the opt-in answerability arm (``evals/public/judge.py``).

No network: a fake Anthropic client returns scripted responses, so the answerer
+ judge plumbing, verdict parsing, fail-closed paths, and aggregation are all
exercised without a key or the SDK.
"""

from __future__ import annotations

import json
import types

import pytest

from evals.public import judge
from evals.public.backends import BackendResult


def _block(text: str):
    return types.SimpleNamespace(type="text", text=text)


def _resp(text: str, stop_reason: str = "end_turn"):
    return types.SimpleNamespace(content=[_block(text)], stop_reason=stop_reason)


class FakeClient:
    """Routes by system prompt: answerer vs judge. Records calls."""

    def __init__(self, *, answer="HTTPBasicAuth in auth.py applies it.", verdict=None):
        self._answer = answer
        self._verdict = verdict or {"score": 2, "grounded": True, "rationale": "correct"}
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        system = kwargs.get("system", "")
        if system.startswith("You are answering"):
            return _resp(self._answer)
        return _resp(json.dumps(self._verdict))


def test_answer_question_uses_context():
    client = FakeClient()
    out = judge.answer_question(client, "how is basic auth applied", "class HTTPBasicAuth: ...")
    assert "HTTPBasicAuth" in out
    # answerer call carries adaptive thinking + the pinned model
    call = client.calls[0]
    assert call["model"] == judge.JUDGE_MODEL
    assert call["thinking"] == {"type": "adaptive"}


def test_answer_question_empty_context_is_insufficient_without_call():
    client = FakeClient()
    out = judge.answer_question(client, "q", "   ")
    assert out == judge.INSUFFICIENT
    assert client.calls == []  # never spends a call on an empty window


def test_answer_question_handles_refusal():
    client = FakeClient()
    client.create = lambda **k: _resp("", stop_reason="refusal")  # type: ignore[method-assign]
    assert judge.answer_question(client, "q", "some context") == ""


def test_judge_answer_structured_verdict():
    client = FakeClient(verdict={"score": 2, "grounded": True, "rationale": "names the class"})
    v = judge.judge_answer(client, "q", "class HTTPBasicAuth", ["auth.py"], "It is HTTPBasicAuth.")
    assert v.answered and v.score == 2 and v.grounded
    assert v.normalized == 1.0
    # judge call requests a structured json_schema verdict
    assert client.calls[0]["output_config"]["format"]["type"] == "json_schema"


def test_judge_answer_insufficient_shortcircuits():
    client = FakeClient()
    v = judge.judge_answer(client, "q", "sym", ["f.py"], judge.INSUFFICIENT)
    assert not v.answered and v.score == 0 and not v.grounded
    assert client.calls == []  # no judge call when the answerer declined


def test_judge_answer_unparseable_fails_closed():
    client = FakeClient()
    client.create = lambda **k: _resp("not json")  # type: ignore[method-assign]
    v = judge.judge_answer(client, "q", "sym", ["f.py"], "a real answer")
    assert v.answered and v.score == 0 and not v.grounded


def test_judge_arm_aggregates_per_backend():
    client = FakeClient(verdict={"score": 2, "grounded": True, "rationale": "ok"})
    arm = judge.JudgeArm(client)
    query = {"question": "q", "oracle_symbol": "class HTTPBasicAuth", "gold_files": ["auth.py"]}
    results = [
        BackendResult("neuralmind", "q1", ["auth.py"], ["auth.py"], 100, context_text="ctx"),
        BackendResult("ripgrep", "q1", ["auth.py"], [], 0, context_text=""),  # empty window
    ]
    arm.judge_query(query, results)
    summary = arm.summary()
    assert summary["neuralmind"]["mean_score"] == 1.0
    assert summary["neuralmind"]["answered_rate"] == 1.0
    # empty-window backend scores 0 / not answered (recall→answer gap shows up)
    assert summary["ripgrep"]["answered_rate"] == 0.0
    assert summary["ripgrep"]["mean_score"] == 0.0
    # raw transcripts captured for both backends
    assert {r["backend"] for r in arm.raw} == {"neuralmind", "ripgrep"}


def test_available_false_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert judge.available() is False
    assert judge.make_client() is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
