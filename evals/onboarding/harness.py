"""Onboarding-lift A/B harness + report (E1.5).

The faithfulness eval (``evals/faithfulness``) answers *"does NeuralMind's
selected context contain the right facts?"*. This one answers the question that
is NeuralMind's headline differentiator — the thing static-graph competitors
don't have:

> Does an agent that inherits a **committed team synapse memory** retrieve
> better on its *first* queries than a **cold agent with no memory** — and by
> how much?

It is a formalisation of the self-benchmark's Phase-3 synapse A/B
(``tests/benchmark/run.py``: top-k hit rate 71.7% → 83.3% with recall on),
turned into a committed-baseline eval scored by the same offline judge as the
faithfulness eval.

The two arms share **one** built index and differ in exactly one thing — the
``NEURALMIND_SYNAPSE_INJECT`` flag — so the measured lift is attributable to
associative recall and nothing else:

  * **cold** — synapse recall **off**; the committed memory is never consulted.
  * **onboarded** — the committed team baseline (``seed_history.json``) replayed
    through the real reinforcement path, recall **on**.

Import-safe: only the standard library and the faithfulness modules are
imported at load. ``neuralmind`` (chromadb etc.) is imported lazily inside the
provider factory, so this module and its unit tests run in a minimal
environment with injected stub providers.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from ..faithfulness.harness import _resolve_fixture, count_tokens
from ..faithfulness.runner import OfflineJudge, Query, QuerySet, load_query_set

SCHEMA_VERSION = 1

_SEED_PATH = Path(__file__).resolve().parent / "seed_history.json"

# Recall toggle (same switch the benchmark Phase-3 A/B and the prompt-time hook
# read). "0" disables associative recall; "1" enables it.
_INJECT_ENV = "NEURALMIND_SYNAPSE_INJECT"

# Fan-out of the L3 ranked retrieval the headline hit-rate metric scores. Mirrors
# the production default (``ContextSelector.get_l3_search(n=4)``) so the eval
# measures associative recall exactly where it acts: re-ranking/displacing within
# the top-k the agent actually sees, not the saturated full-context window.
RETRIEVAL_TOP_K = 4


# --------------------------------------------------------------------------- #
# Committed team baseline (seed history)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class SeedHistory:
    """A replayable record of co-edit sessions — the committed team memory."""

    fixture: str
    repeats: int
    sessions: tuple[tuple[str, ...], ...]

    @property
    def total_activations(self) -> int:
        return self.repeats * len(self.sessions)


def load_seed_history(path: str | os.PathLike[str] | None = None) -> SeedHistory:
    """Load + validate ``seed_history.json``.

    Raises ``ValueError`` on a malformed file so a broken baseline fails loudly
    rather than silently measuring a no-op lift.
    """
    p = Path(path) if path is not None else _SEED_PATH
    raw = json.loads(p.read_text(encoding="utf-8"))

    version = raw.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version {version!r}; expected {SCHEMA_VERSION}")

    fixture = raw.get("fixture")
    if not isinstance(fixture, str) or not fixture.strip():
        raise ValueError("seed history is missing a non-empty 'fixture'")

    repeats = raw.get("repeats")
    if not isinstance(repeats, int) or repeats < 1:
        raise ValueError("seed history 'repeats' must be a positive integer")

    raw_sessions = raw.get("sessions")
    if not isinstance(raw_sessions, list) or not raw_sessions:
        raise ValueError("seed history needs a non-empty 'sessions' list")

    sessions: list[tuple[str, ...]] = []
    for i, sess in enumerate(raw_sessions):
        if not isinstance(sess, list) or len(sess) < 2:
            raise ValueError(f"sessions[{i}] must be a list of >= 2 file paths (a co-edit group)")
        for f in sess:
            if not isinstance(f, str) or not f.strip():
                raise ValueError(f"sessions[{i}] has a non-string/empty file path")
        sessions.append(tuple(sess))

    return SeedHistory(fixture=fixture, repeats=repeats, sessions=tuple(sessions))


def replay_history(nm, seed: SeedHistory) -> int:
    """Replay the committed sessions into ``nm``'s synapse store via the real
    ``activate_files`` path (the same entry point the file watcher uses).

    Returns the synapse edge count after seeding.
    """
    for _ in range(seed.repeats):
        for session in seed.sessions:
            nm.activate_files(list(session))
    store = nm.synapses
    return store.stats().get("edges", 0) if store else 0


# --------------------------------------------------------------------------- #
# Context providers (cold vs onboarded), backed by the real pipeline
# --------------------------------------------------------------------------- #
@contextmanager
def _inject(inject: bool):
    """Scope ``NEURALMIND_SYNAPSE_INJECT`` to a measurement, restoring it after.

    The only thing that differs between the cold and onboarded arms is this
    flag, so both metrics toggle it through the same guard.
    """
    prev = os.environ.get(_INJECT_ENV)
    os.environ[_INJECT_ENV] = "1" if inject else "0"
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop(_INJECT_ENV, None)
        else:
            os.environ[_INJECT_ENV] = prev


def _query_context(nm, question: str, *, inject: bool) -> str:
    """Full selected context for ``question`` with recall toggled.

    Reads through ``selector.get_query_context`` (not ``nm.query``) so a
    measurement pass never reinforces the graph mid-run. Feeds the secondary
    fact-recall and full-context grounding signals.
    """
    with _inject(inject):
        return nm.selector.get_query_context(question).context


def _query_retrieval(nm, question: str, *, inject: bool) -> str:
    """The L3 ranked top-k retrieval for ``question`` with recall toggled.

    This is where associative recall actually acts — re-ranking and displacing
    within the ``RETRIEVAL_TOP_K`` hits the agent sees — so the headline
    module-coverage hit-rate is scored here, not over the full L0–L3 window
    (which saturates because every expected module fits at full budget).
    Read-only: ``get_l3_search`` never reinforces the graph.
    """
    with _inject(inject):
        text, _ = nm.selector.get_l3_search(question, n=RETRIEVAL_TOP_K)
        return text


@dataclass(frozen=True)
class ArmProviders:
    """The cold/onboarded answer + retrieval sources for one shared index.

    ``*_context`` return the full L0–L3 window (fact-recall + grounding);
    ``*_retrieval`` return the L3 ranked top-k (the headline hit-rate). All four
    are injectable so the harness is unit-testable without the retrieval stack.
    """

    cold_context: Callable[[Query], str]
    onboarded_context: Callable[[Query], str]
    cold_retrieval: Callable[[Query], str]
    onboarded_retrieval: Callable[[Query], str]


def neuralmind_providers(project_path: str, seed: SeedHistory) -> ArmProviders:
    """Build the cold/onboarded providers over one shared, seeded index.

    The committed baseline is replayed once up front; the cold arm runs with
    recall off (so it never consults that memory), the onboarded arm with recall
    on. Lazily imports ``neuralmind`` and raises ``RuntimeError`` with an
    actionable message when the deps/built graph are missing.
    """
    try:
        from neuralmind import NeuralMind
        from neuralmind.core import GraphNotBuiltError
    except Exception as exc:  # pragma: no cover - exercised only without deps
        raise RuntimeError(
            "the onboarding A/B needs the retrieval stack (chromadb etc.); "
            f"install neuralmind with its deps to run it ({exc})"
        ) from exc

    nm = NeuralMind(project_path)
    try:
        nm.build()
        # Start from an empty store so the baseline is exactly the committed
        # history, then replay the team memory once.
        if nm.synapses is not None:
            nm.synapses.reset()
        replay_history(nm, seed)
    except GraphNotBuiltError as exc:  # pragma: no cover - needs real env
        raise RuntimeError(
            f"no code graph for {project_path!r}; run `neuralmind build` first ({exc})"
        ) from exc

    return ArmProviders(
        cold_context=lambda q: _query_context(nm, q.question, inject=False),
        onboarded_context=lambda q: _query_context(nm, q.question, inject=True),
        cold_retrieval=lambda q: _query_retrieval(nm, q.question, inject=False),
        onboarded_retrieval=lambda q: _query_retrieval(nm, q.question, inject=True),
    )


# --------------------------------------------------------------------------- #
# A/B run
# --------------------------------------------------------------------------- #
@dataclass
class OnboardingResult:
    """One query's cold vs onboarded outcome.

    ``hit_rate`` is the headline: the fraction of the query's expected modules
    surfaced in the L3 ranked top-k — the slice associative recall actually
    re-ranks. ``recall``/``grounding`` are scored over the full L0–L3 window and
    reported as secondaries (grounding saturates at full budget; fact-recall is
    budget-traded as recall swaps weak hits for co-edited hubs)."""

    query_id: str
    cold_hit_rate: float
    onboarded_hit_rate: float
    cold_recall: float
    onboarded_recall: float
    cold_grounding: float
    onboarded_grounding: float
    cold_tokens: int
    onboarded_tokens: int

    @property
    def hit_rate_lift(self) -> float:
        return self.onboarded_hit_rate - self.cold_hit_rate

    @property
    def recall_lift(self) -> float:
        return self.onboarded_recall - self.cold_recall

    @property
    def grounding_lift(self) -> float:
        return self.onboarded_grounding - self.cold_grounding

    def to_dict(self) -> dict:
        return {
            "query_id": self.query_id,
            "cold_hit_rate": round(self.cold_hit_rate, 4),
            "onboarded_hit_rate": round(self.onboarded_hit_rate, 4),
            "hit_rate_lift": round(self.hit_rate_lift, 4),
            "cold_recall": round(self.cold_recall, 4),
            "onboarded_recall": round(self.onboarded_recall, 4),
            "recall_lift": round(self.recall_lift, 4),
            "cold_grounding": round(self.cold_grounding, 4),
            "onboarded_grounding": round(self.onboarded_grounding, 4),
            "grounding_lift": round(self.grounding_lift, 4),
            "cold_tokens": self.cold_tokens,
            "onboarded_tokens": self.onboarded_tokens,
        }


def run_ab(
    query_set: QuerySet,
    project_path: str | None = None,
    *,
    seed: SeedHistory | None = None,
    cold_provider: Callable[[Query], str] | None = None,
    onboarded_provider: Callable[[Query], str] | None = None,
    cold_retrieval: Callable[[Query], str] | None = None,
    onboarded_retrieval: Callable[[Query], str] | None = None,
    judge: OfflineJudge | None = None,
) -> list[OnboardingResult]:
    """Run the onboarding A/B over every query in ``query_set``.

    The four providers are injectable so the harness is unit-testable without
    the retrieval stack; by default they resolve to the real NeuralMind pipeline
    seeded with the committed team baseline. ``*_provider`` yield the full
    context (fact-recall + grounding); ``*_retrieval`` yield the L3 ranked top-k
    (the headline hit-rate). If a retrieval provider is omitted it falls back to
    its context provider, so a context-only call still scores coherently.
    """
    judge = judge or OfflineJudge()
    seed = seed or load_seed_history()

    if cold_provider is None or onboarded_provider is None:
        fixture_dir = _resolve_fixture(query_set, project_path)
        arms = neuralmind_providers(str(fixture_dir), seed)
        cold_provider = arms.cold_context
        onboarded_provider = arms.onboarded_context
        cold_retrieval = cold_retrieval or arms.cold_retrieval
        onboarded_retrieval = onboarded_retrieval or arms.onboarded_retrieval

    cold_retrieval = cold_retrieval or cold_provider
    onboarded_retrieval = onboarded_retrieval or onboarded_provider

    results: list[OnboardingResult] = []
    for q in query_set.queries:
        cold_ctx = cold_provider(q)
        onb_ctx = onboarded_provider(q)
        # Hit-rate is grounding scored over the ranked top-k retrieval, where
        # associative recall re-ranks/displaces, rather than the full window.
        cold_ret = cold_retrieval(q)
        onb_ret = onboarded_retrieval(q)
        results.append(
            OnboardingResult(
                query_id=q.id,
                cold_hit_rate=judge.grounding_rate(q, cold_ret),
                onboarded_hit_rate=judge.grounding_rate(q, onb_ret),
                cold_recall=judge.fact_recall(q, cold_ctx).recall,
                onboarded_recall=judge.fact_recall(q, onb_ctx).recall,
                cold_grounding=judge.grounding_rate(q, cold_ctx),
                onboarded_grounding=judge.grounding_rate(q, onb_ctx),
                cold_tokens=count_tokens(cold_ctx),
                onboarded_tokens=count_tokens(onb_ctx),
            )
        )
    return results


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


@dataclass
class OnboardingReport:
    """Aggregated onboarding-lift report (the E1.5 deliverable)."""

    fixture: str
    n_queries: int
    seed_sessions: int
    cold_mean_hit_rate: float
    onboarded_mean_hit_rate: float
    cold_mean_recall: float
    onboarded_mean_recall: float
    cold_mean_grounding: float
    onboarded_mean_grounding: float
    cold_total_tokens: int
    onboarded_total_tokens: int
    per_query: list[OnboardingResult] = field(default_factory=list)

    @property
    def onboarding_lift(self) -> float:
        """The headline + CI-gated number: mean top-k module hit-rate gain from
        inheriting the committed team memory (onboarded − cold).

        This is the metric associative recall is built to move — the share of a
        query's expected modules that land in the ranked top-k the agent sees,
        the same signal as the self-benchmark's Phase-3 A/B. Full-context
        grounding saturates at this fixture's budget and raw fact-recall is
        budget-traded, so both are reported below as honest secondaries."""
        return self.onboarded_mean_hit_rate - self.cold_mean_hit_rate

    @property
    def recall_lift(self) -> float:
        return self.onboarded_mean_recall - self.cold_mean_recall

    @property
    def grounding_lift(self) -> float:
        return self.onboarded_mean_grounding - self.cold_mean_grounding

    def to_dict(self) -> dict:
        return {
            "fixture": self.fixture,
            "n_queries": self.n_queries,
            "seed_sessions": self.seed_sessions,
            "onboarding_lift": round(self.onboarding_lift, 4),
            "recall_lift": round(self.recall_lift, 4),
            "grounding_lift": round(self.grounding_lift, 4),
            "cold_mean_hit_rate": round(self.cold_mean_hit_rate, 4),
            "onboarded_mean_hit_rate": round(self.onboarded_mean_hit_rate, 4),
            "cold_mean_recall": round(self.cold_mean_recall, 4),
            "onboarded_mean_recall": round(self.onboarded_mean_recall, 4),
            "cold_mean_grounding": round(self.cold_mean_grounding, 4),
            "onboarded_mean_grounding": round(self.onboarded_mean_grounding, 4),
            "cold_total_tokens": self.cold_total_tokens,
            "onboarded_total_tokens": self.onboarded_total_tokens,
            "per_query": [r.to_dict() for r in self.per_query],
        }


def build_report(
    query_set: QuerySet, results: list[OnboardingResult], *, seed: SeedHistory | None = None
) -> OnboardingReport:
    return OnboardingReport(
        fixture=query_set.fixture,
        n_queries=len(results),
        seed_sessions=len(seed.sessions) if seed else 0,
        cold_mean_hit_rate=_mean([r.cold_hit_rate for r in results]),
        onboarded_mean_hit_rate=_mean([r.onboarded_hit_rate for r in results]),
        cold_mean_recall=_mean([r.cold_recall for r in results]),
        onboarded_mean_recall=_mean([r.onboarded_recall for r in results]),
        cold_mean_grounding=_mean([r.cold_grounding for r in results]),
        onboarded_mean_grounding=_mean([r.onboarded_grounding for r in results]),
        cold_total_tokens=sum(r.cold_tokens for r in results),
        onboarded_total_tokens=sum(r.onboarded_tokens for r in results),
        per_query=results,
    )


def render_json(report: OnboardingReport) -> str:
    return json.dumps(report.to_dict(), indent=2)


def render_markdown(report: OnboardingReport) -> str:
    lift_pts = report.onboarding_lift * 100
    recall_pts = report.recall_lift * 100
    ground_pts = report.grounding_lift * 100
    lines = [
        "## NeuralMind onboarding-lift eval",
        "",
        f"**Fixture:** `{report.fixture}` — {report.n_queries} queries, "
        f"{report.seed_sessions} committed team co-edit sessions.",
        "",
        f"- **Onboarding lift: {lift_pts:+.1f} points** top-k module hit-rate "
        f"(onboarded {report.onboarded_mean_hit_rate * 100:.1f}% vs "
        f"cold {report.cold_mean_hit_rate * 100:.1f}% of expected modules in the "
        f"ranked top-{RETRIEVAL_TOP_K})",
        f"- Fact-recall lift: {recall_pts:+.1f} points (secondary — onboarded "
        f"{report.onboarded_mean_recall * 100:.1f}% vs cold "
        f"{report.cold_mean_recall * 100:.1f}%; recall trades fact-density for "
        f"co-edited hubs at a fixed budget)",
        f"- Full-context grounding lift: {ground_pts:+.1f} points (secondary — "
        f"saturates when every expected module already fits the window)",
        f"- Token budget: `{report.onboarded_total_tokens:,}` onboarded / "
        f"`{report.cold_total_tokens:,}` cold (recall is budget-neutral by design)",
        "",
        "| Query | Cold hit | Onb hit | Δ | Cold rec | Onb rec |",
        "|-------|---------:|--------:|--:|---------:|--------:|",
    ]
    for r in report.per_query:
        lines.append(
            f"| `{r.query_id}` | {r.cold_hit_rate * 100:.0f}% | "
            f"{r.onboarded_hit_rate * 100:.0f}% | {r.hit_rate_lift * 100:+.0f} | "
            f"{r.cold_recall * 100:.0f}% | {r.onboarded_recall * 100:.0f}% |"
        )
    lines += [
        "",
        "Onboarding lift = the top-k module hit-rate gain when an agent inherits "
        "a committed team synapse memory (recall on) vs a cold agent that never "
        "had it (recall off), over the same gold queries at the same token "
        "budget. A positive lift is the learned-memory differentiator: "
        "associative recall surfaces co-edited modules into the ranked top-"
        f"{RETRIEVAL_TOP_K} that a purely textual search leaves out — the same "
        "signal as the self-benchmark's Phase-3 A/B.",
        "",
    ]
    return "\n".join(lines)


def run_and_report(
    project_path: str | None = None,
    query_set: QuerySet | None = None,
    *,
    seed: SeedHistory | None = None,
    **run_kwargs,
) -> OnboardingReport:
    """Convenience: load the gold set + committed baseline (if not supplied),
    run the A/B, aggregate."""
    qs = query_set or load_query_set()
    seed = seed or load_seed_history()
    results = run_ab(qs, project_path, seed=seed, **run_kwargs)
    return build_report(qs, results, seed=seed)
