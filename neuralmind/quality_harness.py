# neuralmind/quality_harness.py — CI-gated tuner promotion (PRD 2 C4).
#
# The tuner (C3) evaluates its own candidates and would promote autonomously
# if fitness > incumbent * 1.05. This is self-measurement with no independent
# validation. QualityHarness is the independent gate: it runs retrieval with
# the candidate's params against fixture queries, scores with quality.py and
# ragas.py, and returns a verdict. Promotion requires harness pass AND
# hysteresis beat.
#
# Fail-open: if fixtures or embedder are unavailable, the harness returns
# passed=True with fitness=0.0 (the candidate simply won't be promoted over
# a valid incumbent -- safe fail-open).

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .quality import QualityThresholds, aggregate, evaluate_query

log = logging.getLogger(__name__)


@dataclass
class HarnessVerdict:
    """Result of independent quality validation."""

    fitness: float = 0.0  # scalar for comparison with incumbent
    ragas_score: float = 0.0  # answerability proxy (relevance axis)
    retrieval_score: float = 0.0  # MRR from quality.py
    passed: bool = False  # all QualityThresholds met
    failures: list[str] = field(default_factory=list)
    per_query: list[dict] = field(default_factory=list)


@dataclass
class PromotionDecision:
    """Gate decision for a tuner candidate."""

    verdict: str = "hold"  # "promote" | "rollback" | "hold"
    reason: str = ""  # human-readable rationale
    candidate_fitness: float = 0.0  # tuner's self-measurement
    incumbent_fitness: float = 0.0  # incumbent's fitness
    harness_verdict: HarnessVerdict | None = None


class QualityHarness:
    """Independent quality validation gate for tuner candidates (C4).

    Stdlib-only at module level. Heavy deps (GraphEmbedder) imported lazily
    inside evaluate() so this module imports cleanly without the embedding
    stack -- mirroring fitness.py / ragas.py conventions.
    """

    def __init__(
        self,
        project_path: str | Path,
        thresholds: QualityThresholds | None = None,
        embed_fn: Callable | None = None,
        incumbent_params: dict | None = None,
    ):
        self.project_path = Path(project_path)
        self.thresholds = thresholds or QualityThresholds()
        self.embed_fn = embed_fn
        self.incumbent_params = incumbent_params

    def evaluate(self, candidate_params: dict) -> HarnessVerdict:
        """Run independent validation of a candidate config.

        Steps:
        1. Load fixtures via load_fixture_queries()
        2. For each fixture: run embedder.search() with candidate params
        3. Score retrieval with quality.py (MRR, nDCG, hit-rate)
        4. Aggregate + compare against QualityThresholds
        5. Return HarnessVerdict

        Fail-open: returns passed=True with fitness=0.0 when fixtures or
        embedder are unavailable (a candidate with fitness=0.0 won't be
        promoted over a valid incumbent).
        """
        from .fixtures import load_fixture_queries

        fixtures = load_fixture_queries(self.project_path, n=20)
        if not fixtures:
            log.debug("QualityHarness: no fixtures available, fail-open")
            return HarnessVerdict(
                fitness=0.0,
                ragas_score=0.0,
                retrieval_score=0.0,
                passed=True,
                failures=[],
                per_query=[],
            )

        # Lazy embedder load -- keeps this module importable without deps.
        try:
            from .embedder import GraphEmbedder

            embedder = GraphEmbedder(str(self.project_path))
            if not embedder.load_graph():
                log.debug("QualityHarness: embedder graph load failed, fail-open")
                return HarnessVerdict(
                    fitness=0.0,
                    ragas_score=0.0,
                    retrieval_score=0.0,
                    passed=True,
                    failures=[],
                    per_query=[],
                )
        except Exception as exc:  # noqa: BLE001 — lazy import may fail
            log.debug("QualityHarness: embedder unavailable: %s", exc)
            return HarnessVerdict(
                fitness=0.0,
                ragas_score=0.0,
                retrieval_score=0.0,
                passed=True,
                failures=[],
                per_query=[],
            )

        # Run retrieval per fixture with the candidate's params applied.
        per_query_results = []
        for fq in fixtures:
            try:
                structural_seed_k = int(round(candidate_params.get("STRUCTURAL_SEED_K", 3)))
                synapse_seed_k = int(round(candidate_params.get("SYNAPSE_SEED_K", 3)))
                search_n = max(structural_seed_k, synapse_seed_k) * 5
                results = embedder.search(fq.query, n=max(search_n, 10))
            except Exception:  # noqa: BLE001 — never crash the gate
                results = []

            retrieved_ids = [r.get("id", "") for r in results if isinstance(r, dict)]
            relevant = list(fq.expected_node_ids) if fq.expected_node_ids else []

            qq = evaluate_query(
                query_id=fq.query[:60],
                ranked=retrieved_ids,
                relevant=relevant,
            )
            per_query_results.append(qq)

        if not per_query_results:
            return HarnessVerdict(
                fitness=0.0,
                ragas_score=0.0,
                retrieval_score=0.0,
                passed=True,
                failures=[],
                per_query=[],
            )

        suite = aggregate("quality_harness", per_query_results)
        failures = self.thresholds.check(suite)

        # Composite fitness: retrieval quality + answerability, weighted.
        # Mirrors the tuner's compute_fitness structure (retrieval + session)
        # but measured independently against fixture queries.
        retrieval_score = suite.mrr
        ragas_score = suite.answerability
        fitness = 0.6 * retrieval_score + 0.4 * ragas_score
        # NaN-safe clamp: max(0.0, min(1.0, nan)) returns 1.0 — wrong direction.
        # Explicit isfinite check so NaN/Inf regressions don't promote.
        if not math.isfinite(fitness):
            fitness = 0.0
        else:
            fitness = max(0.0, min(1.0, fitness))

        return HarnessVerdict(
            fitness=fitness,
            ragas_score=ragas_score,
            retrieval_score=retrieval_score,
            passed=len(failures) == 0,
            failures=failures,
            per_query=[q.to_dict() for q in per_query_results],
        )

    def decide(
        self,
        candidate_fitness: float,
        incumbent_fitness: float,
        harness_verdict: HarnessVerdict,
        hysteresis: float = 0.05,
    ) -> PromotionDecision:
        """Decide promote/rollback/hold based on gate logic.

        Gate:
          verdict.passed AND fitness > incumbent*(1+hysteresis)  -> PROMOTE
          fitness < incumbent                                     -> ROLLBACK
          otherwise                                                -> HOLD
        """
        if not harness_verdict.passed:
            return PromotionDecision(
                verdict="hold",
                reason=f"harness failed: {'; '.join(harness_verdict.failures)}",
                candidate_fitness=candidate_fitness,
                incumbent_fitness=incumbent_fitness,
                harness_verdict=harness_verdict,
            )

        if harness_verdict.fitness > incumbent_fitness * (1.0 + hysteresis):
            return PromotionDecision(
                verdict="promote",
                reason="harness pass + beats hysteresis",
                candidate_fitness=candidate_fitness,
                incumbent_fitness=incumbent_fitness,
                harness_verdict=harness_verdict,
            )

        if harness_verdict.fitness < incumbent_fitness:
            return PromotionDecision(
                verdict="rollback",
                reason="harness pass but below incumbent",
                candidate_fitness=candidate_fitness,
                incumbent_fitness=incumbent_fitness,
                harness_verdict=harness_verdict,
            )

        return PromotionDecision(
            verdict="hold",
            reason="harness pass but within hysteresis",
            candidate_fitness=candidate_fitness,
            incumbent_fitness=incumbent_fitness,
            harness_verdict=harness_verdict,
        )
