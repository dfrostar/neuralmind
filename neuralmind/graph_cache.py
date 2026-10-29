# SPDX-License-Identifier: MIT
"""graph_cache.py — the loaded graph, kept between processes in a fast binary file.

Every backend loads the whole graph before it answers: ``.neuralmind/
index_ir.json`` when it is at least as new as ``graph.json``, else
``graph.json``. A hook runs as a new process for every prompt, so it paid that
load every time. On hermes-agent (269,151 nodes, 634,765 edges, a 424 MB
``index_ir.json``) reading the IR and converting it back to the graph took
6.2 s of the ``prompt-submit`` hook's 8.5 s on an M3, and the Hermes plugin
stops a hook after 8 s.

``graph_cache.marshal`` next to the IR holds that converted graph in
:mod:`marshal` format, which reads back in about 0.4 s there. Its header is the
size, mtime and inode of both source files, the NeuralMind version (the IR
conversion can change between versions) and the Python version (marshal's
format belongs to the interpreter). A header that doesn't match, an unreadable
file or anything that isn't a graph dict means the sources are read as before:
the cache changes how fast the graph loads, never what loads.

A load that missed writes the cache, when the file it read is at least
``CACHE_MIN_BYTES``: below that, JSON is fast enough and the copy isn't worth
the disk. ``neuralmind build`` writes it too (:func:`warm`), so the first hook
after a build is fast. A hook that finds it missing or stale also starts
:func:`warm_in_background` before its own load: on a slower machine that load
outlasts the Hermes plugin's timeout, and a hook stopped mid-load would never
write the cache, so every later prompt would miss again. Writes go to a
temporary file renamed into place, so a reader never sees half of one.
``NEURALMIND_GRAPH_CACHE=0`` turns the cache off, reading and writing.

The file holds the same labels and paths as ``graph.json``, in the same
self-ignoring ``.neuralmind/`` directory. :mod:`marshal` builds only plain
values (it never runs code while loading), but it isn't meant for files
someone else wrote: this one is written and read by NeuralMind on one machine,
like ``synapses.db`` beside it.
"""

from __future__ import annotations

import json
import logging
import marshal
import os
import secrets
import subprocess  # nosec B404 - starts this interpreter with a fixed argument list, no shell
import sys
from pathlib import Path
from typing import Any

try:  # POSIX
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]
try:  # Windows
    import msvcrt
except ImportError:
    msvcrt = None  # type: ignore[assignment]

CACHE_ENV = "NEURALMIND_GRAPH_CACHE"
CACHE_FILENAME = "graph_cache.marshal"
LOCK_FILENAME = "graph_cache.lock"

logger = logging.getLogger(__name__)
# Smaller sources aren't cached: a 16 MB IR converts in about 0.2 s.
CACHE_MIN_BYTES = 16 * 1024 * 1024
_MAGIC = b"NMGRAPH1 "
# Longer than any header the key makes; bounds the read of a corrupt file.
_HEADER_MAX = 64 * 1024


def enabled() -> bool:
    return os.environ.get(CACHE_ENV) != "0"


def cache_path(ir_path: Path) -> Path:
    return Path(ir_path).with_name(CACHE_FILENAME)


def prefer_ir(ir_path: Path, graph_path: Path) -> bool:
    """True when the persisted IR is present and not stale vs graph.json."""
    if not ir_path.exists():
        return False
    if not graph_path.exists():
        return True
    try:
        return ir_path.stat().st_mtime >= graph_path.stat().st_mtime
    except OSError:
        return False


def load(ir_path: Path, graph_path: Path) -> dict[str, Any] | None:
    """The graph a backend loads, from the cache when it matches. None when there is none.

    Raises as reading ``graph.json`` does, as the backends always have.
    """
    ir_path, graph_path = Path(ir_path), Path(graph_path)
    if not enabled():
        return _read_sources(ir_path, graph_path)[0]
    key = _key(ir_path, graph_path)
    cached = _read(cache_path(ir_path), key)
    if cached is not None:
        return cached
    graph, size = _read_sources(ir_path, graph_path)
    # A source rewritten while it was read: its graph doesn't belong to either stat.
    if graph is not None and size >= CACHE_MIN_BYTES and _key(ir_path, graph_path) == key:
        _write(cache_path(ir_path), key, graph)
    return graph


def warm(ir_path: Path, graph_path: Path) -> None:
    """Write the cache for the sources as they are now, if it's missing or stale. Fails open."""
    ir_path, graph_path = Path(ir_path), Path(graph_path)
    try:
        if _needs_writing(ir_path, graph_path):
            load(ir_path, graph_path)
    except Exception:
        logger.debug("graph cache not written for %s", ir_path, exc_info=True)


