"""RAGAS-axis faithfulness & relevance scoring for the offline judge (PRD 2).

``fact_recall`` / ``contradiction_score`` / ``faithfulness`` are stdlib-only
and run without the embedding stack. ``context_precision`` / ``context_recall``
/ ``answer_relevance`` defer to an injected ``embed_fn`` — when absent or
failing, those columns return ``None`` rather than crashing the pipeline.

Definitions (per-query, against ``gold_facts`` and ``query``/``retrieved``):

- **fact_recall** — fraction of gold facts whose tokens appear in the answer.
  Rejects gold facts shorter than 2 chars as non-informative.
- **contradiction_score** — detects negation-flips (gold says X, answer says
  NOT X) and mutually-exclusive choice violations. Returns 0.0–1.0.
- **faithfulness** — ``fact_recall * (1 - contradiction)``. Always populated
  even without an embedder. Multiplicative so a totally irrelevant answer
  (fact_recall=0) scores 0.0 regardless of contradiction, and a fully recalled
  but fully contradicted answer (contradiction=1) also scores 0.0.
- **context_precision** — fraction of retrieved docs whose embedding cosine
  with the gold-facts centroid is positive. ``None`` without ``embed_fn``.
- **context_recall** — fraction of gold-facts' nearest retrieved doc above a
  relevance threshold. ``None`` without ``embed_fn``.
- **answer_relevance** — cosine between answer embedding and query embedding.
  ``None`` without ``embed_fn``.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Callable


# --------------------------------------------------------------------------- #
# Embedding helpers                                                            #
# --------------------------------------------------------------------------- #


def cosine(a: list[float], b: list[float]) -> float:
    """Pure-python cosine similarity; 0.0 when either vector is zero-length."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a <= 0.0 or mag_b <= 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


