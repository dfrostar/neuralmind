"""JSONL bridge — writer + tailer + cross-process bus integration."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from neuralmind.event_bus import EventBus, get_event_bus
from neuralmind.event_log import (
    EventLogTailer,
    EventLogWriter,
    default_log_path,
    event_log_enabled,
)


def _read_lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for raw in path.read_bytes().splitlines():
        if not raw:
            continue
        out.append(json.loads(raw.decode("utf-8")))
    return out


def test_writer_appends_one_json_line_per_call(tmp_path):
    log = tmp_path / "events.jsonl"
    w = EventLogWriter(log)
    assert w.write({"type": "a", "ts": 1.0}) is True
    assert w.write({"type": "b", "ts": 2.0, "nodes": ["x", "y"]}) is True

    lines = _read_lines(log)
    assert [ev["type"] for ev in lines] == ["a", "b"]
    assert lines[1]["nodes"] == ["x", "y"]


def test_writer_creates_parent_directory_lazily(tmp_path):
    nested = tmp_path / "deep" / "nest" / "events.jsonl"
    assert not nested.parent.exists()
    w = EventLogWriter(nested)
    assert w.write({"type": "ok"}) is True
    assert nested.is_file()


def test_writer_concurrent_writes_dont_interleave_bytes(tmp_path):
    log = tmp_path / "events.jsonl"
    w = EventLogWriter(log)

    def burst(tid: int) -> None:
        for i in range(50):
            w.write({"type": "p", "tid": tid, "i": i})

    threads = [threading.Thread(target=burst, args=(t,)) for t in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lines = _read_lines(log)
    # 4 * 50 = 200 lines, all well-formed JSON.
    assert len(lines) == 200
    assert all(ev["type"] == "p" for ev in lines)


def test_writer_swallows_unserializable_payload(tmp_path):
    """Non-JSON payloads are dropped, not raised — bridge is best-effort."""
    log = tmp_path / "events.jsonl"
    w = EventLogWriter(log)

    class Weird:
        pass

    # ``default=str`` in the writer means even Weird() stringifies, so
    # write succeeds. We assert the success + parseable line.
    assert w.write({"type": "x", "blob": Weird()}) is True
    lines = _read_lines(log)
    assert lines[0]["type"] == "x"
    assert isinstance(lines[0]["blob"], str)


def test_tailer_picks_up_new_lines_after_start(tmp_path):
    log = tmp_path / "events.jsonl"
    log.touch()
    received: list[dict] = []
    done = threading.Event()

    def on_event(ev: dict) -> None:
        received.append(ev)
        if len(received) >= 3:
            done.set()

    tailer = EventLogTailer(log, on_event, poll_interval=0.05)
    tailer.start()
    try:
        time.sleep(0.15)  # let the tailer seek-to-end
        w = EventLogWriter(log)
        for i in range(3):
            w.write({"type": "burst", "i": i})
        assert done.wait(timeout=2.0), f"only got {received}"
    finally:
        tailer.stop(timeout=2.0)

    assert [ev["i"] for ev in received] == [0, 1, 2]


def test_tailer_seeks_to_end_so_history_is_not_replayed(tmp_path):
    log = tmp_path / "events.jsonl"
    w = EventLogWriter(log)
    for i in range(5):
        w.write({"type": "old", "i": i})

    received: list[dict] = []
    tailer = EventLogTailer(log, received.append, poll_interval=0.05)
    tailer.start()
    try:
        time.sleep(0.25)
        # New event after start should arrive; the 5 historical ones must not.
        w.write({"type": "new", "i": 99})
        deadline = time.time() + 2.0
        while time.time() < deadline and not received:
            time.sleep(0.05)
    finally:
        tailer.stop(timeout=2.0)

    assert received and received[0]["type"] == "new"
    assert all(ev["type"] == "new" for ev in received)


def test_tailer_skips_malformed_lines(tmp_path):
    log = tmp_path / "events.jsonl"
    log.touch()
    received: list[dict] = []

    tailer = EventLogTailer(log, received.append, poll_interval=0.05)
    tailer.start()
    try:
        time.sleep(0.15)
        with open(log, "ab") as fh:
            fh.write(b"not json at all\n")
            fh.write(b'{"type": "good", "i": 1}\n')
            fh.write(b"{broken\n")
            fh.write(b'{"type": "good", "i": 2}\n')
        deadline = time.time() + 2.0
        while time.time() < deadline and len(received) < 2:
            time.sleep(0.05)
    finally:
        tailer.stop(timeout=2.0)

    assert [ev.get("i") for ev in received] == [1, 2]


def test_tailer_recovers_from_rotation_without_dropping_prewritten_lines(tmp_path):
    """Rotation race: lines already in the new file when rotation is
    detected must still be delivered. Reopening at EOF would skip them
    until the next write — silent event loss for the live activity feed
    (#115)."""
    log = tmp_path / "events.jsonl"
    log.touch()
    received: list[dict] = []
    tailer = EventLogTailer(log, received.append, poll_interval=0.05)
    tailer.start()
    try:
        time.sleep(0.15)  # let tailer seek-to-end on the original (empty) file
        # logrotate-style rename + write to the NEW file before the tailer's
        # next poll runs. These lines must not be skipped.
        rotated = tmp_path / "events.jsonl.1"
        log.rename(rotated)
        with open(log, "wb") as fh:
            fh.write(b'{"type": "prewritten", "i": 0}\n')
            fh.write(b'{"type": "prewritten", "i": 1}\n')
            fh.write(b'{"type": "prewritten", "i": 2}\n')
        deadline = time.time() + 3.0
        while (
            time.time() < deadline
            and sum(1 for ev in received if ev.get("type") == "prewritten") < 3
        ):
            time.sleep(0.05)
    finally:
        tailer.stop(timeout=2.0)

    prewritten = [ev for ev in received if ev.get("type") == "prewritten"]
    assert [ev["i"] for ev in prewritten] == [0, 1, 2]


def test_tailer_recovers_from_rotation(tmp_path):
    """logrotate-style rename + new file: inode changes, tailer resumes."""
    log = tmp_path / "events.jsonl"
    log.touch()
    received: list[dict] = []
    tailer = EventLogTailer(log, received.append, poll_interval=0.05)
    tailer.start()
    try:
        time.sleep(0.15)
        w_pre = EventLogWriter(log)
        w_pre.write({"type": "pre"})
        # Give the tailer a chance to read "pre" before we rotate.
        deadline = time.time() + 2.0
        while time.time() < deadline and not any(ev["type"] == "pre" for ev in received):
            time.sleep(0.05)
        # logrotate-style: rename existing file, replace with a fresh inode.
        rotated = tmp_path / "events.jsonl.1"
        log.rename(rotated)
        log.touch()
        # Tailer notices inode change and re-opens at end of new (empty) file.
        time.sleep(0.2)
        w_post = EventLogWriter(log)
        w_post.write({"type": "post"})
        deadline = time.time() + 3.0
        while time.time() < deadline and not any(ev["type"] == "post" for ev in received):
            time.sleep(0.05)
    finally:
        tailer.stop(timeout=2.0)

    types = [ev["type"] for ev in received]
    assert "pre" in types
    assert "post" in types


def test_tailer_callback_exception_does_not_kill_thread(tmp_path):
    log = tmp_path / "events.jsonl"
    log.touch()
    received: list[dict] = []

    def on_event(ev: dict) -> None:
        if ev.get("i") == 0:
            raise RuntimeError("boom")
        received.append(ev)

    tailer = EventLogTailer(log, on_event, poll_interval=0.05)
    tailer.start()
    try:
        time.sleep(0.15)
        w = EventLogWriter(log)
        w.write({"type": "x", "i": 0})  # callback raises
        w.write({"type": "x", "i": 1})  # but thread keeps going
        deadline = time.time() + 2.0
        while time.time() < deadline and not received:
            time.sleep(0.05)
    finally:
        tailer.stop(timeout=2.0)

    assert received and received[0]["i"] == 1


def test_bus_publish_writes_to_log_when_writer_configured(tmp_path):
    log = tmp_path / "events.jsonl"
    bus = EventBus()
    bus.configure_event_log(EventLogWriter(log))
    bus.publish("synapse", {"nodes": ["a", "b"], "pair_count": 1})
    bus.publish("file", {"count": 2})

    lines = _read_lines(log)
    assert [ev["type"] for ev in lines] == ["synapse", "file"]
    # Every event must carry pid so a cross-process consumer can dedupe.
    assert all(ev["_pid"] == os.getpid() for ev in lines)
    assert all("ts" in ev for ev in lines)


def test_bus_publish_writes_to_log_even_without_subscribers(tmp_path):
    """Disk side channel is the whole point of the bridge — it must
    fire when no in-process subscribers exist, otherwise a headless
    ``neuralmind watch`` daemon would never persist anything."""
    log = tmp_path / "events.jsonl"
    bus = EventBus()
    bus.configure_event_log(EventLogWriter(log))
    assert bus.subscriber_count() == 0
    bus.publish("synapse", {"pair_count": 3})
    assert _read_lines(log)[0]["pair_count"] == 3


def test_bus_fanout_only_skips_writer(tmp_path):
    """Tailer republish path must not write back to the same file it
    just read — that would loop forever."""
    log = tmp_path / "events.jsonl"
    bus = EventBus()
    bus.configure_event_log(EventLogWriter(log))
    sub = bus.subscribe()
    try:
        bus._fanout_only({"type": "external", "_pid": 99999, "ts": 1.0})
        ev = sub.get(timeout=0.5)
        assert ev is not None and ev["type"] == "external"
        assert _read_lines(log) == []
    finally:
        sub.close()


def test_bus_publish_idle_when_no_writer_and_no_subscribers():
    """No fan-out, no writer, no event allocation. Keeps ``reinforce``
    cheap during normal headless use."""
    bus = EventBus()
    assert bus.publish("x") == 0
    assert bus.publish("y", {"k": 1}) == 0


def test_clearing_writer_disables_the_side_channel(tmp_path):
    log = tmp_path / "events.jsonl"
    bus = EventBus()
    bus.configure_event_log(EventLogWriter(log))
    bus.publish("first", {})
    bus.configure_event_log(None)
    bus.publish("second", {})
    types = [ev["type"] for ev in _read_lines(log)]
    assert types == ["first"]


def test_publish_does_not_raise_when_writer_errors(monkeypatch, tmp_path):
    """A broken filesystem must never break a synapse write."""
    log = tmp_path / "events.jsonl"
    writer = EventLogWriter(log)

    def boom(_ev: dict) -> bool:
        raise OSError("disk gone")

    monkeypatch.setattr(writer, "write", boom)
    bus = EventBus()
    bus.configure_event_log(writer)
    bus.publish("synapse", {"pair_count": 1})  # must not raise


def test_event_log_enabled_respects_env_var(monkeypatch):
    monkeypatch.delenv("NEURALMIND_EVENT_LOG", raising=False)
    assert event_log_enabled() is True
    monkeypatch.setenv("NEURALMIND_EVENT_LOG", "0")
    assert event_log_enabled() is False
    monkeypatch.setenv("NEURALMIND_EVENT_LOG", "1")
    assert event_log_enabled() is True


def test_default_log_path_is_under_dot_neuralmind(tmp_path):
    p = default_log_path(tmp_path)
    assert p == tmp_path / ".neuralmind" / "events.jsonl"


def test_cross_process_handoff_via_jsonl(tmp_path):
    """End-to-end: writer process appends, reader process tails and
    republishes locally. This is the contract the graph view depends
    on — a ``neuralmind watch`` daemon's events must reach the server's
    in-process bus without going through any IPC machinery beyond the
    JSONL file."""
    log = tmp_path / "events.jsonl"
    log.touch()

    # "Server" side: tailer republishes onto a local bus.
    server_bus = EventBus()

    def on_external(event: dict) -> None:
        if event.get("_pid") == os.getpid():
            # Real server filters self-events; this test forces a
            # foreign pid below so this branch is never taken here.
            return
        server_bus._fanout_only(event)

    tailer = EventLogTailer(log, on_external, poll_interval=0.05)
    tailer.start()
    sub = server_bus.subscribe()
    try:
        time.sleep(0.15)

        # "Watcher" side: writes a synapse event with a foreign pid so
        # the tailer's pid filter doesn't skip it.
        writer = EventLogWriter(log)
        writer.write(
            {
                "type": "synapse",
                "ts": time.time(),
                "_pid": os.getpid() + 1,
                "nodes": ["alpha", "beta"],
                "pair_count": 1,
            }
        )

        ev = sub.get(timeout=2.0)
        assert ev is not None
        assert ev["type"] == "synapse"
        assert ev["nodes"] == ["alpha", "beta"]
    finally:
        sub.close()
        tailer.stop(timeout=2.0)


def test_module_level_configure_event_log_targets_singleton(tmp_path):
    """``configure_event_log`` exposed at module level must wire the
    same singleton bus that ``publish()`` uses, otherwise emit-points
    that import ``publish`` would silently bypass the writer."""
    from neuralmind.event_bus import configure_event_log, publish

    log = tmp_path / "events.jsonl"
    bus = get_event_bus()
    configure_event_log(EventLogWriter(log))
    try:
        publish("synapse", {"pair_count": 7})
        lines = _read_lines(log)
        assert lines and lines[0]["pair_count"] == 7
    finally:
        configure_event_log(None)
