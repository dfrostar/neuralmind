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
    - Auto-promote is gated behind MIN_SIGNALS_BEFORE_AUTO_PROMOTE
    - Proposal tracks baseline_tag and candidate_tag for rollback
    - Promotion history persisted to SQLite (crash-safe)
    - Incumbent state persisted to SQLite (crash-safe)
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
    IDLE = "idle"
    SHIPPING = "shipping"
    SHIPPED = "shipped"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


MIN_SIGNALS_BEFORE_AUTO_PROMOTE = 5

ShipCallable = Callable[[ExperimentResult], None]


def _noop_ship(result: ExperimentResult) -> None:
    log.info(
        "Experiment %s verdict=%s (default ship callable is no-op). "
        "Human review required before promotion.",
        result.experiment_id,
        result.verdict.value,
    )


@dataclass
class Proposal:
    """An improvement proposal with rollback tag tracking."""

    proposal_id: str
    title: str
    hypothesis: str
    baseline_tag: str
    candidate_tag: str
    metric_name: str
    baseline_value: float
    candidate_value: float
    status: str = "proposed"
    signal_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "title": self.title,
            "hypothesis": self.hypothesis,
            "baseline_tag": self.baseline_tag,
            "candidate_tag": self.candidate_tag,
            "metric_name": self.metric_name,
            "baseline_value": self.baseline_value,
            "candidate_value": self.candidate_value,
            "status": self.status,
            "signal_count": self.signal_count,
        }


