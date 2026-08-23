"""Progress reporting for long-running CLI work (ingest, embed, scan).

Two rendering modes, picked from the destination stream:

- **TTY** — an in-place bar with a percentage and an ETA, redrawn at most
  every ``min_redraw_interval`` seconds so a fast loop doesn't spend its
  time writing escape sequences.
- **Not a TTY** (CI logs, agent shells, ``| tee``, a redirect) — plain
  milestone lines every ``milestone_pct`` percent. A long embed still
  shows movement instead of looking hung, and the log stays greppable.

Every terminal probe is guarded. ``isatty()`` raises on a closed stream,
on some pytest capture objects, and on a pipe whose fd has gone away —
the same class of failure behind the ``tcsetattr: Inappropriate ioctl
for device`` noise seen when NeuralMind runs under an agent shell. A
progress bar must never be the reason an ingest dies, so every write is
best-effort too.

Output goes to **stderr** by default, which keeps ``--json`` on stdout
machine-readable while progress is still visible.

Example:
    >>> from neuralmind.progress import ProgressReporter
    >>> with ProgressReporter(len(files), label="Embedding") as bar:
    ...     for f in files:
    ...         embed(f)
    ...         bar.advance(detail=f.name)
"""

from __future__ import annotations

import os
import sys
import time
from types import TracebackType
from typing import TextIO

__all__ = ["ProgressReporter", "format_duration", "stream_is_tty"]

_BAR_WIDTH = 24
_FILLED = "█"
_EMPTY = "░"


def stream_is_tty(stream: TextIO | None) -> bool:
    """True only when ``stream`` is a real terminal.

    Never raises: a missing/failing ``isatty`` means "not a terminal",
    which is the safe answer for every caller here.
    """
    if stream is None:
        return False
    isatty = getattr(stream, "isatty", None)
    if not callable(isatty):
        return False
    try:
        return bool(isatty())
    except Exception:
        return False