def _tok(text: str) -> set[str]:
    """Lowercase alphanumeric tokens from arbitrary text."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


# --------------------------------------------------------------------------- #
# fact_recall                                                                 #
# --------------------------------------------------------------------------- #


def fact_recall(answer: str, gold_facts: Iterable[str], *, aliases: dict[str, list[str]] = {}) -> float:
    """Fraction of *informative* gold facts whose tokens appear in ``answer``.

    A fact is counted as "recalled" if every one of its tokens appears in the
    answer (after lowercasing). Gold facts shorter than 2 chars are rejected as
    non-informative and excluded from both the numerator and denominator.
    ``aliases`` maps a fact-id to extra surface forms so heuristic recall is
    not brittle to exact wording.
    """
    _aliases = aliases or {}
    facts = [f for f in gold_facts if f and len(f.strip()) >= 2]
    if not facts:
        return 0.0
    answer_lower = answer.lower()
    hits = 0
    for fact in facts:
        fact_lower = fact.lower()
        # The fact and every alias must have all their tokens in the answer
        surfaces = [fact_lower] + [a.lower() for a in _aliases.get(fact, [])]
        # Count the fact as recalled if ANY surface form's tokens are present
        ok = False
        for surface in surfaces:
            tokens = _tok(surface)
            if not tokens:
                continue
            if all(tok in answer_lower for tok in tokens):
                ok = True
                break
        if ok:
            hits += 1
    return hits / len(facts)


# --------------------------------------------------------------------------- #
# contradiction_score                                                         #
# --------------------------------------------------------------------------- #


# Negation cue words: if a gold token-set appears in the answer with one of
# these cued in front, we treat it as a negation-flip.
_NEGATION_CUES = (
    "no", "not", "never", "don't", "doesn't", "didn't", "isn't", "aren't",
    "wasn't", "weren't", "cannot", "can't", "won't", "without", "false",
    "incorrect", "invalid", "unable", "cannot",
)


def _is_negated(answer_lower: str, token: str) -> bool:
    """Return True if ``token`` in the answer is preceded by a negation cue."""
    # Cheap heuristic: locate the token, then check the preceding window.
    idx = answer_lower.find(token)
    if idx < 0:
        return False
    window = answer_lower[max(0, idx - 20):idx].split()
    return any(cue in window[-3:] for cue in _NEGATION_CUES) if window else False


def contradiction_score(answer: str, gold_facts: Iterable[str]) -> float:
    """0.0–1.0 contradiction signal between ``answer`` and gold facts.

    Two signals (union, averaged):
    1. **Negation-flips** — a gold fact's tokens appear in the answer, but
       immediately preceded by a negation cue.
    2. **Mutually-exclusive choices** — gold says X, answer says Y (a known
       alternative), and X is absent. Detected via curated pairs.
    """
    facts = [f for f in gold_facts if f and len(f.strip()) >= 2]
    if not facts:
        return 0.0
    answer_lower = answer.lower()

    # --- Signal 1: negation-flips ------------------------------------------ #
    flip_hits = 0
    for fact in facts:
        tokens = _tok(fact)
        if not tokens:
            continue
        # Gold fact's tokens all present?
        if all(tok in answer_lower for tok in tokens):
            # Any of those tokens negated?
            if any(_is_negated(answer_lower, tok) for tok in tokens):
                flip_hits += 1
    neg_rate = flip_hits / len(facts)

    # --- Signal 2: mutually-exclusive-choice violations -------------------- #
    # Curated pairs: if the answer picks one side of a mutually-exclusive
    # pair, the gold fact's side must also be present — else it's a flip.
    exclusive_pairs = [
        {"sqlite", "postgresql"}, {"sqlite", "postgres"}, {"sqlite", "mysql"},
        {"stripe", "paypal"}, {"jwt", "oauth"}, {"hs256", "rs256"},
        {"soft-delete", "hard-delete"}, {"sync", "async"},
    ]
    choice_hits = 0
    for fact in facts:
        fact_tokens = _tok(fact)
        for a, b in exclusive_pairs:
            # Fact mentions one side, answer mentions the other exclusively.
            if (
                (a in fact_tokens and b in answer_lower and a not in answer_lower)
                or (b in fact_tokens and a in answer_lower and b not in answer_lower)
            ):
                choice_hits += 1
                break
    choice_rate = choice_hits / len(facts)

    return 0.5 * neg_rate + 0.5 * choice_rate


# --------------------------------------------------------------------------- #
# RAGAS-score dataclasses                                                      #
# --------------------------------------------------------------------------- #


@dataclass
class RagasScore:
    """Per-query RAGAS-axis scores (None columns = embed_fn unavailable)."""

    context_precision: float | None
    context_recall: float | None
    faithfulness: float
    answer_relevance: float | None

    def to_dict(self) -> dict:
        return {
            "context_precision": (round(self.context_precision, 4) if self.context_precision is not None else None),
            "context_recall": (round(self.context_recall, 4) if self.context_recall is not None else None),
            "faithfulness": round(self.faithfulness, 4),
            "answer_relevance": (round(self.answer_relevance, 4) if self.answer_relevance is not None else None),
        }


@dataclass
class RagasSuiteReport:
    """Aggregated RAGAS scores across a query list."""

    suite: str
    n_queries: int
    mean_context_precision: float | None
    mean_context_recall: float | None
    mean_faithfulness: float
    mean_answer_relevance: float | None
    per_query: list[RagasScore] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "suite": self.suite,
            "n_queries": self.n_queries,
            "mean_context_precision": (round(self.mean_context_precision, 4) if self.mean_context_precision is not None else None),
            "mean_context_recall": (round(self.mean_context_recall, 4) if self.mean_context_recall is not None else None),
            "mean_faithfulness": round(self.mean_faithfulness, 4),
            "mean_answer_relevance": (round(self.mean_answer_relevance, 4) if self.mean_answer_relevance is not None else None),
            "per_query": [q.to_dict() for q in self.per_query],
        }


# --------------------------------------------------------------------------- #
# score() — the primary entry point                                           #
# --------------------------------------------------------------------------- #


def score(
    *,
    query: str,
    retrieved: Iterable[str],
    answer: str,
    gold_facts: Iterable[str],
    embed_fn: Callable[[str], list[float]] | None = None,
    facts_have_aliases: dict[str, list[str]] = {},
) -> RagasScore:
    """Score one query end-to-end.

    ``faithfulness`` is always populated. Embedding-dependent columns
    (``context_precision``, ``context_recall``, ``answer_relevance``) return
    ``None`` when ``embed_fn`` is absent or fails at call time.
    """
    facts = list(gold_facts)
    fr = fact_recall(answer, facts, aliases=facts_have_aliases)
    con = contradiction_score(answer, facts)
    faith = fr * (1.0 - con)

    cp: float | None = None
    cr: float | None = None
    ar: float | None = None

    if embed_fn is not None:
        try:
            # context_precision: how many retrieved docs are relevant to gold.
            ans_emb = embed_fn(answer)
            gold_str = ". ".join(g for g in facts if g and len(g.strip()) >= 2)
            gold_emb = embed_fn(gold_str) if gold_str else None

            retrieved_list = list(retrieved)
            if retrieved_list and gold_emb is not None:
                relevant = 0
                for doc in retrieved_list:
                    d_emb = embed_fn(doc)
                    if cosine(d_emb, gold_emb) > 0.0:
                        relevant += 1
                cp = relevant / len(retrieved_list)
            else:
                cp = 0.0

            # context_recall: each gold fact's nearest retrieved doc cosine > 0.
            if retrieved_list and facts:
                recalled = 0
                for fact in facts:
                    if not fact or len(fact.strip()) < 2:
                        continue
                    f_emb = embed_fn(fact)
                    best = max(cosine(f_emb, embed_fn(d)) for d in retrieved_list)
                    if best > 0.0:
                        recalled += 1
                cr = recalled / len([f for f in facts if f and len(f.strip()) >= 2])
            else:
                cr = 0.0

            # answer_relevance: answer ↔ query cosine.
            q_emb = embed_fn(query)
            ar = cosine(ans_emb, q_emb)
        except Exception:
            # Any embed_fn failure: keep cosine columns None.
            cp, cr, ar = None, None, None

    return RagasScore(
        context_precision=cp,
        context_recall=cr,
        faithfulness=faith,
        answer_relevance=ar,
    )


# --------------------------------------------------------------------------- #
# aggregate() — mirror SuiteQuality pattern                                  #
# --------------------------------------------------------------------------- #


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _mean_opt(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return _mean(present) if present else None


def aggregate(suite: str, per_query: list[RagasScore]) -> RagasSuiteReport:
    """Roll per-query RAGAS scores into suite-level means."""
    return RagasSuiteReport(
        suite=suite,
        n_queries=len(per_query),
        mean_context_precision=_mean_opt([q.context_precision for q in per_query]),
        mean_context_recall=_mean_opt([q.context_recall for q in per_query]),
        mean_faithfulness=_mean([q.faithfulness for q in per_query]),
        mean_answer_relevance=_mean_opt([q.answer_relevance for q in per_query]),
        per_query=per_query,
    )
