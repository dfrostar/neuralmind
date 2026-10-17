"""freshness.py — is the code graph in step with the files on disk?

A graph that lags the code is the most dangerous kind of stale index: every
query still "works", it just answers from code that no longer exists and
can't see code that does. ``graph_freshness`` compares the graph with the
working tree in both directions, whatever tool produced the graph, using
directory walks, ``stat`` calls and a few ``git`` plumbing commands — never a
parse — so ``doctor``, ``health``, ``build`` and the MCP wakeup can all afford
to run it.

What it reports:

* ``missing_from_graph`` — indexable files on disk the graph has never seen
  (new code the index can't answer about).
* ``gone_from_disk`` — files the graph still serves that no longer exist
  (deleted or renamed code).
* ``foreign_separators`` — node paths using ``\\`` on a POSIX host: the
  graph was built on Windows, so none of its paths line up with this tree.
* ``changed_since_graph`` — files the graph knows that changed after it was
  built. For a graph committed to git this comes from ``git diff`` against
  the commit that last touched the graph; for an untracked graph (the
  built-in ``.neuralmind/graph.json``) from mtimes, confirmed by the
  extraction cache's content hashes when one exists. Checkout mtimes are
  never used for a tracked graph: a fresh clone stamps every file with the
  checkout time, which says nothing about when it changed.
* ``graph_age_commits`` — commits since the graph last changed, when the
  graph is tracked; ``None`` on a shallow clone, where the history needed to
  count them isn't there.
* ``index_mismatch`` (``check_index=True`` only) — the graph changed after
  the last build (``graphify update``, a pull, a hand edit), so the stored
  vectors still describe the old one: new nodes can't be found and removed
  ones still come back. The build records which graph it embedded, with a
  fingerprint, in ``build_status.json``.

Status: FAIL when missing + gone exceed 10% of indexable files, any node
path uses foreign separators, or the index was built from another graph;
WARN when either list is non-empty or files changed since the graph; OK
otherwise.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath

from .paths import CANONICAL_DIR, LEGACY_DIR, graph_json_path

OK = "ok"
WARN = "warn"
FAIL = "fail"

# missing + gone above this share of indexable files means the graph no
# longer describes this tree.
FAIL_DRIFT_RATIO = 0.10

# Examples printed per list. The full lists stay on the report.
MAX_EXAMPLES = 5

_GIT_TIMEOUT_S = 5


@dataclass
class FreshnessReport:
    """Result of comparing a code graph with the working tree."""

    status: str
    graph_path: Path
    source: str  # "built-in" | "graphify" | a generator name | "unknown"
    graph_date: str | None = None  # YYYY-MM-DD
    node_count: int = 0
    indexable_count: int = 0
    missing_from_graph: list[str] = field(default_factory=list)
    gone_from_disk: list[str] = field(default_factory=list)
    foreign_separators: int = 0
    foreign_separator_files: int = 0
    changed_since_graph: list[str] = field(default_factory=list)
    changed_method: str = ""  # "git" | "mtime" | "hash" | ""
    graph_age_commits: int | None = None
    age_note: str = ""  # why graph_age_commits is None, when it is
    index_mismatch: str = ""  # why the vectors don't match this graph, when they don't
    project: Path | None = None
    # When the files behind the drift were last modified (Unix time): the
    # newest per list, and the oldest dated change of all, i.e. how long the
    # index has been behind. Files gone from disk and foreign separators have
    # no date of their own.
    newest_missing_mtime: float | None = None
    newest_changed_mtime: float | None = None
    oldest_change_mtime: float | None = None

    @property
    def ok(self) -> bool:
        return self.status == OK

    @property
    def is_graphify(self) -> bool:
        return self.source == "graphify"

    def display_path(self) -> str:
        if self.project is not None:
            try:
                return self.graph_path.relative_to(self.project).as_posix()
            except ValueError:
                pass
        return str(self.graph_path)

    def header(self) -> str:
        """``graphify-out/graph.json (graphify, 2026-04-22, 214 commits behind HEAD)``"""
        bits = [self.source]
        if self.graph_date:
            bits.append(self.graph_date)
        if self.graph_age_commits is not None:
            n = self.graph_age_commits
            bits.append(f"{n:,} commit{'s' if n != 1 else ''} behind HEAD")
        elif self.age_note:
            bits.append(self.age_note)
        return f"{self.display_path()} ({', '.join(bits)})"

    def problem_lines(self) -> list[str]:
        """One line per finding, each naming up to ``MAX_EXAMPLES`` files."""
        lines: list[str] = []
        if self.missing_from_graph:
            lines.append(
                f"{len(self.missing_from_graph):,} file"
                f"{'s' if len(self.missing_from_graph) != 1 else ''} on disk not in graph"
                f"{_examples(self.missing_from_graph)}{_newest(self.newest_missing_mtime)}"
            )
        if self.gone_from_disk:
            lines.append(
                f"{len(self.gone_from_disk):,} file"
                f"{'s' if len(self.gone_from_disk) != 1 else ''} in graph no longer on disk"
                f"{_examples(self.gone_from_disk)}"
            )
        if self.foreign_separators:
            lines.append(
                f"{self.foreign_separators:,} node paths ({self.foreign_separator_files:,} files) "
                "use '\\' separators (built on Windows)"
            )
        if self.changed_since_graph:
            lines.append(
                f"{len(self.changed_since_graph):,} file"
                f"{'s' if len(self.changed_since_graph) != 1 else ''} changed since the graph "
                f"was built{_examples(self.changed_since_graph)}"
                f"{_newest(self.newest_changed_mtime)}"
            )
        if self.index_mismatch:
            lines.append(f"{self.index_mismatch}: the stored vectors still describe the old graph")
        return lines

    def _graph_drifted(self) -> bool:
        return bool(
            self.missing_from_graph
            or self.gone_from_disk
            or self.foreign_separators
            or self.changed_since_graph
        )

    def behind_seconds(self, now: float | None = None) -> float | None:
        """How long the index has been behind: since its oldest dated change.

        None when the report is OK or none of its drift has a date.
        """
        if self.status == OK or self.oldest_change_mtime is None:
            return None
        now = time.time() if now is None else now
        return max(0.0, now - self.oldest_change_mtime)

    def exceeds(self, stale_after: float, now: float | None = None) -> bool:
        """Whether the drift is older than ``stale_after`` seconds (``stale_after``).

        Drift with no date (files gone from disk, a graph built on another
        OS) can't be shown to be recent, so it always exceeds.
        """
        if self.status == OK:
            return False
        if self.gone_from_disk or self.foreign_separators:
            return True
        behind = self.behind_seconds(now)
        return behind is None or behind > stale_after

    def overdue_reason(self, stale_after: float) -> str:
        """Why :meth:`exceeds` is true, for the doctor line; "" when it isn't."""
        if not self.exceeds(stale_after):
            return ""
        limit = format_duration(stale_after)
        if self.gone_from_disk or self.foreign_separators:
            return f"drift with no date (deleted files or another OS's paths) never fits stale_after {limit}"
        behind = self.behind_seconds()
        if behind is None:
            return f"drift with no date never fits stale_after {limit}"
        return f"behind for {format_age(behind)}, over stale_after {limit}"

    def fix_command(self, project_arg: str = ".") -> str:
        if self.status == OK:
            return ""
        if self.source == "built-in" or not self._graph_drifted():
            # The graph is current; only the vectors lag it.
            return f"neuralmind build {project_arg}"
        return f"neuralmind build {project_arg} --regenerate-graph"

    def render(self, project_arg: str = ".", indent: str = "       ") -> str:
        """The multi-line report ``doctor`` and ``build`` print."""
        out = [f"[{self.status.upper()}] Code graph: {self.header()}"]
        out.extend(f"{indent}{line}" for line in self.problem_lines())
        fix = self.fix_command(project_arg)
        if fix:
            out.append(f"{indent}-> {fix}")
        return "\n".join(out)

    def one_line(self, project_arg: str = ".") -> str:
        """The single line the MCP wakeup prefixes when the graph isn't OK."""
        if self.status == OK:
            return ""
        parts = []
        if self.missing_from_graph:
            parts.append(f"{len(self.missing_from_graph):,} files missing from graph")
        if self.gone_from_disk:
            parts.append(f"{len(self.gone_from_disk):,} deleted files still indexed")
        if self.foreign_separators:
            parts.append("graph built on another OS")
        if self.changed_since_graph:
            parts.append(f"{len(self.changed_since_graph):,} files changed since the graph")
        if self.index_mismatch:
            parts.append("graph changed since the last build")
        what = "; ".join(parts) or "graph out of date"
        return f"Index is stale: {what}. Run {self.fix_command(project_arg)}."

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "graph_path": str(self.graph_path),
            "source": self.source,
            "graph_date": self.graph_date,
            "node_count": self.node_count,
            "indexable_count": self.indexable_count,
            "missing_from_graph": self.missing_from_graph,
            "gone_from_disk": self.gone_from_disk,
            "foreign_separators": self.foreign_separators,
            "foreign_separator_files": self.foreign_separator_files,
            "changed_since_graph": self.changed_since_graph,
            "changed_method": self.changed_method,
            "graph_age_commits": self.graph_age_commits,
            "age_note": self.age_note,
            "index_mismatch": self.index_mismatch,
            "newest_missing_mtime": self.newest_missing_mtime,
            "newest_changed_mtime": self.newest_changed_mtime,
            "oldest_change_mtime": self.oldest_change_mtime,
            "behind_seconds": _round(self.behind_seconds()),
        }


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


