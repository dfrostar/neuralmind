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

from .paths import graph_json_path

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
    """Is there a code graph, and does it match the files on disk?

    Delegates to :func:`neuralmind.freshness.graph_freshness`, which compares
    the graph with the working tree in both directions whatever tool made it
    — graphify graphs never carry ``embedded_at``, so a per-node timestamp
    check would pass them unexamined.
    """
    graph = graph_json_path(project)
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
    except Exception as e:  # corrupt / truncated graph.json
        return Check(
            "Code graph",
            FAIL,
            f"unreadable ({e})",
            fix=f"Regenerate it: neuralmind build {project} --regenerate-graph",
        )

    from .freshness import graph_freshness

    try:
        report = graph_freshness(project, graph, check_index=True)
    except Exception as e:  # pragma: no cover - diagnostic only
        return Check("Code graph", WARN, f"{nodes} nodes at {graph} (freshness check failed: {e})")
    if report is None:
        return Check("Code graph", OK, f"{nodes} nodes at {graph}")
    detail = f"{report.header()}, {nodes:,} nodes"
    problems = report.problem_lines()
    if problems:
        detail += "\n         " + "\n         ".join(problems)
    return Check("Code graph", report.status, detail, fix=report.fix_command(str(project)))


def _graph_node_ids(project: Path) -> set[str] | None:
    """Ids a build of the current graph would embed, or None if unreadable."""
    try:
        g = json.loads(graph_json_path(project).read_text(encoding="utf-8"))
    except Exception:
        return None
    return {
        str(n.get("id", n.get("label", "")))
        for n in g.get("nodes", []) or []
        if isinstance(n, dict) and n.get("id", n.get("label", ""))
    }


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
    scopes: list[str] = []
    if total == 0:
        # Book-mode / scoped builds write store.<scope>.sqlite (code/content/
        # docs) instead of the default-scope store.sqlite read above. Per-scope
        # stores partition nodes (a node matches exactly one scope), so summing
        # them is correct — but only when the default store is empty, since an
        # all-scope store overlaps the per-scope ones. Without this, doctor
        # reports "no nodes embedded" on a perfectly healthy book build.
        import sqlite3

        from .paths import vector_db_path

        tv_dir = Path(vector_db_path(project, "turbovec"))
        for store_file in sorted(tv_dir.glob("store.*.sqlite")):
            scopes.append(store_file.name[len("store.") : -len(".sqlite")])
            con = None
            try:
                # as_uri() percent-encodes and uses forward slashes, so the
                # read-only URI also works on Windows (a raw f"file:{path}"
                # silently fails to open there and the store would be skipped).
                con = sqlite3.connect(store_file.as_uri() + "?mode=ro", uri=True)
                row = con.execute("SELECT COUNT(*) AS c FROM nodes").fetchone()
                total += int(row[0]) if row else 0
            except (sqlite3.Error, ValueError):
                continue
            finally:
                if con is not None:
                    con.close()
    if total > 0:
        minds = [mind]
        if scopes:
            # Compare each scoped store with its own slice of the graph; the
            # default embedder above reads the (empty) all-scope store.
            try:
                minds = [NeuralMind(str(project), scope=scope) for scope in scopes]
            except Exception:
                minds = []
        return _compare_index_with_graph(project, minds, total, backend)
    # No nodes at canonical path — is a legacy graphify-out/ index orphaned?
    legacy_note = ""
    try:
        from neuralmind.paths import legacy_artifact

        legacy_vec = legacy_artifact(project, "neuralmind_turbovec")
        legacy_chroma = legacy_artifact(project, "neuralmind_db")
        if legacy_vec.exists() or legacy_chroma.exists():
            legacy_note = (
                " — a legacy graphify-out/ index exists; it is NOT read "
                'anymore. Run `python -c "from neuralmind.paths import '
                "migrate_legacy_artifacts; "
                "print(migrate_legacy_artifacts('.'))\"` to move it, or "
                "rebuild with `neuralmind build`."
            )
    except Exception:
        pass  # diagnostic only; never fail the check on this
    return Check(
        "Semantic index",
        FAIL,
        f"no nodes embedded ({backend} backend){legacy_note}",
        fix="Build it: neuralmind build",
    )


