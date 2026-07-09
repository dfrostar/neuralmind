"""Mine git commit history into synapse co-change priors.

The synapse layer is NeuralMind's differentiator, but on a fresh install it
is empty: the associative memory only becomes useful after roughly a week of
real editing feeds it co-activation signal. Meanwhile every repository already
contains that signal, thousands of observations deep — files that changed
together in a commit are the same thing ``activate_files`` learns from a live
edit, just already recorded. This module seeds the store from it, turning the
cold start into a useful-on-first-query prior.

Design decisions, and why:

- **File granularity.** Each changed path maps to its single file-level graph
  node, not every symbol in the file. A k-file commit is therefore k(k-1)/2
  pairs, not a clique over every symbol node of every file (which routing
  through ``activate_files`` would produce — a 5-file commit could be ~5,000
  pairs). Co-change is a file-level phenomenon; mining it at file level keeps
  the signal clean and the write bounded.

- **Commit-size down-weighting.** A focused two-file commit is strong evidence
  the two files relate; a 200-file refactor is noise. Per-commit pair weight
  scales as ``PAIR_WEIGHT_BASE / (k - 1)``, and commits touching more than
  ``max_files`` files are skipped outright — both a noise gate and an O(k^2)
  guard.

- **A dedicated, quiet, sticky namespace.** Edges land in ``history`` at
  ``W_HISTORY`` (below personal and shared): a prior, never louder than what
  you actually did. It decays slowly (``HISTORY_DECAY_RATE``) because a
  co-change fact about the repo is long-lived, and it is cleared and re-mined
  independently (``neuralmind memory reset --namespace history``).

- **Durable pairs are born protected.** A pair seen in >= ``LTP_THRESHOLD``
  commits is written with that activation count, so the decay layer's LTP
  floor protects it from the first tick — a structural fact shouldn't fade
  before the user has generated any real usage to replace it.

The parser (:func:`parse_git_log`) is separated from the subprocess call
(:func:`run_git_log`) so the whole pipeline is testable on stdlib alone,
without a git binary or a real repository.
"""

from __future__ import annotations

import subprocess
from collections import defaultdict
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import NamedTuple

from .synapses import (
    HISTORY_NAMESPACE,
    LTP_THRESHOLD,
    TRANSITION_WEIGHT_CAP,
    WEIGHT_CAP,
)

__all__ = [
    "HISTORY_NAMESPACE",
    "DEFAULT_MAX_COMMITS",
    "DEFAULT_MAX_FILES",
    "PAIR_WEIGHT_BASE",
    "SESSION_WINDOW_SECONDS",
    "CommitRecord",
    "build_file_node_index",
    "parse_git_log",
    "run_git_log",
    "cochange_edges",
    "transition_rows",
]

DEFAULT_MAX_COMMITS = 2000
DEFAULT_MAX_FILES = 50
PAIR_WEIGHT_BASE = 0.5

# Two consecutive commits by the same author within this window are treated as
# one work session: "after committing A, they went on to commit B". Across a
# longer gap (overnight, next week) the sequence stops meaning "what follows
# what" and becomes coincidence of the calendar.
SESSION_WINDOW_SECONDS = 6 * 3600

# A NUL byte can never appear in a git pathname, so prefixing each commit's
# hash line with one gives an unambiguous record delimiter that no file path
# can forge. Within that line, the ASCII unit separator splits
# hash / author / author-timestamp — also impossible in a pathname.
_COMMIT_SENTINEL = "\x00"
_FIELD_SEP = "\x1f"


class CommitRecord(NamedTuple):
    """One commit's changed paths plus the metadata session-detection needs."""

    files: list[str]
    author: str | None = None
    timestamp: int | None = None


# Full-content re-parse of a single file's changed lines is cheap, but a giant
# vendored drop or generated-code commit can list tens of thousands of paths.
# Stop accumulating a commit's file list once it is clearly past any sane
# max_files, so a pathological commit can't balloon memory before it's skipped.
_HARD_FILE_LIMIT = 5000