def format_age(seconds: float) -> str:
    """``45s``, ``12m``, ``3h``, ``2d``: the largest whole unit."""
    seconds = max(0.0, seconds)
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= size:
            return f"{int(seconds // size)}{unit}"
    return f"{int(seconds)}s"


def format_duration(seconds: float) -> str:
    """A ``stale_after`` limit as written: the largest unit it fills exactly (``90m``)."""
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= size and seconds % size == 0:
            return f"{int(seconds // size)}{unit}"
    return f"{seconds:g}s"


DRIFT_SEEN_FILE = "drift_seen.json"


def track_drift(project: str | Path, report: FreshnessReport | None) -> None:
    """Date the drift from when each unindexed file was first seen, not its mtime.

    A file rewritten while it waits for a rebuild (generated code, a file a
    tool keeps touching while the watcher is down) gets a new mtime each time,
    so the mtime alone would restart the clock and keep a ``stale_after`` gate
    passing forever. ``.neuralmind/drift_seen.json`` keeps, per file that is
    missing from the graph or changed since it, the time it was first seen;
    a file drops out once it is indexed, and the record goes when nothing
    drifts. Written only when the gate is in use, never creates
    ``.neuralmind/``, and fail-open.
    """
    if report is None:
        return
    root = Path(project).resolve()
    state_dir = root / CANONICAL_DIR
    if not state_dir.is_dir():
        return
    path = state_dir / DRIFT_SEEN_FILE
    drifted = set(report.missing_from_graph) | set(report.changed_since_graph)
    try:
        seen = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError):
        seen = {}
    if not isinstance(seen, dict):
        seen = {}
    now = time.time()
    current: dict[str, float] = {}
    for rel in sorted(drifted):
        first = seen.get(rel)
        if isinstance(first, (int, float)):
            current[rel] = float(first)
            continue
        try:
            current[rel] = min((root / rel).stat().st_mtime, now)
        except OSError:
            current[rel] = now
    if current:
        oldest = min(current.values())
        if report.oldest_change_mtime is None or oldest < report.oldest_change_mtime:
            report.oldest_change_mtime = oldest
    try:
        if not current:
            if path.exists():
                path.unlink()
        elif current != seen:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(current, indent=1, sort_keys=True), encoding="utf-8")
            os.replace(tmp, path)
    except OSError:
        pass


