"""Faithfulness A/B harness + report (E1.2 + E1.4).

This turns the E1.1 foundation (gold-fact dataset + offline recall scorer in
``runner.py``) into an actual *number*: for every query it scores a
NeuralMind-selected context against a **matched-budget naive baseline** and
reports the faithfulness delta.

Design (see ``README.md``):
  * The default answerer is deterministic and offline — the "answer" *is* the
    context provided to the model (retrieval-as-answer). So expected-fact
    recall over that text measures whether the *selected context* actually
    contains the gold facts. No LLM, no network → safe as a CI gate.
  * The baseline is naive truncation to the **same token budget** as the
    NeuralMind context. That makes it an honest fight: "does smart selection
    beat dumb truncation at equal tokens?" — not "does a 800-token context
    beat the whole 50k-token repo?" (which the whole repo trivially wins on
    recall while costing 40-70x the tokens).

Import-safe: only the standard library and ``.runner`` are imported at module
load. ``tiktoken`` and ``neuralmind.core`` are imported lazily inside the
functions that need them, so this module — and its unit tests — run in a
minimal environment without the heavy retrieval dependencies.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .runner import OfflineJudge, Query, QuerySet, load_query_set

# Source file extensions that make up a fixture's "whole repo" baseline.
_SOURCE_GLOBS = ("*.py", "*.ts", "*.go", "*.js")

# Repo root = three levels up from this file (evals/faithfulness/harness.py).
_REPO_ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# Tokenisation
# --------------------------------------------------------------------------- #
def count_tokens(text: str) -> int:
    """Token count via ``tiktoken`` when available, else a ~4-chars/token
    approximation.

    The approximation is rough but the A/B stays fair because both the
    NeuralMind and naive sides are measured with the same function. Mirrors
    the fallback chain in ``tests/benchmark/run.py``.
    """
    try:
        import tiktoken
    except Exception:
        return max(1, len(text) // 4)
    for name in ("o200k_base", "cl100k_base"):
        try:
            enc = tiktoken.get_encoding(name)
            return len(enc.encode(text))
        except Exception:  # noqa: PERF203 - tiny fixed loop
            continue
    return max(1, len(text) // 4)


def _truncate_to_tokens(text: str, budget: int) -> str:
    """Head-truncate ``text`` to approximately ``budget`` tokens.

    Word-granular and deterministic; binary-searches the word count so the
    result lands at or just under the budget regardless of which tokenizer
    ``count_tokens`` resolved to.
    """
    if budget <= 0 or not text:
        return ""
    words = text.split()
    if count_tokens(text) <= budget:
        return text
    lo, hi = 0, len(words)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if count_tokens(" ".join(words[:mid])) <= budget:
            lo = mid
        else:
            hi = mid
    return " ".join(words[:lo])


# --------------------------------------------------------------------------- #
# Context providers
# --------------------------------------------------------------------------- #
def _fixture_source_text(fixture_dir: Path) -> str:
    """Concatenate every source file in the fixture, each under a ``# path``
    header so module references survive into the naive baseline (fair: both
    sides label their files)."""
    parts: list[str] = []
    for pattern in _SOURCE_GLOBS:
        for f in sorted(fixture_dir.rglob(pattern)):
            if "__pycache__" in f.parts or f.name == "__init__.py":
                continue
            rel = f.relative_to(fixture_dir).as_posix()
            parts.append(f"# {rel}\n{f.read_text(encoding='utf-8')}")
    return "\n\n".join(parts)


def naive_context(fixture_dir: Path, budget_tokens: int) -> str:
    """The matched-budget naive baseline: the concatenated repo, head-truncated
    to ``budget_tokens``. Deterministic, dependency-free, relevance-blind."""
    return _truncate_to_tokens(_fixture_source_text(fixture_dir), budget_tokens)


def neuralmind_context_provider(project_path: str) -> Callable[[Query], str]:
    """Build a context provider backed by the real NeuralMind pipeline.

    Lazily imports ``neuralmind`` (chromadb etc.) and constructs the index
    once, returning a ``query -> context`` callable. Raises ``RuntimeError``
    with an actionable message if the deps or the built graph are missing —
    the CLI turns that into a graceful degrade.
    """
    try:
        from neuralmind import NeuralMind
        from neuralmind.core import GraphNotBuiltError
    except Exception as exc:  # pragma: no cover - exercised only without deps
        raise RuntimeError(
            "the faithfulness A/B needs the retrieval stack (chromadb etc.); "
            f"install neuralmind with its deps to run it ({exc})"
        ) from exc

    nm = NeuralMind(project_path)

    def provide(query: Query) -> str:
        try:
            return nm.query(query.question).context
        except GraphNotBuiltError as exc:  # pragma: no cover - needs real env
            raise RuntimeError(
                f"no code graph for {project_path!r}; run `graphify update` then "
                f"`neuralmind build` first ({exc})"
            ) from exc

    return provide


# --------------------------------------------------------------------------- #
# Answerer
# --------------------------------------------------------------------------- #
class ContextAnswerer:
    """Deterministic, offline answerer: the answer *is* the provided context.

    Scoring this with the offline expected-fact-recall judge measures whether
    the selected context contains the gold facts — the question the eval cares
    about. A real LLM answerer is the opt-in path (``NEURALMIND_EVAL_LLM_JUDGE``)
    and is never the default or the CI gate.
    """

    def answer(self, query: Query, context: str) -> str:  # noqa: ARG002
        return context


# --------------------------------------------------------------------------- #
# A/B run
# --------------------------------------------------------------------------- #
@dataclass
class ABResult:
    """One query's with-NeuralMind vs matched-budget-naive outcome."""

    query_id: str
    nm_recall: float
    naive_recall: float
    nm_tokens: int
    naive_tokens: int
    nm_grounding: float
    naive_grounding: float
    nm_contradiction: float

    @property
    def recall_delta(self) -> float:
        return self.nm_recall - self.naive_recall

    def to_dict(self) -> dict:
        return {
            "query_id": self.query_id,
            "nm_recall": round(self.nm_recall, 4),
            "naive_recall": round(self.naive_recall, 4),
            "recall_delta": round(self.recall_delta, 4),
            "nm_tokens": self.nm_tokens,
            "naive_tokens": self.naive_tokens,
            "nm_grounding": round(self.nm_grounding, 4),
            "naive_grounding": round(self.naive_grounding, 4),
            "nm_contradiction": round(self.nm_contradiction, 4),
        }