def build_file_node_index(nodes: Iterable[dict]) -> dict[str, str]:
    """Map ``source_file`` -> the id of that file's file-level graph node.

    The graph carries one node per file (``label == source_file``, e.g. label
    ``src/api.py``) plus one per symbol (``label == "handler()"``). We want the
    file node: co-change is between files, and seeding at file granularity is
    what keeps a commit from exploding into a symbol clique.

    A path that has only symbol nodes and no file node (unusual, but possible
    for some artifact extractors) simply won't appear here and is skipped by
    the miner — a missing prior, never a wrong one.
    """
    index: dict[str, str] = {}
    for node in nodes:
        source_file = node.get("source_file")
        node_id = node.get("id")
        if source_file and node_id and node.get("label") == source_file:
            # First file node for a path wins; later duplicates (there
            # shouldn't be any) are ignored rather than silently reassigned.
            index.setdefault(source_file, node_id)
    return index


def parse_git_log(lines: Iterable[str]) -> Iterator[CommitRecord]:
    """Parse ``git log --name-only --pretty=format:%x00%H%x1f%an%x1f%at``.

    Yields one :class:`CommitRecord` per commit, in log order (newest first). A
    line starting with the NUL sentinel opens a new commit — its unit-separated
    fields are hash / author / author-timestamp, with the last two optional so
    a bare ``%x00%H`` stream (the pre-transition format) still parses, just
    with ``author``/``timestamp`` of ``None``. Every other non-blank line is a
    changed path. Empty commits yield an empty ``files`` list and are dropped
    downstream. Pure and streaming — pass it real subprocess output or a
    hand-written fixture.
    """

    def _finish(files: list[str], meta: list[str]) -> CommitRecord:
        author = meta[1].strip() if len(meta) > 1 and meta[1].strip() else None
        timestamp: int | None = None
        if len(meta) > 2:
            try:
                timestamp = int(meta[2].strip())
            except ValueError:
                timestamp = None
        return CommitRecord(files, author, timestamp)

    current: list[str] | None = None
    meta: list[str] = []
    overflowed = False
    for raw in lines:
        line = raw.rstrip("\n")
        if line.startswith(_COMMIT_SENTINEL):
            if current is not None:
                yield _finish(current, meta)
            meta = line[len(_COMMIT_SENTINEL) :].split(_FIELD_SEP)
            current = []
            overflowed = False
            continue
        if current is None:
            # Output before the first sentinel — shouldn't happen with our
            # format string, but tolerate it rather than crash.
            continue
        if not line:
            continue
        if overflowed:
            continue
        current.append(line)
        if len(current) >= _HARD_FILE_LIMIT:
            # Keep draining this commit's lines but stop growing the list; the
            # miner will skip it on max_files anyway.
            overflowed = True
    if current is not None:
        yield _finish(current, meta)


def run_git_log(project_path: str | Path, max_commits: int = DEFAULT_MAX_COMMITS) -> Iterator[str]:
    """Stream ``git log`` output lines for :func:`parse_git_log`.

    Non-merge commits only (a merge's combined diff would fabricate a huge
    spurious clique). Streams via ``Popen`` so a deep history isn't buffered
    into one multi-megabyte string, and always reaps the child process.
    Yields nothing when git is unavailable or the path isn't a repository —
    the caller reports "no history mined" rather than raising.
    """
    cmd = [
        "git",
        "-C",
        str(project_path),
        "log",
        "--no-merges",
        "--name-only",
        # hash / author email / author timestamp, unit-separated. The email is
        # the session-detection identity (stabler than the display name).
        "--pretty=format:%x00%H%x1f%ae%x1f%at",
        f"--max-count={int(max_commits)}",
    ]
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, ValueError):
        return
    try:
        assert proc.stdout is not None
        yield from proc.stdout
    finally:
        if proc.stdout is not None:
            proc.stdout.close()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