def _compare_index_with_graph(project: Path, minds: list, total: int, backend: str) -> Check:
    """Vector store vs graph: equal is OK, extra vectors FAIL, missing WARN.

    Extra vectors are nodes that left the graph but can still be returned by
    search. Content ingested with ``ingest``/``ingest-content`` lives in the
    store without being in the graph and isn't counted as extra. ``minds``
    holds one instance per store: the all-scope store, or each scoped store
    of a book/scoped build, each compared with the graph nodes in its scope.
    """
    graph_ids = _graph_node_ids(project)
    if graph_ids is None or not minds:
        return Check("Semantic index", OK, f"{total} nodes embedded ({backend} backend)")
    orphans: set[str] = set()
    stored_total = 0
    expected: set[str] = set()
    stored: set[str] = set()
    counted = True
    for mind in minds:
        embedder = mind.embedder
        try:
            if not getattr(embedder, "nodes", None):
                embedder.load_graph()
        except Exception:
            pass
        finder = getattr(embedder, "orphaned_node_ids", None)
        if callable(finder):
            try:
                found, in_store = finder()
                orphans |= found
                stored_total += in_store
            except Exception:
                pass
        ids = _stored_ids(embedder)
        if ids is None:
            counted = False
            continue
        stored |= ids
        expected |= _scope_graph_ids(embedder, graph_ids)
    if orphans:
        # Past half the store the build's safety valve keeps orphans, so a
        # plain build can't clear them: say --prune.
        prune = " --prune" if stored_total and len(orphans) > 0.5 * stored_total else ""
        return Check(
            "Semantic index",
            FAIL,
            f"{len(orphans):,} vectors not in graph (stale results possible); "
            f"{total:,} stored, graph has {len(graph_ids):,} nodes ({backend} backend)",
            fix=f"Rebuild to purge them: neuralmind build {project}{prune}",
        )
    missing = len(expected - stored) if counted else 0
    if missing:
        return Check(
            "Semantic index",
            WARN,
            f"{missing:,} graph nodes not yet embedded; {total:,} stored, graph has "
            f"{len(graph_ids):,} nodes ({backend} backend)",
            fix=f"Embed them: neuralmind build {project}",
        )
    return Check(
        "Semantic index",
        OK,
        f"{total:,} nodes embedded, matching the graph's {len(graph_ids):,} ({backend} backend)",
    )


def _stored_ids(embedder) -> set[str] | None:
    """Node ids with a stored vector in this embedder's store, or None if unknown."""
    conn = getattr(embedder, "_conn", None)
    try:
        if conn is not None:
            return {str(r[0]) for r in conn.execute("SELECT node_id FROM nodes").fetchall()}
        return set(embedder.collection.get(include=[]).get("ids") or [])
    except Exception:
        return None


def _scope_graph_ids(embedder, graph_ids: set[str]) -> set[str]:
    """The graph node ids this store is meant to hold (its scope's slice)."""
    in_scope = getattr(embedder, "_node_matches_scope", None)
    if not callable(in_scope) or getattr(embedder, "_scope", "all") == "all":
        return set(graph_ids)
    out: set[str] = set()
    for node in getattr(embedder, "nodes", None) or []:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id", node.get("label", "")))
        if node_id in graph_ids and in_scope(node):
            out.add(node_id)
    return out


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
        from neuralmind.memory import memory_off_reasons_and_steps

        reasons, steps = memory_off_reasons_and_steps()
    except Exception as e:
        return Check("Query memory", WARN, f"could not check ({e})")
    if not reasons:
        return Check("Query memory", OK, "enabled (logging queries for learning)")
    # NEURALMIND_MEMORY defaults to on, so "set it to 1" (the old advice)
    # never helped: name what is actually off and what turns it on.
    return Check(
        "Query memory",
        WARN,
        f"disabled ({'; '.join(reasons)})",
        fix=f"To enable, {' and '.join(steps)}.",
    )


def _check_doc_code_alignment(project: Path) -> Check:
    """Warn when code-doc mtime desync suggests stale documentation.

    Heuristic: for each document/header node in graph.json, if the doc file
    is newer than the directory's newest code file, flag it as potentially
    stale. Fail-open: never FAIL — this is advisory.
    """
    graph_path = graph_json_path(project)
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
    """Check if the turbovec index is compatible with the installed version.

    Only a project whose backend resolves to turbovec has a turbovec index.
    On any other backend the check reports itself not applicable without
    constructing TurboVecEmbedder, which would create an empty store and
    then report an index that doesn't exist as compatible.
    """
    try:
        from neuralmind.backend_manager import (
            SUPPORTED_BACKENDS,
            TURBOVEC_BACKENDS,
            project_backend,
        )

        backend_name = project_backend(project)
    except Exception as e:
        return Check("Turbovec compatibility", WARN, f"could not resolve backend ({e})")
    if backend_name not in SUPPORTED_BACKENDS:
        return Check(
            "Turbovec compatibility",
            WARN,
            f"could not resolve backend (unsupported backend: {backend_name})",
        )
    if backend_name not in TURBOVEC_BACKENDS:
        return Check(
            "Turbovec compatibility",
            OK,
            f"not applicable: the {backend_name} backend keeps no turbovec index",
        )
    try:
        from neuralmind.turbovec_backend import TurboVecEmbedder

        backend = TurboVecEmbedder(str(project))
        index_path = backend._index_path
        stale_path = index_path.with_name(index_path.name + ".stale")
        if stale_path.exists():
            # A .stale file is a past quarantine, not necessarily a current
            # fault: `build` (or the next search) rebuilds the index and leaves
            # the backup behind. So try the live index, with turbovec's own
            # load, never _load_index(), which renames and rebuilds files.
            # doctor stays read-only.
            if _index_loads(index_path):
                return Check(
                    "Turbovec compatibility",
                    OK,
                    f"Index loads (a backup from a repaired version mismatch is "
                    f"still at {stale_path.name}; delete it once you no longer need it)",
                )
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


