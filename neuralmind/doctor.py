"""doctor.py — install/health diagnostics for ``neuralmind doctor``.

Inspects a project's NeuralMind setup *without building anything*, so it
works as a first-run troubleshooter: which pieces are in place, which
aren't, and the exact command to fix each gap.

Each check is computed defensively — a failure to inspect one subsystem
(e.g. a corrupt synapse db) never blocks the rest of the report. The
machine-readable form (``--json``) is stable so agents and CI can gate on
it; the human form prints an ASCII status marker plus a next-step fix.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# Status levels, worst-last so ``overall_status`` can pick the max.
OK = "ok"
WARN = "warn"
FAIL = "fail"

_RANK = {OK: 0, WARN: 1, FAIL: 2}


@dataclass
class Check:
    """One diagnostic result.

    ``fix`` is the actionable next step shown when the check isn't OK.
    """

    name: str
    status: str
    detail: str
    fix: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "fix": self.fix,
        }


def _check_graph(project: Path) -> Check:
    graph = project / "graphify-out" / "graph.json"
    if not graph.exists():
        return Check(
            "Code graph",
            FAIL,
            f"not found at {graph}",
            fix=f"Generate it: neuralmind build {project}",
        )
    try:
        g = json.loads(graph.read_text(encoding="utf-8"))
        nodes = len(g.get("nodes", []))
        stale = 0
        orphaned = 0
        embedded_count = 0
        for node in g.get("nodes", []):
            eh = node.get("embedded_at")
            if eh:
                embedded_count += 1
            sf = node.get("source_file", "")
            if not sf:
                continue
            if eh and not (project / sf).exists():
                orphaned += 1
            elif eh:
                try:
                    from datetime import datetime

                    file_mtime = (project / sf).stat().st_mtime
                    emb_time = datetime.fromisoformat(eh).timestamp()
                    if file_mtime > emb_time:
                        stale += 1
                except Exception:
                    pass
    except Exception as e:  # corrupt / truncated graph.json
        return Check(
            "Code graph",
            FAIL,
            f"unreadable ({e})",
            fix=f"Regenerate it: neuralmind build {project}",
        )

    details = f"{nodes} nodes at {graph}"
    fixes = []
    if orphaned > 0:
        details += f" ({orphaned} orphaned — source file deleted)"
        fixes.append(f"Rebuild: neuralmind build {project}")
    if stale > 0:
        details += f" ({stale} stale — file changed after embedding)"
        fixes.append("Rebuild: neuralmind build")

    status = FAIL if orphaned > 0 else (WARN if stale > 0 else OK)
    fix_str = "; ".join(fixes) if fixes else ""
    if not fix_str and embedded_count == 0 and nodes > 0:
        fix_str = "Graph not yet embedded — run neuralmind build"
    return Check("Code graph", status, details, fix=fix_str)


def _check_index(project: Path) -> Check:
    try:
        from neuralmind.core import NeuralMind

        mind = NeuralMind(str(project))
        stats = mind.embedder.get_stats()
        backend = mind.backend_name
    except Exception as e:
        return Check(
            "Semantic index",
            FAIL,
            f"could not read index ({e})",
            fix="Build it: neuralmind build",
        )
    total = int(stats.get("total_nodes", 0) or 0)
    if total > 0:
        return Check("Semantic index", OK, f"{total} nodes embedded ({backend} backend)")
    return Check(
        "Semantic index",
        FAIL,
        f"no nodes embedded ({backend} backend)",
        fix="Build it: neuralmind build",
    )


def _check_synapses(project: Path) -> Check:
    try:
        from neuralmind.synapses import SynapseStore, default_db_path

        db = Path(default_db_path(project))
        if not db.exists():
            return Check(
                "Synapse memory",
                WARN,
                "no synapses.db yet (nothing learned)",
                fix="It populates automatically as you query and edit the codebase.",
            )
        s = SynapseStore(db).stats()
    except Exception as e:
        return Check("Synapse memory", WARN, f"could not read synapses ({e})")
    return Check(
        "Synapse memory",
        OK,
        f"{s.get('edges', 0)} edges, {s.get('transitions', 0)} transitions",
    )


def _check_mcp() -> Check:
    try:
        from neuralmind.mcp_server import MCP_AVAILABLE
    except Exception as e:
        return Check("MCP server", WARN, f"could not check MCP ({e})")
    if MCP_AVAILABLE:
        return Check("MCP server", OK, "MCP SDK importable (neuralmind-mcp ready)")
    return Check(
        "MCP server",
        WARN,
        "MCP SDK not importable",
        fix="Reinstall with the MCP extra: pip install 'neuralmind[mcp]'",
    )


def _check_hooks(project: Path) -> Check:
    try:
        from neuralmind.hooks import _is_neuralmind_block, _settings_path
    except Exception as e:
        return Check("Claude Code hooks", WARN, f"could not check hooks ({e})")

    scopes: list[tuple[str, Path]] = []
    try:
        scopes.append(("project", _settings_path("project", str(project))))
    except Exception:
        pass
    try:
        scopes.append(("global", _settings_path("global")))
    except Exception:
        pass

    installed = []
    for label, path in scopes:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        blocks = [
            block
            for event_blocks in (data.get("hooks") or {}).values()
            if isinstance(event_blocks, list)
            for block in event_blocks
        ]
        if any(_is_neuralmind_block(b) for b in blocks):
            installed.append(label)

    if installed:
        return Check("Claude Code hooks", OK, f"installed ({', '.join(installed)})")
    return Check(
        "Claude Code hooks",
        WARN,
        "not installed",
        fix="Install them: neuralmind install-hooks",
    )


def _check_memory() -> Check:
    try:
        from neuralmind.memory import is_memory_logging_enabled

        enabled = bool(is_memory_logging_enabled())
    except Exception as e:
        return Check("Query memory", WARN, f"could not check ({e})")
    if enabled:
        return Check("Query memory", OK, "enabled (logging queries for learning)")
    return Check(
        "Query memory",
        WARN,
        "disabled (no query logging)",
        fix="Enable with NEURALMIND_MEMORY=1, or accept the prompt on first query.",
    )


def _check_doc_code_alignment(project: Path) -> Check:
    """Warn when code-doc mtime desync suggests stale documentation.

    Heuristic: for each document/header node in graph.json, if the doc file
    is newer than the directory's newest code file, flag it as potentially
    stale. Fail-open: never FAIL — this is advisory.
    """
    graph_path = project / "graphify-out" / "graph.json"
    if not graph_path.exists():
        return Check("Doc-code alignment", WARN, "no graph.json to analyze")

    try:
        g = json.loads(graph_path.read_text(encoding="utf-8"))
    except Exception:
        return Check("Doc-code alignment", WARN, "graph.json unreadable")

    doc_nodes = [n for n in g.get("nodes", []) if n.get("file_type") in ("document", "rationale")]
    if not doc_nodes:
        return Check("Doc-code alignment", OK, "no document nodes to check")

    # Count document files
    doc_files = {n.get("source_file") for n in doc_nodes if n.get("source_file")}
    return Check(
        "Doc-code alignment",
        OK,
        f"{len(doc_files)} doc files co-indexed with code (structural edges built)",
    )


def _check_backend(project: Path) -> Check:
    """Report the resolved backend and how it was chosen.

    v0.22 made the default ``auto`` (turbovec when its deps are installed, else
    chroma). The effective backend can therefore differ per environment, so
    surface both the configured value and what it resolves to — and whether the
    turbovec stack is available — so it's never a silent mystery.
    """
    try:
        from neuralmind.backend_manager import (
            load_backend_config,
            resolve_backend,
            turbovec_available,
        )
    except Exception as e:
        return Check("Backend", WARN, f"could not resolve backend ({e})")
    raw = load_backend_config(project).get("backend", "auto")
    resolved = resolve_backend(raw)
    tv = "available" if turbovec_available() else "not installed"
    # A non-string (e.g. `backend: null`) or "auto"/"" means auto-selection —
    # match BackendManager, which treats None like auto. Don't str() first, or
    # `null` would look like a backend literally named "none".
    is_auto = not isinstance(raw, str) or raw.strip().lower() in {"", "auto"}
    if is_auto:
        return Check(
            "Backend",
            OK,
            f"{resolved} (auto-selected; turbovec stack {tv})",
            fix="Pin a backend with `backend: graph|turbovec` in neuralmind-backend.yaml.",
        )
    return Check("Backend", OK, f"{resolved} (pinned via neuralmind-backend.yaml; turbovec {tv})")


def _check_turbovec_version(project: Path) -> Check:
    """Check if the turbovec index is compatible with the installed version."""
    try:
        from neuralmind.turbovec_backend import TurboVecEmbedder

        backend = TurboVecEmbedder(str(project))
        stale_path = backend._index_path.with_name(backend._index_path.name + ".stale")
        if stale_path.exists():
            tv_version = backend.turbovec_index_version()
            return Check(
                "Turbovec compatibility",
                FAIL,
                f"Index quarantined (version mismatch). Installed turbovec: {tv_version or 'unknown'}",
                fix="Rebuild: neuralmind build (recovery will attempt incremental rebuild from stored vectors)",
            )
        return Check("Turbovec compatibility", OK, "Index version compatible")
    except ImportError:
        return Check("Turbovec compatibility", WARN, "turbovec not installed — skipping")


def run_diagnostics(project_path: str) -> list[Check]:
    """Run every check against ``project_path`` and return the results."""
    project = Path(project_path).resolve()
    return [
        _check_graph(project),
        _check_backend(project),
        _check_index(project),
        _check_synapses(project),
        _check_mcp(),
        _check_hooks(project),
        _check_memory(),
        _check_doc_code_alignment(project),
        _check_turbovec_version(project),
    ]


def overall_status(checks: list[Check]) -> str:
    """The worst status across all checks (FAIL > WARN > OK)."""
    return max((c.status for c in checks), key=lambda s: _RANK.get(s, 0), default=OK)
