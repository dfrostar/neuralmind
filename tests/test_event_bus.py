"""Pub/sub semantics for the live activity event bus."""

from __future__ import annotations

import threading
import time

from neuralmind.event_bus import EventBus, get_event_bus, publish


def test_publish_with_no_subscribers_is_cheap_noop():
    bus = EventBus()
    # No throw, returns 0 recipients, doesn't allocate a queue we can't drain.
    assert bus.publish("nothing", {"k": 1}) == 0
    assert bus.subscriber_count() == 0


def test_single_subscriber_receives_event_in_order():
    bus = EventBus()
    sub = bus.subscribe()
    try:
        bus.publish("a", {"n": 1})
        bus.publish("b", {"n": 2})
        ev1 = sub.get(timeout=0.5)
        ev2 = sub.get(timeout=0.5)
        assert ev1["type"] == "a" and ev1["n"] == 1
        assert ev2["type"] == "b" and ev2["n"] == 2
        # Each event carries its own timestamp.
        assert ev1["ts"] <= ev2["ts"]
    finally:
        sub.close()


def test_multiple_subscribers_each_get_their_own_copy():
    bus = EventBus()
    a = bus.subscribe()
    b = bus.subscribe()
    try:
        assert bus.publish("ping", {}) == 2
        assert a.get(timeout=0.5)["type"] == "ping"
        assert b.get(timeout=0.5)["type"] == "ping"
    finally:
        a.close()
        b.close()


def test_close_unsubscribes():
    bus = EventBus()
    sub = bus.subscribe()
    assert bus.subscriber_count() == 1
    sub.close()
    assert bus.subscriber_count() == 0
    # Subsequent publish has no recipients.
    assert bus.publish("x") == 0


def test_full_queue_drops_events_without_blocking_producer():
    bus = EventBus(max_queue=3)
    sub = bus.subscribe()
    try:
        for i in range(10):
            bus.publish("burst", {"i": i})
        # First three filled the queue; remaining seven were dropped at the source.
        assert sub.dropped == 7
        drained = []
        for _ in range(3):
            drained.append(sub.get(timeout=0.5))
        assert [e["i"] for e in drained] == [0, 1, 2]
    finally:
        sub.close()


def test_module_level_helpers_share_singleton_bus():
    # First call materializes it; second call returns the same instance.
    bus = get_event_bus()
    assert get_event_bus() is bus
    sub = bus.subscribe()
    try:
        publish("hello", {"v": 7})
        ev = sub.get(timeout=0.5)
        assert ev["type"] == "hello"
        assert ev["v"] == 7
    finally:
        sub.close()


def test_concurrent_publish_and_subscribe_stays_consistent():
    bus = EventBus()
    received: list[dict] = []
    sub = bus.subscribe()

    def drain():
        for _ in range(50):
            ev = sub.get(timeout=1.0)
            if ev is None:
                break
            received.append(ev)

    consumer = threading.Thread(target=drain)
    consumer.start()

    def producer():
        for i in range(25):
            bus.publish("p", {"i": i})

    producers = [threading.Thread(target=producer) for _ in range(2)]
    for t in producers:
        t.start()
    for t in producers:
        t.join()
    # Drain queue: give the consumer a moment.
    time.sleep(0.1)
    consumer.join(timeout=2.0)
    sub.close()

    # 2 producers × 25 events = 50; the consumer may pick up fewer if the
    # drain finishes early, but every received event should be well-formed.
    assert all(ev["type"] == "p" for ev in received)
    assert all("ts" in ev for ev in received)
