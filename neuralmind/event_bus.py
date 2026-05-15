"""
event_bus.py — Process-local pub/sub for live activity events.

``publish()`` is O(1) when nothing is subscribed, so wiring emit-points
into ``SynapseStore.reinforce`` and the file watcher doesn't pay a tax
during normal headless use. The graph-view SSE endpoint subscribes when
a browser connects; tests subscribe explicitly.

Each subscription owns a bounded queue — if a slow consumer falls
behind, oldest events are dropped at the producer side and a
``dropped`` counter is incremented on the subscription, so the
producer is never blocked on the bus.
"""

from __future__ import annotations

import threading
import time
from queue import Empty, Full, Queue
from typing import Any

DEFAULT_QUEUE_SIZE = 256


class Subscription:
    """A single subscriber's bounded queue. Use ``get()`` to consume."""

    def __init__(self, bus: EventBus, maxsize: int = DEFAULT_QUEUE_SIZE):
        self._queue: Queue[dict[str, Any]] = Queue(maxsize=maxsize)
        self._bus = bus
        self.dropped = 0

    def get(self, timeout: float | None = None) -> dict[str, Any] | None:
        """Block until an event arrives or ``timeout`` elapses. Returns None on timeout."""
        try:
            return self._queue.get(timeout=timeout)
        except Empty:
            return None

    def close(self) -> None:
        self._bus._unsubscribe(self)

    def _offer(self, event: dict[str, Any]) -> None:
        try:
            self._queue.put_nowait(event)
        except Full:
            self.dropped += 1


class EventBus:
    """Thread-safe fan-out. ``publish`` with no subscribers is O(1)."""

    def __init__(self, max_queue: int = DEFAULT_QUEUE_SIZE):
        self._lock = threading.Lock()
        self._subs: list[Subscription] = []
        self.max_queue = max_queue

    def subscribe(self) -> Subscription:
        sub = Subscription(self, maxsize=self.max_queue)
        with self._lock:
            self._subs.append(sub)
        return sub

    def _unsubscribe(self, sub: Subscription) -> None:
        with self._lock:
            try:
                self._subs.remove(sub)
            except ValueError:
                pass

    def publish(self, event_type: str, payload: dict[str, Any] | None = None) -> int:
        """Fan an event out to every current subscriber. Returns recipient count."""
        with self._lock:
            subs = list(self._subs)
        if not subs:
            return 0
        event: dict[str, Any] = {"type": event_type, "ts": time.time()}
        if payload:
            event.update(payload)
        for sub in subs:
            sub._offer(event)
        return len(subs)

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subs)


_BUS: EventBus | None = None
_BUS_LOCK = threading.Lock()


def get_event_bus() -> EventBus:
    """Return (and lazily create) the process-wide event bus."""
    global _BUS
    if _BUS is None:
        with _BUS_LOCK:
            if _BUS is None:
                _BUS = EventBus()
    return _BUS


def publish(event_type: str, payload: dict[str, Any] | None = None) -> int:
    """Shortcut for ``get_event_bus().publish(...)`` — safe to call anywhere."""
    return get_event_bus().publish(event_type, payload)