def health_status(report: FreshnessReport | None, stale_after: float | None) -> str:
    """``healthy``, ``catching_up``, ``stale`` or ``unknown``: the health verdict.

    Shared by ``neuralmind health`` and the MCP ``neuralmind_health`` tool.
    No report is ``unknown``, never healthy. With ``stale_after``, drift that
    hasn't lasted that long is ``catching_up``; only ``stale`` and ``unknown``
    are failures.
    """
    if report is None:
        return "unknown"
    if report.status == OK:
        return "healthy"
    if stale_after is not None and not report.exceeds(stale_after):
        return "catching_up"
    return "stale"


def _newest(mtime: float | None) -> str:
    """``; newest modified 2h ago``: when the most recent file in a list changed."""
    if mtime is None:
        return ""
    return f"; newest modified {format_age(time.time() - mtime)} ago"


_DURATION_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([smhd])\s*$", re.IGNORECASE)
_DURATION_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_duration(raw: str | float | int | None) -> float | None:
    """``"30m"`` -> 1800.0 seconds. Units: s, m, h, d. None for anything else.

    A bare number is refused rather than guessed at: ``30`` could mean
    seconds or minutes, and a stale-after gate set to the wrong one is quietly
    useless.
    """
    if raw is None or isinstance(raw, bool):
        return None
    match = _DURATION_RE.match(str(raw))
    if not match:
        return None
    return float(match.group(1)) * _DURATION_UNITS[match.group(2).lower()]