def _index_loads(index_path: Path) -> bool:
    """Whether the installed turbovec can load the index file, read-only."""
    if not index_path.exists():
        return False
    try:
        import turbovec

        turbovec.IdMapIndex.load(str(index_path))
    except Exception:
        return False
    return True


def _check_security_policy(project: Path) -> Check:
    """The ``security:`` settings that decide what NeuralMind refuses."""
    import stat
    import sys

    from neuralmind.backend_manager import backend_config_path, read_backend_config_file
    from neuralmind.identity import os_identity
    from neuralmind.mcp_security import role_policy_problem
    from neuralmind.security_config import (
        IDENTITY_INVALID,
        IDENTITY_OS,
        load_security_settings,
    )

    name = "Security policy"
    path = backend_config_path(project)
    if path is not None:
        try:
            read_backend_config_file(path)
        except Exception as e:
            return Check(
                name,
                FAIL,
                f"{path.name} does not parse ({e}); its settings are ignored, or refused if it names a security setting",
                fix=f"Fix the syntax in {path.name}.",
            )
    policy_problem = role_policy_problem(project)
    if policy_problem:
        return Check(
            name,
            FAIL,
            f"MCP calls are refused: {policy_problem}",
            fix="Fix or remove the security setting named above, then restart the MCP server.",
        )
    settings = load_security_settings(project)
    if settings.identity == IDENTITY_INVALID:
        return Check(
            name,
            FAIL,
            f"MCP calls are refused: {settings.problem}",
            fix="Correct the security: section.",
        )
    if settings.identity != IDENTITY_OS:
        return Check(
            name,
            OK,
            "identity: declared (MCP callers name their own actor and role)",
            fix="Set security.identity: os to take identity from the OS account instead.",
        )

    account = os_identity()
    if not account:
        return Check(
            name,
            FAIL,
            "identity: os, but this OS account can't be determined; MCP calls are refused",
        )
    role = settings.users.get(account, settings.default_role)
    if role is None:
        return Check(
            name,
            WARN,
            f"identity: os; account '{account}' has no role, so its MCP calls are refused",
            fix=f"Add '{account}' to security.users or set security.default_role.",
        )
    detail = f"identity: os; account '{account}' gets role '{role}'"
    if path is not None and sys.platform != "win32":
        mode = path.stat().st_mode
        if mode & stat.S_IWOTH:
            return Check(
                name,
                FAIL,
                f"{path.name} is writable by every user; MCP calls are refused",
                fix=f"chmod o-w {path.name}",
            )
        if mode & stat.S_IWGRP:
            return Check(
                name,
                WARN,
                f"{detail}, but {path.name} is group-writable, so anyone in the group can change roles",
                fix=f"chmod g-w {path.name}",
            )
    return Check(name, OK, detail)


def _check_storage_encryption(project: Path) -> Check:
    """Whether the project's volume is encrypted, and whether that's required."""
    from neuralmind.security_config import load_security_settings
    from neuralmind.storage_guard import check_storage

    name = "Storage encryption"
    required = load_security_settings(project).require_encrypted_storage
    status = check_storage(project)
    fips = {True: "; OS FIPS mode on", False: "; OS FIPS mode off", None: ""}[status.fips_mode]
    if status.encrypted is True:
        if required and status.fips_mode is False:
            return Check(
                name,
                WARN,
                f"{status.detail}{fips}",
                fix="CMMC needs FIPS-validated cryptography: enable the OS FIPS mode.",
            )
        return Check(name, OK, f"{status.detail}{fips}")
    if required:
        return Check(
            name,
            FAIL,
            f"required, and not verified: {status.detail}. NeuralMind refuses to run here",
            fix="Turn on FileVault, BitLocker, or LUKS for this volume.",
        )
    state = "not encrypted" if status.encrypted is False else "not verified"
    return Check(name, OK, f"{state} ({status.detail}); not required by this project")


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
        _check_security_policy(project),
        _check_storage_encryption(project),
    ]


def overall_status(checks: list[Check]) -> str:
    """The worst status across all checks (FAIL > WARN > OK)."""
    return max((c.status for c in checks), key=lambda s: _RANK.get(s, 0), default=OK)
