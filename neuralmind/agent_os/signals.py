"""signals.py — Page-Hinkley anomaly detection for Agent OS metrics streams.

Detects small persistent shifts in metrics without fixed thresholds.
Emits Signal records when anomalies are detected.

Design:
    - Page-Hinkley test: tracks cumulative sum of deviations from
      running mean. When cumulative deviation exceeds a threshold
      (lambda) times the standard deviation, a signal fires.
    - Lambda scales with data volatility — fixed thresholds miss
      small persistent shifts and fire on seasonal variance.
    - Signals have severity based on deviation magnitude.
    - Per-metric state is held in memory (no DB writes).
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

log = logging.getLogger(__name__)

# Minimum samples required before Page-Hinkley can fire. Prevents false
# positives on constant baselines where std collapses to ~0 and a single
# transient outlier would produce an infinite severity ratio.
MIN_SAMPLES_BEFORE_ALERT = 10


class SeverityLevel(str, Enum):
    """Signal severity levels."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


_SEVERITY_THRESHOLDS = {
    # (cumulative_deviation / running_std) → severity
    0.5: SeverityLevel.INFO,
    1.0: SeverityLevel.LOW,
    2.0: SeverityLevel.MEDIUM,
    4.0: SeverityLevel.HIGH,
    8.0: SeverityLevel.CRITICAL,
}


@dataclass
class Signal:
    """An anomaly signal detected in a metric stream."""

    signal_id: str
    timestamp: float
    metric_name: str
    value: float
    baseline: float
    delta: float  # absolute deviation from baseline
    severity: float  # deviation / running_std
    level: SeverityLevel = SeverityLevel.INFO
    acknowledged: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "timestamp": self.timestamp,
            "metric_name": self.metric_name,
            "value": round(self.value, 6),
            "baseline": round(self.baseline, 6),
            "delta": round(self.delta, 6),
            "severity": round(self.severity, 3),
            "level": self.level.value,
            "acknowledged": self.acknowledged,
        }


@dataclass
class _PageHinkleyState:
    """Internal state for a single metric's Page-Hinkley test."""

    metric_name: str
    count: int = 0
    running_sum: float = 0.0
    m2: float = 0.0  # Welford: sum of squared distance from the running mean
    min_cum_dev: float = 0.0
    max_cum_dev: float = 0.0
    lambda_threshold: float = 4.0  # alert threshold (× running_std)
    last_signal_at: float = 0.0
    cooldown_seconds: float = 60.0

    @property
    def running_mean(self) -> float:
        return self.running_sum / max(self.count, 1)

    @property
    def running_std(self) -> float:
        if self.count < 2:
            return 0.0
        variance = self.m2 / self.count
        return math.sqrt(max(variance, 0.0))

    @property
    def cumulative_deviation(self) -> float:
        return self.max_cum_dev - self.min_cum_dev

    def _severity_level(self) -> SeverityLevel:
        ratio = self.severity_ratio
        assigned = SeverityLevel.INFO
        for threshold, level in sorted(_SEVERITY_THRESHOLDS.items()):
            if ratio >= threshold:
                assigned = level
        return assigned

    @property
    def severity_ratio(self) -> float:
        std = self.running_std
        if std < 1e-9:
            return 0.0
        return self.cumulative_deviation / std

    def update(self, value: float) -> Signal | None:
        """Update state with a new metric value.

        Returns a Signal if the Page-Hinkley test fires, else None.
        """
        # Welford's online algorithm: update M2 before incrementing count
        # so variance is never computed via sum-of-squares cancellation.
        self.count += 1
        delta = value - self.running_mean
        self.running_sum += value
        delta2 = value - self.running_mean
        self.m2 += delta * delta2

        # Deviation from the running (arithmetic) mean
        mean = self.running_mean
        deviation = value - mean
        # Track cumulative deviation (Page-Hinkley core)
        self.max_cum_dev = max(self.max_cum_dev + deviation, 0.0)
        self.min_cum_dev = min(self.min_cum_dev + deviation, 0.0)

        # Check if cumulative deviation exceeds threshold
        std = self.running_std
        severity = self.severity_ratio
        now = time.time()

        # Require minimum sample count before firing to prevent false
        # positives on constant baselines (where std collapses to ~0).
        if (
            severity >= self.lambda_threshold
            and std > 1e-9
            and self.count >= MIN_SAMPLES_BEFORE_ALERT
        ):
            if now - self.last_signal_at < self.cooldown_seconds:
                return None
            self.last_signal_at = now
            level = self._severity_level()
            signal = Signal(
                signal_id=f"sig_{self.metric_name}_{int(now)}",
                timestamp=now,
                metric_name=self.metric_name,
                value=value,
                baseline=mean,
                delta=deviation,
                severity=severity,
                level=level,
            )
            # Reset cumulative trackers after signal fires
            self.max_cum_dev = 0.0
            self.min_cum_dev = 0.0
            return signal

        return None


class SignalDetector:
    """Multi-metric Page-Hinkley anomaly detector.

    Usage:
        detector = SignalDetector()
        signal = detector.update("latency_ms", 850.0)
        if signal:
            print(f"Anomaly: {signal.metric_name} = {signal.value}")
    """

    def __init__(
        self,
        lambda_threshold: float = 4.0,
        cooldown_seconds: float = 60.0,
    ) -> None:
        self._lambda_threshold = lambda_threshold
        self._cooldown_seconds = cooldown_seconds
        self._state: dict[str, _PageHinkleyState] = {}

    def _get_state(self, metric_name: str) -> _PageHinkleyState:
        if metric_name not in self._state:
            self._state[metric_name] = _PageHinkleyState(
                metric_name=metric_name,
                lambda_threshold=self._lambda_threshold,
                cooldown_seconds=self._cooldown_seconds,
            )
        return self._state[metric_name]

    def update(self, metric_name: str, value: float) -> Signal | None:
        """Update a metric value. Returns Signal if anomaly detected."""
        state = self._get_state(metric_name)
        return state.update(float(value))

    def update_batch(self, metrics: dict[str, float]) -> list[Signal]:
        """Update multiple metrics. Returns list of new signals."""
        signals = []
        for name, value in metrics.items():
            signal = self.update(name, value)
            if signal:
                signals.append(signal)
        return signals

    def get_stats(self, metric_name: str) -> dict[str, float] | None:
        """Get current Page-Hinkley statistics for a metric."""
        state = self._state.get(metric_name)
        if state is None:
            return None
        return {
            "count": state.count,
            "running_mean": state.running_mean,
            "running_std": state.running_std,
            "cumulative_deviation": state.cumulative_deviation,
            "severity_ratio": state.severity_ratio,
        }

    def list_metrics(self) -> list[str]:
        """List all tracked metric names."""
        return list(self._state.keys())

    def reset(self, metric_name: str | None = None) -> None:
        """Reset state for a metric (or all)."""
        if metric_name:
            self._state.pop(metric_name, None)
        else:
            self._state.clear()