def cochange_edges(
    commit_filesets: Iterable[list[str]],
    path_to_node: dict[str, str],
    *,
    max_files: int = DEFAULT_MAX_FILES,
    weight_base: float = PAIR_WEIGHT_BASE,
) -> tuple[list[tuple[str, str, float, int]], dict]:
    """Turn per-commit file lists into ``import_edges`` rows plus stats.

    For each usable commit (>= 2 and <= ``max_files`` *indexed* files), every
    file pair accrues ``weight_base / (k - 1)`` and a co-change count of one.
    Accumulated weight is saturated at ``WEIGHT_CAP``; the count becomes the
    edge's activation count, so a pair seen in >= ``LTP_THRESHOLD`` commits is
    minted already LTP-protected.

    Returns ``(rows, stats)`` where each row is
    ``(node_a, node_b, weight, activation_count)`` — exactly
    ``SynapseStore.import_edges``' contract.

    Accepts :class:`CommitRecord` items or bare path lists — co-change only
    needs the file sets, so tests can stay on plain lists.
    """
    strength: dict[tuple[str, str], float] = defaultdict(float)
    counts: dict[tuple[str, str], int] = defaultdict(int)

    commits_total = 0
    commits_used = 0
    commits_too_large = 0
    commits_no_overlap = 0

    for commit in commit_filesets:
        paths = getattr(commit, "files", commit)
        commits_total += 1
        # Map to file nodes, dedupe, drop paths not in the index (deleted /
        # renamed-away / never-indexed files map to nothing).
        node_ids: list[str] = []
        seen: set[str] = set()
        for path in paths:
            node_id = path_to_node.get(path)
            if node_id is not None and node_id not in seen:
                seen.add(node_id)
                node_ids.append(node_id)

        k = len(node_ids)
        if k < 2:
            commits_no_overlap += 1
            continue
        if k > max_files:
            commits_too_large += 1
            continue

        commits_used += 1
        contribution = weight_base / (k - 1)
        for i in range(k):
            for j in range(i + 1, k):
                a, b = node_ids[i], node_ids[j]
                pair = (a, b) if a < b else (b, a)
                strength[pair] += contribution
                counts[pair] += 1

    rows: list[tuple[str, str, float, int]] = []
    ltp_edges = 0
    for pair, raw_weight in strength.items():
        count = counts[pair]
        rows.append((pair[0], pair[1], min(WEIGHT_CAP, raw_weight), count))
        if count >= LTP_THRESHOLD:
            ltp_edges += 1

    stats = {
        "commits_scanned": commits_total,
        "commits_used": commits_used,
        "commits_too_large": commits_too_large,
        "commits_no_overlap": commits_no_overlap,
        "edges": len(rows),
        "ltp_edges": ltp_edges,
    }
    return rows, stats


def transition_rows(
    commits: list[CommitRecord],
    path_to_node: dict[str, str],
    *,
    max_files: int = DEFAULT_MAX_FILES,
    session_window: int = SESSION_WINDOW_SECONDS,
) -> tuple[list[tuple[str, str, float, int]], dict]:
    """Mine directional "what came next" transitions from commit sequences.

    Two consecutive commits by the **same author** within ``session_window``
    seconds are one work session: after touching commit A's files, the author
    went on to touch commit B's. Each (a in A, b in B, a != b) pair accrues a
    transition ``a -> b`` with weight ``1 / (|A| * |B|)`` — a surgical
    one-file-then-one-file sequence carries the weight of a single live
    observation, a broad pair of commits spreads the same evidence thin.

    Keys are the repo-relative POSIX paths git emits, filtered to files that
    still exist in the graph — the same form a user types into
    ``neuralmind next src/api.py``. Rebased or reordered history (a negative
    timestamp delta) breaks the session rather than fabricating a sequence.

    Returns ``(rows, stats)`` where each row is
    ``(from_path, to_path, weight, count)`` — exactly
    ``SynapseStore.import_transitions``' contract.
    """
    weight: dict[tuple[str, str], float] = defaultdict(float)
    counts: dict[tuple[str, str], int] = defaultdict(int)
    sessions_used = 0

    def _usable(commit: CommitRecord) -> list[str]:
        paths = [p for p in dict.fromkeys(commit.files) if p in path_to_node]
        return paths if 0 < len(paths) <= max_files else []

    # git log emits newest-first; a session reads oldest -> newest.
    ordered = list(reversed(commits))
    for older, newer in zip(ordered, ordered[1:], strict=False):
        if older.author is None or older.author != newer.author:
            continue
        if older.timestamp is None or newer.timestamp is None:
            continue
        gap = newer.timestamp - older.timestamp
        if not 0 <= gap <= session_window:
            continue
        src, dst = _usable(older), _usable(newer)
        if not src or not dst:
            continue
        sessions_used += 1
        contribution = 1.0 / (len(src) * len(dst))
        for a in src:
            for b in dst:
                if a == b:
                    continue
                weight[(a, b)] += contribution
                counts[(a, b)] += 1

    rows = [(a, b, min(TRANSITION_WEIGHT_CAP, w), counts[(a, b)]) for (a, b), w in weight.items()]
    return rows, {"sessions_used": sessions_used, "transitions": len(rows)}
