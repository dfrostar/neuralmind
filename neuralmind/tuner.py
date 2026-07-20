# tuner.py — population-based evolutionary search (PRD 2 C3).
#
# Critical path. The tuner is the moat: it makes the product
# self-improving at the local level without a research team.
#
# Local-first: runs in the daemon, offline (weekly, configurable).
# Population 10-20, bounded generations (5-10), Gaussian perturbation
# around current best + uniform-exploration probability 0.15.
# Evaluation uses C1 fitness (``neuralmind/fitness.py``) against real
# query traces from ``reasoning_traces`` (A1). CI-gated promotion with
# hysteresis margin.
#
# Fail-open: if fitness eval fails, the incumbent stands; no partial
# promotion; unknown parameter names are logged and skipped, never crash.

from __future__ import annotations

import json
import logging
import math
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .contracts import (
    META_TUNER_FITNESS,
    META_TUNER_INCUMBENT,
    META_TUNER_LAST_DECISION,
    META_TUNER_PROMOTED_AT,
    TUNABLE_PARAMS,
    clamp_value,
)
from .fitness import FitnessInputs, compute_fitness
from .tuning import resolve_effective

log = logging.getLogger(__name__)


# ----------------------------------------------------------------------- #
# Dataclasses
# ----------------------------------------------------------------------- #


@dataclass
class TuneRun:
    """Result of a single tuner generation."""

    generation: int
    population_size: int
    best_fitness: float
    incumbent_fitness: float
    promoted: bool
    best_params: dict[str, float]
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "generation": self.generation,
            "population_size": self.population_size,
            "best_fitness": round(self.best_fitness, 6),
            "incumbent_fitness": round(self.incumbent_fitness, 6),
            "promoted": self.promoted,
            "best_params": {k: round(v, 6) for k, v in self.best_params.items()},
            "ts": self.ts,
        }


# ----------------------------------------------------------------------- #
# PopulationTuner
# ----------------------------------------------------------------------- #


