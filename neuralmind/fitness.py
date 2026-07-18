"""
fitness.py — Multi-objective fitness function for the self-improvement engine (PRD 2 C1).

The tuner's North Star. Three axes combined via weighted product (zero on any
axis dominates, so a config that tanks faithfulness while saving tokens still
scores ~0):

  - Retrieval quality: faithfulness delta from the RAGAS-axis offline judge
    (the "does the agent answer better" signal).
  - Efficiency: token-cost reduction ratio (the "does it cost less" signal).
  - Session health: re-query-rate + transition-margin (the "does the agent
    stop repeating itself" signal).

Weights are operator-configurable via NEURALMIND_FITNESS_WEIGHTS="0.5,0.3,0.2",
persisted in the synapse meta table, tunable per project. CI-gated: fails on
regression (not just absolute floor).

Pure and stdlib-only at the module level — deps (ragas, quality, memory) are
imported lazily so the fitness module imports cleanly in any context.
"""

from __future__ import annotations

import os
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

# Synapse meta table keys for persistence
META_KEY_FITNESS_WEIGHTS = "self_improve:fitness_weights"
META_KEY_FITNESS_BASELINE = "self_improve:fitness_baseline"
META_KEY_FITNESS_LAST = "self_improve:fitness_last"
META_KEY_FITNESS_TS = "self_improve:fitness_timestamp"

# Default weights: retrieval quality dominates, efficiency second, session health third.
DEFAULT_WEIGHTS = (0.5, 0.3, 0.2)

# Hysteresis margin: a candidate must beat the incumbent by this fraction to promote.
# Used by the tuner (C3) — not by fitness itself.
DEFAULT_HYSTERESIS = 0.05


def _parse_weights(raw: str | None) -> tuple[float, float, float]:
    """Parse a comma-separated weight string like "0.5,0.3,0.2" into a 3-tuple.

    Falls back on DEFAULT_WEIGHTS when the env var is unset, malformed, or
    doesn't normalize to a positive sum. Weights are normalized to sum to 1.0
    so the product is comparable across configurations.
    """
    if not raw:
        return DEFAULT_WEIGHTS
    try:
        parts = [float(p.strip()) for p in raw.split(",") if p.strip()]
    except (TypeError, ValueError):
        return DEFAULT_WEIGHTS
    if len(parts) != 3:
        return DEFAULT_WEIGHTS
    total = sum(parts)
    if total <= 0.0:
        return DEFAULT_WEIGHTS
    return tuple(p / total for p in parts)  # type: ignore[return-value]


def get_weights(project_path: str | Path | None = None) -> tuple[float, float, float]:
    """Read fitness weights from env var first, then synapse meta, then default."""
    env = os.environ.get("NEURALMIND_FITNESS_WEIGHTS")
    if env:
        return _parse_weights(env)
    if project_path is not None:
        from .synapses import SynapseStore, default_db_path

        try:
            store = SynapseStore(default_db_path(project_path))
            raw = store.get_meta(META_KEY_FITNESS_WEIGHTS)
            if raw:
                return _parse_weights(raw)
        except Exception:
            pass
    return DEFAULT_WEIGHTS


def set_weights(
    project_path: str | Path,
    weights: tuple[float, float, float],
) -> None:
    """Persist fitness weights to the synapse meta table (normalized)."""
    total = sum(weights)
    if total <= 0.0:
        return
    normalized = tuple(w / total for w in weights)
    from .synapses import SynapseStore, default_db_path

    store = SynapseStore(default_db_path(project_path))
    store.set_meta(META_KEY_FITNESS_WEIGHTS, ",".join(f"{w:.4f}" for w in normalized))


@dataclass
class FitnessInputs:
    """The three raw signals the fitness function consumes.

    retrieval_quality: faithfulness delta from the RAGAS-axis judge (0..1+).
    efficiency: token-cost reduction ratio (1.0 = baseline, higher = cheaper).
    session_health: 1.0 - re_query_rate (1.0 = healthy, no re-queries).
    """

    retrieval_quality: float = 0.0
    efficiency: float = 1.0
    session_health: float = 1.0


