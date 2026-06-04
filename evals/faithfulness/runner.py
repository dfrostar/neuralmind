"""Faithfulness eval runner — E1.1 foundation skeleton.

Pure standard library at import time: NO chromadb / graphify / neuralmind
imports at module load, so this file loads and is unit-testable in a
minimal environment. Heavy machinery (the real answerer wired to
``neuralmind.core``) is imported lazily inside the functions that need it
once E1.2 lands.

What this module ships today (E1.1):
  * ``load_query_set`` — parse + lightly validate ``queries.json``.
  * ``OfflineJudge.fact_recall`` — the offline, zero-network
    expected-fact-recall scorer. This is the default, CI-gating signal.

What is intentionally left as TODO (later tasks of issue #172):
  * E1.2 — answer generation (with-NeuralMind vs naive baseline).
  * E1.3 — grounding-rate + contradiction scoring, and the opt-in
    LLM-as-judge behind ``NEURALMIND_EVAL_LLM_JUDGE``.
  * E1.4 — the ``neuralmind eval`` report (delta, per-query breakdown, JSON).

See ``schema.md`` for the data contract and ``README.md`` for the design
(offline judge = default + gate; API judge = opt-in, labelled as leaving
the machine).
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_VERSION = 1

# Opt-in, never the default and never the CI gate. Documented in README.md.
LLM_JUDGE_ENV = "NEURALMIND_EVAL_LLM_JUDGE"

_QUERIES_PATH = Path(__file__).resolve().parent / "queries.json"

_WORD_RE = re.compile(r"[a-z0-9]+")


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ExpectedFact:
    """A single checkable claim a correct answer must contain."""

    id: str
    fact: str
    aliases: tuple[str, ...] = ()

    def surfaces(self) -> tuple[str, ...]:
        """All strings that count as expressing this fact."""
        return (self.fact, *self.aliases)


@dataclass(frozen=True)
class Query:
    """One eval query with its rubric of expected facts."""

    id: str
    question: str
    expected_facts: tuple[ExpectedFact, ...]
    expected_modules: tuple[str, ...] = ()
    shape: str = ""


@dataclass
class QuerySet:
    """The loaded, validated query set."""

    schema_version: int
    fixture: str
    queries: list[Query] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.queries)


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def load_query_set(path: str | os.PathLike[str] | None = None) -> QuerySet:
    """Load and validate ``queries.json``.

    Raises ``ValueError`` on a malformed file or an unsupported
    ``schema_version`` so a bad gold set fails loudly rather than silently
    scoring against nothing.
    """
    p = Path(path) if path is not None else _QUERIES_PATH
    raw = json.loads(p.read_text(encoding="utf-8"))

    version = raw.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version {version!r}; runner expects {SCHEMA_VERSION}")

    queries: list[Query] = []
    seen_ids: set[str] = set()
    for entry in raw.get("queries", []):
        qid = entry["id"]
        if qid in seen_ids:
            raise ValueError(f"duplicate query id: {qid!r}")
        seen_ids.add(qid)

        facts: list[ExpectedFact] = []
        for f in entry.get("expected_facts", []):
            facts.append(
                ExpectedFact(
                    id=f["id"],
                    fact=f["fact"],
                    aliases=tuple(f.get("aliases", [])),
                )
            )
        if not facts:
            raise ValueError(f"query {qid!r} has no expected_facts")

        queries.append(
            Query(
                id=qid,
                question=entry["question"],
                expected_facts=tuple(facts),
                expected_modules=tuple(entry.get("expected_modules", [])),
                shape=entry.get("shape", ""),
            )
        )

    if not queries:
        raise ValueError("query set is empty")

    return QuerySet(
        schema_version=version,
        fixture=raw.get("fixture", ""),
        queries=queries,
    )


# --------------------------------------------------------------------------- #
# Scoring interface
# --------------------------------------------------------------------------- #
def _normalize(text: str) -> str:
    """Lowercase + collapse non-alphanumerics to single spaces.

    Makes substring matching robust to punctuation/casing/whitespace so a
    fact like ``hmac.compare_digest`` matches an answer that writes
    ``hmac compare digest`` or ``HMAC.compare_digest()``.
    """
    return " ".join(_WORD_RE.findall(text.lower()))


@dataclass
class FactResult:
    fact_id: str
    matched: bool
    matched_on: str = ""


@dataclass
class RecallResult:
    """Per-query expected-fact-recall outcome."""

    query_id: str
    matched: int
    total: int
    facts: list[FactResult] = field(default_factory=list)

    @property
    def recall(self) -> float:
        return self.matched / self.total if self.total else 0.0


class OfflineJudge:
    """Zero-network heuristic judge — the default and CI-gating signal.

    E1.1 implements expected-fact recall. Grounding-rate and contradiction
    scoring are E1.3 (stubbed below). This judge NEVER makes a network
    call; the opt-in LLM-as-judge (``NEURALMIND_EVAL_LLM_JUDGE``) is a
    separate path added in E1.3.
    """

    def fact_matched(self, fact: ExpectedFact, answer_norm: str) -> FactResult:
        """Does ``answer_norm`` (already normalized) express ``fact``?"""
        for surface in fact.surfaces():
            needle = _normalize(surface)
            if needle and needle in answer_norm:
                return FactResult(fact.id, matched=True, matched_on=surface)
        return FactResult(fact.id, matched=False)

    def fact_recall(self, query: Query, answer: str) -> RecallResult:
        """Fraction of ``query``'s expected facts present in ``answer``."""
        answer_norm = _normalize(answer)
        results = [self.fact_matched(f, answer_norm) for f in query.expected_facts]
        matched = sum(1 for r in results if r.matched)
        return RecallResult(
            query_id=query.id,
            matched=matched,
            total=len(query.expected_facts),
            facts=results,
        )

    def mean_recall(self, pairs: Iterable[tuple[Query, str]]) -> float:
        """Mean per-query fact recall over (query, answer) pairs."""
        results = [self.fact_recall(q, a) for q, a in pairs]
        if not results:
            return 0.0
        return sum(r.recall for r in results) / len(results)

    # -- E1.3 TODOs ------------------------------------------------------- #
    def grounding_rate(self, query: Query, answer: str) -> float:
        """TODO(E1.3): fraction of answer claims attributable to
        ``query.expected_modules`` / retrieved context. Zero-network."""
        raise NotImplementedError("grounding_rate lands in E1.3")

    def contradiction_score(self, query: Query, answer: str) -> float:
        """TODO(E1.3): detect statements that conflict with the gold facts
        (e.g. PostgreSQL vs SQLite, RS256 vs HS256). Zero-network."""
        raise NotImplementedError("contradiction_score lands in E1.3")


