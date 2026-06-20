"""Opt-in, LLM-judged **answerability** arm for the public benchmark.

The deterministic table scores *gold-file recall* — did the objectively-correct
file land in the assembled context (no LLM, fully reproducible). That measures
**locating**, not **answering**. This arm adds the clearly-labeled *secondary*
signal: given exactly the context a backend would put in the window, can a model
actually answer the question — and is the answer grounded in that context?

How it stays honest (see ``docs/prd/answerability-judge.md``):

- **Each backend is judged on its real window** — whole files for
  ``full-file``/``ripgrep``, retrieved chunks for ``embedding-rag``, the compact
  L0–L3 assembly for ``neuralmind`` (``BackendResult.context_text``). Identical
  answerer + judge prompts and the same pinned model across all backends.
- **The answerer may use only the provided context** and must say so when the
  context is insufficient — so a low-recall window scores low instead of being
  papered over from the model's prior knowledge.
- **Published provenance.** Model id is pinned and printed; the answerer prompt,
  the judge rubric, and every raw transcript are committed under
  ``bench/public/judge/``. A skeptic can re-score or swap the model.
- **Never the headline.** Recall-at-N×-tokens stays primary; this is secondary.

This is a **separate, opt-in arm** (``python -m evals.public.run --judge``); it
needs ``ANTHROPIC_API_KEY`` and fails closed (clean skip) without one, so the
default run and CI never call an external model.
"""

from __future__ import annotations

import json
import os
import statistics
from dataclasses import dataclass, field
from typing import Any

from .backends import BackendResult

# Pin the judge/answerer model so the arm is reproducible and auditable.
JUDGE_MODEL = "claude-opus-4-8"
ANSWERER_MAX_TOKENS = 1024
JUDGE_MAX_TOKENS = 512
# Sentinel the answerer is told to emit when the window can't support an answer.
INSUFFICIENT = "INSUFFICIENT CONTEXT"

ANSWERER_SYSTEM = (
    "You are answering a question about a codebase using ONLY the context "
    "provided in the user message. Do not use any outside knowledge of the "
    "library. If the provided context does not contain enough information to "
    f"answer, reply with exactly '{INSUFFICIENT}' and nothing else. Otherwise "
    "answer concisely (2-4 sentences), naming the specific function, class, or "
    "mechanism in the context that answers the question."
)

JUDGE_SYSTEM = (
    "You are grading whether a candidate answer correctly answers a question "
    "about a codebase. You are given the question, the GOLD anchor (the "
    "definition-site symbol and file that authoritatively answer it), and the "
    "candidate answer. Score correctness against the gold anchor:\n"
    "  2 = correctly identifies the mechanism centered on the gold symbol\n"
    "  1 = partially correct or vague but on the right track\n"
    "  0 = wrong, generic, or declines for insufficient context\n"
    "Also set 'grounded' true only if the answer is specific and consistent "
    "with the gold anchor (not a generic guess). Give a one-sentence rationale."
)

_VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "enum": [0, 1, 2]},
        "grounded": {"type": "boolean"},
        "rationale": {"type": "string"},
    },
    "required": ["score", "grounded", "rationale"],
    "additionalProperties": False,
}


def available() -> bool:
    """True iff the answerability arm can run (key present + SDK importable)."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def make_client() -> Any | None:
    """A pinned Anthropic client, or ``None`` if the arm can't run (fail closed)."""
    if not available():
        return None
    import anthropic

    return anthropic.Anthropic()


def _text_of(response: Any) -> str:
    """First text block of a Messages response (''  on refusal/empty)."""
    if getattr(response, "stop_reason", None) == "refusal":
        return ""
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "text":
            return str(getattr(block, "text", "") or "")
    return ""


@dataclass
class Verdict:
    """The judge's grade of one answer (normalized for aggregation)."""

    answered: bool  # the answerer produced a real answer (not INSUFFICIENT/refusal)
    score: int  # 0/1/2 correctness vs the gold anchor
    grounded: bool
    rationale: str

    @property
    def normalized(self) -> float:
        """Correctness on a 0–1 scale (score / 2)."""
        return self.score / 2.0


def answer_question(client: Any, question: str, context_text: str) -> str:
    """Answer ``question`` from ``context_text`` only (or '' / INSUFFICIENT)."""
    if not context_text.strip():
        return INSUFFICIENT
    resp = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=ANSWERER_MAX_TOKENS,
        thinking={"type": "adaptive"},
        system=ANSWERER_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": f"Question: {question}\n\n--- CONTEXT ---\n{context_text}",
            }
        ],
    )
    return _text_of(resp).strip()


def judge_answer(
    client: Any, question: str, oracle_symbol: str, gold_files: list[str], answer: str
) -> Verdict:
    """Grade ``answer`` against the gold anchor with a structured verdict."""
    answered = bool(answer) and answer.strip().upper() != INSUFFICIENT
    if not answered:
        return Verdict(answered=False, score=0, grounded=False, rationale="insufficient context")
    resp = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=JUDGE_MAX_TOKENS,
        system=JUDGE_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Question: {question}\n"
                    f"GOLD symbol: {oracle_symbol}\n"
                    f"GOLD file(s): {', '.join(gold_files)}\n"
                    f"Candidate answer: {answer}"
                ),
            }
        ],
        output_config={"format": {"type": "json_schema", "schema": _VERDICT_SCHEMA}},
    )
    text = _text_of(resp)
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        # A judge call that didn't return parseable JSON is recorded as a
        # no-score (fail closed), never crashes the arm.
        return Verdict(answered=True, score=0, grounded=False, rationale="unparseable verdict")
    return Verdict(
        answered=True,
        score=int(data.get("score", 0)),
        grounded=bool(data.get("grounded", False)),
        rationale=str(data.get("rationale", "")),
    )


@dataclass
class JudgeArm:
    """Runs the answerability arm over backends and accumulates verdicts + traces."""

    client: Any
    model: str = JUDGE_MODEL
    by_backend: dict[str, list[Verdict]] = field(default_factory=dict)
    raw: list[dict[str, Any]] = field(default_factory=list)

    def judge_query(self, query: dict[str, Any], results: list[BackendResult]) -> None:
        """Answer + grade every backend's window for one query."""
        question = query["question"]
        oracle = query.get("oracle_symbol", "")
        gold = query.get("gold_files", [])
        for r in results:
            answer = answer_question(self.client, question, r.context_text)
            verdict = judge_answer(self.client, question, oracle, gold, answer)
            self.by_backend.setdefault(r.backend, []).append(verdict)
            self.raw.append(
                {
                    "query_id": r.query_id,
                    "backend": r.backend,
                    "question": question,
                    "oracle_symbol": oracle,
                    "gold_files": gold,
                    "context_tokens": r.tokens,
                    "answer": answer,
                    "score": verdict.score,
                    "answered": verdict.answered,
                    "grounded": verdict.grounded,
                    "rationale": verdict.rationale,
                }
            )

    def summary(self) -> dict[str, dict[str, Any]]:
        """Per-backend answerability rollup."""
        out: dict[str, dict[str, Any]] = {}
        for backend, verdicts in self.by_backend.items():
            if not verdicts:
                continue
            n = len(verdicts)
            out[backend] = {
                "n": n,
                "mean_score": round(statistics.mean(v.normalized for v in verdicts), 4),
                "answered_rate": round(sum(v.answered for v in verdicts) / n, 4),
                "grounded_rate": round(sum(v.grounded for v in verdicts) / n, 4),
            }
        return out
