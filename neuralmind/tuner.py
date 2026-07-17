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
    META_TUNER_PROMOTED_AT,
    TUNABLE_PARAMS,
    TuneableParam,
    clamp_value,
    get_param,
)
from .fitness import FitnessInputs, FitnessScore, compute_fitness
from .tuning import resolve_effective

log = logging.getLogger(__name__)


# ----------------------------------------------------------------------- #
# Dataclasses
# ----------------------------------------------------------------------- #


@dataclass
class CandidateConfig:
    """One candidate parameter set."""

    params: dict[str, float]
    fitness: float = 0.0


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
        self._rng = random.Random()

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
        store: Any | None = None,
    ) -> float:
        """Evaluate a candidate against C1 fitness on real query traces.

        Uses ``reasoning_traces`` from A1 when available. Fail-open:
        returns ``0.0`` when evaluation cannot complete (so the candidate
        is never promoted over a valid incumbent).
        """
        try:
            return self._fitness_from_traces(params, store)
        except Exception as exc:  # noqa: BLE001 — fail-open
            log.warning("evaluate_candidate failed: %s", exc)
            return 0.0

    def _fitness_from_traces(
        self,
        params: dict[str, float],
        store: Any | None,
    ) -> float:
        """Derive a C1 fitness score from reasoning traces + param map."""
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
        success_total = sum(t.success_signal for t in traces)
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
        return default_budget / candidate_budget

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

    # ------------------------------------------------------------------- #
    # Runner
    # ------------------------------------------------------------------- #

    def run_generation(self) -> TuneRun | None:
        """Run one full generation (population sample + eval + promote).

        Returns ``None`` when no-op (no project, empty traces, etc.).
        """
        if self.project_path is None:
            return None

        incumbent = self._load_incumbent()
        incumbent_fitness = self._load_incumbent_fitness()
        if incumbent_fitness == 0.0:
            incumbent_fitness = self.evaluate_candidate(incumbent)
            self._save_incumbent(incumbent, incumbent_fitness)

        rng = random.Random()
        best_params = incumbent
        best_fitness = incumbent_fitness
        for _ in range(self.population_size):
            candidate_map = self.sample_candidate(incumbent, rng=rng)
            candidate_fitness = self.evaluate_candidate(candidate_map)
            if candidate_fitness > best_fitness:
                best_fitness = candidate_fitness
                best_params = candidate_map

        promoted = False
        if self.promote_if_better(best_params, best_fitness, incumbent_fitness):
            self._save_incumbent(best_params, best_fitness)
            promoted = True

        return TuneRun(
            generation=0,
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