def _mtimes(root: Path, rels: list[str]) -> list[float]:
    out: list[float] = []
    for rel in rels:
        try:
            out.append((root / rel).stat().st_mtime)
        except OSError:
            continue
    return out


def _examples(items: list[str]) -> str:
    if not items:
        return ""
    shown = ", ".join(items[:MAX_EXAMPLES])
    more = ", ..." if len(items) > MAX_EXAMPLES else ""
    return f" ({shown}{more})"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def normalize_source_path(raw: str, root: Path) -> str:
    """A graph ``source_file`` as a POSIX path relative to ``root``.

    ``PurePosixPath(PureWindowsPath(p))`` makes ``tests\\x.py`` and
    ``tests/x.py`` compare equal; absolute paths under ``root`` are made
    relative, and a leading ``./`` is dropped.
    """
    p = str(raw).strip()
    if not p:
        return ""
    posix = PurePosixPath(PureWindowsPath(p)).as_posix() if "\\" in p else p
    if posix.startswith("./"):
        posix = posix[2:]
    if os.path.isabs(posix):
        try:
            return Path(posix).resolve().relative_to(root).as_posix()
        except (ValueError, OSError):
            return posix
    return posix


def graph_source_kind(graph: dict, graph_path: Path) -> str:
    """Which tool produced ``graph``: built-in, graphify, or its own label."""
    generated_by = str(graph.get("generated_by", "") or "")
    if "neuralmind.graphgen" in generated_by:
        return "built-in"
    if LEGACY_DIR in graph_path.parts or "graphify" in generated_by.lower():
        return "graphify"
    if generated_by:
        return generated_by
    return "unknown"


