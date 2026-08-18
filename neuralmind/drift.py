"""
drift.py — Commit-time pattern-drift detection over the code graph.

The synapse layer answers "what is related to this?" and
:mod:`neuralmind.cohesion` turns a surfaced cluster into "which member
breaks the cluster's shared pattern?". Both run at *recall* time, over
whatever the agent happened to ask about. Neither of them looks at the
one artifact that always knows what actually changed: the diff.

This module closes that loop. Given a git diff, it maps the changed
lines back onto graph nodes, builds each changed symbol's *peer group*
— its siblings in the same file or class, narrowed to the ones that
share its naming role — and asks the cohesion primitive whether the
symbol you just touched skips an association a strong majority of its
peers share.

That is "code drift" in the sense that matters for an agent-written
codebase: not a lint violation and not a broken test, but handler #11
quietly not doing what handlers #1-#10 all do. Tests pass, review skims
it, and the codebase erodes one plausible-looking function at a time.

Design:
- Stdlib-only (no ChromaDB, no tree-sitter, no embedder), matching the
  synapse/structural layers, so ``tests/test_drift.py`` runs without the
  full dependency set and the pre-commit hook costs a JSON load rather
  than a model load.
- Reuses :func:`neuralmind.cohesion.find_outliers` for the consensus
  math and :class:`neuralmind.structural.StructuralIndex` for adjacency
  instead of restating either — a drift detector that drifted from the
  primitives it was built on would be a poor advertisement.
- Reports only symbols *in the diff*. The graph is full of pre-existing
  odd-ones-out; blaming a commit for those trains people to ignore the
  check.
- Fails quiet, never loud: an unparseable diff, a cold graph, or a
  symbol the graph has never seen yields no findings rather than a
  false accusation.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .cohesion import DEFAULT_COHESION, DEFAULT_MIN_PEERS, find_outliers
from .structural import StructuralIndex

# Relations whose *forward* view defines "what this symbol reaches out to".
# Calls dominate (a skipped call is the classic drift), and inheritance
# catches the sibling class that forgot its base.
DRIFT_RELATIONS: tuple[str, ...] = ("calls", "inherits")
DRIFT_VIEWS: tuple[str, ...] = ("callees", "bases")

# A peer group needs at least this many members before consensus means
# anything; below it, "the majority" is one or two symbols.
DEFAULT_MAX_FINDINGS = 10

# Name tokens shorter than this are too generic to define a role group
# (``_``, ``b``, ``id``), so they never narrow a sibling set.
MIN_ROLE_TOKEN = 3

# Refs flow in from a CLI argument and a git hook, so they reach
# ``subprocess`` as data. Same allowlist the compliance CI check uses.
_SAFE_REF = re.compile(r"^[A-Za-z0-9_./^\-~@]+$")

# ``@@ -12,3 +14,9 @@`` — we only care about the new-side range, since a
# deleted line has no symbol left to blame.
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


@dataclass(frozen=True)
class DriftFinding:
    """One changed symbol that skips a pattern its peers share.

    ``node`` was touched by the diff and does *not* reach ``associate``,
    while ``peers`` of the ``group_size`` symbols in its peer group do.
    ``share`` is the strength of that consensus in ``[0, 1]``.
    """

    node: str
    label: str
    source_file: str
    line: int
    associate: str
    associate_label: str
    peers: int
    group_size: int

    @property
    def share(self) -> float:
        others = self.group_size - 1
        return self.peers / others if others else 0.0

    def to_dict(self) -> dict:
        return {
            "node": self.node,
            "label": self.label,
            "file": self.source_file,
            "line": self.line,
            "skips": self.associate,
            "skips_label": self.associate_label,
            "peers": self.peers,
            "group_size": self.group_size,
            "share": round(self.share, 3),
        }


# --------------------------------------------------------------------- #
# Diff → changed line ranges
# --------------------------------------------------------------------- #


def parse_diff_hunks(diff_text: str) -> dict[str, list[tuple[int, int]]]:
    """Map ``path -> [(start_line, end_line), ...]`` from unified diff text.

    Reads the ``+++ b/path`` headers and the new-side range of each
    ``@@`` hunk, so the ranges index the *post-change* file — the same
    coordinate space the graph's ``source_location`` uses. Pure-deleted
    hunks (new-side count of 0) are skipped: there is no resulting line
    to attribute to a symbol. ``/dev/null`` targets (file deletions) are
    dropped for the same reason.
    """
    ranges: dict[str, list[tuple[int, int]]] = defaultdict(list)
    current: str | None = None
    for line in (diff_text or "").splitlines():
        if line.startswith("+++ "):
            target = line[4:].strip()
            # git writes `+++ b/path`; `--no-prefix` or /dev/null vary it.
            if target == "/dev/null":
                current = None
                continue
            if target.startswith("b/"):
                target = target[2:]
            current = target or None
            continue
        if current is None or not line.startswith("@@"):
            continue
        match = _HUNK.match(line)
        if not match:
            continue
        start = int(match.group(1))
        count = int(match.group(2)) if match.group(2) is not None else 1
        if count <= 0:
            continue
        ranges[current].append((start, start + count - 1))
    return dict(ranges)


def diff_text(project_path: str | Path, *, base: str | None = None, staged: bool = False) -> str:
    """Return unified diff text for the requested comparison, or ``""``.

    ``staged=True`` diffs the index against ``HEAD`` — what a
    ``pre-commit`` hook is about to let through. Otherwise the working
    tree is compared against ``base`` (default ``HEAD``). Zero context
    lines keep the hunk ranges tight around what actually changed, so a
    one-line edit does not implicate its neighbors.

    Any git failure returns ``""``; the caller reports "nothing to
    check" rather than treating a missing repo as a violation.
    """
    if base is not None and not _SAFE_REF.match(base):
        return ""
    cmd = ["git", "-C", str(project_path), "diff", "--unified=0", "--no-color"]
    if staged:
        cmd.append("--cached")
    if base is not None:
        cmd.append(base)
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True, errors="replace")
    except (subprocess.CalledProcessError, OSError):
        return ""


# --------------------------------------------------------------------- #
# Graph view — containers, members, and line→symbol mapping
# --------------------------------------------------------------------- #


def _location_line(node: dict) -> int:
    """Parse graphify's ``source_location`` (``"L23"``) to an int line."""
    raw = str(node.get("source_location", "") or "")
    match = re.search(r"(\d+)", raw)
    return int(match.group(1)) if match else 0


