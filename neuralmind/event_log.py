"""
event_log.py — JSONL bridge so live events cross process boundaries.

The in-process ``event_bus`` only fans events out to subscribers inside
the same Python process. That's enough for ``neuralmind serve``, but
``neuralmind watch`` (or a hook-driven Claude Code session) runs in a
separate process whose synapse reinforcements would never reach the
graph view's canvas otherwise.

This module solves that with a deliberately boring side channel:

- :class:`EventLogWriter` appends each published event as one JSON line
  to ``<project>/.neuralmind/events.jsonl``. Every event carries a
  ``_pid`` so consumers can tell self-emissions apart from cross-process
  ones.
- :class:`EventLogTailer` is a background thread used by the server. It
  seeks to end of file on start (no history replay), polls for new
  lines, parses each one, and fires a callback. The callback in
  ``server.py`` re-publishes external events on the local bus *without*
  going back through the writer — that's what keeps it from looping.

Both classes are best-effort: a flaky filesystem must never break a
synapse write or the live feed.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

DEFAULT_POLL_INTERVAL = 0.5

_MAX_LINE_BYTES = 64 * 1024  # Skip pathologically long lines.


class EventLogWriter:
    """Append JSON events to a line-delimited file. Thread-safe."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._broken = False

    def write(self, event: dict[str, Any]) -> bool:
        """Append one line. Returns True on success, False if swallowed.

        Once a write fails we set ``_broken`` so subsequent writes don't
        retry on every call — a single broken filesystem shouldn't
        thrash the hot path. Recover by constructing a new writer.
        """
        if self._broken:
            return False
        try:
            line = json.dumps(event, separators=(",", ":"), default=str)
        except (TypeError, ValueError):
            return False
        encoded = (line + "\n").encode("utf-8")
        with self._lock:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.path, "ab") as fh:
                    fh.write(encoded)
                return True
            except OSError:
                self._broken = True
                return False


class EventLogTailer:
    """Poll a JSONL event log and fire a callback for each new line.

    On ``start()`` we seek to the current end of file — historical
    events are deliberately not replayed. If the file is truncated,
    rotated, or replaced (size shrinks or inode changes), we re-open
    and resume from the new start.
    """

    def __init__(
        self,
        path: str | Path,
        on_event: Callable[[dict[str, Any]], None],
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ):
        self.path = Path(path)
        self._on_event = on_event
        self._poll_interval = poll_interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="event-log-tailer", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
        self._thread = None

    def _open_at_end(self):
        try:
            fh = open(self.path, "rb")
        except FileNotFoundError:
            return None, None
        except OSError:
            return None, None
        try:
            fh.seek(0, 2)  # to EOF
            offset = fh.tell()
            inode = self._stat_inode()
        except OSError:
            fh.close()
            return None, None
        return fh, (inode, offset)

    def _stat_inode(self) -> int | None:
        try:
            return self.path.stat().st_ino
        except OSError:
            return None

    def _run(self) -> None:
        fh = None
        inode: int | None = None
        buf = b""
        while not self._stop.is_set():
            if fh is None:
                fh, state = self._open_at_end()
                if fh is None:
                    if self._stop.wait(self._poll_interval):
                        return
                    continue
                inode = state[0] if state else None
                buf = b""
            # Detect rotation/truncation: inode change or size shrink.
            try:
                cur_inode = self._stat_inode()
                cur_size = self.path.stat().st_size
                if cur_inode != inode or cur_size < fh.tell():
                    fh.close()
                    fh = None
                    inode = None
                    continue
            except OSError:
                fh.close()
                fh = None
                continue

            chunk = fh.read(8192)
            if chunk:
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line or len(line) > _MAX_LINE_BYTES:
                        continue
                    self._dispatch(line)
                continue
            if self._stop.wait(self._poll_interval):
                break

        if fh is not None:
            try:
                fh.close()
            except OSError:
                pass

    def _dispatch(self, raw: bytes) -> None:
        try:
            event = json.loads(raw.decode("utf-8", errors="replace"))
        except (ValueError, UnicodeDecodeError):
            return
        if not isinstance(event, dict):
            return
        try:
            self._on_event(event)
        except Exception:
            # The callback must not be allowed to crash the tailer; the
            # whole point is "best-effort live feed."
            pass


def default_log_path(project_path: str | Path) -> Path:
    """Where the JSONL bridge lives for a given project."""
    return Path(project_path) / ".neuralmind" / "events.jsonl"


def event_log_enabled() -> bool:
    """``NEURALMIND_EVENT_LOG=0`` disables the cross-process bridge."""
    return os.environ.get("NEURALMIND_EVENT_LOG", "1") != "0"
