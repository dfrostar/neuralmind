"""promotion.py — Auto-promote/rollback wiring for Agent OS.

Wire the experiment runner to actually act on verdicts:
- PROMOTED → update tuner incumbent via ship_callable
- ROLLED_BACK → revert to baseline_tag

Pattern follows autopilot's promotion_engine.py:
- ship_callable is DI (default no-op for safety)
- Exceptions are logged, not bubbled (fail-open)

Design:
    - PromotionEngine wraps ExperimentRunner with side effects
    - Only acts when verdict is PROMOTED or ROLLED_BACK
    - PENDING/RUNNING/MEASURING/REJECTED are no-ops (no action needed)
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .experiment import ExperimentResult, ExperimentRunner, ExperimentStatus

log = logging.getLogger(__name__)


class PromotionStatus(str, Enum):
    """Lifecycle states for a promotion."""

    IDLE = "idle"
    SHIPPING = "shipping"
    SHIPPED = "shipped"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


# Type alias: (experiment_result) → None
ShipCallable = Callable[[ExperimentResult], None]


def _noop_ship(result: ExperimentResult) -> None:
    """Default ship callable — does nothing (human-in-the-loop)."""
    log.info(
        "Experiment %s verdict=%s (default ship callable is no-op). "
        "Human review required before promotion.",
        result.experiment_id,
        result.verdict.value,
    )


@dataclass
class PromotionRecord:
    """Record of a promotion action."""

    promotion_id: str
    experiment_id: str
    ts: str
    status: PromotionStatus
    delta: float
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "promotion_id": self.promotion_id,
            "experiment_id": self.experiment_id,
            "ts": self.ts,
            "status": self.status.value,
            "delta": round(self.delta, 6),
            "message": self.message,
        }


class PromotionEngine:
    """Runs experiments with optional auto-promotion/rollback.

    Wraps ExperimentRunner with side effects (ship_callable).

    Usage:
        engine = PromotionEngine(ship_callable=my_tuner_update)
        result = engine.run(
            proposal_id="prop_123",
            metric_name="latency_ms",
            baseline_value=840.0,
            candidate_value=810.0,
        )
        if result.verdict == ExperimentStatus.PROMOTED:
            # ship_callable already fired
            pass
    """

    def __init__(
        self,
        ship_callable: ShipCallable | None = None,
        auto_promote_threshold: float = 0.05,
        auto_rollback_threshold: float = -0.03,
    ) -> None:
        self._runner = ExperimentRunner(
            promote_threshold_pct=auto_promote_threshold * 100,
            rollback_threshold_pct=auto_rollback_threshold * 100,
        )
        self._ship_callable = ship_callable or _noop_ship
        self._history: list[PromotionRecord] = []

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
        """Run an experiment and act on the verdict.

        Returns the ExperimentResult (same as ExperimentRunner.run).
        Side effects (promotion/rollback) happen before return.
        """
        result = self._runner.run(
            proposal_id=proposal_id,
            metric_name=metric_name,
            baseline_value=baseline_value,
            candidate_value=candidate_value,
            threshold_pct=threshold_pct,
            higher_is_better=higher_is_better,
            details=details,
        )

        # Act on verdict
        if result.verdict == ExperimentStatus.PROMOTED:
            self._promote(result)
        elif result.verdict == ExperimentStatus.ROLLED_BACK:
            self._rollback(result)
        # REJECTED, PENDING, RUNNING, MEASURING → no action

        return result

    def _promote(self, result: ExperimentResult) -> None:
        """Promote a verified improvement."""
        record = PromotionRecord(
            promotion_id=f"prom_{uuid.uuid4().hex[:12]}",
            experiment_id=result.experiment_id,
            ts=datetime.now(timezone.utc).isoformat(),
            status=PromotionStatus.SHIPPING,
            delta=result.delta,
            message=f"Promoting {result.metric_name} (delta={result.delta:.3f})",
        )
        self._history.append(record)

        try:
            self._ship_callable(result)
            record.status = PromotionStatus.SHIPPED
            log.info(
                "Promotion %s shipped: %s (delta=%.3f)",
                record.promotion_id,
                result.metric_name,
                result.delta,
            )
        except Exception as exc:
            record.status = PromotionStatus.FAILED
            log.exception(
                "Promotion %s failed for experiment %s: %s",
                record.promotion_id,
                result.experiment_id,
                exc,
            )

    def _rollback(self, result: ExperimentResult) -> None:
        """Rollback a regression."""
        record = PromotionRecord(
            promotion_id=f"prom_{uuid.uuid4().hex[:12]}",
            experiment_id=result.experiment_id,
            ts=datetime.now(timezone.utc).isoformat(),
            status=PromotionStatus.ROLLING_BACK,
            delta=result.delta,
            message=f"Rolling back {result.metric_name} (delta={result.delta:.3f})",
        )
        self._history.append(record)

        try:
            self._ship_callable(result)
            record.status = PromotionStatus.ROLLED_BACK
            log.info(
                "Rollback %s completed: %s (delta=%.3f)",
                record.promotion_id,
                result.metric_name,
                result.delta,
            )
        except Exception as exc:
            record.status = PromotionStatus.FAILED
            log.exception(
                "Rollback %s failed for experiment %s: %s",
                record.promotion_id,
                result.experiment_id,
                exc,
            )

    def get_history(self) -> list[PromotionRecord]:
        """Return promotion history (newest first)."""
        return list(reversed(self._history))

    def clear_history(self) -> None:
        """Clear promotion history."""
        self._history.clear()