class GraphView:
    """Read-only helpers over a loaded ``graph.json`` dict.

    Holds the three things drift detection needs and nothing else: the
    ``contains`` hierarchy (to find a symbol's siblings), a per-file
    ordering of code symbols (to map a diff line to the symbol that owns
    it), and a :class:`~neuralmind.structural.StructuralIndex` for the
    outward edges the consensus is computed over.
    """

    def __init__(self, graph: dict) -> None:
        nodes = graph.get("nodes") or []
        links = graph.get("links") or graph.get("edges") or []
        self.nodes: dict[str, dict] = {
            str(n["id"]): n for n in nodes if isinstance(n, dict) and n.get("id")
        }
        # container -> members, and the reverse, from `contains` edges.
        self.members: dict[str, list[str]] = defaultdict(list)
        self.container_of: dict[str, str] = {}
        for link in links:
            if not isinstance(link, dict):
                continue
            if link.get("relation") != "contains":
                continue
            src = str(link.get("source", link.get("_src", "")) or "")
            tgt = str(link.get("target", link.get("_tgt", "")) or "")
            if not src or not tgt or src == tgt:
                continue
            self.members[src].append(tgt)
            # A node contained by two parents is a graph anomaly; first wins.
            self.container_of.setdefault(tgt, src)
        # Every node that owns members is a container (a file or a class),
        # never a leaf symbol we would blame for a change.
        self.containers: frozenset[str] = frozenset(self.members)

        # file path -> code symbols in that file, ordered by start line.
        by_file: dict[str, list[tuple[int, str]]] = defaultdict(list)
        for node_id, node in self.nodes.items():
            if node.get("file_type") != "code" or node_id in self.containers:
                continue
            source_file = str(node.get("source_file", "") or "")
            if not source_file:
                continue
            by_file[source_file].append((_location_line(node), node_id))
        self.file_symbols: dict[str, list[tuple[int, str]]] = {
            path: sorted(entries) for path, entries in by_file.items()
        }

        self.structural = StructuralIndex().build_from_edges(links)

    def label(self, node_id: str) -> str:
        """Human label for a node id, falling back to the id itself."""
        node = self.nodes.get(node_id)
        return str(node.get("label", node_id)) if node else node_id

    def associates(self, node_id: str) -> list[tuple[str, float]]:
        """Outward structural edges of ``node_id`` as ``(id, weight)``.

        The shape :func:`~neuralmind.cohesion.find_outliers` expects. Only
        the forward views in :data:`DRIFT_VIEWS` count: "my peers all call
        X and I don't" is a pattern the author controls, whereas "my peers
        are all called by X" is a fact about the rest of the codebase.
        """
        views = self.structural.neighbors(node_id, DRIFT_RELATIONS)
        out: list[tuple[str, float]] = []
        for view in DRIFT_VIEWS:
            out.extend((other, 1.0) for other in views.get(view, ()))
        return out

    def symbols_for_ranges(self, ranges: dict[str, list[tuple[int, int]]]) -> list[str]:
        """Map changed line ranges to the code symbols that own them.

        Within a file, symbols are ordered by start line and a changed
        line is attributed to the last symbol starting at or before it —
        graphify records a start line but no end line, so this is the
        closest containment the graph supports. Lines above the first
        symbol (imports, module docstrings) belong to no symbol and are
        dropped rather than blamed on the file node.

        Returns node ids in a stable order, de-duplicated.
        """
        hits: list[str] = []
        for path, spans in ranges.items():
            entries = self.file_symbols.get(path)
            if not entries:
                continue
            for start, end in spans:
                for index, (line, node_id) in enumerate(entries):
                    if line > end:
                        break
                    # Owns the change if the next symbol starts after it.
                    next_line = entries[index + 1][0] if index + 1 < len(entries) else None
                    if next_line is not None and next_line <= start:
                        continue
                    if line <= end:
                        hits.append(node_id)
        return list(dict.fromkeys(hits))


