"""
event_bus.py — Process-local pub/sub for live activity events.

``publish()`` is O(1) when nothing is subscribed and no JSONL writer is
configured, so wiring emit-points into ``SynapseStore.reinforce`` and
the file watcher doesn't pay a tax during normal headless use. The
graph-view SSE endpoint subscribes when a browser connects; tests
subscribe explicitly.

Each subscription owns a bounded queue — if a slow consumer falls
behind, oldest events are dropped at the producer side and a
``dropped`` counter is incremented on the subscription, so the
producer is never blocked on the bus.

When a JSONL writer is attached via :func:`configure_event_log`, every
published event is also appended to disk so a separate process (e.g.
``neuralmind watch``) can carry events to the graph-view server. Events
carry a ``_pid`` field so the server's tailer can ignore lines it wrote
itself.
"""

from __future__ import annotations

import os
import threading
import time
from queue import Empty, Full, Queue
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .event_log import EventLogWriter

DEFAULT_QUEUE_SIZE = 256
_PID = os.getpid()


class Subscription:
    """A single subscriber's bounded queue. Use ``get()`` to consume."""

    def __init__(self, bus: EventBus, maxsize: int = DEFAULT_QUEUE_SIZE):
        self._queue: Queue[dict[str, Any]] = Queue(maxsize=maxsize)
        self._bus = bus
        self._drop_lock = threading.Lock()
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
        # Live feeds care more about fresh state than complete history, so when
        # a slow consumer fills the queue we drop the oldest item before
        # enqueuing the new one. Concurrent producers can race on the
        # get-then-put sequence; we just retry once, then count the drop.
        try:
            self._queue.put_nowait(event)
            return
        except Full:
            pass
        try:
            self._queue.get_nowait()
        except Empty:
            pass
        try:
            self._queue.put_nowait(event)
        except Full:
            pass
        with self._drop_lock:
            self.dropped += 1


class EventBus:
    """Thread-safe fan-out. ``publish`` is O(1) when idle."""

    def __init__(self, max_queue: int = DEFAULT_QUEUE_SIZE):
        self._lock = threading.Lock()
        self._subs: list[Subscription] = []
        self.max_queue = max_queue
        self._log_writer: EventLogWriter | None = None

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

    def configure_event_log(self, writer: EventLogWriter | None) -> None:
        """Attach (or clear with None) the JSONL writer used by ``publish``.

        When a writer is set, every published event is appended to disk
        as one JSON line so other processes can consume it. Setting it
        to ``None`` disables the side channel without touching subs.
        """
        with self._lock:
            self._log_writer = writer

    def publish(self, event_type: str, payload: dict[str, Any] | None = None) -> int:
        """Fan an event out to every current subscriber. Returns recipient count.

        If a JSONL writer is configured the event is also appended to
        disk, regardless of subscriber count — that's the whole point of
        the cross-process bridge.
        """
        with self._lock:
            subs = list(self._subs)
            writer = self._log_writer
        if not subs and writer is None:
            return 0
        event: dict[str, Any] = {"type": event_type, "ts": time.time(), "_pid": _PID}
        if payload:
            event.update(payload)
        if writer is not None:
            try:
                writer.write(event)
            except Exception:
                # Bridge must never break a real synapse write.
                pass
        for sub in subs:
            sub._offer(event)
        return len(subs)

    def _fanout_only(self, event: dict[str, Any]) -> int:
        """Deliver a pre-built external event to in-process subscribers.

        Used by the JSONL tailer to republish events that arrived from
        another process. Skips the writer so it can't loop back into the
        file we just read.
        """
        with self._lock:
            subs = list(self._subs)
        if not subs:
            return 0
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


def configure_event_log(writer: EventLogWriter | None) -> None:
    """Module-level shortcut for ``get_event_bus().configure_event_log(...)``."""
    get_event_bus().configure_event_log(writer)
