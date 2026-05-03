"""
synapse_memory.py — Export learned synapses into agent-readable memory files.

The synapse store learns weighted associations between code nodes from
co-activation. Those weights are useful to Claude even when it doesn't
explicitly call NeuralMind's MCP tools — if we render them as a
markdown topic file under Claude Code's auto-memory directory, the
model loads them on session start and naturally references the
associations during reasoning.

This module is purely an export: it reads the synapse store and writes
markdown. It never blocks reads/writes on the live store, and it fails
open (returns the empty list of paths written) on any error so callers
in hooks don't have to handle exceptions.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .synapses import LTP_THRESHOLD, SynapseStore, default_db_path

DEFAULT_TOP_PAIRS = 25
DEFAULT_TOP_HUBS = 8
DEFAULT_MIN_WEIGHT = 0.05
PROJECT_MEMORY_FILENAME = "SYNAPSE_MEMORY.md"
CLAUDE_AUTO_FILENAME = "synapse-activations.md"


def _claude_project_slug(project_path: Path) -> str:
    """Derive Claude Code's per-project slug from an absolute path.

    Claude Code names project memory directories by replacing path
    separators with hyphens (the same convention it uses for transcripts).
    Returns a slug like ``-home-user-myrepo``. The leading separator
    becomes a leading hyphen, which is intentional and matches what we
    see in ``~/.claude/projects/`` on real installs.
    """
    return str(project_path).replace("/", "-").replace("\\", "-")


def claude_auto_memory_dir(project_path: str | Path) -> Path:
    """Return Claude Code's auto-memory directory for this project.

    Path layout:
        ~/.claude/projects/<slug>/memory/

    The directory may not exist on systems where Claude Code hasn't been
    used or hasn't created auto-memory yet — callers should treat
    nonexistence as "skip the global export" and only write the
    project-local file.
    """
    slug = _claude_project_slug(Path(project_path).resolve())
    return Path.home() / ".claude" / "projects" / slug / "memory"


def project_memory_file(project_path: str | Path) -> Path:
    """Return the project-local synapse memory file path.

    Always writable. Users typically import it from CLAUDE.md via
    ``@.neuralmind/SYNAPSE_MEMORY.md`` so the content loads regardless
    of whether the global auto-memory directory exists.
    """
    return Path(project_path) / ".neuralmind" / PROJECT_MEMORY_FILENAME


def _format_id(node_id: str, labels: dict[str, str]) -> str:
    label = labels.get(node_id)
    if label and label != node_id:
        return f"`{label}` ({node_id})"
    return f"`{node_id}`"


def _top_pairs(
    db_path: Path, limit: int, min_weight: float
) -> list[tuple[str, str, float, int]]:
    """Read the top N strongest synapse pairs directly from the DB.

    We bypass SynapseStore's query helpers so we can grab weight +
    activation_count in one round trip, ordered. Tolerates a missing or
    locked DB by returning an empty list.
    """
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(db_path, timeout=2.0)
        try:
            cur = conn.execute(
                """
                SELECT node_a, node_b, weight, activation_count
                FROM synapses
                WHERE weight >= ?
                ORDER BY weight DESC, activation_count DESC
                LIMIT ?
                """,
                (min_weight, limit),
            )
            return [(a, b, float(w), int(c)) for a, b, w, c in cur.fetchall()]
        finally:
            conn.close()
    except sqlite3.Error:
        return []


def _resolve_labels(node_ids: list[str], embedder) -> dict[str, str]:
    """Best-effort lookup of human-readable labels for a list of node ids.

    Returns ``{}`` when the embedder isn't built or doesn't expose a
    label-resolution path. The node id alone still renders cleanly, so
    we intentionally never raise from here.
    """
    if embedder is None or not node_ids:
        return {}
    labels: dict[str, str] = {}
    # Try the in-memory graph first — cheap and covers the typical case.
    nodes_iter = getattr(embedder, "nodes", None)
    if isinstance(nodes_iter, list):
        wanted = set(node_ids)
        for node in nodes_iter:
            nid = node.get("id")
            if nid in wanted:
                lbl = node.get("label")
                if lbl:
                    labels[nid] = str(lbl)
    return labels


def render_synapse_memory(
    project_path: str | Path,
    *,
    embedder=None,
    top_pairs: int = DEFAULT_TOP_PAIRS,
    top_hubs: int = DEFAULT_TOP_HUBS,
    min_weight: float = DEFAULT_MIN_WEIGHT,
) -> str:
    """Render the synapse memory file as a markdown string.

    Empty store still produces a valid (mostly empty) document so
    downstream readers can rely on the file existing.
    """
    project_path = Path(project_path)
    db_path = default_db_path(project_path)
    store = SynapseStore(db_path)
    stats = store.stats()

    pairs = _top_pairs(db_path, top_pairs, min_weight)
    pair_node_ids: list[str] = []
    for a, b, _, _ in pairs:
        pair_node_ids.extend((a, b))
    hubs = stats.get("top_hubs", [])[:top_hubs]
    hub_ids = [nid for nid, _ in hubs]

    labels = _resolve_labels(list(set(pair_node_ids + hub_ids)), embedder)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines: list[str] = [
        "# NeuralMind Synapse Memory",
        "",
        "_Auto-generated by NeuralMind. Do not edit — regenerated each session._",
        "",
        f"- Updated: {now}",
        f"- Edges learned: {stats['edges']} ({stats['ltp_edges']} long-term)",
        f"- Total synapse weight: {stats['total_weight']:.2f}",
        f"- Active nodes: {stats['nodes']}",
        "",
        "These associations were learned by NeuralMind from how the agent and",
        "the codebase have actually been used together. Treat them as a hint",
        "about which areas of the code tend to belong to the same thought —",
        "not as ground truth. Lower weights = newer or weaker associations.",
        "",
    ]

    if pairs:
        lines.append("## Strongest associations")
        lines.append("")
        for a, b, weight, count in pairs:
            tag = " *(long-term)*" if count >= LTP_THRESHOLD else ""
            lines.append(
                f"- {_format_id(a, labels)} ↔ {_format_id(b, labels)} — "
                f"weight {weight:.2f}, fired {count}×{tag}"
            )
        lines.append("")
    else:
        lines.append("## Strongest associations")
        lines.append("")
        lines.append("_(none yet — synapse store is empty or below threshold)_")
        lines.append("")

    if hubs:
        lines.append("## Hub nodes (most connected)")
        lines.append("")
        for node_id, degree in hubs:
            lines.append(f"- {_format_id(node_id, labels)} — {degree} connections")
        lines.append("")

    return "\n".join(lines)


def export_synapse_memory(
    project_path: str | Path,
    *,
    embedder=None,
    top_pairs: int = DEFAULT_TOP_PAIRS,
    top_hubs: int = DEFAULT_TOP_HUBS,
    min_weight: float = DEFAULT_MIN_WEIGHT,
    write_claude_auto_memory: bool = True,
) -> list[Path]:
    """Render the synapse memory and write it to disk.

    Always writes ``<project>/.neuralmind/SYNAPSE_MEMORY.md``. When
    Claude Code's auto-memory directory exists for this project, also
    writes ``<auto>/synapse-activations.md`` so the model picks it up
    on session start. Returns the list of paths written.

    Failures are swallowed (returns whichever paths did succeed) so
    hooks can call this safely.
    """
    written: list[Path] = []
    try:
        text = render_synapse_memory(
            project_path,
            embedder=embedder,
            top_pairs=top_pairs,
            top_hubs=top_hubs,
            min_weight=min_weight,
        )
    except Exception:
        return written

    project_target = project_memory_file(project_path)
    try:
        project_target.parent.mkdir(parents=True, exist_ok=True)
        project_target.write_text(text, encoding="utf-8")
        written.append(project_target)
    except OSError:
        pass

    if write_claude_auto_memory:
        auto_dir = claude_auto_memory_dir(project_path)
        if auto_dir.exists():
            auto_target = auto_dir / CLAUDE_AUTO_FILENAME
            try:
                auto_target.write_text(text, encoding="utf-8")
                written.append(auto_target)
            except OSError:
                pass

    return written