# --------------------------------------------------------------------- #
# Peer groups
# --------------------------------------------------------------------- #


def _role_tokens(label: str) -> tuple[str, str]:
    """Split a symbol label into its ``(first, last)`` role tokens.

    ``create_user()`` → ``("create", "user")``; ``_on_charge_failed()`` →
    ``("on", "failed")``. Trailing ``()`` (the built-in backend's marker
    for a callable) and leading underscores are stripped so a private
    helper groups with its public siblings. Tokens below
    :data:`MIN_ROLE_TOKEN` characters are dropped — they are too generic
    to name a role.
    """
    name = label.strip()
    if name.endswith("()"):
        name = name[:-2]
    parts = [p for p in name.strip("_").split("_") if len(p) >= MIN_ROLE_TOKEN]
    if not parts:
        return ("", "")
    return (parts[0].lower(), parts[-1].lower())


def peer_group(view: GraphView, node_id: str, *, min_peers: int = DEFAULT_MIN_PEERS) -> list[str]:
    """Return the symbols ``node_id`` should be consistent with.

    Starts from its siblings — the other code symbols in the same
    container (file or class) — then narrows to the ones sharing its
    naming role when such a subgroup is both large enough to carry a
    majority and strictly smaller than the full sibling set. So
    ``refund_endpoint`` is judged against the other ``*_endpoint``
    handlers rather than against every exception class in the module,
    which is what makes a consensus meaningful instead of merely
    arithmetic.

    Returns ``[]`` when the group would be too small to have both a
    majority and a dissenter, which is the common, quiet case.
    """
    container = view.container_of.get(node_id)
    if not container:
        return []
    siblings = [
        member
        for member in view.members.get(container, ())
        if member in view.nodes
        and view.nodes[member].get("file_type") == "code"
        and member not in view.containers
    ]
    if len(siblings) < min_peers + 1:
        return []

    first, last = _role_tokens(view.label(node_id))
    best: list[str] | None = None
    for position, token in ((1, last), (0, first)):
        if not token:
            continue
        group = [s for s in siblings if _role_tokens(view.label(s))[position] == token]
        if len(group) < min_peers + 1 or len(group) >= len(siblings):
            # Too small to judge, or it is just the sibling set again.
            continue
        if best is None or len(group) < len(best):
            best = group
    return best if best is not None else siblings


