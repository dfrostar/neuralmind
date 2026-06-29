"""Tests for FileActivityWatcher.

The watcher has two backends: watchdog (event-driven) and a polling
fallback. We exercise both implicitly by relying on whichever one
is present in the runtime environment, but the asserts only depend
on observable behaviour: a callback firing at least once with the
edited file in its batch.
"""

from __future__ import annotations

import time

from neuralmind.watcher import DEFAULT_IGNORES, FileActivityWatcher, _is_ignored


def test_is_ignored_matches_default_dirs(tmp_path):
    project = tmp_path
    junk = project / ".git" / "config"
    junk.parent.mkdir(parents=True)
    junk.write_text("x")
    real = project / "src" / "app.py"
    real.parent.mkdir(parents=True)
    real.write_text("x")

    assert _is_ignored(junk, project, DEFAULT_IGNORES) is True
    assert _is_ignored(real, project, DEFAULT_IGNORES) is False


def test_is_ignored_when_path_outside_root(tmp_path):
    other = tmp_path.parent / "elsewhere.txt"
    assert _is_ignored(other, tmp_path, DEFAULT_IGNORES) is True


def test_watcher_records_edits_and_flushes_batch(tmp_path):
    received: list[list[str]] = []

    def cb(paths):
        received.append(list(paths))

    target = tmp_path / "alpha.py"
    target.write_text("v0")  # exists before watcher starts

    w = FileActivityWatcher(tmp_path, cb, debounce=0.3, poll_interval=0.4, ignores=DEFAULT_IGNORES)
    w.start()
    try:
        # Give the polling backend one cycle to seed mtimes, then modify.
        time.sleep(0.6)
        target.write_text("v1")
        # Give backends time: watchdog reacts ~immediately,
        # polling reacts within poll_interval, then debounce flushes.
        deadline = time.time() + 4.0
        while time.time() < deadline and not received:
            time.sleep(0.1)
    finally:
        w.stop()

    assert received, "watcher fired no batches; backend may be misbehaving"
    flat = [p for batch in received for p in batch]
    assert any(str(target) == p for p in flat)


def test_watcher_skips_ignored_paths(tmp_path):
    received: list[list[str]] = []

    def cb(paths):
        received.append(list(paths))

    ignored_dir = tmp_path / ".git"
    ignored_dir.mkdir()
    junk = ignored_dir / "HEAD"
    junk.write_text("v0")

    w = FileActivityWatcher(tmp_path, cb, debounce=0.3, poll_interval=0.4, ignores=DEFAULT_IGNORES)
    w.start()
    try:
        time.sleep(0.6)
        junk.write_text("v1")
        time.sleep(2.0)
    finally:
        w.stop()

    flat = [p for batch in received for p in batch]
    assert not any(str(junk) == p for p in flat)


def test_stop_is_idempotent(tmp_path):
    w = FileActivityWatcher(tmp_path, lambda paths: None, debounce=0.3, poll_interval=0.4)
    w.start()
    w.stop()
    w.stop()  # second stop must not raise


def test_deletion_callback_fires_when_file_removed(tmp_path):
    """deletion_callback must be called immediately when a tracked file disappears."""
    deleted: list[list[str]] = []

    def on_delete(paths):
        deleted.append(list(paths))

    target = tmp_path / "victim.py"
    target.write_text("hello")

    w = FileActivityWatcher(
        tmp_path,
        lambda paths: None,
        debounce=0.1,
        poll_interval=0.3,
        deletion_callback=on_delete,
    )
    w.start()
    try:
        # Seed the mtime table so the file is "known" to the poll loop
        time.sleep(0.5)
        target.unlink()
        # Poll loop must detect the deletion within poll_interval + a small margin
        deadline = time.time() + 3.0
        while time.time() < deadline and not deleted:
            time.sleep(0.1)
    finally:
        w.stop()

    assert deleted, "deletion_callback was never fired"
    flat = [p for batch in deleted for p in batch]
    assert any(str(target) == p for p in flat), f"deleted file not in callback: {flat}"


def test_no_deletion_callback_no_crash(tmp_path):
    """Watcher without deletion_callback must not crash when files disappear."""
    target = tmp_path / "ephemeral.py"
    target.write_text("v0")

    w = FileActivityWatcher(tmp_path, lambda paths: None, debounce=0.1, poll_interval=0.3)
    w.start()
    try:
        time.sleep(0.5)
        target.unlink()
        time.sleep(0.5)
    finally:
        w.stop()  # should not raise


def test_flush_delivers_batch_sorted_by_timestamp(tmp_path):
    """The flush loop must order ready paths by edit timestamp, not dict-
    insertion order. A file that was touched then re-touched should appear
    at its latest position so the directional transition recorder sees the
    actual chronological order. (v0.11.0+)"""
    received: list[list[str]] = []

    def cb(paths):
        received.append(list(paths))

    w = FileActivityWatcher(tmp_path, cb, debounce=0.1, poll_interval=10.0)
    # Seed _pending with out-of-order timestamps: A was inserted first but
    # has the LATER timestamp (simulating a re-touch); B inserted second but
    # earlier ts. Chronological order is [B, A].
    now = time.time()
    w._pending = {"A": now - 1.0, "B": now - 2.0}
    w.start()
    try:
        deadline = time.time() + 2.0
        while time.time() < deadline and not received:
            time.sleep(0.05)
    finally:
        w.stop()

    assert received, "flush did not fire"
    # First (and likely only) batch should be sorted by timestamp ascending:
    # B (older ts) before A (newer ts), not dict insertion order [A, B].
    assert received[0] == ["B", "A"], f"expected chronological order [B, A], got {received[0]}"