@dataclass
class FitnessScore:
    """A computed fitness score with decomposition for explainability."""

    total: float
    retrieval_quality: float
    efficiency: float
    session_health: float
    weights: tuple[float, float, float]
    components: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total": round(self.total, 6),
            "retrieval_quality": round(self.retrieval_quality, 4),
            "efficiency": round(self.efficiency, 4),
            "session_health": round(self.session_health, 4),
            "weights": [round(w, 4) for w in self.weights],
            "components": {k: round(v, 6) for k, v in self.components.items()},
        }


def _clamp(value: float, lo: float = 0.0, hi: float | None = None) -> float:
    """Clamp value to [lo, hi]. If hi is None, no upper bound. NaN/Inf → lo."""
    if math.isnan(value) or math.isinf(value):
        return lo
    if value < lo:
        return lo
    if hi is not None and value > hi:
        return hi
    return value


def compute_fitness(
    inputs: FitnessInputs,
    weights: tuple[float, float, float] | None = None,
) -> FitnessScore:
    """Compute the multi-objective fitness score via weighted product.

    The product form means a zero on any axis dominates: a config that
    achieves perfect efficiency but zero retrieval quality scores 0.0, which
    is correct (an agent that's fast but wrong is worthless).

    For numerical stability with small weights, we use the log-space form:
    log(product) = sum(w_i * log(x_i)), then exp() the result.
    """
    import math

    if weights is None:
        weights = DEFAULT_WEIGHTS

    # Clamp inputs: rq and sh are bounded [0, 1]. Efficiency > 1.0 is
    # valid (reduction ratio 2.0 = half the tokens) and must NOT be clamped.
    rq = _clamp(inputs.retrieval_quality, 0.0, 1.0)
    # Efficiency has no documented upper bound, but clamp to defend against
    # float overflow from pathological efficiency_ratio values.
    ef = min(inputs.efficiency, 10.0)
    sh = _clamp(inputs.session_health, 0.0, 1.0)

    # Weighted product in log space: avoids underflow with small weights.
    # When any component is exactly 0, the product is 0 (correct dominance).
    if rq == 0.0 or ef == 0.0 or sh == 0.0:
        total = 0.0
    else:
        log_sum = weights[0] * math.log(rq) + weights[1] * math.log(ef) + weights[2] * math.log(sh)
        total = math.exp(log_sum)

    return FitnessScore(
        total=round(total, 6),
        retrieval_quality=rq,
        efficiency=ef,
        session_health=sh,
        weights=weights,
        components={
            "rq_term": rq ** weights[0] if rq > 0 else 0.0,
            "ef_term": ef ** weights[1] if ef > 0 else 0.0,
            "sh_term": sh ** weights[2] if sh > 0 else 0.0,
        },
    )


def session_health_from_events(
    events: list[dict],
    *,
    re_query_rate_override: float | None = None,
) -> float:
    """Derive the session health signal from logged query events.

    1.0 - re_query_rate, clamped to [0, 1]. A session with no re-queries
    scores 1.0; a session where every query is a re-query scores 0.0.
    """
    if re_query_rate_override is not None:
        return _clamp(1.0 - re_query_rate_override, 0.0, 1.0)
    if not events:
        return 1.0
    from .memory import re_query_rate

    rate = re_query_rate(events)
    return _clamp(1.0 - rate, 0.0, 1.0)


def compute_fitness_from_events(
    events: list[dict],
    *,
    faithfulness_delta: float,
    reduction_ratio: float,
    weights: tuple[float, float, float] | None = None,
) -> FitnessScore:
    """Convenience: derive session health from events and compute fitness."""
    sh = session_health_from_events(events)
    inputs = FitnessInputs(
        retrieval_quality=faithfulness_delta,
        efficiency=reduction_ratio,
        session_health=sh,
    )
    return compute_fitness(inputs, weights=weights)