# --------------------------------------------------------------------- #
# Detection
# --------------------------------------------------------------------- #


def find_drift(
    graph: dict,
    changed_ranges: dict[str, list[tuple[int, int]]],
    *,
    cohesion: float = DEFAULT_COHESION,
    min_peers: int = DEFAULT_MIN_PEERS,
    max_findings: int = DEFAULT_MAX_FINDINGS,
) -> list[DriftFinding]:
    """Find changed symbols that break their peer group's shared pattern.

    Maps ``changed_ranges`` (from :func:`parse_diff_hunks`) onto graph
    symbols, and for each one runs :func:`~neuralmind.cohesion.find_outliers`
    over its :func:`peer_group`, keeping only the findings that name the
    changed symbol itself. Ranked by consensus strength, strongest first.

    Empty whenever the graph is cold, the diff touches nothing the graph
    knows, or every changed symbol agrees with its peers.
    """
    view = GraphView(graph)
    changed = view.symbols_for_ranges(changed_ranges)
    if not changed:
        return []

    findings: list[DriftFinding] = []
    seen: set[tuple[str, str]] = set()
    for node_id in changed:
        group = peer_group(view, node_id, min_peers=min_peers)
        if not group or node_id not in group:
            continue
        try:
            outliers = find_outliers(
                group,
                view.associates,
                cohesion=cohesion,
                min_peers=min_peers,
                max_findings=max_findings,
            )
        except Exception:
            # A malformed graph must not break a commit.
            continue
        node = view.nodes.get(node_id, {})
        for outlier in outliers:
            if outlier.node != node_id:
                # A pre-existing odd-one-out this commit did not touch.
                continue
            key = (node_id, outlier.associate)
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                DriftFinding(
                    node=node_id,
                    label=view.label(node_id),
                    source_file=str(node.get("source_file", "") or ""),
                    line=_location_line(node),
                    associate=outlier.associate,
                    associate_label=view.label(outlier.associate),
                    peers=outlier.peers,
                    group_size=outlier.cluster_size,
                )
            )

    findings.sort(key=lambda f: (f.share, f.peers), reverse=True)
    return findings[:max_findings]


def format_drift(findings: list[DriftFinding], *, strict: bool = False) -> str:
    """Render findings as a compact block for a terminal or a hook.

    Empty string when there is nothing to report, so a caller can print
    it unconditionally without emitting a dangling header.
    """
    if not findings:
        return ""
    verb = "blocked" if strict else "warning"
    lines = [f"## NeuralMind drift check ({verb}) — {len(findings)} finding(s)", ""]
    for finding in findings:
        location = f"{finding.source_file}:{finding.line}" if finding.source_file else finding.node
        pct = round(finding.share * 100)
        lines.append(
            f"- {location} — `{finding.label}` skips `{finding.associate_label}`, "
            f"which {finding.peers} of its {finding.group_size - 1} peers ({pct}%) use. "
            "Confirm this is deliberate."
        )
    lines.append("")
    if strict:
        lines.append("Commit blocked. Fix the drift, or re-run without --strict to warn only.")
    else:
        lines.append("Warning only — the commit proceeds. Use --strict to block on drift.")
    return "\n".join(lines)