class TunerIncumbent:
    """Tracks the current best-known value for a tunable metric.

    State is persisted to SQLite for crash recovery.
    """

    def __init__(
        self,
        metric_name: str,
        initial_value: float,
        tag: str = "baseline",
        store: Any = None,
        tenant_id: str = "default",
    ) -> None:
        self.metric_name = metric_name
        self.value = initial_value
        self.tag = tag
        self._store = store
        self._tenant_id = tenant_id
        self._history: list[dict[str, Any]] = []

        # Load persisted state if available
        if store is not None:
            persisted = store.get_incumbent(tenant_id, metric_name)
            if persisted is not None:
                self.value = persisted["value"]
                self.tag = persisted["tag"]
                import json
                self._history = json.loads(persisted.get("history", "[]"))

    def update(self, new_value: float, new_tag: str, reason: str) -> None:
        old_value = self.value
        old_tag = self.tag
        self.value = new_value
        self.tag = new_tag
        self._history.append({
            "from_value": old_value,
            "from_tag": old_tag,
            "to_value": new_value,
            "to_tag": new_tag,
            "reason": reason,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        log.info(
            "Tuner incumbent %s: %s (%s) → %s (%s) — %s",
            self.metric_name,
            old_value,
            old_tag,
            new_value,
            new_tag,
            reason,
        )
        # Persist to store
        if self._store is not None:
            self._store.persist_incumbent(
                self._tenant_id, self.metric_name, new_value, new_tag, self._history
            )

    def get_history(self) -> list[dict[str, Any]]:
        return list(reversed(self._history))


def _tuner_incumbent_ship_callable(incumbent: TunerIncumbent, proposal: Proposal) -> ShipCallable:
    """Create a ship_callable that updates the tuner incumbent."""

    def ship(result: ExperimentResult) -> None:
        if result.verdict == ExperimentStatus.PROMOTED:
            incumbent.update(
                new_value=proposal.candidate_value,
                new_tag=proposal.candidate_tag,
                reason=f"Promoted {result.experiment_id} (delta={result.delta:.3f})",
            )
        elif result.verdict == ExperimentStatus.ROLLED_BACK:
            incumbent.update(
                new_value=proposal.baseline_value,
                new_tag=proposal.baseline_tag,
                reason=f"Rolled back {result.experiment_id} (delta={result.delta:.3f})",
            )

    return ship


@dataclass
class PromotionRecord:
    """Record a promotion action."""

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
    Persists promotion history and incumbent state to SQLite.
    """

    def __init__(
        self,
        ship_callable: ShipCallable | None = None,
        auto_promote_threshold: float = 0.05,
        auto_rollback_threshold: float = -0.03,
        incumbent: TunerIncumbent | None = None,
        proposal: Proposal | None = None,
        signal_count: int = 0,
        store: Any = None,
        tenant_id: str = "default",
    ) -> None:
        self._runner = ExperimentRunner(
            promote_threshold_pct=auto_promote_threshold * 100,
            rollback_threshold_pct=auto_rollback_threshold * 100,
            store=store,
            tenant_id=tenant_id,
        )
        self._incumbent = incumbent
        self._proposal = proposal
        self._signal_count = signal_count
        self._store = store
        self._tenant_id = tenant_id

        if incumbent is not None and proposal is not None:
            self._ship_callable = _tuner_incumbent_ship_callable(incumbent, proposal)
            self._auto_promote = True
        else:
            self._ship_callable = ship_callable or _noop_ship
            self._auto_promote = False

        self._history: list[PromotionRecord] = []

    def run(
        self,
        proposal_id: str | None = None,
        metric_name: str | None = None,
        baseline_value: float | None = None,
        candidate_value: float | None = None,
        threshold_pct: float | None = None,
        higher_is_better: bool = False,
        details: dict[str, Any] | None = None,
    ) -> ExperimentResult:
        if self._proposal is not None:
            pid = proposal_id or self._proposal.proposal_id
            mname = metric_name or self._proposal.metric_name
            bval = baseline_value if baseline_value is not None else self._proposal.baseline_value
            cval = candidate_value if candidate_value is not None else self._proposal.candidate_value
        else:
            pid = proposal_id or f"prop_{uuid.uuid4().hex[:12]}"
            mname = metric_name or "unknown"
            bval = baseline_value if baseline_value is not None else 0.0
            cval = candidate_value if candidate_value is not None else 0.0

        result = self._runner.run(
            proposal_id=pid,
            metric_name=mname,
            baseline_value=bval,
            candidate_value=cval,
            threshold_pct=threshold_pct,
            higher_is_better=higher_is_better,
            details=details,
        )

        if result.verdict == ExperimentStatus.PROMOTED:
            self._promote(result)
        elif result.verdict == ExperimentStatus.ROLLED_BACK:
            self._rollback(result)

        return result

    def _promote(self, result: ExperimentResult) -> None:
        if self._auto_promote and self._signal_count < MIN_SIGNALS_BEFORE_AUTO_PROMOTE:
            log.info(
                "Promotion skipped: signal_count=%d < MIN_SIGNALS_BEFORE_AUTO_PROMOTE=%d",
                self._signal_count,
                MIN_SIGNALS_BEFORE_AUTO_PROMOTE,
            )
            record = PromotionRecord(
                promotion_id=f"prom_{uuid.uuid4().hex[:12]}",
                experiment_id=result.experiment_id,
                ts=datetime.now(timezone.utc).isoformat(),
                status=PromotionStatus.IDLE,
                delta=result.delta,
                message=f"Promotion skipped: insufficient signals ({self._signal_count}/{MIN_SIGNALS_BEFORE_AUTO_PROMOTE})",
            )
            self._history.append(record)
            if self._store is not None:
                self._store.insert_promotion(self._tenant_id, record.to_dict())
            return

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
            if self._proposal is not None:
                self._proposal.status = "promoted"
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

        if self._store is not None:
            self._store.insert_promotion(self._tenant_id, record.to_dict())

    def _rollback(self, result: ExperimentResult) -> None:
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
            if self._proposal is not None:
                self._proposal.status = "rolled_back"
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

        if self._store is not None:
            self._store.insert_promotion(self._tenant_id, record.to_dict())

    def get_history(self) -> list[PromotionRecord]:
        return list(reversed(self._history))

    def clear_history(self) -> None:
        self._history.clear()