def format_duration(seconds: float) -> str:
    """Human-readable duration: ``42s``, ``3m07s``, ``1h04m``."""
    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        return "--"
    if seconds != seconds or seconds in (float("inf"), float("-inf")):  # NaN / inf
        return "--"
    seconds = max(0.0, seconds)
    if seconds < 10:
        # A decimal below 10s keeps short spans honest — rounding 2.6s to
        # "3s" reads as a contradiction next to a "--timeout 2" that fired.
        return f"{seconds:.1f}s"
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes, secs = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m{secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


class ProgressReporter:
    """Render progress for a bounded loop.

    Args:
        total: Number of units of work. ``0`` disables output — there is
            nothing to report progress against.
        label: Prefix shown before the bar (e.g. ``"Embedding"``).
        stream: Destination. Defaults to ``sys.stderr`` so stdout stays
            clean for ``--json``.
        enabled: Force output on/off. ``None`` (default) decides from
            ``total`` and ``NEURALMIND_NO_PROGRESS``.
        milestone_pct: Non-TTY line cadence, in percent.
        min_redraw_interval: Minimum seconds between TTY redraws.
    """

    def __init__(
        self,
        total: int,
        *,
        label: str = "",
        stream: TextIO | None = None,
        enabled: bool | None = None,
        milestone_pct: int = 10,
        min_redraw_interval: float = 0.1,
    ) -> None:
        try:
            self.total = max(0, int(total))
        except (TypeError, ValueError):
            self.total = 0
        self.label = label
        self._stream = sys.stderr if stream is None else stream
        self._tty = stream_is_tty(self._stream)
        if enabled is None:
            enabled = self.total > 0 and os.environ.get("NEURALMIND_NO_PROGRESS") != "1"
        self.enabled = bool(enabled)
        self._milestone_pct = max(1, int(milestone_pct))
        self._min_redraw = max(0.0, float(min_redraw_interval))

        self.done = 0
        self._start = time.monotonic()
        self._last_draw = 0.0
        self._last_milestone = -1
        self._painted = 0  # width of the bar currently on screen (TTY only)

    # -- lifecycle ---------------------------------------------------------- #
    def __enter__(self) -> ProgressReporter:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # Clear the bar even when the loop raised, so the traceback isn't
        # printed on top of a half-drawn line.
        self.clear()

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._start

    # -- reporting ---------------------------------------------------------- #
    def advance(self, n: int = 1, detail: str = "") -> None:
        """Record ``n`` completed units and redraw if it's time to."""
        self.done += max(0, int(n))
        if self.total:
            self.done = min(self.done, self.total)
        if not self.enabled:
            return
        if self._tty:
            self._draw(detail, force=self.done >= self.total)
        else:
            self._milestone(detail)

    def write_line(self, text: str) -> None:
        """Print a line without smearing an in-place bar.

        Verbose per-item logging goes through here so the bar is cleared
        first and repainted on the next ``advance``.
        """
        self.clear()
        self._write(f"{text}\n")

    def clear(self) -> None:
        """Erase the in-place bar, if one is on screen."""
        if self._painted:
            self._write("\r" + " " * self._painted + "\r")
            self._painted = 0

    def finish(self, summary: str = "") -> None:
        """Clear the bar and optionally print a closing line."""
        self.clear()
        if summary and self.enabled:
            self._write(f"{summary}\n")

    # -- internals ---------------------------------------------------------- #
    def _eta_text(self) -> str:
        elapsed = self.elapsed
        if self.done <= 0 or self.total <= 0:
            return f"{format_duration(elapsed)} elapsed"
        remaining = (elapsed / self.done) * (self.total - self.done)
        if self.done >= self.total:
            return f"{format_duration(elapsed)} total"
        return f"{format_duration(elapsed)} elapsed, ~{format_duration(remaining)} left"

    def _draw(self, detail: str, force: bool = False) -> None:
        now = time.monotonic()
        if not force and (now - self._last_draw) < self._min_redraw:
            return
        self._last_draw = now
        frac = (self.done / self.total) if self.total else 0.0
        filled = int(round(frac * _BAR_WIDTH))
        bar = _FILLED * filled + _EMPTY * (_BAR_WIDTH - filled)
        prefix = f"{self.label} " if self.label else ""
        line = f"{prefix}[{bar}] {self.done}/{self.total} {frac * 100:5.1f}% · {self._eta_text()}"
        if detail:
            line = f"{line} · {detail}"
        line = self._truncate(line)
        pad = " " * max(0, self._painted - len(line))
        self._write(f"\r{line}{pad}")
        self._painted = len(line)

    def _milestone(self, detail: str) -> None:
        if self.total <= 0:
            return
        pct = int((self.done / self.total) * 100)
        bucket = pct - (pct % self._milestone_pct)
        # Always announce the final unit, even when it doesn't land on a bucket.
        final = self.done >= self.total
        if not final and bucket <= self._last_milestone:
            return
        self._last_milestone = max(bucket, self._last_milestone)
        prefix = f"{self.label} " if self.label else ""
        line = f"{prefix}{self.done}/{self.total} ({pct}%) · {self._eta_text()}"
        if detail:
            line = f"{line} · {detail}"
        self._write(f"{line}\n")

    @staticmethod
    def _truncate(line: str, limit: int = 200) -> str:
        try:
            limit = min(limit, max(40, (os.get_terminal_size().columns or limit) - 1))
        except Exception:
            # No controlling terminal — the same guard rationale as isatty().
            pass
        return line if len(line) <= limit else line[: limit - 1] + "…"

    def _write(self, text: str) -> None:
        try:
            self._stream.write(text)
            self._stream.flush()
        except Exception:
            # A broken pipe or a closed capture stream must not kill the
            # work the bar is only describing. Stop trying after the first
            # failure so we don't burn time per item.
            self.enabled = False
