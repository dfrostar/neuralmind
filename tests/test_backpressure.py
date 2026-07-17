"""Tests for F4 — backpressure + circuit breakers."""
import pytest
from neuralmind.backpressure import (
    CircuitBreaker,
    CircuitState,
    ProjectBackpressure,
    ProjectLock,
)


class TestCircuitBreaker:
    def test_initial_state_closed(self):
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED

    def test_opens_after_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_rejects_when_open(self):
        cb = CircuitBreaker("test", failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert not cb.allow_request()

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.01)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        import time; time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.allow_request()

    def test_closes_after_half_open_success(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.01)
        cb.record_failure()
        cb.record_failure()
        import time; time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED


class TestProjectBackpressure:
    def test_acquire_release(self):
        bp = ProjectBackpressure.for_project("/tmp/test-project-bp")
        # Reset for test
        bp._count = 0
        bp._rejected_count = 0
        assert bp.acquire()
        assert bp.active == 1
        bp.release()
        assert bp.active == 0

    def test_rejects_when_full(self):
        bp = ProjectBackpressure("/tmp/test-bp-reject", max_concurrent=1)
        assert bp.acquire()
        assert not bp.acquire(timeout=0)
        assert bp.rejected >= 1


class TestProjectLock:
    def test_acquire_release(self):
        pl = ProjectLock("/tmp/test-project-lock")
        pl.backpressure._count = 0
        assert pl.acquire(timeout=0)
        pl.release()