def run_ab(
    query_set: QuerySet,
    project_path: str | None = None,
    *,
    context_provider: Callable[[Query], str] | None = None,
    naive_provider: Callable[[int], str] | None = None,
    answerer: ContextAnswerer | None = None,
    judge: OfflineJudge | None = None,
) -> list[ABResult]:
    """Run the faithfulness A/B over every query in ``query_set``.

    ``context_provider`` and ``naive_provider`` are injectable so the harness
    is unit-testable without the retrieval stack; by default they resolve to
    the real NeuralMind pipeline and the fixture-truncation baseline.
    """
    answerer = answerer or ContextAnswerer()
    judge = judge or OfflineJudge()

    # The fixture defaults to the gold set's own ``fixture`` (resolved against
    # the repo root) when no explicit project is given, so a bare ``--run``
    # self-evaluates the reference fixture.
    fixture_dir = _resolve_fixture(query_set, project_path)

    if context_provider is None:
        context_provider = neuralmind_context_provider(str(fixture_dir))
    if naive_provider is None:
        naive_provider = lambda budget: naive_context(fixture_dir, budget)  # noqa: E731

    results: list[ABResult] = []
    for q in query_set.queries:
        nm_ctx = context_provider(q)
        budget = count_tokens(nm_ctx)
        naive_ctx = naive_provider(budget)

        nm_ans = answerer.answer(q, nm_ctx)
        naive_ans = answerer.answer(q, naive_ctx)
        results.append(
            ABResult(
                query_id=q.id,
                nm_recall=judge.fact_recall(q, nm_ans).recall,
                naive_recall=judge.fact_recall(q, naive_ans).recall,
                nm_tokens=budget,
                naive_tokens=count_tokens(naive_ctx),
                nm_grounding=judge.grounding_rate(q, nm_ans),
                naive_grounding=judge.grounding_rate(q, naive_ans),
                nm_contradiction=judge.contradiction_score(q, nm_ans),
            )
        )
    return results


