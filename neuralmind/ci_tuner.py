"""
C4 — CI-gated tuner promotion.

The tuner (C3) proposes configs. Promotion must be CI-gated against
the fixture query set with hysteresis. Runs as a local
`neuralmindbenchmark --tuner-ci` command: tuner proposes → fitness eval
on fixtures → promote only if fitness beats incumbent by margin.

Requires C3 (done) + D (done: fitness.py, quality.py).

Local-first. Stdlib-only. Fail-open.
"""

from __future__ import annotations

import json
import os
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
    register_param,
)




@dataclass
class PromotionVerdict:
    """Result of a CI-gated promotion check."""
    promoted: bool
    candidate_fitness: float
    incumbent_fitness: float
    best_params: dict[str, float]
    reason: str = ""
    generation: int = 0
    hysteresis: float = 0.05

    def to_dict(self) -> dict:
        return {
            "promoted": self.promoted,
            "candidate_fitness": round(self.candidate_fitness, 6),
            "incumbent_fitness": round(self.incumbent_fitness, 6),
            "hysteresis": self.hysteresis,
            "threshold": round(self.incumbent_fitness * (1.0 + self.hysteresis), 6),
            "generation": self.generation,
            "reason": self.reason,
        }



class CIGatedTuner:
    """
    CI-gated tuner promotion. Wraps the population-based tuner (C3)
    with a fixture-evaluated promotion gate.

    Usage:
        tuner = CIGatedTuner(project_path)
        result = tuner.run_ci_eval()
        if result.promoted:
            tuner.promote(result.best_params)
    """

    def __init__(
        self,
        project_path: str | Path | None = None,
        population_size: int | None = None,
        generations: int | None = None,
        hysteresis: float | None = None,
    ):
        from .tuner import PopulationTuner
        self.tuner = PopulationTuner(
            project_path=project_path,
            population_size=population_size,
            generations=generations,
            hysteresis=hysteresis,
        )
        self.project_path = Path(project_path) if project_path else None

    def run_ci_eval(self) -> PromotionVerdict:
        """
        Run tuner generation and evaluate against CI gate.
        
        Returns PromotionVerdict with promotion decision.
        """
        tune_result = self.tuner.run_generation()
        if tune_result is None:
            return PromotionVerdict(
                promoted=False,
                candidate_fitness=0.0,
                incumbent_fitness=0.0,
                best_params={},
                reason="tuner returned None (no eval data)",
            )

        candidate_fitness = tune_result.best_fitness
        incumbent_fitness = tune_result.incumbent_fitness
        promoted = tune_result.promoted

        return PromotionVerdict(
            promoted=promoted,
            candidate_fitness=candidate_fitness,
            incumbent_fitness=incumbent_fitness,
            best_params=tune_result.best_params,
            generation=tune_result.generation,
            hysteresis=self.tuner.hysteresis,
            reason=f"gen {tune_result.generation}: {'promoted' if promoted else 'no improvement'}",
        )

    def promote(self, params: dict[str, float], fitness: float | None = None) -> bool:
        """Persist promoted params + fitness to synapse meta. Fail-open."""
        if self.project_path is None:
            return False
        try:
            from .synapses import SynapseStore, default_db_path

            store = SynapseStore(default_db_path(self.project_path))
            clean = {k: round(v, 6) for k, v in params.items() if k in TUNABLE_PARAMS}
            store.set_meta(META_TUNER_INCUMBENT, json.dumps(clean, sort_keys=True))
            if fitness is not None:
                store.set_meta(META_TUNER_FITNESS, f"{fitness:.6f}")
                store.set_meta(META_TUNER_PROMOTED_AT, time.strftime("%Y-%m-%dT%H:%M:%S"))
            return True
        except Exception:
            return False


def run_ci_gated_promotion(
    project_path: str | Path | None = None,
    *,
    verbose: bool = False,
) -> dict:
    """Entry point for `neuralmind benchmark --tuner-ci`."""
    tuner = CIGatedTuner(project_path=project_path)
    result = tuner.run_ci_eval()
    
    if result.promoted:
        tuner.promote(result.best_params, fitness=result.candidate_fitness)
        if verbose:
            print(f"PROMOTED: fitness {result.candidate_fitness:.4f} > {result.incumbent_fitness:.4f}")
    else:
        if verbose:
            print(f"KEPT INCUMBENT: {result.candidate_fitness:.4f} vs {result.incumbent_fitness:.4f}")
    
    return result.to_dict()


if __name__ == "__main__":
    import sys
    project = sys.argv[1] if len(sys.argv) > 1 else "."
    result = run_ci_gated_promotion(project, verbose=True)
    print(json.dumps(result, indent=2))
