"""
watcher.py — File change watcher that feeds activation signals.

Watches the project tree and treats any file edit as a soft activation
signal for the nodes that live in that file. Edits in close temporal
proximity reinforce synapses between their files (the brain analogue of
"these things were touched together"), even when the LLM never queried
NeuralMind directly.

The watcher uses ``watchdog`` if installed and falls back to a polling
loop based on file mtimes when it isn't, so it works in lightweight
environments without an extra dependency.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterable
from pathlib import Path

CoActivationCallback = Callable[[list[str]], None]

DEFAULT_DEBOUNCE = 0.75
DEFAULT_POLL_INTERVAL = 2.0
DEFAULT_IGNORES = (
    ".git",
    ".neuralmind",
    "graphify-out",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
)


def _is_ignored(path: Path, project_root: Path, ignores: Iterable[str]) -> bool:
    try:
        rel = path.relative_to(project_root)
    except ValueError:
        return True
    parts = set(rel.parts)
    return any(token in parts for token in ignores)


class FileActivityWatcher:
    """Coalesces file edits into co-activation batches.

    Edits arriving within ``debounce`` seconds of each other are grouped
    and delivered as a single batch to ``callback``. The callback runs on
    the watcher thread and should be cheap (just enqueue the work).
    """

    def __init__(
        self,
        project_path: str | Path,
        callback: CoActivationCallback,
        debounce: float = DEFAULT_DEBOUNCE,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        ignores: Iterable[str] = DEFAULT_IGNORES,
    ):
        self.project_path = Path(project_path).resolve()
        self.callback = callback
        self.debounce = debounce
        self.poll_interval = poll_interval
        self.ignores = tuple(ignores)
        self._pending: dict[str, float] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._flusher: threading.Thread | None = None
        self._observer = None
        self._poll_thread: threading.Thread | None = None
        self._mtimes: dict[str, float] = {}

    def _record(self, path: Path) -> None:
        if _is_ignored(path, self.project_path, self.ignores):
            return
        if not path.is_file():
            return
        with self._lock:
            self._pending[str(path)] = time.time()

    def _flush_loop(self) -> None:
        while not self._stop.is_set():
            time.sleep(self.debounce / 2)
            cutoff = time.time() - self.debounce
            with self._lock:
                ready = [p for p, ts in self._pending.items() if ts <= cutoff]
                for p in ready:
                    self._pending.pop(p, None)
            if ready:
                try:
                    self.callback(ready)
                except Exception:
                    pass

    def _poll_loop(self) -> None:
        while not self._stop.is_set():
            try:
                for path in self.project_path.rglob("*"):
                    if _is_ignored(path, self.project_path, self.ignores):
                        continue
                    if not path.is_file():
                        continue
                    try:
                        mtime = path.stat().st_mtime
                    except OSError:
                        continue
                    key = str(path)
                    prev = self._mtimes.get(key)
                    if prev is None:
                        self._mtimes[key] = mtime
                        continue
                    if mtime > prev:
                        self._mtimes[key] = mtime
                        self._record(path)
            except Exception:
                pass
            self._stop.wait(self.poll_interval)

    def start(self) -> None:
        if self._flusher is not None:
            return
        self._stop.clear()
        self._flusher = threading.Thread(target=self._flush_loop, daemon=True)
        self._flusher.start()

        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer

            class _Handler(FileSystemEventHandler):
                def __init__(self, outer: FileActivityWatcher):
                    self.outer = outer

                def on_modified(self, event):
                    if event.is_directory:
                        return
                    self.outer._record(Path(event.src_path))

                def on_created(self, event):
                    if event.is_directory:
                        return
                    self.outer._record(Path(event.src_path))

            self._observer = Observer()
            self._observer.schedule(_Handler(self), str(self.project_path), recursive=True)
            self._observer.start()
        except Exception:
            self._observer = None
            self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._poll_thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=2.0)
            except Exception:
                pass
            self._observer = None
        if self._poll_thread is not None:
            self._poll_thread.join(timeout=2.0)
            self._poll_thread = None
        if self._flusher is not None:
            self._flusher.join(timeout=2.0)
            self._flusher = None

    def __enter__(self) -> FileActivityWatcher:
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()
