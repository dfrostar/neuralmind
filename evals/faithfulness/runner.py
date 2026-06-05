"""Faithfulness eval runner — gold-fact dataset + offline judge.

Pure standard library at import time: NO chromadb / graphify / neuralmind
imports at module load, so this file loads and is unit-testable in a
minimal environment. The heavy A/B machinery (the real answerer wired to
``neuralmind.core``) lives in ``harness.py`` and is imported lazily by the
``--run`` path.

What this module ships:
  * ``load_query_set`` — parse + lightly validate ``queries.json``.
  * ``OfflineJudge`` — the offline, zero-network judge. Three dimensions:
    ``fact_recall`` (the headline + CI-gating signal), ``grounding_rate``,
    and ``contradiction_score``. None of them make a network call.
  * CLI: ``--selfcheck`` (dependency-free gate) and ``--run`` (the
    with-NeuralMind vs matched-budget-naive faithfulness A/B + report;
    ``--json`` for machines), which delegates to ``harness.py``.

The opt-in LLM-as-judge (``NEURALMIND_EVAL_LLM_JUDGE``) is the only path
that would leave the machine, and is never the default or the CI gate.

See ``schema.md`` for the data contract and ``README.md`` for the design.
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

    fixture = raw.get("fixture")
    if not isinstance(fixture, str) or not fixture.strip():
        raise ValueError(
            "query set is missing a non-empty 'fixture' (path to the gold-fact source)"
        )

    raw_queries = raw.get("queries")
    if not isinstance(raw_queries, list):
        raise ValueError("'queries' must be a list")

    queries: list[Query] = []
    seen_ids: set[str] = set()
    for i, entry in enumerate(raw_queries):
        if not isinstance(entry, dict):
            raise ValueError(f"queries[{i}] must be an object, got {type(entry).__name__}")

        qid = entry.get("id")
        if not isinstance(qid, str) or not qid.strip():
            raise ValueError(f"queries[{i}] is missing a non-empty string 'id'")
        if qid in seen_ids:
            raise ValueError(f"duplicate query id: {qid!r}")
        seen_ids.add(qid)

        question = entry.get("question")
        if not isinstance(question, str) or not question.strip():
            raise ValueError(f"query {qid!r} is missing a non-empty 'question'")

        modules = entry.get("expected_modules")
        if not isinstance(modules, list) or not modules:
            raise ValueError(f"query {qid!r} needs a non-empty 'expected_modules' list")
        for m in modules:
            if not isinstance(m, str) or not m.strip():
                raise ValueError(
                    f"query {qid!r} has a non-string/empty entry in 'expected_modules'"
                )

        facts: list[ExpectedFact] = []
        seen_fact_ids: set[str] = set()
        for f in entry.get("expected_facts", []):
            if not isinstance(f, dict):
                raise ValueError(f"query {qid!r} has a non-object entry in 'expected_facts'")
            fid = f.get("id")
            ftext = f.get("fact")
            if not isinstance(fid, str) or not fid.strip():
                raise ValueError(f"query {qid!r} has an expected_fact missing a non-empty 'id'")
            if fid in seen_fact_ids:
                raise ValueError(f"duplicate expected_fact id {fid!r} in query {qid!r}")
            seen_fact_ids.add(fid)
            if not isinstance(ftext, str) or not ftext.strip():
                raise ValueError(f"fact {fid!r} in query {qid!r} is missing non-empty 'fact' text")
            # 'aliases' must be a list of non-empty strings. A bare string here
            # would otherwise be silently exploded into per-character aliases
            # (tuple("postgres") -> 'p','o','s',...), corrupting recall scoring.
            aliases = f.get("aliases", [])
            if not isinstance(aliases, list):
                raise ValueError(
                    f"fact {fid!r} in query {qid!r}: 'aliases' must be a list of strings, "
                    f"got {type(aliases).__name__}"
                )
            for a in aliases:
                if not isinstance(a, str) or not a.strip():
                    raise ValueError(f"fact {fid!r} in query {qid!r} has a non-string/empty alias")
            facts.append(ExpectedFact(id=fid, fact=ftext, aliases=tuple(aliases)))
        if not facts:
            raise ValueError(f"query {qid!r} has no expected_facts")

        queries.append(
            Query(
                id=qid,
                question=question,
                expected_facts=tuple(facts),
                expected_modules=tuple(modules),
                shape=entry.get("shape", ""),
            )
        )

    if not queries:
        raise ValueError("query set is empty")

    return QuerySet(
        schema_version=version,
        fixture=fixture,
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


def _phrase_in(answer_norm: str, needle_norm: str) -> bool:
    """Whole-word/phrase containment over already-normalized token strings.

    Both arguments are space-delimited normalized tokens. Padding with
    spaces makes the check token-boundary aware so a short needle like
    ``id`` or ``t`` can't match *inside* an unrelated word (``valid``,
    ``not``) and silently inflate the CI-gating recall score. Multi-word
    needles still match as a contiguous phrase.
    """
    if not needle_norm:
        return False
    return f" {needle_norm} " in f" {answer_norm} "


def _module_cited(module: str, answer: str) -> bool:
    """Is ``module`` (a fixture-relative path like ``auth/handlers.py``)
    referenced in ``answer``? Matches the full path or a distinctive basename."""
    a = answer.lower()
    m = module.lower()
    if m in a:
        return True
    base = m.rsplit("/", 1)[-1]
    return len(base) > 3 and base in a


# Mutually-exclusive technical choices in the fixture domain. Each group is a
# set of competing *choices*; each choice is one or more synonymous surface
# tokens (matched as whole words). If a query's gold facts pick exactly one
# choice and the answer asserts a *different* choice, that's a contradiction.
# Conservative on purpose — only well-known, unambiguous pairs, so the CI gate
# isn't tripped by false positives. Synonyms within a choice (postgres ==
# postgresql) never conflict with each other.
_CONTRADICTION_GROUPS: tuple[tuple[tuple[str, ...], ...], ...] = (
    # Primary persistence engine. Redis is deliberately excluded: it's
    # typically a cache *alongside* the primary store, not a competing choice,
    # so "sqlite + a redis cache" must not read as a contradiction.
    (("sqlite",), ("postgresql", "postgres"), ("mysql",), ("mongodb",)),
    (("hs256",), ("rs256",), ("es256",)),
    (("symmetric",), ("asymmetric",)),
    (("bcrypt",), ("scrypt",), ("argon2",), ("pbkdf2",)),
)


def _choice_present(text_norm: str, choice: tuple[str, ...]) -> bool:
    """Is any synonym of ``choice`` present in the normalized text (whole-word)?"""
    return any(_phrase_in(text_norm, _normalize(tok)) for tok in choice)


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
        """Does ``answer_norm`` (already normalized) express ``fact``?

        Matching is token/phrase-boundary aware (see ``_phrase_in``) and
        rejects needles that collapse to a single ultra-short token (e.g.
        an alias like ``t=`` → ``t``), which are too noisy to trust as the
        CI-gating recall signal.
        """
        for surface in fact.surfaces():
            needle = _normalize(surface)
            if not needle:
                continue
            tokens = needle.split()
            if len(tokens) == 1 and len(tokens[0]) < 2:
                continue
            if _phrase_in(answer_norm, needle):
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

    def grounding_rate(self, query: Query, answer: str) -> float:
        """Fraction of the query's ``expected_modules`` referenced in ``answer``.

        An offline proxy for "is the answer drawn from the right sources?": the
        deterministic answer is the selected context, which labels each snippet
        with its file path, so this measures whether the gold modules actually
        made it into the context. Zero-network.
        """
        modules = query.expected_modules
        if not modules:
            return 0.0
        cited = sum(1 for m in modules if _module_cited(m, answer))
        return cited / len(modules)

    def contradiction_score(self, query: Query, answer: str) -> float:
        """Rate of statements in ``answer`` that conflict with the gold facts.

        Conservative and offline: for each group of mutually-exclusive choices
        (e.g. SQLite vs PostgreSQL, HS256 vs RS256), if the gold facts pick
        exactly one side and the answer asserts a *different* side, that's a
        contradiction. Returns contradictions / applicable-groups — ``0.0``
        means none detected (lower is better).
        """
        gold_norm = _normalize(" ".join(s for f in query.expected_facts for s in f.surfaces()))
        answer_norm = _normalize(answer)
        applicable = 0
        contradicted = 0
        for group in _CONTRADICTION_GROUPS:
            gold_choices = [c for c in group if _choice_present(gold_norm, c)]
            if len(gold_choices) != 1:
                continue  # group not unambiguously relevant to this query
            applicable += 1
            gold_choice = gold_choices[0]
            if any(_choice_present(answer_norm, c) for c in group if c is not gold_choice):
                contradicted += 1
        return contradicted / applicable if applicable else 0.0


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


def _arg_value(argv: list[str], flag: str) -> str | None:
    """Return the value following ``flag`` in ``argv``, or None."""
    if flag in argv:
        i = argv.index(flag)
        if i + 1 < len(argv):
            return argv[i + 1]
    return None


def _run(argv: list[str]) -> int:
    """Run the faithfulness A/B and print the report (E1.2 + E1.4).

    Requires the retrieval stack (chromadb) and a built index for the fixture;
    degrades with a clear, actionable message when they're absent so a minimal
    environment falls back to ``--selfcheck`` instead of crashing.
    """
    if _llm_judge_enabled():
        print(
            f"[{LLM_JUDGE_ENV}=on] LLM-as-judge mode requested: answers and gold "
            "facts would be sent to a third-party API (NOT local). The offline "
            "judge remains the default and the gate.",
            file=sys.stderr,
        )
    try:
        from . import harness
    except ImportError:
        # Allow running as a plain script (python evals/faithfulness/runner.py):
        # put the repo root on the path and import the package absolutely.
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from evals.faithfulness import harness  # type: ignore[no-redef]

    try:
        report = harness.run_and_report(_arg_value(argv, "--project"))
    except RuntimeError as exc:
        print(f"faithfulness A/B unavailable: {exc}", file=sys.stderr)
        print(
            "Run with --selfcheck to validate the gold set + offline scorer "
            "without the retrieval stack.",
            file=sys.stderr,
        )
        return 2
    print(harness.render_json(report) if "--json" in argv else harness.render_markdown(report))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--selfcheck" in argv:
        return _selfcheck()
    if "--run" in argv:
        return _run(argv)

    print("Faithfulness eval. Usage:")
    print("  --selfcheck            validate the gold set + offline scorer (no deps)")
    print("  --run [--project P]    run the with-NeuralMind vs naive A/B + report")
    print("  --run --json           emit the report as JSON")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
