"""ignore.py — which files are in the index: what git covers, minus our ignores.

By default the index covers what git covers. Inside a git repository the file
list comes from git itself::

    git ls-files --cached --others --exclude-standard   # tracked + untracked, not ignored
    git ls-files --cached --ignored --exclude-standard  # tracked but matching an ignore rule

and the second list is subtracted from the first. ``--exclude-standard`` makes
git apply nested ``.gitignore`` files, ``.git/info/exclude`` and the global
excludes file exactly as git does, with no reimplementation here. Tracked files
that match an ignore rule (force-added copies under an ignored directory) are
excluded too: the rule states the intent, and those copies are exactly what
duplicates symbols in the index.

Outside a git repository (or without git), callers walk the tree and apply the
top-level ``.gitignore`` with :func:`matches`, which implements gitignore
pattern semantics: last match wins, ``!`` re-includes, ``/`` anchors, ``**``
crosses directories. ``.neuralmindignore`` uses the same engine, so both files
mean the same thing.

``.neuralmind.yaml`` widens or turns this off:

* ``respect_gitignore: false`` — index ignored files again (v4.4 behaviour)
* ``include_ignored: ["generated/api/**"]`` — pull specific ignored paths back in
"""

from __future__ import annotations

import os
import re
import subprocess
from collections import Counter
from pathlib import Path

_GIT_TIMEOUT_S = 20


# --------------------------------------------------------------------------- #
# gitignore pattern semantics
# --------------------------------------------------------------------------- #
def load_patterns(project_path: Path, filename: str) -> tuple[str, ...]:
    """``.gitignore``-style patterns from ``filename`` under ``project_path``, in order."""
    ignore_path = Path(project_path) / filename
    if not ignore_path.exists():
        return ()
    try:
        content = ignore_path.read_text(encoding="utf-8")
    except OSError:
        return ()

    patterns: list[str] = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return tuple(patterns)


def pattern_regex(pattern: str):
    """Translate one .gitignore pattern to a regex matching a repo-relative path.

    - A trailing ``/`` means directory-only; the pattern matches the dir
      path itself or anything under it.
    - A leading ``/`` anchors the pattern to the repo root.
    - A ``/`` anywhere else also anchors the pattern (gitignore rule).
    - Without a ``/``, the pattern matches the basename at any depth.
    - ``**`` matches across path separators; ``*``/``?`` do not cross ``/``.
    Returns None for empty/comment patterns.
    """
    p = pattern.strip()
    if not p or p.startswith("#"):
        return None
    dir_only = p.endswith("/")
    if dir_only:
        p = p.rstrip("/")
    rooted = p.startswith("/")
    if rooted:
        p = p.lstrip("/")
    # A '/' anywhere in the pattern anchors it to the repo root
    # (gitignore rule), except the '**/' prefix which means "any depth".
    leading_dstar = p.startswith("**/")
    anchored = rooted or ("/" in p and not leading_dstar)
    if leading_dstar:
        p = p[3:]

    out = ["^"]
    i = 0
    while i < len(p):
        c = p[i]
        if c == "*":
            if i + 1 < len(p) and p[i + 1] == "*":
                if i + 2 < len(p) and p[i + 2] == "/":
                    out.append("(?:[^/]+/)*")
                    i += 3
                else:
                    out.append(".*")
                    i += 2
            else:
                out.append("[^/]*")
                i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c in ".[](){}+^$|\\":
            out.append("\\" + c)
            i += 1
        else:
            out.append(c)
            i += 1
    out.append("$")
    body = "".join(out)

    if anchored:
        if dir_only:
            return re.compile(body[:-1] + "(?:/.*)?$")
        # An anchored pattern also ignores everything under a directory it names.
        return re.compile(body[:-1] + "(?:/.*)?$")

    # Unanchored patterns match at any depth. For a file pattern this is a
    # basename match anywhere; the same glob ALSO matches a directory name
    # anywhere (gitignore: "temp*" ignores a/temporary/x; "**/name" matches
    # both nested/name/x and bare name).
    prefix = "^(?:.*/)?"
    if dir_only:
        return re.compile(prefix + body[1:-1] + "(?:/.*)?$")
    return re.compile(prefix + body[1:] + "|" + prefix + body[1:-1] + "(?:/.*)?$")


