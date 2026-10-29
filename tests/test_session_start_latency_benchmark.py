"""The session-start benchmark tells a detached process's end from none (tests/benchmark/session_start_latency.py)."""

from __future__ import annotations

import os
import sys
import time

import pytest

from tests.benchmark import session_start_latency


@pytest.fixture
def fast(monkeypatch):
    monkeypatch.setattr(session_start_latency, "START_WAIT", 0.3)


def test_no_process_is_no_end(tmp_path, fast):
    (tmp_path / ".neuralmind").mkdir()
    assert session_start_latency._maintenance_end(tmp_path) is None


@pytest.mark.skipif(sys.platform == "win32", reason="flock")
def test_the_end_is_when_the_lock_is_released(tmp_path, fast):
    import fcntl
    import threading

    (tmp_path / ".neuralmind").mkdir()
    lock = tmp_path / ".neuralmind" / session_start_latency.LOCK_FILENAME
    fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    released = []

    def release():
        time.sleep(0.5)
        released.append(time.perf_counter())
        os.close(fd)

    threading.Thread(target=release).start()
    end = session_start_latency._maintenance_end(tmp_path)
    assert end is not None and end >= released[0]


def test_the_lock_name_is_the_one_the_hook_uses():
    from neuralmind import session_maintenance

    assert session_start_latency.LOCK_FILENAME == session_maintenance.LOCK_FILENAME