# --------------------------------------------------------------------- #
# Project-level entry point
# --------------------------------------------------------------------- #


def load_graph(project_path: str | Path) -> dict:
    """Load a project's ``graph.json``, or ``{}`` when there is none.

    Goes through :func:`neuralmind.ir.project_artifact` so a project root
    arriving from a CLI argument or a hook cannot escape its own tree.
    """
    from . import ir as ir_mod

    try:
        path = ir_mod.project_artifact(project_path, "graphify-out", "graph.json")
    except ValueError:
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            graph = json.load(handle)
    except (OSError, ValueError):
        return {}
    return graph if isinstance(graph, dict) else {}


def refresh_graph(project_path: str | Path, graph: dict, paths: list[str]) -> dict:
    """Re-parse ``paths`` into a copy of ``graph`` so new symbols are visible.

    The persisted graph is only as fresh as the last build, and the
    ``post-commit`` hook rebuilds *after* the commit — so at ``pre-commit``
    time a brand-new function, the single most common shape of agent
    drift, would be invisible. Splicing just the changed files back in
    costs a tree-sitter parse of those files and no embedder work.

    Deep-copies first: ``graphgen.update_files`` splices in place, and a
    check must never mutate the index it reads. Returns ``graph``
    unchanged when tree-sitter is unavailable, the graph came from
    graphify, or anything at all goes wrong — a stale graph yields
    weaker findings, while a failed refresh must not fail the commit.
    """
    if not graph or not paths:
        return graph
    if "neuralmind.graphgen" not in str(graph.get("generated_by", "")):
        # A real graphify build is graphify's to update.
        return graph
    try:
        import copy

        from . import graphgen

        if not graphgen.is_available():
            return graph
        root = Path(project_path).resolve()
        indexable = graphgen.SUPPORTED_SUFFIXES | graphgen._DOC_SUFFIXES
        changed = [rel for rel in paths if Path(rel).suffix in indexable and (root / rel).is_file()]
        if not changed:
            return graph
        refreshed, _ = graphgen.update_files(project_path, copy.deepcopy(graph), changed, [])
        return refreshed if isinstance(refreshed, dict) else graph
    except Exception:
        return graph


def check_project(
    project_path: str | Path,
    *,
    base: str | None = None,
    staged: bool = False,
    cohesion: float = DEFAULT_COHESION,
    min_peers: int = DEFAULT_MIN_PEERS,
    max_findings: int = DEFAULT_MAX_FINDINGS,
    refresh: bool = True,
) -> dict:
    """Run the whole drift check for a project and return a result dict.

    ``{"findings": [...], "changed_files": [...], "symbols_checked": int,
    "graph": "loaded"|"missing"}``. The single entry point the CLI, the
    git hook, and any future MCP tool share, so all three report the
    same thing.
    """
    ranges = parse_diff_hunks(diff_text(project_path, base=base, staged=staged))
    result: dict = {
        "findings": [],
        "changed_files": sorted(ranges),
        "symbols_checked": 0,
        "graph": "missing",
    }
    if not ranges:
        return result

    graph = load_graph(project_path)
    if not graph.get("nodes"):
        return result
    result["graph"] = "loaded"
    if refresh and os.environ.get("NEURALMIND_DRIFT_REFRESH") != "0":
        graph = refresh_graph(project_path, graph, sorted(ranges))

    view = GraphView(graph)
    result["symbols_checked"] = len(view.symbols_for_ranges(ranges))
    findings = find_drift(
        graph,
        ranges,
        cohesion=cohesion,
        min_peers=min_peers,
        max_findings=max_findings,
    )
    result["findings"] = [f.to_dict() for f in findings]
    result["_findings"] = findings
    return result
