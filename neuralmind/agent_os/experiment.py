"""experiment.py — A/B experiment runner for the Agent OS signal loop.

Implements the experiment arm of the self-improving loop:
- Proposed change → baseline/candidate tags
- Run metric collection → measure delta
- p-value-governed promote/rollback decision
- Results logged for governance audit trail

This is a POC implementation (no statistical test yet) — the metric
collector and promote/rollback wiring are real.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

log = logging.getLogger(__name__)


class ExperimentStatus(str, Enum):
    """Lifecycle states for an experiment."""

    PENDING = "pending"
    RUNNING = "running"
    MEASURING = "measuring"
    PROMOTED = "promoted"
    ROLLED_BACK = "rolled_back"
    REJECTED = "rejected"


@dataclass
class ExperimentResult:
    """Result of an A/B experiment."""

    experiment_id: str
    proposal_id: str
    metric_name: str
    baseline_value: float
    candidate_value: float
    delta: float  # positive = improvement (after higher_is_better normalization)
    p_value: float | None  # None if no statistical test
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
            "verdict": self.verdict.value,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "details": self.details,
        }


class ExperimentRunner:
    """Runs A/B experiments with metric collection.

    POC scope: measures two values, computes delta, applies threshold
    governance. No statistical significance test yet (requires sample
    populations and a t-test / bootstrap CI).

    Usage:
        runner = ExperimentRunner()
        result = runner.run(
            proposal_id="prop_123",
            metric_name="latency_ms",
            baseline_value=840.0,
            candidate_value=810.0,
            threshold_pct=5.0,  # need 5% improvement
            higher_is_better=False,  # lower latency is better
        )
        if result.verdict == ExperimentStatus.PROMOTED:
            ship_it()
    """

    def __init__(
        self,
        promote_threshold_pct: float = 5.0,
        rollback_threshold_pct: float = -3.0,
    ) -> None:
        self._promote_threshold = promote_threshold_pct / 100.0
        self._rollback_threshold = rollback_threshold_pct / 100.0
        self._history: list[ExperimentResult] = []

    @staticmethod
    def _compute_delta(baseline: float, candidate: float, higher_is_better: bool = False) -> float:
        """Compute fractional delta.

        Args:
            baseline: Current value.
            candidate: Proposed value.
            higher_is_better: If True, positive delta = improvement.
                            If False (default), negative delta = improvement
                            (e.g., lower latency is better).
        """
        if abs(baseline) < 1e-9:
            if abs(candidate) < 1e-9:
                return 0.0
            # Degenerate baseline: report the direction of the change, then
            # apply the higher_is_better inversion like the normal path, so a
            # lower-is-better metric (e.g. latency) doesn't promote a large
            # candidate as a 100% "improvement".
            return 1.0 if higher_is_better else -1.0
        raw = (candidate - baseline) / abs(baseline)
        # Invert so positive delta always = improvement
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
        """Run an A/B experiment and return the verdict.

        Args:
            proposal_id: The proposal this experiment validates.
            metric_name: The metric being tested.
            baseline_value: The baseline (current) metric value.
            candidate_value: The candidate (proposed) metric value.
            threshold_pct: Override the promote threshold for this run.
            higher_is_better: If True, higher values are improvements
                (throughput). If False (default), lower values are
                improvements (latency).
            details: Additional context for audit trail.

        Returns:
            ExperimentResult with the computed verdict.
        """
        promote_threshold = (
            threshold_pct / 100.0 if threshold_pct is not None
            else self._promote_threshold
        )
        delta = self._compute_delta(baseline_value, candidate_value, higher_is_better)

        # Verdict logic (deterministic, auditable)
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
            p_value=None,  # POC: no p-value yet
            verdict=verdict,
            started_at=datetime.now(timezone.utc).isoformat(),
            ended_at=datetime.now(timezone.utc).isoformat(),
            details=details or {},
        )
        self._history.append(result)
        return result

    def get_history(self) -> list[ExperimentResult]:
        """Return experiment history (newest first)."""
        return list(reversed(self._history))

    def clear_history(self) -> None:
        """Clear experiment history."""
        self._history.clear()