def warm_in_background(project_path: str | Path) -> bool:
    """Start a detached process that writes the project's cache, when it needs writing.

    True when one was started. The child outlives the hook that starts it,
    and its output goes nowhere, so a caller waiting on the hook's pipes isn't
    kept waiting by it. Only one runs per project at a time (:func:`_main`).
    Fails open.
    """
    try:
        from .child_python import HAS_SAFE_PATH, python_argv, python_env
        from .paths import graph_json_path

        root = Path(project_path).resolve()
        ir_path = root / ".neuralmind" / "index_ir.json"
        if not _needs_writing(ir_path, graph_json_path(root)):
            return False
        # This interpreter, a fixed module, and the resolved project path as one argument.
        subprocess.Popen(  # nosec B603 - fixed argument list, no shell
            python_argv("-m", "neuralmind.graph_cache", str(root)),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            # 3.10 has no -P: start in the state directory, which holds no modules.
            cwd=None if HAS_SAFE_PATH else str(ir_path.parent),
            env=python_env(),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except Exception:
        return False


def _needs_writing(ir_path: Path, graph_path: Path) -> bool:
    """Whether a large enough source has no current cache, in a directory it can be written to.

    An unwritable ``.neuralmind/`` would otherwise have every prompt start a
    writer that loads the whole graph and then can't write it.
    """
    if not enabled() or not ir_path.parent.is_dir() or not os.access(ir_path.parent, os.W_OK):
        return False
    source = ir_path if prefer_ir(ir_path, graph_path) else graph_path
    if _size(source) < CACHE_MIN_BYTES:
        return False
    return not _header_matches(cache_path(ir_path), _key(ir_path, graph_path))


def _main(argv: list[str]) -> int:
    """``python -m neuralmind.graph_cache <project>``: write its cache, under its lock.

    A second warmer started while one runs exits at once: the OS lock is
    released when its holder exits, however it exits.
    """
    if len(argv) != 1:
        return 2
    from .paths import graph_json_path

    root = Path(argv[0]).resolve()
    state = root / ".neuralmind"
    if not state.is_dir():
        return 0
    try:
        fd = os.open(state / LOCK_FILENAME, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError:
        return 0
    try:
        if _try_lock(fd):
            warm(state / "index_ir.json", graph_json_path(root))
    finally:
        os.close(fd)
    return 0


def _try_lock(fd: int) -> bool:
    """Take the lock without blocking; False while another process holds it."""
    try:
        if fcntl is not None:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        elif msvcrt is not None:  # pragma: no cover - Windows
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        return True
    except OSError:
        return False


def _read_sources(ir_path: Path, graph_path: Path) -> tuple[dict[str, Any] | None, int]:
    """The graph from the IR or graph.json, and the size of the file it came from."""
    from . import ir as ir_mod

    if prefer_ir(ir_path, graph_path):
        try:
            index_ir = ir_mod.IndexIR.from_dict(json.loads(ir_path.read_text(encoding="utf-8")))
            return ir_mod.to_graph_json(index_ir), _size(ir_path)
        except (json.JSONDecodeError, ir_mod.IRError, KeyError, ValueError):
            pass
    if not graph_path.exists():
        return None, 0
    with graph_path.open(encoding="utf-8") as f:
        return json.load(f), _size(graph_path)


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _stat(path: Path) -> list[int] | None:
    # Not the path: a backend and a warmer can spell the same file differently.
    try:
        st = path.stat()
    except OSError:
        return None
    return [st.st_size, st.st_mtime_ns, st.st_ino]


def _key(ir_path: Path, graph_path: Path) -> bytes:
    from . import __version__

    key = {
        "graph": _stat(graph_path),
        "ir": _stat(ir_path),
        "marshal": marshal.version,
        "neuralmind": __version__,
        "python": list(sys.version_info[:2]),
    }
    return _MAGIC + json.dumps(key, sort_keys=True).encode("utf-8") + b"\n"


def _header_matches(path: Path, key: bytes) -> bool:
    try:
        with path.open("rb") as fh:
            return fh.readline(_HEADER_MAX) == key
    except OSError:
        return False


def _read(path: Path, key: bytes) -> dict[str, Any] | None:
    try:
        with path.open("rb") as fh:
            if fh.readline(_HEADER_MAX) != key:
                return None
            # NeuralMind's own file in the self-ignoring state directory, behind a
            # header that must match; marshal builds plain values and runs no code,
            # and the result is type-checked below (see the module docstring).
            graph = marshal.loads(fh.read())  # nosec B302
    except (OSError, EOFError, ValueError, TypeError):
        return None
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list):
        return None
    return graph


def _write(path: Path, key: bytes, graph: dict[str, Any]) -> None:
    """Write the cache atomically; skipped when ``.neuralmind/`` doesn't exist. Fails open."""
    if not path.parent.is_dir():
        return
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    try:
        data = marshal.dumps(graph)
        with tmp.open("wb") as fh:
            fh.write(key)
            fh.write(data)
        os.replace(tmp, path)
    except (OSError, ValueError):
        try:
            tmp.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