def _git(root: Path, *args: str) -> str | None:
    """Run a git command under ``root``; None when git or the repo is absent."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _indexable_suffixes(source: str, graph_suffixes: set[str], config) -> frozenset[str]:
    """Suffixes whose files the graph is expected to cover.

    For the built-in graph: every code language whose grammar is installed,
    plus markdown, SQL and Protobuf — the files graphgen always turns into
    nodes. A graphify graph parses the same tree-sitter languages, so every
    installed code language counts for it too (a Python-only graph still
    notices new TypeScript); markdown and schema files count only when the
    graph already holds some, so a graphify graph that never indexed markdown
    isn't "missing" every README. For any other producer only suffixes the
    graph contains count — or, when it names no files at all, the code
    languages, so an empty graph over a code tree isn't reported current.
    YAML is left to :data:`_CONTENT_GATED_SUFFIXES`.
    """
    from . import graphgen

    code: set[str] = set()
    for suffix, lang in graphgen._SUFFIX_LANG.items():
        try:
            if graphgen.language_available(lang):
                code.add(suffix)
        except Exception:
            continue
    docs = set(graphgen._DOC_SUFFIXES)
    schema = set(graphgen._SCHEMA_SUFFIXES) - _CONTENT_GATED_SUFFIXES
    if getattr(config, "mode", "auto") == "prose":
        code = set()
    if source == "built-in":
        return frozenset(code | docs | schema)
    known = set(graphgen.SUPPORTED_SUFFIXES) | docs | schema
    held = graph_suffixes & known
    if source == "graphify":
        return frozenset(code | (held & (docs | schema)))
    return frozenset(held or code)


# Schema suffixes whose files become nodes only when their content qualifies
# (a YAML file only if it's an OpenAPI/AsyncAPI spec). Counting every one on
# disk would report each CI config as missing, so only those the graph
# already holds are compared: their edits and deletions are caught, a new
# spec added since the build isn't.
_CONTENT_GATED_SUFFIXES = frozenset({".yaml", ".yml"})


def indexable_files(root: Path, suffixes: frozenset[str], config=None) -> list[str]:
    """Files graphgen would index under ``root`` for ``suffixes`` (POSIX, relative)."""
    from . import graphgen

    if not suffixes:
        return []
    files = graphgen._iter_files(root, graphgen._DEFAULT_IGNORES, suffixes)
    if config is not None:
        files = config.apply_globs(root, files)
    return sorted(f.relative_to(root).as_posix() for f in files)


def _inside_git_work_tree(root: Path) -> bool:
    """No git process unless there's a repository to ask (see neuralmind.ignore)."""
    from .ignore import inside_git_work_tree

    return inside_git_work_tree(root)


def _graph_git_state(root: Path, graph_path: Path) -> dict | None:
    """Commit info for a graph file tracked in git, or None when untracked."""
    if not _inside_git_work_tree(root):
        return None
    try:
        rel = graph_path.resolve().relative_to(root).as_posix()
    except (ValueError, OSError):
        return None
    if _git(root, "ls-files", "--error-unmatch", "--", rel) is None:
        return None
    log = _git(root, "log", "-1", "--format=%H%x00%cI", "--", rel)
    if not log or "\x00" not in log:
        return None
    commit, date = log.strip().split("\x00", 1)
    shallow = (_git(root, "rev-parse", "--is-shallow-repository") or "").strip() == "true"
    return {"rel": rel, "commit": commit, "date": date[:10], "shallow": shallow}


def _changed_via_git(root: Path, state: dict, known: set[str]) -> list[str]:
    """Files the graph knows that differ from the commit that last wrote it.

    ``git diff <commit>`` compares that commit with the working tree, so it
    covers later commits and uncommitted edits in one call. ``--relative``
    with the ``.`` pathspec limits it to the project and prints paths relative
    to it, so a project in a subdirectory of a larger repository compares
    like with like (and doesn't diff the whole repository).
    """
    out = _git(root, "diff", "--name-only", "--relative", state["commit"], "--", ".")
    if out is None:
        return []
    changed = {line.strip() for line in out.splitlines() if line.strip()}
    changed.discard(state["rel"])
    return sorted(changed & known)


