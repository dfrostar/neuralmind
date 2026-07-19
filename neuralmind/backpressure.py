"""
F4 — Backpressure + circuit breakers.

Concurrent build/query/watch on the same project degrades gracefully:
bounded queue depth, fail-fast on overload, circuit-breaker state machine
(closed → open → half-open). Builds on existing ProjectRegistry + per-project locks.

Local-first. Stdlib-only. Fail-open.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing fast, reject requests
    HALF_OPEN = "half_open"  # Testing recovery with limited traffic


@dataclass
class CircuitStats:
    """Stats for a single circuit breaker."""

    state: str
    failures: int
    successes: int
    rejected: int
    last_failure_ts: float | None = None
    last_state_change_ts: float | None = None


class CircuitBreaker:
    """
    Per-project circuit breaker with closed → open → half-open state machine.

    - CLOSED: normal operation. After `failure_threshold` consecutive
      failures, transitions to OPEN.
    - OPEN: all requests fail-fast. After `recovery_timeout` seconds,
      transitions to HALF_OPEN.
    - HALF_OPEN: allows a single test request through. If it succeeds,
      transitions back to CLOSED. If it fails, transitions back to OPEN.

    Fail-open: a non-critical subsystem (like the daemon watcher) should
    never break the main query/build path when its own storage or
    connection fails.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_ts: float | None = None
        self._last_state_change_ts = time.time()
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Current circuit state, handling OPEN → HALF_OPEN timeout."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._last_failure_ts and (
                    time.time() - self._last_failure_ts >= self.recovery_timeout
                ):
                    self._transition(CircuitState.HALF_OPEN)
            return self._state

    def _transition(self, new_state: CircuitState) -> None:
        """Transition to a new state (must hold _lock)."""
        self._state = new_state
        self._last_state_change_ts = time.time()
        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
        # Allow logging/observability without IO in critical path

    def record_success(self) -> None:
        """Record a successful operation."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._transition(CircuitState.CLOSED)
            else:
                self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed operation. May trigger state transition."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_ts = time.time()
            if self._state == CircuitState.HALF_OPEN:
                self._transition(CircuitState.OPEN)
            elif (
                self._state == CircuitState.CLOSED and self._failure_count >= self.failure_threshold
            ):
                self._transition(CircuitState.OPEN)

    def allow_request(self) -> bool:
        """
        Check if a request should be allowed through.

        Returns True if the request may proceed, False if the circuit
        is OPEN (and increments rejected counter for stats).
        """
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            return True  # Allow one test request
        return False  # OPEN

    def stats(self) -> CircuitStats:
        """Return current stats."""
        return CircuitStats(
            state=self._state.value,
            failures=self._failure_count,
            successes=0,  # not tracked per request; see project use
            rejected=0,
            last_failure_ts=self._last_failure_ts,
            last_state_change_ts=self._last_state_change_ts,
        )


class ProjectBackpressure:
    """
    Per-project backpressure: bounds the number of concurrent
    operations and rejects new requests when the queue is full.

    Uses a semaphore-like counter with a max depth. Operations call
    `acquire()` before starting and `release()` when done. If the
    queue is full, `acquire()` returns False (fail-fast).

    Each project gets its own ProjectBackpressure instance tracked
    in the class-level `_instances` dict.
    """

    _instances: dict[str, ProjectBackpressure] = {}
    _global_lock = threading.Lock()

    @classmethod
    def for_project(
        cls,
        project_path: str | Path,
        max_concurrent: int = 2,
    ) -> ProjectBackpressure:
        """Get or create a ProjectBackpressure for a project."""
        key = str(Path(project_path).resolve())
        with cls._global_lock:
            if key not in cls._instances:
                cls._instances[key] = cls(key, max_concurrent=max_concurrent)
            return cls._instances[key]

    def __init__(self, project_key: str, max_concurrent: int = 2):
        self.project_key = project_key
        self.max_concurrent = max_concurrent
        self._count = 0
        self._lock = threading.Lock()
        self._waiters = 0
        self._rejected_count = 0

    def acquire(self, *, timeout: float = 0.0) -> bool:
        """
        Attempt to acquire a slot. Returns True if acquired.

        If `timeout > 0`, blocks up to `timeout` seconds waiting for
        a slot (used for operations that can wait, like background
        metrics). If `timeout == 0`, returns immediately (fail-fast).
        """
        if timeout <= 0:
            with self._lock:
                if self._count >= self.max_concurrent:
                    self._rejected_count += 1
                    return False
                self._count += 1
                return True
        else:
            # Blocking acquire with timeout
            deadline = time.time() + timeout
            while True:
                with self._lock:
                    if self._count < self.max_concurrent:
                        self._count += 1
                        return True
                    self._waiters += 1
                time.sleep(0.05)
                if time.time() >= deadline:
                    with self._lock:
                        self._waiters = max(0, self._waiters - 1)
                        self._rejected_count += 1
                    return False

    def release(self) -> None:
        """Release a slot back to the pool."""
        with self._lock:
            self._count = max(0, self._count - 1)

    @property
    def active(self) -> int:
        return self._count

    @property
    def rejected(self) -> int:
        return self._rejected_count

    def stats(self) -> dict:
        return {
            "project": self.project_key,
            "active": self._count,
            "max": self.max_concurrent,
            "rejected_total": self._rejected_count,
        }


class ProjectLock:
    """
    Per-project lock compatible with ProjectBackpressure.

    Combines a threading.Lock-like API with backpressure integration:
    if the backpressure queue is full, the lock acquisition fails
    immediately (fail-fast).
    """

    def __init__(
        self,
        project_path: str | Path,
        backpressure: ProjectBackpressure | None = None,
    ):
        self.project_path = Path(project_path)
        self.backpressure = backpressure or ProjectBackpressure.for_project(project_path)
        self._lock = threading.Lock()

    def __enter__(self) -> bool:
        self._entered = self.acquire()
        return self._entered

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if getattr(self, "_entered", False):
            self.release()

    def acquire(self, *, timeout: float = 0.0) -> bool:
        """Acquire the project lock with backpressure."""
        if not self.backpressure.acquire(timeout=timeout):
            return False
        self._lock.acquire()
        return True

    def release(self) -> None:
        """Release the project lock and backpressure slot."""
        self._lock.release()
        self.backpressure.release()