def _resolve_fixture(query_set: QuerySet, project_path: str | None) -> Path:
    """Pick the directory the naive baseline reads from: an explicit
    ``project_path`` wins, else the query set's ``fixture`` resolved against
    the repo root."""
    if project_path is not None:
        return Path(project_path)
    return (_REPO_ROOT / query_set.fixture).resolve()


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
@dataclass
class EvalReport:
    """Aggregated faithfulness report (the E1.4 deliverable)."""

    fixture: str
    n_queries: int
    nm_mean_recall: float
    naive_mean_recall: float
    nm_mean_grounding: float
    naive_mean_grounding: float
    nm_mean_contradiction: float
    nm_total_tokens: int
    naive_total_tokens: int
    per_query: list[ABResult] = field(default_factory=list)

    @property
    def faithfulness_delta(self) -> float:
        """The headline number: mean fact-recall gain of NeuralMind's selected
        context over the matched-budget naive baseline."""
        return self.nm_mean_recall - self.naive_mean_recall

    def to_dict(self) -> dict:
        return {
            "fixture": self.fixture,
            "n_queries": self.n_queries,
            "faithfulness_delta": round(self.faithfulness_delta, 4),
            "nm_mean_recall": round(self.nm_mean_recall, 4),
            "naive_mean_recall": round(self.naive_mean_recall, 4),
            "nm_mean_grounding": round(self.nm_mean_grounding, 4),
            "naive_mean_grounding": round(self.naive_mean_grounding, 4),
            "nm_mean_contradiction": round(self.nm_mean_contradiction, 4),
            "nm_total_tokens": self.nm_total_tokens,
            "naive_total_tokens": self.naive_total_tokens,
            "per_query": [r.to_dict() for r in self.per_query],
        }


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def build_report(query_set: QuerySet, results: list[ABResult]) -> EvalReport:
    return EvalReport(
        fixture=query_set.fixture,
        n_queries=len(results),
        nm_mean_recall=_mean([r.nm_recall for r in results]),
        naive_mean_recall=_mean([r.naive_recall for r in results]),
        nm_mean_grounding=_mean([r.nm_grounding for r in results]),
        naive_mean_grounding=_mean([r.naive_grounding for r in results]),
        nm_mean_contradiction=_mean([r.nm_contradiction for r in results]),
        nm_total_tokens=sum(r.nm_tokens for r in results),
        naive_total_tokens=sum(r.naive_tokens for r in results),
        per_query=results,
    )


def render_json(report: EvalReport) -> str:
    return json.dumps(report.to_dict(), indent=2)


def render_markdown(report: EvalReport) -> str:
    """Human-readable report — the same shape the benchmark report uses."""
    delta_pts = report.faithfulness_delta * 100
    lines = [
        "## NeuralMind faithfulness eval",
        "",
        f"**Fixture:** `{report.fixture}` — {report.n_queries} queries.",
        "",
        f"- **Faithfulness delta: {delta_pts:+.1f} points** "
        f"(NeuralMind {report.nm_mean_recall * 100:.1f}% vs "
        f"naive {report.naive_mean_recall * 100:.1f}% expected-fact recall, "
        "at a matched token budget)",
        f"- Grounding rate: **{report.nm_mean_grounding * 100:.1f}%** "
        f"(naive {report.naive_mean_grounding * 100:.1f}%)",
        f"- Contradiction rate: **{report.nm_mean_contradiction * 100:.1f}%** "
        "(lower is better; 0% = no gold-fact conflicts detected)",
        f"- Token budget: `{report.nm_total_tokens:,}` NeuralMind / "
        f"`{report.naive_total_tokens:,}` naive (matched per query)",
        "",
        "| Query | NM recall | Naive recall | Δ | Grounding | Contra | Tokens |",
        "|-------|----------:|-------------:|--:|----------:|-------:|-------:|",
    ]
    for r in report.per_query:
        lines.append(
            f"| `{r.query_id}` | {r.nm_recall * 100:.0f}% | {r.naive_recall * 100:.0f}% | "
            f"{r.recall_delta * 100:+.0f} | {r.nm_grounding * 100:.0f}% | "
            f"{r.nm_contradiction * 100:.0f}% | {r.nm_tokens:,} |"
        )
    lines += [
        "",
        "Faithfulness = expected-fact recall of the answer; the deterministic "
        "offline judge scores whether the *selected context* contains each gold "
        "fact. The baseline is naive truncation to the same per-query token "
        "budget, so a positive delta means smart selection beats dumb "
        "truncation at equal cost.",
        "",
    ]
    return "\n".join(lines)


def run_and_report(
    project_path: str | None = None,
    query_set: QuerySet | None = None,
    **run_kwargs,
) -> EvalReport:
    """Convenience: load the gold set (if not supplied), run the A/B, aggregate."""
    qs = query_set or load_query_set()
    results = run_ab(qs, project_path, **run_kwargs)
    return build_report(qs, results)
