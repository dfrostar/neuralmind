"""child_python.py — start this interpreter as a child, clear of the caller's cwd.

``python -c`` and ``python -m`` put the working directory first on
``sys.path``, ahead of the standard library. NeuralMind runs from inside
users' repositories, so a child started in a package folder with its own
``types.py`` or ``enum.py`` (click's ``src/click/`` has a ``types.py``)
imports that instead, and dies before running a line of NeuralMind:
``import base64`` -> ``re`` -> ``enum`` -> ``from types import ...``.

* Python 3.11+: ``-P`` keeps the working directory off ``sys.path``.
* Python 3.10 has no ``-P`` and ignores ``PYTHONSAFEPATH``, so the child runs
  from an empty temporary directory instead: the entry is still added, but
  there is nothing in it to find.

Not ``-I``: that also drops ``PYTHONPATH``, which running a checkout relies on
(``PYTHONPATH=<worktree> python -m evals.public.run``).
"""

from __future__ import annotations

import contextlib
import os
import sys
import tempfile
from collections.abc import Iterator

# Whether this interpreter has ``-P`` (Python 3.11+).
HAS_SAFE_PATH = sys.version_info >= (3, 11)

# Path settings made absolute for the child, so they mean the same thing from
# the 3.10 child's temporary directory. A pre-seeded model the child failed to
# find would be downloaded: the network request the setting exists to avoid.
_PATH_SETTINGS = ("NEURALMIND_ONNX_MODEL_DIR",)


def python_argv(*args: str) -> list[str]:
    """The command that runs this interpreter with ``args`` (``-c ...``, ``-m ...``)."""
    if HAS_SAFE_PATH:
        return [sys.executable, "-P", *args]
    return [sys.executable, *args]


@contextlib.contextmanager
def python_cwd() -> Iterator[str | None]:
    """The working directory to start a :func:`python_argv` child in.

    ``None``, the caller's own, where ``-P`` covers it; on 3.10 an empty
    temporary directory, removed on exit. Give the child absolute paths.
    """
    if HAS_SAFE_PATH:
        yield None
        return
    with tempfile.TemporaryDirectory(prefix="neuralmind-") as empty:
        yield empty


def python_env() -> dict[str, str]:
    """The environment for a :func:`python_argv` child: this process's own,
    with relative path settings made absolute."""
    env = dict(os.environ)
    for name in _PATH_SETTINGS:
        if env.get(name):
            env[name] = os.path.abspath(env[name])
    return env
