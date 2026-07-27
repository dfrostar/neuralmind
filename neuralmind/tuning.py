"""tuning.py — expanded parameter space for the self-improvement engine (C2).

Maps every knob the tuner can optimize into a ``TuneableParam`` and
registers them in ``neuralmind/contracts.py``. The tuner (C3), the
context selector, the decay module, and the CLI all read from this
registry — no hardcoded constants scattered across modules.

Pure, stdlib-only, fail-open: unknown parameter names are logged and
skipped, never crash.

See Also:
    - ``neuralmind/contracts.py`` — TuneableParam dataclass + registry
    - ``neuralmind/tuner.py`` — consumer (C3)
    - ``tests/test_tuning.py`` — test cases

Version:
    0.53.0
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .contracts import TuneableParam, register_param

log = logging.getLogger(__name__)

# ----------------------------------------------------------------------- #
# Canonical parameter definitions.
#
# Bounds mirror the existing clamp constants in context_selector.py and
# synapses.py, so the tuner can never propose a value the selector would
# reject.
# ----------------------------------------------------------------------- #

DEFAULT_PARAMS: list[TuneableParam] = [
    # Synapse-driven recall (context_selector.py)
    TuneableParam(
        "SYNAPSE_SEED_K",
        1,
        10,
        3,
        "Top-k search hits that seed spreading activation",
    ),
    TuneableParam(
        "SYNAPSE_BOOST_WEIGHT",
        0.0,
        2.0,
        0.3,
        "Synapse-driven recall boost weight",
    ),
    TuneableParam(
        "SYNAPSE_PULL_IN_MAX",
        0,
        5,
        2,
        "Maximum synapse-neighbors pulled into L3 per hit",
    ),
    TuneableParam(
        "SYNAPSE_PULL_IN_MIN_ENERGY",
        0.01,
        0.5,
        0.15,
        "Minimum activation energy to pull in a synapse-neighbor",
    ),
    # Structural recall (context_selector.py)
    TuneableParam(
        "STRUCTURAL_SEED_K",
        1,
        10,
        3,
        "Top-k structural hits that seed expansion",
    ),
    TuneableParam(
        "STRUCTURAL_BOOST_WEIGHT",
        0.0,
        2.0,
        0.35,
        "Structural-edge recall boost weight (>= synapse weight)",
    ),
    TuneableParam(
        "STRUCTURAL_PULL_IN_MAX",
        0,
        5,
        2,
        "Maximum structural-neighbors pulled into L3 per hit",
    ),
    # Layer token budgets (context_selector.py)
    TuneableParam("L0_MAX_TOKENS", 50, 300, 150, "L0 identity layer token budget"),
    TuneableParam("L1_MAX_TOKENS", 200, 1000, 600, "L1 summary layer token budget"),
    TuneableParam("L2_MAX_TOKENS", 400, 1500, 800, "L2 on-demand layer token budget"),
    TuneableParam("L3_MAX_TOKENS", 500, 2000, 1000, "L3 search layer token budget"),
    # Spreading activation (synapses.py)
    TuneableParam(
        "SPREAD_DEPTH",
        1,
        5,
        2,
        "Graph spread depth (hops from seed)",
    ),
    TuneableParam(
        "SPREAD_DECAY",
        0.1,
        1.0,
        0.6,
        "Activation decay per hop during spread",
    ),
    TuneableParam(
        "SPREAD_TOP_K",
        3,
        30,
        12,
        "Top-k neighbors retained after each spread hop",
    ),
    # Hub normalization
    TuneableParam(
        "STRUCTURAL_HUB_DEGREE",
        10,
        100,
        50,
        "Degree threshold above which a node is treated as a hub",
    ),
    # Per-edge decay bounds (A3 / learned_decay.py)
    TuneableParam(
        "DECAY_RATE_MIN",
        1.0,
        30.0,
        3.0,
        "Minimum per-edge half-life (days)",
    ),
    TuneableParam(
        "DECAY_RATE_MAX",
        30.0,
        365.0,
        120.0,
        "Maximum per-edge half-life (days)",
    ),
]


# ----------------------------------------------------------------------- #
# Registry initialisation
# ----------------------------------------------------------------------- #


def init_registry() -> None:
    """Register all default parameters. Idempotent (overwrites are no-ops)."""
    for param in DEFAULT_PARAMS:
        register_param(param)


def get_bounds(name: str) -> tuple[float, float]:
    """Get ``(min, max)`` for a parameter.

    Returns ``(0.0, 1.0)`` if the name is unknown (fail-open).
    """
    from .contracts import get_param

    param = get_param(name)
    if param is None:
        return (0.0, 1.0)
    return (param.min_value, param.max_value)


def get_default(name: str) -> float:
    """Get the default value for a parameter.

    Returns ``0.0`` for unknown names (fail-open).
    """
    from .contracts import get_param

    param = get_param(name)
    if param is None:
        return 0.0
    return param.default


# ----------------------------------------------------------------------- #
# Persistence — params are stored in the synapse meta table as JSON so
# they survive restarts and are per-project.
# ----------------------------------------------------------------------- #

META_PARAMS_KEY = "self_improve:params"


def load_params(
    project_path: str | Path,
) -> dict[str, float]:
    """Read tuneable parameters from the synapse meta table.

    Returns an empty dict when nothing has been persisted yet, the store
    is unreadable, or the stored JSON is malformed (fail-open).
    """
    try:
        from .synapses import SynapseStore, default_db_path

        store = SynapseStore(default_db_path(project_path))
        raw = store.get_meta(META_PARAMS_KEY)
        if not raw:
            return {}
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return {}
        return {k: float(v) for k, v in parsed.items() if isinstance(v, (int, float))}
    except Exception as exc:  # noqa: BLE001 — fail-open
        log.debug("load_params failed: %s", exc)
        return {}


def save_params(
    project_path: str | Path,
    params: dict[str, float],
) -> bool:
    """Persist tuneable parameters to the synapse meta table.

    Unknown keys are skipped (logged). Returns ``False`` on any error
    (fail-open — never raises).
    """
    from .contracts import get_param

    try:
        clean: dict[str, float] = {}
        for k, v in params.items():
            if get_param(k) is None:
                log.warning("save_params: skipping unknown parameter %r", k)
                continue
            clean[k] = float(v)
        from .synapses import SynapseStore, default_db_path

        store = SynapseStore(default_db_path(project_path))
        store.set_meta(META_PARAMS_KEY, json.dumps(clean, sort_keys=True))
        return True
    except Exception as exc:  # noqa: BL0001 — fail-open
        log.warning("save_params failed: %s", exc)
        return False


def resolve_effective(
    project_path: str | Path | None,
) -> dict[str, float]:
    """Return the effective parameter map: persisted overrides + defaults.

    Order: registry default ← persisted override.
    """
    from .contracts import TUNABLE_PARAMS

    effective = {name: p.default for name, p in TUNABLE_PARAMS.items()}
    if project_path is not None:
        persisted = load_params(project_path)
        for k, v in persisted.items():
            if k in effective:
                effective[k] = v
    return effective


# ----------------------------------------------------------------------- #
# Selector integration helpers
#
# These thin wrappers let ``context_selector.py`` (and any future caller)
# read the effective value of a knob without knowing about persistence.
# ----------------------------------------------------------------------- #


def effective_int(project_path: str | Path | None, name: str) -> int:
    """Read a tuneable param as int (layer budgets)."""
    return int(round(resolve_effective(project_path).get(name, get_default(name))))


def effective_float(project_path: str | Path | None, name: str) -> float:
    """Read a tuneable param as float (weights / decay rates)."""
    return resolve_effective(project_path).get(name, get_default(name))


# Eagerly register at import time so any caller that imports
# ``neuralmind.contracts`` sees the canonical set.
init_registry()
