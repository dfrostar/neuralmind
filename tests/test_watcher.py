"""Tests for FileActivityWatcher.

The watcher has two backends: watchdog (event-driven) and a polling
fallback. We exercise both implicitly by relying on whichever one
is present in the runtime environment, but the asserts only depend
on observable behaviour: a callback firing at least once with the
edited file in its batch.
"""

from __future__ import annotations

import os
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


def test_watcher_skips_dts_files(tmp_path):
    """*.d.ts files are build artifacts — edits must not co-activate."""
    assert _is_ignored(tmp_path / "src" / "app.d.ts", tmp_path, DEFAULT_IGNORES) is True
    # Regular .ts is NOT ignored
    assert _is_ignored(tmp_path / "src" / "app.ts", tmp_path, DEFAULT_IGNORES) is False


def test_watcher_skips_node_modules_nested(tmp_path):
    """node_modules nested at any depth is ignored."""
    assert (
        _is_ignored(
            tmp_path / "frontend" / "node_modules" / "lodash" / "index.js",
            tmp_path,
            DEFAULT_IGNORES,
        )
        is True
    )


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


class _FakeClock:
    """Virtual ``time`` module for the flush loop: ``sleep`` advances the
    clock and fires scripted edits at their exact virtual timestamps."""

    def __init__(self, watcher, script, run_for):
        self.now = 1_000.0
        self.start = self.now
        self.watcher = watcher
        self.script = sorted(script, key=lambda e: e[0])
        self.run_for = run_for

    def time(self):
        return self.now

    def sleep(self, seconds):
        target = self.now + seconds
        while self.script and self.start + self.script[0][0] <= target:
            offset, path = self.script.pop(0)
            self.now = self.start + offset
            self.watcher._record(path)
        self.now = target
        if self.now - self.start >= self.run_for:
            self.watcher._stop.set()


def _run_flush_loop(monkeypatch, tmp_path, script, debounce=0.75, run_for=30.0):
    import neuralmind.watcher as watcher_mod

    batches: list[list[str]] = []
    w = FileActivityWatcher(
        tmp_path,
        lambda paths: batches.append([os.path.basename(p) for p in paths]),
        debounce=debounce,
    )
    clock = _FakeClock(w, script, run_for)
    monkeypatch.setattr(watcher_mod, "time", clock)
    w._flush_loop()
    return batches


def _files(tmp_path, *names):
    paths = []
    for name in names:
        p = tmp_path.resolve() / name
        p.write_text("x = 1\n")
        paths.append(p)
    return paths


def test_edits_within_debounce_of_each_other_form_one_batch(monkeypatch, tmp_path):
    """Edits 0.5s apart (debounce 0.75s) are one co-activation batch.

    The loop used to flush each path as soon as *it* was older than the
    debounce, so a, b, c edited 0.5s apart arrived as three single-file
    batches and activate_files never saw a cross-file pair or transition.
    """
    a, b, c = _files(tmp_path, "a.py", "b.py", "c.py")
    batches = _run_flush_loop(monkeypatch, tmp_path, [(0.0, a), (0.5, b), (1.0, c)])
    assert batches == [["a.py", "b.py", "c.py"]]


def test_quiet_gap_splits_batches_and_keeps_edit_order(monkeypatch, tmp_path):
    a, b, c = _files(tmp_path, "a.py", "b.py", "c.py")
    # b, a, then b again (latest timestamp wins); a quiet gap; then c.
    batches = _run_flush_loop(monkeypatch, tmp_path, [(0.0, b), (0.3, a), (0.6, b), (5.0, c)])
    assert batches == [["a.py", "b.py"], ["c.py"]]


def test_continuous_edits_still_flush_eventually(monkeypatch, tmp_path):
    """A file rewritten non-stop must not starve the batch forever."""
    from neuralmind.watcher import MAX_BATCH_DEBOUNCES

    noisy, other = _files(tmp_path, "noisy.py", "other.py")
    script = [(0.1, other)] + [(i * 0.25, noisy) for i in range(200)]
    batches = _run_flush_loop(monkeypatch, tmp_path, script, debounce=0.75, run_for=50.0)
    assert batches, "continuous edits starved the flush loop"
    assert "other.py" in batches[0]
    # The first flush happens within the max-wait window, not after the storm.
    assert len(batches) >= int(50.0 / (0.75 * MAX_BATCH_DEBOUNCES)) - 1
