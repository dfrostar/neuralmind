# SPDX-License-Identifier: MIT
"""session_maintenance.py — the session-start hook's synapse-store work, off the hook's clock.

When a session starts, the hook runs one decay tick over the synapse store,
imports the committed team memory, tunes the selector (opt-in) and exports the
learned associations to ``SYNAPSE_MEMORY.md``. Decay and the export pass over
whole tables: on a hermes-agent store (1,272,023 synapse edges) they took about
6 s of the hook's 6.3–7.7 s on a loaded Linux machine. The Hermes plugin stops
a hook after 8 s and drops its output, so the recap the hook had already
written was lost.

Below ``INLINE_MAX_BYTES`` of ``synapses.db`` the hook still runs them itself,
so the export is on disk before the hook returns. At or above it,
:func:`run_or_start` starts ``python -m neuralmind.session_maintenance
<project>``, a detached process whose output goes nowhere, and the hook
returns. The child runs the same steps in the same order, reading the same
environment switches, so the store and the file end up as the hook would have
left them, a few seconds later. Only one runs per project at a time
(:func:`_main`).
"""

from __future__ import annotations

import logging
import os
import subprocess  # nosec B404 - starts this interpreter with a fixed argument list, no shell
import sys
from pathlib import Path

LOCK_FILENAME = "session_maintenance.lock"
# The work grows with the synapse rows, the file with those and the build's
# structural tables, so a store under the limit holds few enough rows to run
# here. Measured 2026-10-28 on an M3: this repository's 13 MB store took
# 0.1 s, a 79 MB one holding 115,639 edges 0.44 s, and a 1.07 GB one holding
# 1,272,023 (hermes-agent's count) 3.9 s.
INLINE_MAX_BYTES = 64 * 1024 * 1024

logger = logging.getLogger(__name__)


def _export_enabled() -> bool:
    return os.environ.get("NEURALMIND_SYNAPSE_EXPORT") != "0"


def run(project_path: str | Path) -> None:
    """Decay, team-memory import, selector autotune and memory export, in that order.

    Under ``NEURALMIND_NO_LEARN=1`` only the read-only export runs. Each step
    fails open.
    """
    from .learning import learning_disabled

    project_path = str(project_path)
    if not learning_disabled():
        try:
            from .namespaces import resolve_namespace
            from .synapses import SynapseStore, default_db_path

            store = SynapseStore(
                default_db_path(project_path), namespace=resolve_namespace(project_path)
            )
        except Exception:
            return
        try:
            store.decay()
        except Exception:
            logger.debug("decay tick failed for %s", project_path, exc_info=True)
        # Team memory: inherit the committed team bundle once into `shared`, so a
        # fresh clone's agent starts with the team's learned associations. Gated
        # by NEURALMIND_TEAM_MEMORY=0; idempotent (content-hash) and fail-open.
        try:
            from .team_memory import maybe_import_team_memory

            maybe_import_team_memory(project_path, store)
        except Exception:
            logger.debug("team-memory import failed for %s", project_path, exc_info=True)
        # Self-improvement engine: tune the selector from logged usage. Opt-in
        # (not the != "0" pattern) because it is net behavior change. Runs at
        # most once per session, here at the boundary; tune_selector fails open.
        if os.environ.get("NEURALMIND_SELECTOR_AUTOTUNE") == "1":
            try:
                from .self_improve import tune_selector

                tune_selector(project_path)
            except Exception:
                logger.debug("selector autotune failed for %s", project_path, exc_info=True)
    if _export_enabled():
        try:
            from .synapse_memory import export_synapse_memory

            export_synapse_memory(project_path)
        except Exception:
            logger.debug("synapse memory export failed for %s", project_path, exc_info=True)


def run_or_start(project_path: str | Path) -> bool:
    """:func:`run` here for a small store; for a large one, in a detached process.

    True when a process was started. One that can't be started is skipped
    rather than run here: the hook would overrun the caller's timeout, and
    the next session's tick covers the decay owed (``SynapseStore.decay``).
    """
    from .learning import learning_disabled
    from .synapses import default_db_path

    if learning_disabled() and not _export_enabled():
        return False
    project_path = os.path.abspath(project_path)
    try:
        size = default_db_path(project_path).stat().st_size
    except OSError:
        size = 0
    if size < INLINE_MAX_BYTES:
        run(project_path)
        return False
    try:
        from .child_python import HAS_SAFE_PATH, python_argv, python_env

        state = Path(project_path) / ".neuralmind"
        # This interpreter, a fixed module, and the project path as one argument.
        subprocess.Popen(  # nosec B603 - fixed argument list, no shell
            python_argv("-m", "neuralmind.session_maintenance", project_path),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            # 3.10 has no -P: start in the state directory, which holds no modules.
            cwd=None if HAS_SAFE_PATH else str(state),
            env=python_env(),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except Exception:
        return False


def _main(argv: list[str]) -> int:
    """``python -m neuralmind.session_maintenance <project>``: :func:`run`, under its lock.

    A second one started while one runs exits at once: the first is already
    doing what the second would.
    """
    if len(argv) != 1:
        return 2
    from .graph_cache import _try_lock

    state = Path(argv[0]) / ".neuralmind"
    if not state.is_dir():
        return 0
    try:
        fd = os.open(state / LOCK_FILENAME, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError:
        return 0
    try:
        if _try_lock(fd):
            run(argv[0])
    finally:
        os.close(fd)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
