"""Maintenance Eval Harness — 10-task maintenance replay benchmark.

Implements the benchmark protocol from the NeuraKeep Reddit discussion:
run maintenance tasks with memory enabled AND disabled (within-subjects),
measure the delta, and report aggregate metrics.

Benchmark Protocol:
    1. Select real maintenance tasks (bug fix, refactor, dependency upgrade, etc.)
    2. Run each task with memory enabled AND disabled (within-subjects)
    3. Measure: incorrect_recalls, time_to_locate_evidence, token_usage,
       stale_record_influence
    4. Report the delta (memory ON vs OFF)

This module ships with 5 synthetic tasks that exercise the DecisionStore
query path. Each task seeds relevant decisions (some ACTIVE, some STALE)
and measures whether the query path surfaces the right decisions while
suppressing stale ones.

Usage:
    from neuralmind.memory.eval import MaintenanceEval
    eval = MaintenanceEval("/path/to/project")
    report = eval.run(output_format="json")  # or "markdown"
    print(report)

CLI:
    python -m neuralmind.memory.eval [--project PATH] [--format json|markdown]
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .store import DecisionRecord, DecisionStore

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class MaintenanceTask:
    """One synthetic maintenance task for the benchmark.

    Each task simulates a real maintenance scenario (bug fix, refactor, etc.)
    and defines the gold-standard decisions that should be recalled.
    """

    id: str
    description: str
    query: str  # The search query to issue against the DecisionStore
    expected_decision_ids: list[str]  # Gold answers — decisions that SHOULD be recalled
    stale_decision_ids: list[str]  # Decisions that should NOT be recalled (stale)
    relevant_files: list[str]  # Files the task touches (for context)
    task_type: str  # BUGFIX, REFACTOR, DEPENDENCY, CONFIG, TEST


@dataclass
class TaskResult:
    """Per-task result for one arm of the benchmark (memory ON or OFF)."""

    task_id: str
    task_type: str
    query: str
    # Timing
    time_to_locate_evidence_ms: float
    # Recall metrics
    expected_recalled: list[str]  # Expected decision IDs that were returned
    expected_missed: list[str]  # Expected decision IDs NOT returned
    incorrect_recalls: list[str]  # Non-expected decision IDs that were returned
    stale_recalled: list[str]  # Stale decision IDs that were returned (bad)
    # Token usage (approximate — based on result count and content size)
    token_usage: int
    # Raw results for debugging
    result_count: int


@dataclass
class AggregateMetrics:
    """Aggregate metrics across all tasks for one arm."""

    total_tasks: int
    total_expected_recalled: int
    total_expected_missed: int
    total_incorrect_recalls: int
    total_stale_recalled: int
    mean_time_to_locate_ms: float
    total_token_usage: int
    # Derived rates
    recall_rate: float  # expected_recalled / (expected_recalled + expected_missed)
    precision: float  # expected_recalled / (expected_recalled + incorrect_recalls)
    stale_influence_rate: float  # tasks where stale was recalled / total tasks


@dataclass
class BenchmarkReport:
    """Full benchmark report with per-task results and aggregate metrics."""

    project_path: str
    task_count: int
    timestamp: str
    memory_on: list[TaskResult] = field(default_factory=list)
    memory_off: list[TaskResult] = field(default_factory=list)
    aggregate_on: AggregateMetrics | None = None
    aggregate_off: AggregateMetrics | None = None
    # Delta (memory ON - memory OFF, where positive = memory is better)
    delta: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Synthetic task definitions
# ---------------------------------------------------------------------------

# Fixed UUIDs for deterministic benchmark runs. Each task seeds decisions
# with known IDs so we can precisely measure recall.

_TASK_SEED_DECISIONS: dict[str, list[dict[str, Any]]] = {
    "bugfix_auth_bypass": [
        {
            "id": "dec-bugfix-auth-001",
            "title": "Use per-handler authentication middleware",
            "rationale": (
                "Each API handler must authenticate via the shared middleware "
                "rather than inline checks. Prevents auth bypass via overlooked "
                "handlers."
            ),
            "decision_type": "ARCHITECTURE",
            "status": "ACTIVE",
            "files_affected": ["neuralmind/auth.py", "neuralmind/api/handlers.py"],
            "confidence": 0.95,
            "tags": ["security", "auth", "api"],
        },
        {
            "id": "dec-bugfix-auth-002",
            "title": "Validate JWT tokens in authentication flow",
            "rationale": (
                "RS256 is required for authentication to prevent key confusion "
                "attacks. HS256 is vulnerable."
            ),
            "decision_type": "CONFIG",
            "status": "ACTIVE",
            "files_affected": ["neuralmind/auth.py"],
            "confidence": 0.9,
            "tags": ["security", "jwt", "authentication"],
        },
        {
            # STALE: this decision was superseded by dec-bugfix-auth-001
            "id": "dec-bugfix-auth-stale-001",
            "title": "Inline authentication checks in each handler (DEPRECATED)",
            "rationale": (
                "Originally each handler did its own authentication check. This was "
                "replaced by per-handler middleware after the auth bypass CVE."
            ),
            "decision_type": "ARCHITECTURE",
            "status": "STALE",
            "files_affected": ["neuralmind/auth.py", "neuralmind/api/handlers.py"],
            "confidence": 0.3,
            "tags": ["security", "auth", "deprecated"],
        },
    ],
    "refactor_db_pool": [
        {
            "id": "dec-refactor-db-001",
            "title": "Use connection pooling for SQLite WAL mode",
            "rationale": (
                "SQLite WAL mode allows concurrent readers with a single writer. "
                "Connection pooling reduces overhead of opening/closing connections "
                "per query."
            ),
            "decision_type": "ARCHITECTURE",
            "status": "ACTIVE",
            "files_affected": ["neuralmind/db/pool.py", "neuralmind/db/connection.py"],
            "confidence": 0.92,
            "tags": ["database", "performance", "pooling"],
        },
        {
            "id": "dec-refactor-db-002",
            "title": "Extract query builder from connection pool module",
            "rationale": (
                "Raw SQL strings in the connection pool are error-prone. A query builder "
                "provides composability and type safety."
            ),
            "decision_type": "REFACTOR",
            "status": "ACTIVE",
            "files_affected": ["neuralmind/db/query.py"],
            "confidence": 0.88,
            "tags": ["database", "refactoring", "sql", "pool"],
        },
        {
            # STALE: pooling approach changed
            "id": "dec-refactor-db-stale-001",
            "title": "Use thread-local connections without pooling (DEPRECATED)",
            "rationale": (
                "Originally used thread-local connections instead of pooling. This caused "
                "contention under load and was replaced by proper connection pooling."
            ),
            "decision_type": "ARCHITECTURE",
            "status": "STALE",
            "files_affected": ["neuralmind/db/connection.py"],
            "confidence": 0.2,
            "tags": ["database", "deprecated"],
        },
    ],
    "dep_upgrade_sqlite": [
        {
            "id": "dec-dep-sqlite-001",
            "title": "Pin SQLite to >= 3.35 for WAL mode support",
            "rationale": (
                "WAL mode requires SQLite 3.35+. Older versions fall back to "
                "rollback journal which has worse concurrency."
            ),
            "decision_type": "DEPENDENCY",
            "status": "ACTIVE",
            "files_affected": ["pyproject.toml", "requirements.txt"],
            "confidence": 0.95,
            "tags": ["dependency", "sqlite", "wal"],
        },
        {
            "id": "dec-dep-sqlite-002",
            "title": "Use json_each for SQLite overlap queries",
            "rationale": (
                "SQLite's json_each table-valued function allows efficient "
                "overlap detection between files_affected JSON arrays and "
                "changed file lists."
            ),
            "decision_type": "ARCHITECTURE",
            "status": "ACTIVE",
            "files_affected": ["neuralmind/memory/store.py"],
            "confidence": 0.9,
            "tags": ["sqlite", "json", "query"],
        },
        {
            # STALE: old SQLite version constraint
            "id": "dec-dep-sqlite-stale-001",
            "title": "Pin SQLite to 3.28 for legacy compatibility (DEPRECATED)",
            "rationale": (
                "Originally pinned SQLite to 3.28 for an old deployment target. "
                "This was upgraded to 3.35+ for WAL mode."
            ),
            "decision_type": "DEPENDENCY",
            "status": "STALE",
            "files_affected": ["pyproject.toml"],
            "confidence": 0.1,
            "tags": ["dependency", "sqlite", "deprecated"],
        },
    ],
    "config_logging": [
        {
            "id": "dec-config-logging-001",
            "title": "Use structured JSON logging with correlation IDs",
            "rationale": (
                "Structured logs with request correlation IDs enable "
                "distributed tracing and faster debugging."
            ),
            "decision_type": "CONFIG",
            "status": "ACTIVE",
            "files_affected": ["neuralmind/logging/config.py", "neuralmind/logging/formatters.py"],
            "confidence": 0.93,
            "tags": ["logging", "observability", "config"],
        },
        {
            "id": "dec-config-logging-002",
            "title": "Set log level to INFO in production",
            "rationale": (
                "INFO in production keeps log volume manageable. DEBUG in dev aids development."
            ),
            "decision_type": "CONFIG",
            "status": "ACTIVE",
            "files_affected": ["neuralmind/logging/config.py"],
            "confidence": 0.87,
            "tags": ["logging", "config"],
        },
        {
            # STALE: old logging approach
            "id": "dec-config-logging-stale-001",
            "title": "Use plain text logging with print statements (DEPRECATED)",
            "rationale": (
                "Originally used print-based plain text logging. Replaced by structured "
                "JSON logging for production observability."
            ),
            "decision_type": "CONFIG",
            "status": "STALE",
            "files_affected": ["neuralmind/logging/config.py"],
            "confidence": 0.15,
            "tags": ["logging", "deprecated"],
        },
    ],
    "test_decision_store": [
        {
            "id": "dec-test-store-001",
            "title": "Use pytest fixtures for DecisionStore test isolation",
            "rationale": (
                "Each DecisionStore test gets a fresh in-memory SQLite database. Fixtures "
                "ensure no cross-test contamination."
            ),
            "decision_type": "TEST",
            "status": "ACTIVE",
            "files_affected": ["tests/test_store.py", "tests/conftest.py"],
            "confidence": 0.91,
            "tags": ["testing", "pytest", "fixtures", "DecisionStore"],
        },
        {
            "id": "dec-test-store-002",
            "title": "Test FTS5 fallback path with DecisionStore",
            "rationale": (
                "Not all SQLite builds have FTS5. The DecisionStore LIKE fallback must be "
                "tested to ensure graceful degradation."
            ),
            "decision_type": "TEST",
            "status": "ACTIVE",
            "files_affected": ["tests/test_store.py"],
            "confidence": 0.85,
            "tags": ["testing", "fts5", "fallback", "DecisionStore"],
        },
        {
            # STALE: old testing approach
            "id": "dec-test-store-stale-001",
            "title": "Use unittest.TestCase for DecisionStore tests (DEPRECATED)",
            "rationale": (
                "Originally used unittest.TestCase for DecisionStore tests. Migrated to "
                "pytest fixtures for better isolation and parametrize support."
            ),
            "decision_type": "TEST",
            "status": "STALE",
            "files_affected": ["tests/test_store.py"],
            "confidence": 0.2,
            "tags": ["testing", "unittest", "deprecated", "DecisionStore"],
        },
    ],
}


def _build_tasks() -> list[MaintenanceTask]:
    """Build the 5 synthetic maintenance tasks with fixed UUIDs."""
    return [
        MaintenanceTask(
            id="bugfix_auth_bypass",
            description="Fix authentication bypass vulnerability in API handler",
            query="authentication middleware",
            expected_decision_ids=["dec-bugfix-auth-001", "dec-bugfix-auth-002"],
            stale_decision_ids=["dec-bugfix-auth-stale-001"],
            relevant_files=["neuralmind/auth.py", "neuralmind/api/handlers.py"],
            task_type="BUGFIX",
        ),
        MaintenanceTask(
            id="refactor_db_pool",
            description="Extract database connection pooling into a dedicated module",
            query="connection pooling SQLite",
            expected_decision_ids=["dec-refactor-db-001", "dec-refactor-db-002"],
            stale_decision_ids=["dec-refactor-db-stale-001"],
            relevant_files=["neuralmind/db/pool.py", "neuralmind/db/connection.py"],
            task_type="REFACTOR",
        ),
        MaintenanceTask(
            id="dep_upgrade_sqlite",
            description="Upgrade SQLite dependency to support WAL mode and json_each",
            query="SQLite WAL mode",
            expected_decision_ids=["dec-dep-sqlite-001", "dec-dep-sqlite-002"],
            stale_decision_ids=["dec-dep-sqlite-stale-001"],
            relevant_files=["pyproject.toml", "neuralmind/memory/store.py"],
            task_type="DEPENDENCY",
        ),
        MaintenanceTask(
            id="config_logging",
            description="Update logging configuration for structured JSON output",
            query="structured JSON logging",
            expected_decision_ids=["dec-config-logging-001", "dec-config-logging-002"],
            stale_decision_ids=["dec-config-logging-stale-001"],
            relevant_files=["neuralmind/logging/config.py"],
            task_type="CONFIG",
        ),
        MaintenanceTask(
            id="test_decision_store",
            description="Add integration tests for DecisionStore query and invalidation",
            query="DecisionStore test fixtures",
            expected_decision_ids=["dec-test-store-001", "dec-test-store-002"],
            stale_decision_ids=["dec-test-store-stale-001"],
            relevant_files=["tests/test_store.py", "tests/conftest.py"],
            task_type="TEST",
        ),
    ]


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------


def _estimate_tokens(records: list[DecisionRecord]) -> int:
    """Estimate token usage for a list of decision records.

    Uses a simple heuristic: ~4 characters per token, counting title,
    rationale, and evidence fields. This is approximate but consistent
    across arms, making the delta meaningful.
    """
    total_chars = 0
    for rec in records:
        total_chars += len(rec.title)
        total_chars += len(rec.rationale)
        total_chars += len(rec.commit_sha)
        for f in rec.files_affected:
            total_chars += len(f)
        for e in rec.evidence:
            total_chars += len(e)
        for tag in rec.tags:
            total_chars += len(tag)
    return total_chars // 4


# ---------------------------------------------------------------------------
# MaintenanceEval
# ---------------------------------------------------------------------------


class MaintenanceEval:
    """Maintenance replay benchmark harness.

    Runs synthetic maintenance tasks against a DecisionStore with memory
    enabled (default query, filters stale) and disabled (includes all
    statuses), then reports the delta.

    Args:
        project_path: Root of the project. The DecisionStore DB lives at
            ``<project_path>/.neuralmind/memory.db``.
        task_count: Number of tasks to run (max 5 for synthetic tasks).
            Defaults to 10 but only 5 synthetic tasks are defined; the
            harness runs min(task_count, available_tasks).
    """

    def __init__(self, project_path: str, task_count: int = 10) -> None:
        self.project_path = str(Path(project_path).resolve())
        self.task_count = min(task_count, 5)  # 5 synthetic tasks available
        self._tasks = _build_tasks()[: self.task_count]
        self._store: DecisionStore | None = None

    # ------------------------------------------------------------------
    # Setup / teardown
    # ------------------------------------------------------------------

    def _get_store(self) -> DecisionStore:
        """Get or create the DecisionStore for this project."""
        if self._store is None:
            self._store = DecisionStore(self.project_path)
        return self._store

    def _seed_decisions(self) -> None:
        """Seed the DecisionStore with all task decisions.

        Clears existing decisions first to ensure a clean baseline.
        Uses a fresh store each time to avoid cross-contamination.
        """
        store = self._get_store()

        # Clear existing decisions by deleting the DB file
        db_path = Path(self.project_path) / ".neuralmind" / "memory.db"
        if db_path.exists():
            db_path.unlink()
            # Also clear WAL/SHM sidecars
            for suffix in ("-wal", "-shm"):
                sidecar = db_path.with_suffix(db_path.suffix + suffix)
                if sidecar.exists():
                    sidecar.unlink()

        # Re-create store after clearing
        self._store = DecisionStore(self.project_path)
        store = self._store

        # Seed all decisions from task definitions
        now = datetime.now(timezone.utc)
        for _task_id, decisions in _TASK_SEED_DECISIONS.items():
            for d in decisions:
                # Stagger created_at so ordering is deterministic
                created = now - timedelta(hours=len(d["title"]))
                store.record(
                    title=d["title"],
                    rationale=d["rationale"],
                    commit_sha="abc1234" + uuid.uuid4().hex[:4],
                    files_affected=d.get("files_affected", []),
                    decision_type=d.get("decision_type", "ARCHITECTURE"),
                    confidence=d.get("confidence", 1.0),
                    status=d.get("status", "ACTIVE"),
                    author="eval-harness",
                    evidence=[f"Seed evidence for {d['id']}"],
                    rejected_alternatives=[],
                    dependency_constraints=[],
                    tags=d.get("tags", []),
                    id=d["id"],
                    created_at=created,
                    updated_at=created,
                )

    # ------------------------------------------------------------------
    # Query execution
    # ------------------------------------------------------------------

    def _run_task(
        self,
        task: MaintenanceTask,
        *,
        memory_enabled: bool,
    ) -> TaskResult:
        """Run a single task with memory ON or OFF.

        Memory ON: uses default query() which filters to ACTIVE only.
        Memory OFF: uses query(status=None) which includes all statuses,
        simulating a baseline without memory-based stale filtering.
        """
        store = self._get_store()

        # Time the query
        start = time.perf_counter()
        if memory_enabled:
            results = store.query(task.query, limit=10, status="ACTIVE")
        else:
            results = store.query(task.query, limit=10, status=None)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        result_ids = [r.id for r in results]

        # Compute recall metrics
        expected_set = set(task.expected_decision_ids)
        stale_set = set(task.stale_decision_ids)
        result_set = set(result_ids)

        expected_recalled = sorted(expected_set & result_set)
        expected_missed = sorted(expected_set - result_set)
        incorrect_recalls = sorted(result_set - expected_set - stale_set)
        stale_recalled = sorted(stale_set & result_set)

        token_usage = _estimate_tokens(results)

        return TaskResult(
            task_id=task.id,
            task_type=task.task_type,
            query=task.query,
            time_to_locate_evidence_ms=round(elapsed_ms, 3),
            expected_recalled=expected_recalled,
            expected_missed=expected_missed,
            incorrect_recalls=incorrect_recalls,
            stale_recalled=stale_recalled,
            token_usage=token_usage,
            result_count=len(results),
        )

    # ------------------------------------------------------------------
    # Aggregate metrics
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_aggregate(results: list[TaskResult]) -> AggregateMetrics:
        """Compute aggregate metrics from a list of task results."""
        if not results:
            return AggregateMetrics(
                total_tasks=0,
                total_expected_recalled=0,
                total_expected_missed=0,
                total_incorrect_recalls=0,
                total_stale_recalled=0,
                mean_time_to_locate_ms=0.0,
                total_token_usage=0,
                recall_rate=0.0,
                precision=0.0,
                stale_influence_rate=0.0,
            )

        total_expected_recalled = sum(len(r.expected_recalled) for r in results)
        total_expected_missed = sum(len(r.expected_missed) for r in results)
        total_incorrect = sum(len(r.incorrect_recalls) for r in results)
        total_stale = sum(len(r.stale_recalled) for r in results)
        total_time = sum(r.time_to_locate_evidence_ms for r in results)
        total_tokens = sum(r.token_usage for r in results)

        recall_denom = total_expected_recalled + total_expected_missed
        recall_rate = total_expected_recalled / recall_denom if recall_denom > 0 else 0.0

        precision_denom = total_expected_recalled + total_incorrect
        precision = total_expected_recalled / precision_denom if precision_denom > 0 else 0.0

        stale_tasks = sum(1 for r in results if r.stale_recalled)
        stale_influence_rate = stale_tasks / len(results)

        return AggregateMetrics(
            total_tasks=len(results),
            total_expected_recalled=total_expected_recalled,
            total_expected_missed=total_expected_missed,
            total_incorrect_recalls=total_incorrect,
            total_stale_recalled=total_stale,
            mean_time_to_locate_ms=round(total_time / len(results), 3),
            total_token_usage=total_tokens,
            recall_rate=round(recall_rate, 4),
            precision=round(precision, 4),
            stale_influence_rate=round(stale_influence_rate, 4),
        )

    # ------------------------------------------------------------------
    # Report rendering
    # ------------------------------------------------------------------

    @staticmethod
    def _render_json(report: BenchmarkReport) -> str:
        """Render the benchmark report as JSON."""
        data: dict[str, Any] = {
            "project_path": report.project_path,
            "task_count": report.task_count,
            "timestamp": report.timestamp,
            "memory_on": {
                "per_task": [
                    {
                        "task_id": r.task_id,
                        "task_type": r.task_type,
                        "query": r.query,
                        "time_to_locate_evidence_ms": r.time_to_locate_evidence_ms,
                        "expected_recalled": r.expected_recalled,
                        "expected_missed": r.expected_missed,
                        "incorrect_recalls": r.incorrect_recalls,
                        "stale_recalled": r.stale_recalled,
                        "token_usage": r.token_usage,
                        "result_count": r.result_count,
                    }
                    for r in report.memory_on
                ],
                "aggregate": (
                    {
                        "total_tasks": report.aggregate_on.total_tasks,
                        "total_expected_recalled": report.aggregate_on.total_expected_recalled,
                        "total_expected_missed": report.aggregate_on.total_expected_missed,
                        "total_incorrect_recalls": report.aggregate_on.total_incorrect_recalls,
                        "total_stale_recalled": report.aggregate_on.total_stale_recalled,
                        "mean_time_to_locate_ms": report.aggregate_on.mean_time_to_locate_ms,
                        "total_token_usage": report.aggregate_on.total_token_usage,
                        "recall_rate": report.aggregate_on.recall_rate,
                        "precision": report.aggregate_on.precision,
                        "stale_influence_rate": report.aggregate_on.stale_influence_rate,
                    }
                    if report.aggregate_on
                    else None
                ),
            },
            "memory_off": {
                "per_task": [
                    {
                        "task_id": r.task_id,
                        "task_type": r.task_type,
                        "query": r.query,
                        "time_to_locate_evidence_ms": r.time_to_locate_evidence_ms,
                        "expected_recalled": r.expected_recalled,
                        "expected_missed": r.expected_missed,
                        "incorrect_recalls": r.incorrect_recalls,
                        "stale_recalled": r.stale_recalled,
                        "token_usage": r.token_usage,
                        "result_count": r.result_count,
                    }
                    for r in report.memory_off
                ],
                "aggregate": (
                    {
                        "total_tasks": report.aggregate_off.total_tasks,
                        "total_expected_recalled": report.aggregate_off.total_expected_recalled,
                        "total_expected_missed": report.aggregate_off.total_expected_missed,
                        "total_incorrect_recalls": report.aggregate_off.total_incorrect_recalls,
                        "total_stale_recalled": report.aggregate_off.total_stale_recalled,
                        "mean_time_to_locate_ms": report.aggregate_off.mean_time_to_locate_ms,
                        "total_token_usage": report.aggregate_off.total_token_usage,
                        "recall_rate": report.aggregate_off.recall_rate,
                        "precision": report.aggregate_off.precision,
                        "stale_influence_rate": report.aggregate_off.stale_influence_rate,
                    }
                    if report.aggregate_off
                    else None
                ),
            },
            "delta": report.delta,
        }
        return json.dumps(data, indent=2, default=str)

    @staticmethod
    def _render_markdown(report: BenchmarkReport) -> str:
        """Render the benchmark report as Markdown."""
        lines: list[str] = [
            "# Maintenance Eval Benchmark Report",
            "",
            f"**Project**: `{report.project_path}`",
            f"**Tasks**: {report.task_count}",
            f"**Timestamp**: {report.timestamp}",
            "",
        ]

        # Aggregate comparison table
        lines.append("## Aggregate Metrics (Memory ON vs OFF)")
        lines.append("")
        lines.append("| Metric | Memory ON | Memory OFF | Delta |")
        lines.append("|--------|-----------|------------|-------|")

        on = report.aggregate_on
        off = report.aggregate_off
        if on and off:
            rows = [
                (
                    "Recall rate",
                    f"{on.recall_rate:.1%}",
                    f"{off.recall_rate:.1%}",
                    f"{report.delta.get('recall_rate', 0):+.1%}",
                ),
                (
                    "Precision",
                    f"{on.precision:.1%}",
                    f"{off.precision:.1%}",
                    f"{report.delta.get('precision', 0):+.1%}",
                ),
                (
                    "Stale influence rate",
                    f"{on.stale_influence_rate:.1%}",
                    f"{off.stale_influence_rate:.1%}",
                    f"{report.delta.get('stale_influence_rate', 0):+.1%}",
                ),
                (
                    "Mean time to locate (ms)",
                    f"{on.mean_time_to_locate_ms:.1f}",
                    f"{off.mean_time_to_locate_ms:.1f}",
                    f"{report.delta.get('mean_time_to_locate_ms', 0):+.1f}",
                ),
                (
                    "Total token usage",
                    str(on.total_token_usage),
                    str(off.total_token_usage),
                    str(report.delta.get("total_token_usage", 0)),
                ),
                (
                    "Expected recalled",
                    str(on.total_expected_recalled),
                    str(off.total_expected_recalled),
                    str(report.delta.get("total_expected_recalled", 0)),
                ),
                (
                    "Expected missed",
                    str(on.total_expected_missed),
                    str(off.total_expected_missed),
                    str(report.delta.get("total_expected_missed", 0)),
                ),
                (
                    "Incorrect recalls",
                    str(on.total_incorrect_recalls),
                    str(off.total_incorrect_recalls),
                    str(report.delta.get("total_incorrect_recalls", 0)),
                ),
                (
                    "Stale recalled",
                    str(on.total_stale_recalled),
                    str(off.total_stale_recalled),
                    str(report.delta.get("total_stale_recalled", 0)),
                ),
            ]
            for label, on_val, off_val, delta_val in rows:
                lines.append(f"| {label} | {on_val} | {off_val} | {delta_val} |")

        lines.append("")

        # Per-task detail
        lines.append("## Per-Task Results")
        lines.append("")

        for i, task_on in enumerate(report.memory_on):
            task_off = report.memory_off[i] if i < len(report.memory_off) else None
            lines.append(f"### Task {i + 1}: {task_on.task_id} ({task_on.task_type})")
            lines.append("")
            lines.append(f"**Query**: `{task_on.query}`")
            lines.append("")
            lines.append("| Metric | Memory ON | Memory OFF |")
            lines.append("|--------|-----------|------------|")
            lines.append(
                f"| Time to locate (ms) | {task_on.time_to_locate_evidence_ms:.1f} | {task_off.time_to_locate_evidence_ms if task_off else '—'} |"
            )
            lines.append(
                f"| Expected recalled | {', '.join(task_on.expected_recalled) or '—'} | {', '.join(task_off.expected_recalled) if task_off else '—'} |"
            )
            lines.append(
                f"| Expected missed | {', '.join(task_on.expected_missed) or '—'} | {', '.join(task_off.expected_missed) if task_off else '—'} |"
            )
            lines.append(
                f"| Incorrect recalls | {', '.join(task_on.incorrect_recalls) or '—'} | {', '.join(task_off.incorrect_recalls) if task_off else '—'} |"
            )
            lines.append(
                f"| Stale recalled | {', '.join(task_on.stale_recalled) or '—'} | {', '.join(task_off.stale_recalled) if task_off else '—'} |"
            )
            lines.append(
                f"| Token usage | {task_on.token_usage} | {task_off.token_usage if task_off else '—'} |"
            )
            lines.append(
                f"| Result count | {task_on.result_count} | {task_off.result_count if task_off else '—'} |"
            )
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self, output_format: str = "json") -> str:
        """Run the full benchmark and return the report.

        Args:
            output_format: "json" (default) or "markdown".

        Returns:
            The rendered report string.

        Raises:
            ValueError: If output_format is not "json" or "markdown".
        """
        if output_format not in ("json", "markdown"):
            raise ValueError(f"Unknown output_format: {output_format!r}. Use 'json' or 'markdown'.")

        # Seed decisions
        self._seed_decisions()

        # Run memory ON arm
        memory_on_results: list[TaskResult] = []
        for task in self._tasks:
            result = self._run_task(task, memory_enabled=True)
            memory_on_results.append(result)

        # Run memory OFF arm
        memory_off_results: list[TaskResult] = []
        for task in self._tasks:
            result = self._run_task(task, memory_enabled=False)
            memory_off_results.append(result)

        # Compute aggregates
        agg_on = self._compute_aggregate(memory_on_results)
        agg_off = self._compute_aggregate(memory_off_results)

        # Compute delta (memory ON - memory OFF; positive = memory is better)
        delta: dict[str, float] = {}
        if agg_on and agg_off:
            delta["recall_rate"] = round(agg_on.recall_rate - agg_off.recall_rate, 4)
            delta["precision"] = round(agg_on.precision - agg_off.precision, 4)
            # For stale_influence, negative delta is good (memory reduces stale influence)
            delta["stale_influence_rate"] = round(
                agg_on.stale_influence_rate - agg_off.stale_influence_rate, 4
            )
            delta["mean_time_to_locate_ms"] = round(
                agg_on.mean_time_to_locate_ms - agg_off.mean_time_to_locate_ms, 3
            )
            delta["total_token_usage"] = agg_on.total_token_usage - agg_off.total_token_usage
            delta["total_expected_recalled"] = (
                agg_on.total_expected_recalled - agg_off.total_expected_recalled
            )
            delta["total_expected_missed"] = (
                agg_on.total_expected_missed - agg_off.total_expected_missed
            )
            delta["total_incorrect_recalls"] = (
                agg_on.total_incorrect_recalls - agg_off.total_incorrect_recalls
            )
            delta["total_stale_recalled"] = (
                agg_on.total_stale_recalled - agg_off.total_stale_recalled
            )

        report = BenchmarkReport(
            project_path=self.project_path,
            task_count=len(self._tasks),
            timestamp=datetime.now(timezone.utc).isoformat(),
            memory_on=memory_on_results,
            memory_off=memory_off_results,
            aggregate_on=agg_on,
            aggregate_off=agg_off,
            delta=delta,
        )

        if output_format == "json":
            return self._render_json(report)
        return self._render_markdown(report)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for the maintenance eval harness.

    Usage:
        python -m neuralmind.memory.eval [--project PATH] [--format json|markdown]
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Maintenance Eval Harness — benchmark memory ON vs OFF",
    )
    parser.add_argument(
        "--project",
        default=".",
        help="Project path (default: current directory)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format (default: json)",
    )
    args = parser.parse_args()

    eval = MaintenanceEval(args.project)
    report = eval.run(output_format=args.format)
    print(report)


if __name__ == "__main__":
    main()