# --------------------------------------------------------------------------- #
# Answer generation — E1.2 TODO
# --------------------------------------------------------------------------- #
def generate_answer(query: Query, *, with_context: bool) -> str:  # noqa: ARG001
    """TODO(E1.2): produce an answer for ``query``.

    ``with_context=True`` should answer using NeuralMind-selected context
    (lazy-import ``neuralmind.core`` here, NOT at module top, to keep this
    file importable without heavy deps). ``with_context=False`` is the
    naive baseline. Must be deterministic given a fixed answerer.
    """
    raise NotImplementedError("answer generation lands in E1.2")


def _llm_judge_enabled() -> bool:
    """Opt-in only. Never the default, never the CI gate (E1.3)."""
    return os.environ.get(LLM_JUDGE_ENV, "") not in ("", "0", "false", "False")


# --------------------------------------------------------------------------- #
# CLI entry — selfcheck today; full report is E1.4
# --------------------------------------------------------------------------- #
def _selfcheck() -> int:
    """Load the query set and sanity-check the offline scorer end to end.

    No network, no heavy deps. Lets CI confirm the gold set parses and the
    recall scorer behaves before E1.2/E1.4 wire up real answers.
    """
    qs = load_query_set()
    print(f"loaded query set: schema v{qs.schema_version}, {len(qs)} queries")
    print(f"fixture: {qs.fixture}")

    judge = OfflineJudge()
    total_facts = 0
    for q in qs.queries:
        total_facts += len(q.expected_facts)
        # A "perfect" answer that names every fact should score recall 1.0.
        perfect = " ".join(f.fact for f in q.expected_facts)
        r = judge.fact_recall(q, perfect)
        status = "ok" if r.recall == 1.0 else "WARN"
        print(f"  [{status}] {q.id}: {r.matched}/{r.total} facts on a perfect answer")
        if r.recall != 1.0:
            return 1

    # An empty answer must score 0 everywhere.
    empty_mean = judge.mean_recall((q, "") for q in qs.queries)
    print(f"total expected facts: {total_facts}")
    print(f"mean recall on empty answers: {empty_mean:.3f} (expected 0.000)")
    return 0 if empty_mean == 0.0 else 1


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--selfcheck" in argv:
        return _selfcheck()

    if _llm_judge_enabled():
        # Honest, loud notice — answers + gold facts would leave the machine.
        print(
            f"[{LLM_JUDGE_ENV}=on] LLM-as-judge mode requested: answers and gold "
            "facts would be sent to a third-party API (NOT local).",
            file=sys.stderr,
        )

    # The full report (answer A/B + delta + per-query breakdown + --json)
    # is E1.4. Until then, point the user at the selfcheck.
    print("Faithfulness eval (E1.1 skeleton).")
    print("Answer generation (E1.2) and the report (E1.4) are not implemented yet.")
    print("Run with --selfcheck to validate the gold set + offline scorer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