def _changed_via_mtime(root: Path, graph_path: Path, known: set[str]) -> tuple[list[str], str]:
    """Files the graph knows whose mtime is newer than the graph file.

    When the built-in extraction cache exists, a newer mtime only counts if
    the content hash differs too, so a ``touch`` or a branch round-trip that
    restored the same bytes isn't reported.
    """
    try:
        graph_mtime = graph_path.stat().st_mtime
    except OSError:
        return [], ""
    candidates: list[str] = []
    for rel in known:
        try:
            if (root / rel).stat().st_mtime > graph_mtime:
                candidates.append(rel)
        except OSError:
            continue
    if not candidates:
        return [], "mtime"
    cache_path = root / CANONICAL_DIR / "extraction_cache.json"
    cache: dict[str, str] = {}
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            for entry in data.get("files", []) if isinstance(data, dict) else []:
                if isinstance(entry, dict) and entry.get("path") and entry.get("content_hash"):
                    cache[str(entry["path"])] = str(entry["content_hash"])
        except (OSError, ValueError, AttributeError):
            cache = {}
    if not cache:
        return sorted(candidates), "mtime"
    import hashlib

    changed: list[str] = []
    for rel in candidates:
        old_hash = cache.get(rel)
        if not old_hash:
            changed.append(rel)
            continue
        try:
            new_hash = hashlib.sha256((root / rel).read_bytes()).hexdigest()
        except OSError:
            continue
        if new_hash != old_hash:
            changed.append(rel)
    return sorted(changed), "hash"


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def graph_freshness(
    project: str | Path, graph_path: str | Path | None = None, *, check_index: bool = False
) -> FreshnessReport | None:
    """Compare the project's code graph with the files on disk.

    With ``check_index`` (the read-side checks: ``doctor``, ``health``, the
    MCP wakeup) it also checks the vector index was built from this graph as
    it is now. Build-time callers leave it off: the build re-embeds anyway.

    Returns None when there is no graph to compare (nothing built yet), or
    when the graph can't be read.
    """
    root = Path(project).resolve()
    gpath = Path(graph_path) if graph_path is not None else graph_json_path(root)
    if not gpath.exists():
        return None
    try:
        graph = json.loads(gpath.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(graph, dict):
        return None

    from .neuralmind_config import NeuralmindConfig

    config = NeuralmindConfig.load(root)
    source = graph_source_kind(graph, gpath)
    nodes = graph.get("nodes") or []

    posix_host = os.sep == "/"
    foreign_nodes = 0
    foreign_files: set[str] = set()
    graph_files: set[str] = set()
    normalized: dict[str, str] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        raw = node.get("source_file") or ""
        if not raw:
            continue
        raw = str(raw)
        if posix_host and "\\" in raw:
            foreign_nodes += 1
            foreign_files.add(raw)
        rel = normalized.get(raw)
        if rel is None:
            rel = normalized[raw] = normalize_source_path(raw, root)
        if rel:
            graph_files.add(rel)

    graph_suffixes = {PurePosixPath(p).suffix for p in graph_files}
    suffixes = _indexable_suffixes(source, graph_suffixes, config)
    on_disk = set(indexable_files(root, suffixes, config))
    gated = {p for p in graph_files if PurePosixPath(p).suffix in _CONTENT_GATED_SUFFIXES}
    if gated:
        on_disk |= gated & set(indexable_files(root, _CONTENT_GATED_SUFFIXES, config))

    missing = sorted(on_disk - graph_files)
    gone = sorted(p for p in graph_files if not (root / p).exists())

    known = graph_files & on_disk
    state = _graph_git_state(root, gpath)
    report = FreshnessReport(
        status=OK,
        graph_path=gpath,
        source=source,
        node_count=len(nodes),
        indexable_count=len(on_disk),
        missing_from_graph=missing,
        gone_from_disk=gone,
        foreign_separators=foreign_nodes,
        foreign_separator_files=len(foreign_files),
        project=root,
    )
    if state is not None:
        report.graph_date = None if state["shallow"] else state["date"]
        report.changed_since_graph = _changed_via_git(root, state, known)
        report.changed_method = "git"
        if state["shallow"]:
            report.age_note = "age unknown: shallow clone"
        else:
            # Commits touching the project since the graph changed — for a
            # project in a subdirectory, not every commit in the repository.
            count = _git(root, "rev-list", "--count", f"{state['commit']}..HEAD", "--", ".")
            try:
                report.graph_age_commits = int((count or "").strip())
            except ValueError:
                report.graph_age_commits = None
    else:
        report.changed_since_graph, report.changed_method = _changed_via_mtime(root, gpath, known)
    # A shallow clone's checkout stamps the graph file with the clone time,
    # so its mtime would pass off a months-old graph as today's.
    if report.graph_date is None:
        built_at = graph.get("built_at") or (graph.get("graph") or {}).get("built_at")
        if isinstance(built_at, str) and len(built_at) >= 10:
            report.graph_date = built_at[:10]
        elif state is None:
            try:
                report.graph_date = datetime.fromtimestamp(gpath.stat().st_mtime).strftime(
                    "%Y-%m-%d"
                )
            except OSError:
                pass

    if check_index:
        report.index_mismatch = index_graph_mismatch(root, gpath)
    _date_drift(report, root, gpath)
    report.status = classify(report)
    return report


def _date_drift(report: FreshnessReport, root: Path, gpath: Path) -> None:
    """Fill in when the drifted files changed (their mtimes).

    A file the graph has never seen, or one changed since it was built, has
    been waiting for a rebuild since it was last written. A graph that changed
    after the last build has been waiting since the graph was written.
    """
    missing = _mtimes(root, report.missing_from_graph)
    changed = _mtimes(root, report.changed_since_graph)
    report.newest_missing_mtime = max(missing) if missing else None
    report.newest_changed_mtime = max(changed) if changed else None
    dated = missing + changed
    if report.index_mismatch:
        try:
            dated.append(gpath.stat().st_mtime)
        except OSError:
            pass
    report.oldest_change_mtime = min(dated) if dated else None


def graph_fingerprint(path: str | Path) -> dict | None:
    """Size, mtime and content hash of a graph file, as a build records it."""
    path = Path(path)
    try:
        st = path.stat()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None
    return {"size": st.st_size, "mtime_ns": st.st_mtime_ns, "sha256": digest}


def index_graph_mismatch(project: str | Path, graph_path: str | Path | None = None) -> str:
    """Why the vector index wasn't built from the graph as it is now, or ``""``.

    Compares the graph the read path would load with the one the last build
    recorded in ``build_status.json``. Size and mtime settle it when they
    match; otherwise the content hash does, so a fresh clone (new mtimes,
    same bytes) isn't reported. Indexes built before the fingerprint was
    recorded report nothing.
    """
    root = Path(project).resolve()
    gpath = Path(graph_path) if graph_path is not None else graph_json_path(root)
    try:
        status = json.loads((root / CANONICAL_DIR / "build_status.json").read_text("utf-8"))
        record = status.get("graph") or {}
        recorded = record.get("fingerprint") or {}
        recorded_sha = recorded.get("sha256")
    except (OSError, ValueError, AttributeError):
        return ""
    if not recorded_sha:
        return ""
    built_from = Path(str(record.get("path") or ""))
    if not built_from.is_absolute():
        built_from = root / built_from
    try:
        same_file = built_from.resolve() == gpath.resolve()
        st = gpath.stat()
    except OSError:
        return ""
    if not same_file:
        return f"the index was built from {record.get('path')}"
    if st.st_size == recorded.get("size") and st.st_mtime_ns == recorded.get("mtime_ns"):
        return ""
    current = graph_fingerprint(gpath)
    if current is None or current["sha256"] == recorded_sha:
        return ""
    return "the graph changed after the last build"


def classify(report: FreshnessReport) -> str:
    """Status for a report, per the thresholds in the module docstring."""
    drift = len(report.missing_from_graph) + len(report.gone_from_disk)
    denominator = max(report.indexable_count, 1)
    if report.foreign_separators or report.index_mismatch or drift / denominator > FAIL_DRIFT_RATIO:
        return FAIL
    if drift or report.changed_since_graph:
        return WARN
    return OK


# --------------------------------------------------------------------------- #
# Query-time notice
# --------------------------------------------------------------------------- #
# The marker the init-hook's background rebuild leaves when its build fails
# (and removes when one succeeds); see cli._hook_rebuild_lines.
HOOK_BUILD_FAILED = ".hook-build.failed"
HOOK_BUILD_LOG = "hook-build.log"
HOOK_BUILD_LOCK = ".hook-build.lock"


def git_dir(root: Path) -> Path | None:
    """The git directory for ``root`` (a linked worktree's own), found by
    reading ``.git`` rather than running git; None outside a repository."""
    for directory in (root, *root.parents):
        dot = directory / ".git"
        if dot.is_dir():
            return dot
        if dot.is_file():
            try:
                line = dot.read_text(encoding="utf-8").strip()
            except OSError:
                return None
            if not line.startswith("gitdir:"):
                return None
            found = Path(line[len("gitdir:") :].strip())
            return found if found.is_absolute() else (directory / found).resolve()
    return None


def head_commit(root: Path) -> str | None:
    """``HEAD``'s commit for ``root``, or None outside a repository."""
    out = _git(root, "rev-parse", "--verify", "--quiet", "HEAD")
    return out.strip() if out else None


def query_notice(project: str | Path) -> str:
    """One line for an answer the index can't vouch for, else ``""`` (#631).

    ``query``, ``search`` and the MCP tools still answer from a stale index;
    this line tells the agent so, instead of letting old context pass for
    current. It names, in order of severity:

    * an index only in the legacy ``graphify-out/`` layout, which nothing
      reads any more, so semantic search returns nothing;
    * a background rebuild from the init-hook that failed after the last
      successful build;
    * commits since the build started that changed files in the project.

    It runs on every query, so it costs ``stat`` calls only, plus one
    ``git diff`` when ``<git-dir>/logs/HEAD`` moved after the build started.
    That compares the commit the build started from with ``HEAD``, so a
    commit elsewhere in a larger repository, or a branch switch that changed
    nothing here, adds no line. The reflog, not a commit date, says when
    ``HEAD`` moved: a pull checks out commits dated before the build. Never
    raises.
    """
    try:
        return _query_notice(Path(project).resolve())
    except Exception:  # a notice must never break the answer it rides on
        return ""


def _query_notice(root: Path) -> str:
    state = root / CANONICAL_DIR
    status_path = state / "build_status.json"
    rebuild = f"run neuralmind build {root}"
    if not status_path.is_file():
        legacy = root / LEGACY_DIR
        if (legacy / "neuralmind_turbovec").exists() or (legacy / "neuralmind_db").exists():
            return (
                "Index is in the legacy graphify-out/ layout, which NeuralMind no longer "
                f"reads, so semantic search finds nothing: {rebuild}."
            )
        return ""
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
        built_mtime = status_path.stat().st_mtime
    except (OSError, ValueError):
        return ""
    if not isinstance(status, dict):
        return ""

    failed = state / HOOK_BUILD_FAILED
    try:
        failed_after_build = failed.stat().st_mtime > built_mtime
    except OSError:
        failed_after_build = False
    if failed_after_build:
        return (
            "Index may be stale: the last background rebuild failed "
            f"(log: {CANONICAL_DIR}/{HOOK_BUILD_LOG}); {rebuild}."
        )

    started = status.get("build_started_at")
    built_from = status.get("build_head")
    gdir = git_dir(root)
    if not isinstance(started, (int, float)) or not built_from or gdir is None:
        return ""
    try:
        moved = (gdir / "logs" / "HEAD").stat().st_mtime > started
    except OSError:
        return ""
    if not moved:
        return ""
    out = _git(root, "diff", "--name-only", "--relative", str(built_from), "HEAD", "--", ".")
    if out is None:
        # The commit the build started from is gone (a rebase, a gc'd
        # branch), so nothing can say what changed: assume something did.
        changed: list[str] = []
        summary = "HEAD moved to commits the index was not built from"
    else:
        changed = sorted(line.strip() for line in out.splitlines() if line.strip())
        if not changed:
            return ""
        summary = (
            f"{len(changed):,} file{'s' if len(changed) != 1 else ''} changed in commits "
            f"since the last build{_examples(changed)}"
        )
    if (state / HOOK_BUILD_LOCK).is_dir():
        return f"Index is catching up: {summary}; a background rebuild is running."
    return f"Index is stale: {summary}; {rebuild}."
