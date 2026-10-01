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

Status: FAIL when missing + gone exceed 10% of indexable files or any node
path uses foreign separators; WARN when either list is non-empty or files
changed since the graph; OK otherwise.
"""

from __future__ import annotations

import json
import os
import subprocess
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
    project: Path | None = None

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
                f"{_examples(self.missing_from_graph)}"
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
            )
        return lines

    def fix_command(self, project_arg: str = ".") -> str:
        if self.status == OK:
            return ""
        if self.source == "built-in":
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
        }


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
    plus markdown — the files graphgen turns into nodes. For any other
    producer we can't know its language list, so only suffixes the graph
    already contains count: a graphify graph that never indexed markdown
    isn't "missing" every README.
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
    if getattr(config, "mode", "auto") == "prose":
        code = set()
    if source == "built-in":
        return frozenset(code | docs)
    known = set(graphgen.SUPPORTED_SUFFIXES) | docs
    return frozenset(graph_suffixes & known)


def indexable_files(root: Path, suffixes: frozenset[str], config=None) -> list[str]:
    """Files graphgen would index under ``root`` for ``suffixes`` (POSIX, relative)."""
    from . import graphgen

    if not suffixes:
        return []
    files = graphgen._iter_files(root, graphgen._DEFAULT_IGNORES, suffixes)
    if config is not None:
        files = config.apply_globs(root, files)
    return sorted(f.relative_to(root).as_posix() for f in files)


def _graph_git_state(root: Path, graph_path: Path) -> dict | None:
    """Commit info for a graph file tracked in git, or None when untracked."""
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
    covers later commits and uncommitted edits in one call.
    """
    out = _git(root, "diff", "--name-only", state["commit"], "--")
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
    project: str | Path, graph_path: str | Path | None = None
) -> FreshnessReport | None:
    """Compare the project's code graph with the files on disk.

    Returns None when there is no graph to compare (nothing built yet), or
    when the graph can't be read — the callers already report those cases.
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
            count = _git(root, "rev-list", "--count", f"{state['commit']}..HEAD")
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

    report.status = classify(report)
    return report


def classify(report: FreshnessReport) -> str:
    """Status for a report, per the thresholds in the module docstring."""
    drift = len(report.missing_from_graph) + len(report.gone_from_disk)
    denominator = max(report.indexable_count, 1)
    if report.foreign_separators or drift / denominator > FAIL_DRIFT_RATIO:
        return FAIL
    if drift or report.changed_since_graph:
        return WARN
    return OK