class PopulationTuner:
    """Population-based evolutionary search over the tuneable parameter space.

    Configurable via env:
      - NEURALMIND_TUNER_POPULATION (default 15)
      - NEURALMIND_TUNER_GENERATIONS (default 8)
      - NEURALMIND_TUNER_HYSTERESIS (default 0.05)
      - NEURALMIND_TUNER_EXPLORE (default 0.15)
      - NEURALMIND_TUNER_EVAL_DAYS (default 14, how many days of traces to eval)
    """

    def __init__(
        self,
        project_path: str | Path | None = None,
        population_size: int | None = None,
        generations: int | None = None,
        hysteresis: float | None = None,
        uniform_explore_p: float | None = None,
        eval_days: float | None = None,
        harness: Any = None,
    ):
        self.project_path = Path(project_path) if project_path is not None else None
        self.population_size = population_size or int(
            os.environ.get("NEURALMIND_TUNER_POPULATION", 15)
        )
        self.generations = generations or int(os.environ.get("NEURALMIND_TUNER_GENERATIONS", 8))
        self.hysteresis = hysteresis or float(os.environ.get("NEURALMIND_TUNER_HYSTERESIS", 0.05))
        self.uniform_explore_p = uniform_explore_p or float(
            os.environ.get("NEURALMIND_TUNER_EXPLORE", 0.15)
        )
        self.eval_days = eval_days or float(os.environ.get("NEURALMIND_TUNER_EVAL_DAYS", 14.0))
        self.harness = harness
        self._last_decision: Any = None
        self._rng = random.Random()
        # Defensive coerce: truthy negative values pass through `or` and silently
        # invert the promotion gate (negative hysteresis), skip the loop
        # (negative population_size / generations), or break the sampling
        # distribution (uniform_explore_p outside [0, 1]).
        if self.hysteresis <= 0.0:
            log.warning("hysteresis must be positive, got %r — using default 0.05", self.hysteresis)
            self.hysteresis = 0.05
        if self.population_size <= 0:
            log.warning(
                "population_size must be positive, got %r — using default", self.population_size
            )
            self.population_size = int(os.environ.get("NEURALMIND_TUNER_POPULATION", 15))
        if self.generations <= 0:
            log.warning("generations must be positive, got %r — using default 8", self.generations)
            self.generations = int(os.environ.get("NEURALMIND_TUNER_GENERATIONS", 8))
        if self.uniform_explore_p < 0.0:
            log.warning(
                "uniform_explore_p must be in [0,1], got %r — clamping", self.uniform_explore_p
            )
            self.uniform_explore_p = 0.0
        elif self.uniform_explore_p > 1.0:
            log.warning(
                "uniform_explore_p must be in [0,1], got %r — clamping", self.uniform_explore_p
            )
            self.uniform_explore_p = 1.0
        if self.eval_days <= 0.0:
            self.eval_days = 14.0

    # ------------------------------------------------------------------- #
    # Population sampling
    # ------------------------------------------------------------------- #

    def _default_param_map(self) -> dict[str, float]:
        """Start from the effective (default + persisted) param map."""
        return resolve_effective(self.project_path)

    def sample_candidate(
        self,
        incumbent: dict[str, float],
        *,
        rng: random.Random | None = None,
    ) -> dict[str, float]:
        """Sample a candidate: Gaussian perturbation around incumbent.

        With probability ``uniform_explore_p``, draws uniformly from the
        full parameter space instead (diversity injection).
        """
        rng = rng or self._rng
        if rng.random() < self.uniform_explore_p:
            return self._uniform_sample(rng)
        return self._gaussian_perturb(incumbent, rng)

    def _uniform_sample(self, rng: random.Random) -> dict[str, float]:
        """Draw each parameter uniformly from its bounded range."""
        out: dict[str, float] = {}
        for name, param in TUNABLE_PARAMS.items():
            out[name] = rng.uniform(param.min_value, param.max_value)
        return out

    def _gaussian_perturb(
        self,
        incumbent: dict[str, float],
        rng: random.Random,
    ) -> dict[str, float]:
        """Gaussian perturbation around incumbent, clamped to bounds."""
        out: dict[str, float] = {}
        for name, param in TUNABLE_PARAMS.items():
            center = incumbent.get(name, param.default)
            sigma = (param.max_value - param.min_value) / 6.0
            value = rng.gauss(center, sigma)
            out[name] = clamp_value(name, value)
        return out

    # ------------------------------------------------------------------- #
    # Fitness evaluation
    # ------------------------------------------------------------------- #

    def evaluate_candidate(
        self,
        params: dict[str, float],
    ) -> float:
        """Evaluate a candidate against C1 fitness via live retrieval eval.

        Tries live eval first (real retrieval per candidate). Falls back
        to trace-proxy eval when live eval cannot complete. Fail-open:
        returns ``0.0`` when evaluation cannot complete (so the candidate
        is never promoted over a valid incumbent).
        """
        try:
            return self._fitness_from_live_eval(params)
        except Exception as exc:
            log.warning("live eval failed, falling back to traces: %s", exc)
            try:
                return self._fitness_from_traces(params)
            except Exception as exc2:  # noqa: BLE001 — fail-open
                log.warning("trace fallback also failed: %s", exc2)
                return 0.0

    def _fitness_from_live_eval(self, params: dict[str, float]) -> float:
        """Faithful multi-objective eval: run retrieval with candidate params.

        Measures real retrieval_quality (success-rate@5) and session_health
        (re-query-rate) by running fixture queries through the embedder
        with the candidate's retrieval parameters applied.

        Returns 0.0 if fixtures or embedder unavailable (fail-open).
        """
        from .embedder import GraphEmbedder
        from .fixtures import load_fixture_queries

        if self.project_path is None:
            return 0.0

        fixture_queries = load_fixture_queries(self.project_path, n=20)
        if not fixture_queries:
            return 0.0

        try:
            embedder = GraphEmbedder(str(self.project_path))
            if not embedder.load_graph():
                return 0.0
        except Exception:
            return 0.0

        structural_seed_k = int(round(params.get("STRUCTURAL_SEED_K", 3)))
        synapse_seed_k = int(round(params.get("SYNAPSE_SEED_K", 3)))
        search_n = max(structural_seed_k, synapse_seed_k) * 5

        successes = 0
        re_queries = 0
        queries_attempted = 0
        for fq in fixture_queries:
            try:
                results = embedder.search(fq.query, n=max(search_n, 10))
            except Exception:
                continue

            queries_attempted += 1
            # success = any expected node id in retrieved set
            retrieved_ids = {r.get("id", "") for r in results}
            if fq.expected_node_ids:
                if any(eid in retrieved_ids for eid in fq.expected_node_ids):
                    successes += 1
            elif results:
                successes += 1

            # Re-query proxy: queries returning zero results force the user
            # to re-phrase. This varies with search_n (retrieval depth),
            # which is candidate-dependent.
            if not results:
                re_queries += 1

        # Denominator is total fixtures, not just non-throwing ones.
        # Otherwise candidates that cause embedder failures on hard queries
        # get inflated success rates (denominator shrinks).
        retrieval_quality = successes / len(fixture_queries) if fixture_queries else 0.0
        session_health = (
            max(0.0, min(1.0, 1.0 - re_queries / len(fixture_queries))) if fixture_queries else 1.0
        )
        efficiency = self._efficiency_ratio(params)

        inputs = FitnessInputs(
            retrieval_quality=retrieval_quality,
            efficiency=efficiency,
            session_health=session_health,
        )
        return compute_fitness(inputs).total

    def _fitness_from_traces(
        self,
        params: dict[str, float],
    ) -> float:
        """Derive a C1 fitness score from reasoning traces + param map.

        LIMITATION: The retrieval_quality and session_health proxies are
        derived from *historical* traces that are fixed across candidates,
        so only the efficiency axis (total L0-L3 budget) actually varies.
        This makes the tuner effectively a single-variable budget optimizer.

        A faithful multi-objective eval would re-run retrieval with each
        candidate and measure real faithfulness delta — see TRD §4.2 steps
        2-4. That wiring is out of scope for this release; the proxy
        stature is documented here so the limitation isn't mistaken
        for a real measurement.

        Returns 0.0 if traces are unavailable (fail-open: an
        un-evaluable candidate is never promoted over a valid incumbent).
        """
        from .synapses import default_db_path
        from .traces import TraceStore

        if self.project_path is None:
            return 0.0

        traces_path = default_db_path(self.project_path)
        ts = TraceStore(traces_path)
        cutoff = time.time() - (self.eval_days * 86400)
        traces = ts.query(since=cutoff, limit=1000)

        if not traces:
            return 0.0

        # Retrieval quality proxy: weighted mean success signal.
        success_total = sum(t.success_signal for t in traces if math.isfinite(t.success_signal))
        retrieval_quality = success_total / len(traces)

        # Efficiency proxy: compare candidate's L0-L3 token budget to default.
        eff = self._efficiency_ratio(params)

        # Session health proxy: re-query rate from trace collisions.
        re_rate = self._re_query_rate_from_traces(traces)
        session_health = max(0.0, min(1.0, 1.0 - re_rate))

        inputs = FitnessInputs(
            retrieval_quality=retrieval_quality,
            efficiency=eff,
            session_health=session_health,
        )
        score = compute_fitness(inputs)
        return score.total

    def _efficiency_ratio(self, params: dict[str, float]) -> float:
        """Estimate token efficiency relative to the default budget."""
        default_map = self._default_param_map()
        default_budget = (
            default_map.get("L0_MAX_TOKENS", 150)
            + default_map.get("L1_MAX_TOKENS", 600)
            + default_map.get("L2_MAX_TOKENS", 800)
            + default_map.get("L3_MAX_TOKENS", 1000)
        )
        candidate_budget = (
            params.get("L0_MAX_TOKENS", 150)
            + params.get("L1_MAX_TOKENS", 600)
            + params.get("L2_MAX_TOKENS", 800)
            + params.get("L3_MAX_TOKENS", 1000)
        )
        if candidate_budget <= 0:
            return 1.0
        # Cap so clamp-minimum budgets cannot push fitness unboundedly high.
        # TUNABLE_PARAMS bounds currently limit L0-L3 minima to ~50/200/400/500,
        # yielding a raw ratio of ~2.2x at the clamp floor; 10x ceiling provides
        # headroom against future bound changes while preventing float overflow.
        return min(default_budget / candidate_budget, 10.0)

    def _re_query_rate_from_traces(self, traces: list[Any]) -> float:
        """Estimate re-query rate: fraction of traces sharing fingerprints."""
        if not traces:
            return 0.0
        from collections import Counter

        counts = Counter(t.query_fingerprint for t in traces)
        total = len(traces)
        # Fingerprints appearing more than once ≈ re-query signal.
        repeats = sum(c - 1 for c in counts.values() if c > 1)
        return repeats / total if total > 0 else 0.0

    # ------------------------------------------------------------------- #
    # Promotion
    # ------------------------------------------------------------------- #

    def promote_if_better(
        self,
        candidate: dict[str, float],
        fitness: float,
        incumbent_fitness: float,
    ) -> bool:
        """Promote candidate if fitness > incumbent * (1 + hysteresis)."""
        return fitness > incumbent_fitness * (1.0 + self.hysteresis)

    def promote_with_harness(
        self,
        candidate_params: dict[str, float],
        candidate_fitness: float,
        incumbent_fitness: float,
    ) -> Any:
        """Validate candidate with harness before promoting.

        Returns PromotionDecision with verdict + rationale.
        Backward compatible: if harness is None, falls back to
        hysteresis-only promotion.
        """
        from .quality_harness import PromotionDecision

        if self.harness is None:
            if self.promote_if_better(candidate_params, candidate_fitness, incumbent_fitness):
                self._save_incumbent(candidate_params, candidate_fitness)
                return PromotionDecision(
                    verdict="promote",
                    reason="harness disabled, hysteresis only",
                    candidate_fitness=candidate_fitness,
                    incumbent_fitness=incumbent_fitness,
                    harness_verdict=None,
                )
            return PromotionDecision(
                verdict="hold",
                reason="below hysteresis",
                candidate_fitness=candidate_fitness,
                incumbent_fitness=incumbent_fitness,
                harness_verdict=None,
            )

        verdict = self.harness.evaluate(candidate_params)
        decision = self.harness.decide(
            candidate_fitness, incumbent_fitness, verdict, self.hysteresis
        )

        if decision.verdict == "promote":
            self._save_incumbent(candidate_params, verdict.fitness)
        elif decision.verdict == "rollback":
            pass  # incumbent stands
        # hold: nothing

        return decision

    def _record_decision(self, decision: Any) -> None:
        """Persist the last promotion decision to the synapse meta table."""
        try:
            store = self._store()
            store.set_meta(
                META_TUNER_LAST_DECISION,
                json.dumps({
                    "verdict": decision.verdict,
                    "reason": decision.reason,
                    "candidate_fitness": decision.candidate_fitness,
                    "incumbent_fitness": decision.incumbent_fitness,
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }),
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("_record_decision failed: %s", exc)

    # ------------------------------------------------------------------- #
    # Runner
    # ------------------------------------------------------------------- #

    def run_generation(self) -> TuneRun | None:
        """Run evolutionary search across ``self.generations`` generations.

        Each generation samples ``self.population_size`` candidates,
        evaluates them, and (if a candidate beats the incumbent by the
        hysteresis margin) promotes it. Returns the result of the final
        generation, or ``None`` if the tuner is a no-op.
        """
        if self.project_path is None:
            return None

        incumbent = self._load_incumbent()
        incumbent_fitness = self._load_incumbent_fitness()
        if incumbent_fitness == 0.0:
            incumbent_fitness = self.evaluate_candidate(incumbent)
            # Don't persist 0.0 — would wipe genuine stored fitness if
            # eval failed transiently, causing spurious promotion next run.
            if incumbent_fitness > 0.0:
                self._save_incumbent(incumbent, incumbent_fitness)

        best_params = incumbent
        best_fitness = incumbent_fitness
        promoted = False

        # Multi-generation loop. Each generation samples a new population
        # around the current incumbent (which may have been promoted at the
        # end of the previous generation).
        for _gen in range(self.generations):
            rng = random.Random()
            gen_best_params = incumbent
            gen_best_fitness = self.evaluate_candidate(incumbent)
            for _ in range(self.population_size):
                candidate_map = self.sample_candidate(incumbent, rng=rng)
                candidate_fitness = self.evaluate_candidate(candidate_map)
                if candidate_fitness > gen_best_fitness:
                    gen_best_fitness = candidate_fitness
                    gen_best_params = candidate_map

            # C4: if harness is present, validate candidate independently
            # before promoting. The harness is the independent gate that
            # prevents the tuner from promoting based on self-measurement.
            if self.harness is not None:
                decision = self.promote_with_harness(
                    gen_best_params, gen_best_fitness, incumbent_fitness
                )
                self._last_decision = decision
                self._record_decision(decision)
                if decision.verdict == "promote":
                    incumbent = gen_best_params
                    incumbent_fitness = decision.harness_verdict.fitness if decision.harness_verdict else gen_best_fitness
                    best_params = gen_best_params
                    best_fitness = incumbent_fitness
                    promoted = True
                else:
                    best_params = gen_best_params
                    best_fitness = gen_best_fitness
            elif self.promote_if_better(gen_best_params, gen_best_fitness, incumbent_fitness):
                self._save_incumbent(gen_best_params, gen_best_fitness)
                incumbent = gen_best_params
                incumbent_fitness = gen_best_fitness
                best_params = gen_best_params
                best_fitness = gen_best_fitness
                promoted = True
            else:
                # No improvement this generation — carry forward.
                best_params = gen_best_params
                best_fitness = gen_best_fitness

        return TuneRun(
            generation=self.generations - 1,
            population_size=self.population_size,
            best_fitness=best_fitness,
            incumbent_fitness=incumbent_fitness,
            promoted=promoted,
            best_params=dict(best_params),
        )

    # ------------------------------------------------------------------- #
    # Persistence (synapse meta table)
    # ------------------------------------------------------------------- #

    def _store(self) -> Any:
        """Lazily load the synapse store (project_path guaranteed non-None here)."""
        if self.project_path is None:
            raise RuntimeError("PopulationTuner: project_path required for persistence")
        from .synapses import SynapseStore, default_db_path

        return SynapseStore(default_db_path(self.project_path))

    def _load_incumbent(self) -> dict[str, float]:
        try:
            raw = self._store().get_meta(META_TUNER_INCUMBENT)
            if raw:
                loaded = json.loads(raw)
                if isinstance(loaded, dict):
                    # Filter to known tuneable params.
                    return {k: float(v) for k, v in loaded.items() if k in TUNABLE_PARAMS}
        except Exception:
            pass
        return self._default_param_map()

    def _load_incumbent_fitness(self) -> float:
        try:
            raw = self._store().get_meta(META_TUNER_FITNESS)
            if raw:
                return float(raw)
        except Exception:
            pass
        return 0.0

    def _save_incumbent(self, params: dict[str, float], fitness: float) -> None:
        try:
            clean = {k: round(v, 6) for k, v in params.items() if k in TUNABLE_PARAMS}
            store = self._store()
            store.set_meta(META_TUNER_INCUMBENT, json.dumps(clean, sort_keys=True))
            store.set_meta(META_TUNER_FITNESS, f"{fitness:.6f}")
            store.set_meta(META_TUNER_PROMOTED_AT, time.strftime("%Y-%m-%dT%H:%M:%S"))
        except Exception as exc:  # noqa: BLE001
            log.warning("_save_incumbent failed: %s", exc)

    # ----------------------------------------------------------------------- #
    # Scheduling gate (used by the daemon when NEURALMIND_TUNER_ENABLED=1)
    # ----------------------------------------------------------------------- #

    META_RUN_INTERVAL = "self_improve:tuner_run_interval_days"
    META_LAST_RUN = "self_improve:tuner_last_run"

    def should_run(self) -> bool:
        """Check if enough time has passed since last tuner run."""
        try:
            raw = self._store().get_meta(self.META_LAST_RUN)
            if not raw:
                return True
            last = float(raw)
            interval_raw = self._store().get_meta(self.META_RUN_INTERVAL)
            interval = float(interval_raw) if interval_raw else 7.0
            return (time.time() - last) >= (interval * 86400)
        except Exception:
            return True

    def mark_run(self) -> None:
        """Stamp the last-run timestamp for scheduling."""
        try:
            self._store().set_meta(self.META_LAST_RUN, str(time.time()))
        except Exception:
            pass
