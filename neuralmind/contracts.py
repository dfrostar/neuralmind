# neuralmind/contracts.py — shared definitions for Wave 3
#
# Frozen after Wave 3a spike. Consumed by every Wave 3 workstream:
#   C2/C3 (tuning parameter registry)
#   A3 (learned per-edge decay bounds/meta keys)
#   A4 (sleep consolidation meta keys)
#   F2 (shared daemon memory scopes)
#
# Local-first, stdlib-only. No heavy deps.

from __future__ import annotations

from dataclasses import dataclass

# ----------------------------------------------------------------------- #
# C2 / C3 — Tuneable parameter registry
# ----------------------------------------------------------------------- #


@dataclass(frozen=True)
class TuneableParam:
    """A single parameter the tuner can optimize.

    ``clamp()`` bounds any candidate value to ``[min_value, max_value]``.
    ``description`` explains the knob for operator-facing reports.
    """

    name: str
    min_value: float
    max_value: float
    default: float
    description: str

    def clamp(self, value: float) -> float:
        return max(self.min_value, min(self.max_value, value))


# Registry of all tuneable parameters (populated by ``tuning.py`` at
# import time). Idempotent writes via ``register_param``.
TUNABLE_PARAMS: dict[str, TuneableParam] = {}


def register_param(param: TuneableParam) -> None:
    """Register a tuneable parameter. Idempotent."""
    TUNABLE_PARAMS[param.name] = param


def get_param(name: str) -> TuneableParam | None:
    """Look up a parameter by name."""
    return TUNABLE_PARAMS.get(name)


def clamp_value(name: str, value: float) -> float:
    """Clamp a parameter value to its bounds.

    Returns ``value`` unchanged if the parameter is unknown (fail-open).
    """
    param = TUNABLE_PARAMS.get(name)
    if param is None:
        return value
    return param.clamp(value)


def registered_names() -> list[str]:
    """Return all registered parameter names (sorted, for determinism)."""
    return sorted(TUNABLE_PARAMS.keys())


# ----------------------------------------------------------------------- #
# A3 — Synapse meta table keys (learned per-edge decay)
# ----------------------------------------------------------------------- #

META_DECAY_RATE_MIN = "self_improve:decay_rate_min"
META_DECAY_RATE_MAX = "self_improve:decay_rate_max"


# ----------------------------------------------------------------------- #
# C3 — Tuner meta table keys (population-based evolutionary search)
# ----------------------------------------------------------------------- #

META_TUNER_INCUMBENT = "self_improve:tuner_incumbent_config"
META_TUNER_FITNESS = "self_improve:tuner_incumbent_fitness"
META_TUNER_PROMOTED_AT = "self_improve:tuner_promoted_at"
META_TUNER_LAST_DECISION = "self_improve:tuner_last_decision"


# ----------------------------------------------------------------------- #
# A4 — Sleep consolidation meta keys
# ----------------------------------------------------------------------- #

META_SLEEP_LAST_RUN = "self_improve:sleep_last_run"
META_SLEEP_INTERVAL_DAYS = "self_improve:sleep_interval_days"
META_SLEEP_STALE_DAYS = "self_improve:sleep_stale_days"
