"""state_dir.py — the project-local ``.neuralmind/`` state directory

``<project>/.neuralmind/`` holds per-machine state: the synapse store,
index metadata, the event log, and a cache of the most recent Bash
stdout/stderr. None of it is portable, and the output cache can contain
whatever a developer's commands printed — including credentials.

NeuralMind's own repository git-ignores the directory, but a *user's*
repository has no such entry, so a routine ``git add -A`` after a build
would commit the whole thing. This module closes that gap by writing a
self-ignoring ``.gitignore`` inside the directory the moment it is
created, which is the one place the protection travels with the state
rather than depending on the host project's configuration.

Everything here is fail-open: a read-only checkout or an exotic
filesystem must degrade to "no guard written", never to a failed build.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

STATE_DIR_NAME = ".neuralmind"

# The only filename this module ever writes. Pinned so the write sink stays
# a constant even though the directory it lands in is caller-supplied.
GUARD_FILENAME = ".gitignore"

# Appended when a .gitignore already exists but does not ignore everything.
_MANAGED_RULE = """
# Added by NeuralMind: without a catch-all this directory is stageable, and
# it holds per-machine state including a cache of recent command output.
*
"""

# A ``.gitignore`` containing ``*`` ignores every entry in its own
# directory, itself included, so the whole tree stays untracked with a
# single file and no entry in the host project's .gitignore.
_GUARD_CONTENTS = """\
# Created automatically by NeuralMind — do not commit this directory.
#
# .neuralmind/ holds per-machine state: the synapse store, index
# metadata, the event log, and last_output.json (a cache of the most
# recent Bash stdout/stderr, which can contain credentials your commands
# printed). None of it is portable between machines.
#
# The `*` below makes this directory ignore itself, so no entry is
# needed in your project's own .gitignore.
*
"""


def state_dir(project_path: str | Path) -> Path:
    """Resolve ``<project>/.neuralmind`` without creating it."""
    return Path(project_path).resolve() / STATE_DIR_NAME


def _install_guard(target: Path) -> None:
    """Write the self-ignoring ``.gitignore`` into a state directory.

    Self-validating: refuses any directory not named ``.neuralmind``, and
    writes only the fixed ``GUARD_FILENAME``. The path reaching here derives
    from a caller-supplied project path — a CLI argument, or an MCP tool
    input an agent chose — so the write is pinned to a known filename inside
    a known directory name rather than trusting that caller. The path is
    resolved first, so ``..`` segments cannot walk out of the project.

    That makes this the only place a guard file is ever written, and makes a
    bug in any caller unable to scatter ``.gitignore`` files across a disk.

    Idempotent: an existing file is left alone so a user who deliberately
    edited it keeps their version. Never raises.
    """
    try:
        resolved = target.resolve()
        if resolved.name != STATE_DIR_NAME or not resolved.is_dir():
            return
        guard = resolved / GUARD_FILENAME
        if not guard.exists():
            guard.write_text(_GUARD_CONTENTS, encoding="utf-8")
            return
        # An existing file is not proof of protection. An empty or
        # narrowly-scoped .gitignore left the directory stageable while this
        # function reported success, so the documented guarantee quietly did
        # not hold. Preserve whatever the user wrote and append the managed
        # catch-all rather than replacing their rules.
        existing = guard.read_text(encoding="utf-8")
        if any(line.strip() == "*" for line in existing.splitlines()):
            return
        separator = "" if existing.endswith("\n") or not existing else "\n"
        guard.write_text(existing + separator + _MANAGED_RULE, encoding="utf-8")
    except OSError:
        pass  # read-only checkout, permission denied — never fatal


def ensure_state_dir(project_path: str | Path) -> Path:
    """Create ``<project>/.neuralmind`` and make it self-ignoring.

    Returns the directory path; never raises.
    """
    target = state_dir(project_path)
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError:
        return target  # read-only checkout — nothing to guard
    _install_guard(target)
    return target


def ensure_parent_dir(file_path: str | Path) -> Path:
    """Create the parent directory of a file, guarding it if it is state.

    Every module that writes into ``.neuralmind/`` goes through here rather
    than calling ``mkdir`` itself. The guard is only useful if it is
    installed by *whichever* flow creates the directory first — and for many
    users that is not ``build``. A fresh repo running ``neuralmind ingest``,
    or a hook initialising the synapse store, would otherwise materialise an
    unguarded state directory that the next ``git add -A`` happily stages.

    Returns the parent path; never raises.
    """
    # Resolve before use so a ".." segment in a caller-supplied path cannot
    # walk somewhere unintended. _install_guard re-checks the directory name,
    # so the guard is never written outside a state directory.
    try:
        parent = Path(file_path).resolve().parent
    except OSError:
        return Path(file_path).parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return parent
    _install_guard(parent)
    return parent


def tracked_state_files(project_path: str | Path) -> list[str]:
    """Files under ``.neuralmind/`` that git is *already* tracking.

    The ``.gitignore`` guard only affects untracked files, so a project
    that committed its state directory before upgrading stays exposed
    until those files are removed from the index. Returns an empty list
    when git is unavailable or the project is not a repository.
    """
    root = Path(project_path).resolve()
    try:
        result = subprocess.run(
            ["git", "ls-files", "--", STATE_DIR_NAME],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]
