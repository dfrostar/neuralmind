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
top-level ``.gitignore`` with :func:`matches`, which implements gitignore(5)
and is tested against ``git check-ignore``: last match wins, ``!`` re-includes
(but never below an excluded directory), ``/`` anchors, ``dir/`` matches only
directories, ``**`` crosses directories, ``[...]`` is a character class and
``\\`` escapes. ``.neuralmindignore`` uses the same engine, so both files mean
the same thing.

``.neuralmind.yaml`` widens or turns this off:

* ``respect_gitignore: false`` — index ignored files again (v4.4 behaviour)
* ``include_ignored: ["generated/api/**"]`` — pull specific ignored paths back in
"""

from __future__ import annotations

import functools
import os
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import NamedTuple

_GIT_TIMEOUT_S = 20


# --------------------------------------------------------------------------- #
# gitignore pattern semantics
# --------------------------------------------------------------------------- #
def load_patterns(project_path: Path, filename: str) -> tuple[str, ...]:
    """``.gitignore``-style patterns from ``filename`` under ``project_path``, in order.

    Lines are read the way git reads them: a leading UTF-8 BOM is skipped,
    trailing spaces are dropped unless backslash-escaped (leading spaces are
    part of the pattern), and blank lines and ``#`` comments are left out.
    """
    ignore_path = Path(project_path) / filename
    if not ignore_path.exists():
        return ()
    try:
        content = ignore_path.read_text(encoding="utf-8-sig")
    except OSError:
        return ()

    patterns: list[str] = []
    for line in content.split("\n"):
        line = _trim_trailing_spaces(line.removesuffix("\r"))
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return tuple(patterns)


def _trim_trailing_spaces(line: str) -> str:
    """Drop trailing spaces unless a backslash escapes them (git's rule)."""
    last_space = None
    i = 0
    while i < len(line):
        c = line[i]
        if c == " ":
            if last_space is None:
                last_space = i
        else:
            if c == "\\":
                i += 1  # the escaped character, a space included, is kept
            last_space = None
        i += 1
    return line if last_space is None else line[:last_space]


class _Rule(NamedTuple):
    regex: re.Pattern[str]
    negated: bool
    dir_only: bool  # trailing '/': matches directories only
    basename: bool  # no '/' in the pattern: matched against the last component


# POSIX bracket classes as git's wildmatch knows them (ASCII ctype).
_POSIX_CLASSES = {
    "alnum": "a-zA-Z0-9",
    "alpha": "a-zA-Z",
    "blank": " \\t",
    "cntrl": "\\x00-\\x1f\\x7f",
    "digit": "0-9",
    "graph": "\\x21-\\x7e",
    "lower": "a-z",
    "print": "\\x20-\\x7e",
    "punct": "\\x21-\\x2f\\x3a-\\x40\\x5b-\\x60\\x7b-\\x7e",
    "space": " \\t\\n\\r\\f\\v",
    "upper": "A-Z",
    "xdigit": "0-9A-Fa-f",
}


def _compile_rule(pattern: str) -> _Rule | None:
    """Parse one gitignore line; None when it can never match anything."""
    p = _trim_trailing_spaces(pattern)
    if not p or p.startswith("#"):
        return None
    negated = p.startswith("!")
    if negated:
        p = p[1:]
    dir_only = p.endswith("/")
    if dir_only:
        p = p[:-1]
    # A '/' at the start or in the middle anchors the pattern to the ignore
    # file's directory; without one it matches a name at any depth.
    basename = "/" not in p
    if p.startswith("/"):
        p = p[1:]
    body = _glob_to_regex(p, pathname=not basename) if p else None
    if body is None:
        return None
    return _Rule(re.compile(body), negated, dir_only, basename)


def _glob_to_regex(pat: str, *, pathname: bool) -> str | None:
    """Translate a gitignore glob to a regex body, as git's wildmatch reads it.

    ``*``, ``?`` and ``[...]`` never match ``/``. In a ``pathname`` pattern
    (one containing a ``/``) a ``**`` that is a whole path component spans
    directories: leading ``**/`` and inner ``/**/`` match zero or more of
    them, trailing ``/**`` everything inside. Any other run of asterisks is a
    plain ``*``. A backslash makes the next character literal. None means the
    glob can never match (an unclosed ``[``, an unknown ``[:class:]``, a
    trailing backslash).
    """
    out: list[str] = []
    i, n = 0, len(pat)
    while i < n:
        c = pat[i]
        if c == "*":
            j = i
            while j < n and pat[j] == "*":
                j += 1
            if pathname and j - i > 1 and (i == 0 or pat[i - 1] == "/"):
                if j == n:
                    out.append(".*")
                    i = j
                    continue
                slash = 1 if pat[j] == "/" else 2 if pat.startswith("\\/", j) else 0
                if slash:
                    out.append("(?:.*/)?")
                    i = j + slash
                    continue
            out.append("[^/]*")
            i = j
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c == "[":
            cls, i = _bracket_to_regex(pat, i)
            if cls is None:
                return None
            out.append(cls)
        elif c == "\\":
            if i + 1 == n:
                return None
            out.append(re.escape(pat[i + 1]))
            i += 2
        else:
            out.append(re.escape(c))
            i += 1
    return "".join(out)


def _bracket_to_regex(pat: str, i: int) -> tuple[str | None, int]:
    """Translate the ``[...]`` opening at ``pat[i]``: (regex or None, next index).

    As in wildmatch: ``[!...]`` and ``[^...]`` negate, a ``]`` first in the set
    is a member, ``a-z`` is a range, ``\\`` escapes, ``[:digit:]`` and the other
    POSIX classes work. An unclosed set or unknown class matches nothing.
    """
    n = len(pat)
    j = i + 1
    negated = j < n and pat[j] in "!^"
    if negated:
        j += 1
    members: list[str] = []
    prev: str | None = None  # the last single character: a range may start there
    first = True
    while True:
        if j >= n:
            return None, n
        c = pat[j]
        if c == "]" and not first:
            break
        first = False
        if c == "\\":
            j += 1
            if j >= n:
                return None, n
            prev = pat[j]
            members.append(re.escape(prev))
        elif c == "-" and prev is not None and j + 1 < n and pat[j + 1] != "]":
            j += 1
            hi = pat[j]
            if hi == "\\":
                j += 1
                if j >= n:
                    return None, n
                hi = pat[j]
            if prev <= hi:
                members.append(f"{re.escape(prev)}-{re.escape(hi)}")
            prev = None
        elif c == "[" and pat.startswith(":", j + 1):
            close = pat.find("]", j + 2)
            if close == -1:
                return None, n
            if close - 1 > j + 1 and pat[close - 1] == ":":
                cls = _POSIX_CLASSES.get(pat[j + 2 : close - 1])
                if cls is None:
                    return None, n
                members.append(cls)
                prev = None
                j = close
            else:  # no ':]' before the first ']': a literal '['
                prev = "["
                members.append("\\[")
        else:
            prev = c
            members.append(re.escape(c))
        j += 1
    body = "".join(members)
    if negated:
        return f"[^/{body}]", j + 1
    return f"(?!/)[{body}]", j + 1


def pattern_regex(pattern: str):
    """A regex for the paths one pattern (negation aside) ignores, or None.

    Matches a file path when the pattern matches the file itself or any
    directory above it. :func:`matches` is the full engine (pattern order,
    ``!``, directory-only patterns); this stays for single-pattern callers.
    """
    rule = _compile_rule(pattern.removeprefix("!"))
    if rule is None:
        return None
    prefix = "(?:.*/)?" if rule.basename else ""
    tail = "/.*" if rule.dir_only else "(?:/.*)?"
    return re.compile(f"^{prefix}(?:{rule.regex.pattern}){tail}$")


class _Matcher:
    """One compiled pattern list, caching the verdict for each directory."""

    _MAX_CACHED_DIRS = 100_000

    def __init__(self, patterns: tuple[str, ...]) -> None:
        self.rules = tuple(r for r in map(_compile_rule, patterns) if r is not None)
        self._dirs: dict[str, bool] = {}

    def _verdict(self, path: str, name: str, is_dir: bool) -> bool | None:
        """The last matching rule: True ignores, False re-includes, None no match."""
        for rule in reversed(self.rules):
            if rule.dir_only and not is_dir:
                continue
            if rule.regex.fullmatch(name if rule.basename else path):
                return not rule.negated
        return None

    def _dir_excluded(self, path: str) -> bool:
        """True when directory ``path`` or a directory above it is excluded."""
        hit = self._dirs.get(path)
        if hit is None:
            head, _, name = path.rpartition("/")
            hit = bool(head and self._dir_excluded(head)) or bool(self._verdict(path, name, True))
            if len(self._dirs) >= self._MAX_CACHED_DIRS:
                self._dirs.clear()
            self._dirs[path] = hit
        return hit

    def ignored(self, rel_path: str, is_dir: bool | None) -> bool:
        head, _, name = rel_path.rpartition("/")
        # git never looks inside an excluded directory, so a later '!' pattern
        # can't re-include anything below one.
        if head and self._dir_excluded(head):
            return True
        if is_dir is not None:
            return bool(self._verdict(rel_path, name, is_dir))
        # Unknown type: ignored only when ignored as a file and as a directory.
        return bool(self._verdict(rel_path, name, False)) and bool(
            self._verdict(rel_path, name, True)
        )


@functools.lru_cache(maxsize=64)
def _matcher(patterns: tuple[str, ...]) -> _Matcher:
    return _Matcher(patterns)


def matches(
    rel_path: str, patterns: tuple[str, ...] | list[str], *, is_dir: bool | None = None
) -> bool:
    """True when project-relative ``rel_path`` is ignored by ``patterns``.

    gitignore(5) semantics, kept in step with ``git check-ignore``: the last
    matching pattern wins and ``!`` re-includes, except below an excluded
    directory; a pattern ending in ``/`` matches directories only.

    Pass ``is_dir=False`` for a file and ``is_dir=True`` (or a trailing ``/``)
    for a directory to get git's exact answer. Left as None, the path is
    ignored only if it would be ignored either way, so a directory walk that
    doesn't say never prunes a directory git would enter; the one difference
    from git is then a file whose own name a directory-only ``!`` pattern
    (``!*/``) matches, which stays included.
    """
    if not patterns:
        return False
    if rel_path.endswith("/"):
        rel_path, is_dir = rel_path.rstrip("/"), True
    if not rel_path:
        return False
    return _matcher(tuple(patterns)).ignored(rel_path, is_dir)


# --------------------------------------------------------------------------- #
# git-backed listing
# --------------------------------------------------------------------------- #
def _git_lines(root: Path, *args: str) -> list[str] | None:
    return _git_lines_many(root, args)[0]


def _git_lines_many(root: Path, *commands: tuple[str, ...]) -> list[list[str] | None]:
    """Run read-only git commands side by side; one ``-z`` path list (or None) each.

    On a large index each ``git ls-files`` spends most of its time in lstat
    calls, so the listing's commands run at once instead of one after another.
    """
    procs: list[subprocess.Popen | None] = []
    for args in commands:
        try:
            procs.append(
                subprocess.Popen(
                    ["git", "-C", str(root), *args],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
            )
        except OSError:
            procs.append(None)
    results: list[list[str] | None] = []
    for proc in procs:
        if proc is None:
            results.append(None)
            continue
        try:
            out, _ = proc.communicate(timeout=_GIT_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            results.append(None)
            continue
        if proc.returncode != 0:
            results.append(None)
            continue
        text = out.decode("utf-8", errors="surrogateescape")
        results.append([p for p in text.split("\0") if p])
    return results


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
    listed, tracked_ignored, deleted = _git_lines_many(
        root,
        ("ls-files", "-z", "--stage", "--cached", "--others", "--exclude-standard"),
        ("ls-files", "-z", "--cached", "--ignored", "--exclude-standard"),
        ("ls-files", "-z", "--deleted"),  # index entries whose file is gone from disk
    )
    if listed is None:
        return None
    if not listed and _root_is_ignored(root):
        # The project sits in a directory the enclosing repository ignores (a
        # scratch dir, a vendored checkout). That repository's rules say
        # nothing about this project, so walk it with its own .gitignore.
        return None
    excluded = set(tracked_ignored or []) | set(deleted or [])
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
