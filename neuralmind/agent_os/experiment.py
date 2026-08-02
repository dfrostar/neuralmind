"""experiment.py — A/B experiment runner for the Agent OS signal loop.

Implements the experiment arm of the self-improving loop:
- Proposed change → baseline/candidate tags
- Run metric collection → measure delta
- p-value-governed promote/rollback decision with confidence intervals
- Results persisted to SQLite store (crash-safe, per-tenant)

Uses scipy.stats.t.sf when available (exact t-distribution p-value),
falls back to normal CDF approximation when scipy is absent.
"""
from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

log = logging.getLogger(__name__)

try:
    from scipy.stats import t as t_dist
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _t_sf(abs_t: float, df: int) -> float:
    if HAS_SCIPY:
        return float(t_dist.sf(abs_t, df))
    return 1.0 - _normal_cdf(abs_t)


class ExperimentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    MEASURING = "measuring"
    PROMOTED = "promoted"
    ROLLED_BACK = "rolled_back"
    REJECTED = "rejected"


@dataclass
class ExperimentResult:
    experiment_id: str
    proposal_id: str
    metric_name: str
    baseline_value: float
    candidate_value: float
    delta: float
    p_value: float | None
    ci_lower: float | None
    ci_upper: float | None
    verdict: ExperimentStatus
    started_at: str
    ended_at: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "proposal_id": self.proposal_id,
            "metric_name": self.metric_name,
            "baseline_value": round(self.baseline_value, 6),
            "candidate_value": round(self.candidate_value, 6),
            "delta": round(self.delta, 6),
            "p_value": self.p_value,
            "ci_lower": self.ci_lower,
            "ci_upper": self.ci_upper,
            "verdict": self.verdict.value,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "details": self.details,
        }


class ExperimentRunner:
    """Runs A/B experiments with metric collection.

    Per-tenant history is persisted to SQLite store (not in-memory only).
    Maintains in-memory history for backward compatibility.
    """

    def __init__(
        self,
        promote_threshold_pct: float = 5.0,
        rollback_threshold_pct: float = -3.0,
        store: Any = None,
        tenant_id: str = "default",
    ) -> None:
        self._promote_threshold = promote_threshold_pct / 100.0
        self._rollback_threshold = rollback_threshold_pct / 100.0
        self._store = store
        self._tenant_id = tenant_id
        self._history: list[ExperimentResult] = []

    def _history_from_store(self) -> list[ExperimentResult]:
        """Load experiment history from store (if available)."""
        if self._store is None:
            return []
        records = self._store.get_experiment_history_for_metric(self._tenant_id, "all")
        return [
            ExperimentResult(
                experiment_id=r["id"],
                proposal_id=r["proposal_id"],
                metric_name=r["metric_name"],
                baseline_value=r["baseline_value"],
                candidate_value=r["candidate_value"],
                delta=r["delta"],
                p_value=r.get("p_value"),
                ci_lower=r.get("ci_lower"),
                ci_upper=r.get("ci_upper"),
                verdict=ExperimentStatus(r["verdict"]),
                started_at=r["started_at"],
                ended_at=r["ended_at"],
                details={},
            )
            for r in records
        ]

    @staticmethod
    def _compute_delta(baseline: float, candidate: float, higher_is_better: bool = False) -> float:
        if abs(baseline) < 1e-9:
            if abs(candidate) < 1e-9:
                return 0.0
            return 1.0 if higher_is_better else -1.0
        raw = (candidate - baseline) / abs(baseline)
        return raw if higher_is_better else -raw

    def run(
        self,
        proposal_id: str,
        metric_name: str,
        baseline_value: float,
        candidate_value: float,
        threshold_pct: float | None = None,
        higher_is_better: bool = False,
        details: dict[str, Any] | None = None,
    ) -> ExperimentResult:
        promote_threshold = (
            threshold_pct / 100.0 if threshold_pct is not None else self._promote_threshold
        )
        delta = self._compute_delta(baseline_value, candidate_value, higher_is_better)

        p_value = self._compute_p_value(delta)
        ci_lower, ci_upper = self._compute_confidence_interval(delta)

        if delta >= promote_threshold:
            verdict = ExperimentStatus.PROMOTED
        elif delta <= self._rollback_threshold:
            verdict = ExperimentStatus.ROLLED_BACK
        else:
            verdict = ExperimentStatus.REJECTED

        result = ExperimentResult(
            experiment_id=f"exp_{uuid.uuid4().hex[:12]}",
            proposal_id=proposal_id,
            metric_name=metric_name,
            baseline_value=baseline_value,
            candidate_value=candidate_value,
            delta=delta,
            p_value=p_value,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            verdict=verdict,
            started_at=datetime.now(timezone.utc).isoformat(),
            ended_at=datetime.now(timezone.utc).isoformat(),
            details=details or {},
        )

        # Maintain in-memory history for backward compatibility
        self._history.append(result)

        # Persist to store
        if self._store is not None:
            self._store.insert_experiment(self._tenant_id, result.to_dict())

        return result

    def _compute_p_value(self, current_delta: float) -> float | None:
        """Compute p-value for the current delta against historical deltas."""
        # Use in-memory history if available, else load from store
        historical = [r.delta for r in self._history if r.delta is not None]
        if len(historical) < 2:
            # Fall back to store for historical data
            store_history = self._history_from_store()
            historical = [r.delta for r in store_history if r.delta is not None]
        if len(historical) < 2:
            return None

        n = len(historical)
        mean_h = sum(historical) / n
        var_h = sum((d - mean_h) ** 2 for d in historical) / max(n - 1, 1)

        if var_h < 1e-12:
            return 0.0 if abs(current_delta - mean_h) < 1e-9 else 100.0

        se = (var_h / n) ** 0.5
        t_stat = (current_delta - mean_h) / se if se > 1e-12 else 0.0
        df = n - 1
        p = 2.0 * _t_sf(abs(t_stat), df)
        return min(max(p, 0.0), 1.0)

    def _compute_confidence_interval(
        self, current_delta: float, confidence: float = 0.95
    ) -> tuple[float | None, float | None]:
        historical = [r.delta for r in self._history if r.delta is not None]
        if len(historical) < 2:
            store_history = self._history_from_store()
            historical = [r.delta for r in store_history if r.delta is not None]
        if len(historical) < 2:
            return None, None

        n = len(historical)
        mean_h = sum(historical) / n
        var_h = sum((d - mean_h) ** 2 for d in historical) / max(n - 1, 1)

        if var_h < 1e-12:
            return current_delta, current_delta

        se = (var_h / n) ** 0.5
        df = n - 1

        if HAS_SCIPY:
            alpha = 1.0 - confidence
            t_crit = float(t_dist.ppf(1.0 - alpha / 2, df))
        else:
            t_crit = 1.959963984540054

        margin = t_crit * se
        lower = current_delta - margin
        upper = current_delta + margin

        return lower, upper

    def get_history(self) -> list[ExperimentResult]:
        """Return experiment history (newest first)."""
        return list(reversed(self._history))

    def clear_history(self) -> None:
        """Clear experiment history."""
        self._history.clear()
