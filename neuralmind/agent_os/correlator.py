"""correlator.py — Root-cause correlation for Agent OS signals.

When a signal fires, correlate it with recent commits, config changes, and
parameter history to produce a hypothesis about what caused the anomaly.

Pattern follows the self-improving product operations loop:
signal → diagnose → experiment → promote/rollback

Design:
    - Correlator is stateless: each call receives the signal + project context
    - Reads git log, config history, and tuner param history
    - Produces an Insight (cause_type, cause_ref, confidence)
    - Stdlib-only: no external dependencies
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)


class CauseType(str, Enum):
    """Types of root causes."""

    CODE_CHANGE = "code_change"
    CONFIG_CHANGE = "config_change"
    PARAM_CHANGE = "param_change"
    EXTERNAL = "external"
    UNKNOWN = "unknown"


@dataclass
class Insight:
    """A root-cause hypothesis for a signal."""

    insight_id: str
    signal_id: str
    ts: str
    hypothesis: str
    cause_type: CauseType
    cause_ref: str  # commit hash, config key, or param name
    confidence: float  # 0.0-1.0
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "insight_id": self.insight_id,
            "signal_id": self.signal_id,
            "ts": self.ts,
            "hypothesis": self.hypothesis,
            "cause_type": self.cause_type.value,
            "cause_ref": self.cause_ref,
            "confidence": round(self.confidence, 3),
            "details": self.details,
        }


class RootCauseCorrelator:
    """Correlates signals with recent changes to produce root-cause hypotheses.

    Usage:
        correlator = RootCauseCorrelator()
        insight = correlator.correlate(signal, project_path)
        if insight:
            print(f"Hypothesis: {insight.hypothesis}")
    """

    def __init__(
        self,
        git_timeout: float = 5.0,
        lookback_seconds: float = 3600.0,
    ) -> None:
        self._git_timeout = git_timeout
        self._lookback_seconds = lookback_seconds

    def correlate(
        self,
        signal: Any,
        project_path: str | Path,
    ) -> Insight | None:
        """Correlate a signal with recent changes in a project.

        Args:
            signal: A Signal object (or any object with metric_name, timestamp)
            project_path: Path to the project root

        Returns:
            Insight with the most likely root cause, or None if no correlation
        """
        project_path = Path(project_path).resolve()
        now = time.time()
        signal_ts = getattr(signal, "timestamp", now)
        metric_name = getattr(signal, "metric_name", "unknown")

        # Gather evidence
        commits = self._recent_commits(project_path, signal_ts)
        config_changes = self._recent_config_changes(project_path, signal_ts)

        # Score hypotheses
        hypotheses = self._score_hypotheses(signal, commits, config_changes)

        if not hypotheses:
            return Insight(
                insight_id=f"ins_{int(now)}",
                signal_id=getattr(signal, "signal_id", "unknown"),
                ts=datetime.now(timezone.utc).isoformat(),
                hypothesis=f"No correlated changes found for {metric_name} anomaly",
                cause_type=CauseType.UNKNOWN,
                cause_ref="",
                confidence=0.0,
            )

        # Return the highest-confidence hypothesis
        best = max(hypotheses, key=lambda h: h.confidence)
        return best

    def _recent_commits(
        self,
        project_path: Path,
        since_ts: float,
    ) -> list[dict[str, Any]]:
        """Get recent commits from the project's git log."""
        try:
            since_str = datetime.fromtimestamp(since_ts - self._lookback_seconds, tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S"
            )
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    str(project_path),
                    "log",
                    f"--since={since_str}",
                    "--format=%H|%an|%ae|%s|%aI",
                    "--no-merges",
                ],
                capture_output=True,
                text=True,
                timeout=self._git_timeout,
            )
            if result.returncode != 0:
                return []
            commits = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|", 4)
                if len(parts) >= 4:
                    commits.append({
                        "hash": parts[0],
                        "author": parts[1],
                        "email": parts[2],
                        "message": parts[3],
                        "date": parts[4] if len(parts) > 4 else "",
                    })
            return commits
        except (subprocess.TimeoutExpired, OSError):
            return []

    def _recent_config_changes(
        self,
        project_path: Path,
        since_ts: float,
    ) -> list[dict[str, Any]]:
        """Get recent config file changes (YAML/JSON/TOML in project root)."""
        changes = []
        config_files = list(project_path.glob("*.yaml")) + \
                       list(project_path.glob("*.yml")) + \
                       list(project_path.glob("*.json")) + \
                       list(project_path.glob("*.toml"))
        for path in config_files:
            try:
                mtime = path.stat().st_mtime
                if mtime >= since_ts - self._lookback_seconds:
                    changes.append({
                        "file": path.name,
                        "mtime": mtime,
                        "path": str(path),
                    })
            except OSError:
                continue
        return changes

    def _score_hypotheses(
        self,
        signal: Any,
        commits: list[dict[str, Any]],
        config_changes: list[dict[str, Any]],
    ) -> list[Insight]:
        """Score hypotheses based on evidence."""
        hypotheses = []
        now = time.time()
        signal_ts = getattr(signal, "timestamp", now)
        metric_name = getattr(signal, "metric_name", "unknown")
        signal_id = getattr(signal, "signal_id", "unknown")

        # Code change hypothesis
        for commit in commits:
            confidence = self._commit_relevance(commit, metric_name)
            if confidence > 0.1:
                hypotheses.append(Insight(
                    insight_id=f"ins_{commit['hash'][:8]}_{int(now)}",
                    signal_id=signal_id,
                    ts=datetime.now(timezone.utc).isoformat(),
                    hypothesis=(
                        f"Code change by {commit['author']} ({commit['hash'][:8]}) "
                        f"may have caused {metric_name} anomaly: {commit['message'][:80]}"
                    ),
                    cause_type=CauseType.CODE_CHANGE,
                    cause_ref=commit["hash"],
                    confidence=confidence,
                    details=commit,
                ))

        # Config change hypothesis
        for change in config_changes:
            confidence = 0.5  # baseline for config changes
            if metric_name.lower() in change["file"].lower():
                confidence = 0.8  # filename matches metric
            hypotheses.append(Insight(
                insight_id=f"ins_cfg_{change['file']}_{int(now)}",
                signal_id=signal_id,
                ts=datetime.now(timezone.utc).isoformat(),
                hypothesis=(
                    f"Config file {change['file']} was modified recently, "
                    f"possibly affecting {metric_name}"
                ),
                cause_type=CauseType.CONFIG_CHANGE,
                cause_ref=change["file"],
                confidence=confidence,
                details=change,
            ))

        return hypotheses

    def _commit_relevance(self, commit: dict[str, Any], metric_name: str) -> float:
        """Score how relevant a commit is to a metric."""
        message = commit.get("message", "").lower()
        metric_lower = metric_name.lower()

        # Direct mention in commit message
        if metric_lower in message:
            return 0.9

        # Common patterns
        perf_keywords = ["perf", "performance", "speed", "latency", "optimize", "fast", "slow"]
        if any(kw in message for kw in perf_keywords):
            return 0.6

        # Author-based heuristic (frequent contributor)
        # Could be extended with git blame data
        return 0.2
