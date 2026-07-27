"""learned_decay.py — per-edge half-life rates adapted from reinforcement history (A3).

Replaces fixed HALF_LIFE_DAYS scalars with per-edge rates. Bounded to
[DECAY_RATE_MIN, DECAY_RATE_MAX]. The C3 tuner learns the bounds;
this module adapts individual edges based on reinforcement frequency
and recency.

Pure, stdlib-only, fail-open.

See Also:
    - ``neuralmind/contracts.py`` — decay meta key constants
    - ``neuralmind/synapses.py`` — stores per-edge half_life_days
    - ``tests/test_learned_decay.py`` — test cases

Version:
    0.53.0
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any

from .tuning import resolve_effective

log = logging.getLogger(__name__)

LN2 = 0.6931471805599453


def default_bounds(
    project_path: Any = None,
) -> tuple[float, float]:
    """Read (DECAY_RATE_MIN, DECAY_RATE_MAX) from the effective param map.

    Defaults: (3.0, 120.0) — bounded so a rarely-used edge never goes
    shorter than 3 days and a heavily-used edge never longer than 120 days.
    """
    eff = resolve_effective(project_path)
    lo = eff.get("DECAY_RATE_MIN", 3.0)
    hi = eff.get("DECAY_RATE_MAX", 120.0)
    return float(lo), float(hi)


def compute_edge_half_life(
    activation_count: int,
    last_activated: float,
    first_activated: float,
    namespace_default: float,
    project_path: Any = None,
    min_floor: float | None = None,
) -> float:
    """Adapt half-life from reinforcement frequency + recency.

    - Edges with frequent reinforcement get longer half-lives.
    - Edges that are rarely reinforced decay faster.
    - Bounded to [DECAY_RATE_MIN, DECAY_RATE_MAX].

    ``activation_count`` is total lifetime activations. ``last_activated``
    and ``first_activated`` are unix timestamps. ``namespace_default`` is
    the namespace's canonical half-life (fallback when the edge is too new
    to have a meaningful rate).

    ``min_floor`` sets the minimum learned half-life. Defaults to ``lo``
    from the effective param map. For shared-team namespaces, pass
    ``namespace_default`` so the learned rate never falls below the
    namespace's sticky baseline.
    """
    lo, hi = default_bounds(project_path)
    if min_floor is not None:
        lo = max(lo, min_floor)
    now = time.time()

    # Age of the edge in days.
    age_days = max(0.0, (now - first_activated) / 86400.0)
    if age_days < 1.0:
        # Too young — fall back to namespace default.
        return max(lo, min(hi, namespace_default))

    # Reinforcement frequency: activations per day.
    freq = activation_count / age_days

    # Recency confidence: high when the edge was activated recently, decays
    # away with inactivity (at the namespace default's half-life pace). When
    # confidence is high we trust the learned value; when low we revert to
    # the namespace default.
    days_since_last = max(0.0, (now - last_activated) / 86400.0)
    recency_confidence = math.exp(-LN2 * days_since_last / namespace_default)

    # Map frequency → half-life. The function is monotonic but saturating:
    # freq=0 → lo, freq=∞ → hi. At freq=1/day ≈ midpoint.
    try:
        ratio = math.log1p(freq * age_days / 10.0)
    except ValueError:
        ratio = 0.0
    learned = lo + (hi - lo) * (ratio / (1.0 + ratio))
    # Blend: confident (fresh) → learned value, stale → namespace default.
    blended = (1.0 - recency_confidence) * namespace_default + recency_confidence * learned
    return max(lo, min(hi, blended))


def update_learned_half_life(
    store: Any,
    node_a: str,
    node_b: str,
    namespace: str | None = None,
    project_path: Any = None,
    conn: Any = None,
) -> float | None:
    """Recompute and persist the per-edge half-life for a synapse.

    Returns the learned value, or ``None`` on any failure (fail-open).

    If ``conn`` is provided, the function uses it instead of opening a new
    connection. This lets ``reinforce()`` compute learned half-lives within
    its existing upsert transaction.
    """
    try:
        from .synapses import SHARED_NAMESPACE, _canonical

        canonical = _canonical(node_a, node_b)
        if canonical is None:
            return None
        a, b = canonical
        ns = namespace or store.namespace

        def _compute_and_update(existing_conn):
            cur = existing_conn.execute(
                """SELECT weight, activation_count, last_activated, created_at,
                          half_life_days
                   FROM synapses WHERE node_a = ? AND node_b = ? AND namespace = ?""",
                (a, b, ns),
            )
            row = cur.fetchone()
            if row is None:
                return None
            weight, act_count, last_act, created_at, existing = row

            from .synapses import HALF_LIFE_DAYS, NAMESPACE_HALF_LIVES

            ns_default = NAMESPACE_HALF_LIVES.get(ns, HALF_LIFE_DAYS)

            learned = compute_edge_half_life(
                activation_count=act_count,
                last_activated=last_act,
                first_activated=created_at,
                namespace_default=ns_default,
                project_path=project_path,
                min_floor=ns_default if ns == SHARED_NAMESPACE else None,
            )
            existing_conn.execute(
                "UPDATE synapses SET half_life_days = ?, learned_at = ? "
                "WHERE node_a = ? AND node_b = ? AND namespace = ?",
                (learned, time.time(), a, b, ns),
            )
            return learned

        if conn is not None:
            return _compute_and_update(conn)
        with store._connect() as new_conn:
            return _compute_and_update(new_conn)
    except Exception as exc:  # noqa: BLE001 — fail-open
        log.debug("update_learned_half_life failed: %s", exc)
        return None