def matches(rel_path: str, patterns: tuple[str, ...] | list[str]) -> bool:
    """True when project-relative ``rel_path`` is ignored by ``patterns``.

    Follows gitignore's last-matching-pattern-wins semantics, including
    negation (``!pattern``) re-inclusion.
    """
    if not patterns:
        return False

    ignored = False
    for pattern in patterns:
        negated = pattern.startswith("!")
        if negated:
            pattern = pattern[1:].strip()
            if not pattern:
                continue
        rx = pattern_regex(pattern)
        if rx is not None and rx.match(rel_path):
            ignored = not negated
    return ignored


# --------------------------------------------------------------------------- #
# git-backed listing
# --------------------------------------------------------------------------- #
def _git_lines(root: Path, *args: str) -> list[str] | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            timeout=_GIT_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    out = proc.stdout.decode("utf-8", errors="surrogateescape")
    return [p for p in out.split("\0") if p]


def inside_git_work_tree(root: str | Path) -> bool:
    """Cheap pre-check before spawning git: a ``.git`` in ``root`` or above.

    Spawning a process costs tens of milliseconds (more on Windows), and many
    projects — scratch dirs, test fixtures, unpacked archives — aren't
    repositories. ``GIT_DIR`` in the environment means git may work without a
    ``.git`` entry, so it always gets asked then.
    """
    if os.environ.get("GIT_DIR"):
        return True
    root = Path(root).resolve()
    return any((directory / ".git").exists() for directory in (root, *root.parents))


def git_visible_files(root: str | Path) -> set[str] | None:
    """Files git covers under ``root`` (POSIX, relative), or None outside git.

    Tracked and untracked-but-not-ignored files, minus tracked files that
    match an ignore rule. Index entries whose file is gone from disk are
    dropped.
    """
    root = Path(root)
    if not inside_git_work_tree(root):
        return None
    # ``--stage`` prefixes each tracked entry with its mode, so submodules
    # (mode 160000) are known without a stat per file; untracked entries come
    # through bare, and an untracked nested repository as ``dir/``.
    listed = _git_lines(
        root, "ls-files", "-z", "--stage", "--cached", "--others", "--exclude-standard"
    )
    if listed is None:
        return None
    if not listed and _root_is_ignored(root):
        # The project sits in a directory the enclosing repository ignores (a
        # scratch dir, a vendored checkout). That repository's rules say
        # nothing about this project, so walk it with its own .gitignore.
        return None
    excluded = set(
        _git_lines(root, "ls-files", "-z", "--cached", "--ignored", "--exclude-standard") or []
    )
    # Index entries whose file is gone from disk.
    excluded.update(_git_lines(root, "ls-files", "-z", "--deleted") or [])
    files: set[str] = set()
    repos: list[str] = []
    for entry in listed:
        staged = _STAGE_ENTRY.match(entry)
        if staged:
            path = entry[staged.end() :]
            if staged.group(1) == "160000":
                repos.append(path)
            elif path not in excluded:
                files.add(path)
        elif entry.endswith("/"):
            repos.append(entry.rstrip("/"))
        elif entry not in excluded:
            files.add(entry)
    for p in repos:
        if p in excluded:
            continue
        # A submodule or nested repository: git lists the gitlink, not its
        # files. Ask its own git so its .gitignore applies as well.
        full = root / p
        inner = _git_lines(full, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
        files.update(f"{p}/{q}" for q in inner or [] if (full / q).is_file())
    return files


# ``<mode> <object> <stage>\t<path>`` as ``git ls-files --stage`` prints it.
_STAGE_ENTRY = re.compile(r"([0-7]{6}) [0-9a-f]{40,64} [0-3]\t")


def _root_is_ignored(root: Path) -> bool:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "check-ignore", "-q", "."],
            capture_output=True,
            timeout=_GIT_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def is_git_repo(root: str | Path) -> bool:
    return _git_lines(Path(root), "rev-parse", "--show-toplevel") is not None


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def summarize_exclusions(paths: list[str], top: int = 5) -> str:
    """``412 files (projects/ 380, examples/out/ 32)`` — counts by top directory."""
    if not paths:
        return "0 files"
    by_dir: Counter[str] = Counter()
    for p in paths:
        head = p.split("/", 1)[0]
        by_dir[f"{head}/" if "/" in p else head] += 1
    parts = ", ".join(f"{d} {n:,}" for d, n in by_dir.most_common(top))
    more = ", ..." if len(by_dir) > top else ""
    return f"{len(paths):,} file{'s' if len(paths) != 1 else ''} ({parts}{more})"
