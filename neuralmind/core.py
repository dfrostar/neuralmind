"""
core.py — NeuralMind Core System
=================================

Main entry point for the NeuralMind adaptive knowledge system.
Orchestrates embedder and context selector for massive token reduction.

Usage:
    from neuralmind import NeuralMind

    # Initialize for a project
    mind = NeuralMind("/path/to/project")
    mind.build()  # Generate embeddings from graph.json

    # Wake-up context (~600 tokens)
    wakeup = mind.wakeup()
    print(wakeup.context)

    # Query context (~1500 tokens with relevant results)
    result = mind.query("How does authentication work?")
    print(result.context)
    print(f"Token reduction: {result.reduction_ratio:.1f}x")
"""

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import ir as ir_mod
from . import namespaces as ns_mod
from .audit import get_audit_trail
from .backend_manager import BackendManager
from .context_selector import ContextResult, ContextSelector
from .memory import is_memory_logging_enabled, log_query_event, log_wakeup_event
from .synapses import SynapseStore, default_db_path

DEFAULT_HYBRID_HIGHLIGHT_COUNT = 3

# Serializes recent-queries appends within this process. POSIX O_APPEND
# already makes single-line appends atomic, but Windows' CRT implements
# append mode as a separate seek-to-end + write, so two handles writing
# concurrently can interleave and lose lines.
_RECENT_QUERIES_APPEND_LOCK = threading.Lock()

try:
    import msvcrt  # Windows-only: cross-process advisory lock below.
except ImportError:  # pragma: no cover - POSIX
    msvcrt = None  # type: ignore[assignment]


def _lock_byte0(fd: int) -> bool:
    """Best-effort cross-process mutex on byte 0 of *fd* (Windows only).

    POSIX writers don't need it (O_APPEND is atomic) and use flock for
    compaction instead; on Windows both the appender and the compactor
    take this same region so a compaction's read-truncate-rewrite can't
    drop a concurrent process's append. Non-blocking with a short retry
    so a stuck holder can never stall a query.
    """
    if msvcrt is None:
        return False
    import time as _time

    for _ in range(50):  # ~50ms worst case
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            _time.sleep(0.001)
    return False


def _unlock_byte0(fd: int) -> None:
    if msvcrt is None:
        return
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    except OSError:
        pass


# Canonical IR artifacts (PRD 1), under <project>/.neuralmind/.
IR_FILENAME = "index_ir.json"
IR_META_FILENAME = "ir_meta.json"


def validate_project(project_path: str | Path, *, write: bool = False) -> dict:
    """Validate a project's canonical IR without standing up a vector backend.

    The IR is a static schema over ``graph.json`` (or a persisted IR), so this
    deliberately needs no embedding engine — that decoupling is the point of
    PRD 1. Reads the persisted IR when present (and ``write`` is False);
    otherwise adapts ``graph.json`` on the fly. With ``write=True`` it
    (re)materializes the IR to ``.neuralmind/`` (the in-place migration path
    for a legacy project that predates the IR).

    Returns a summary dict; on failure returns ``{"ok": False, "error": ...}``.
    """
    project_path = Path(project_path)
    # Resolve + contain artifact paths: validate is reachable from the daemon
    # with a request-supplied project, so the root is untrusted input.
    graph_path = ir_mod.project_artifact(project_path, "graphify-out", "graph.json")
    ir_path = ir_mod.project_artifact(project_path, ".neuralmind", IR_FILENAME)
    ir_meta_path = ir_mod.project_artifact(project_path, ".neuralmind", IR_META_FILENAME)

    try:
        if ir_path.exists() and not write:
            index_ir = ir_mod.IndexIR.read(ir_path)
        elif graph_path.exists():
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            index_ir = ir_mod.from_graph_json(graph)
        else:
            return {
                "ok": False,
                "error": (
                    f"No index found for {project_path}. Run `neuralmind build` "
                    f"first (or `graphify update {project_path}` if you use "
                    f"the optional graphify backend)."
                ),
            }
    except ir_mod.IRError as exc:
        return {"ok": False, "error": str(exc)}

    # Fold in learned synapses (backend-free: the store is stdlib sqlite).
    index_ir.synapses = ir_mod.load_synapses_for_project(project_path)

    issues = ir_mod.validate_ir(index_ir)
    summary = index_ir.summary()
    summary["validation"] = ir_mod.validation_summary(issues)

    if write:
        ir_path.parent.mkdir(parents=True, exist_ok=True)
        index_ir.write(ir_path)
        ir_meta_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        summary["written_to"] = str(ir_path)

    return summary


class GraphNotBuiltError(RuntimeError):
    """Raised when a query is attempted before the code graph/index exists.

    Carries an actionable, multi-line message naming the exact commands to
    run, so the failure reads as a setup hint instead of an opaque
    ``AttributeError`` from a half-initialised instance.
    """


class NeuralMind:
    """
    Adaptive Neural Knowledge System.

    Replaces static Obsidian wiki with intelligent, query-aware context.
    Achieves 6-49x token reduction through progressive disclosure.
    """

    MAX_HYBRID_HIGHLIGHT_RESULTS = 3

    # Canonical IR artifacts (PRD 1). The IR is materialized from graph.json at
    # build time and validated; the embedder still reads graph.json directly
    # (legacy default), so the IR is a hidden, parity-checked internal contract.
    IR_FILENAME = IR_FILENAME
    IR_META_FILENAME = IR_META_FILENAME

    def __init__(
        self,
        project_path: str,
        db_path: str = None,
        enable_reranking: bool = True,
        backend_type: str | None = None,
        hybrid_context: bool | None = None,
        enable_synapses: bool = True,
        memory_namespace: str | None = None,
    ):
        """
        Initialize NeuralMind for a project.

        Args:
            project_path: Path to project root (where graphify-out/ lives)
            db_path: Optional custom path for ChromaDB storage
            enable_reranking: Deprecated and ignored. The learned_patterns
                reranker was removed; the synapse layer supersedes it. Kept in
                the signature for backward compatibility (callers passing it
                won't break), but it no longer has any effect.
            enable_synapses: If True, run the associative synapse layer that
                learns co-activation patterns across queries and tool calls.
            memory_namespace: Explicit synapse-memory namespace (PRD 4). When
                None, resolved from NEURALMIND_NAMESPACE / the backend config's
                ``memory_namespace`` / the current git branch / ``personal``.
        """
        self.project_path = Path(project_path)
        self.db_path = db_path
        # Deprecated and ignored (see __init__ docstring): retained only so the
        # attribute keeps existing for any code that reads it. The reranker it
        # used to gate has been removed; the synapse layer supersedes it.
        self.enable_reranking = enable_reranking
        self.backend_manager = BackendManager(
            project_path=str(self.project_path), db_path=db_path, backend=backend_type
        )
        self.hybrid_context = (
            bool(self.backend_manager.config.get("hybrid_context", False))
            if hybrid_context is None
            else hybrid_context
        )
        self.audit = get_audit_trail(self.project_path)

        # Initialize components
        self.embedder = self.backend_manager.backend
        self.selector: ContextSelector | None = None

        # State tracking
        self._built = False
        self._build_stats: dict = {}

        # Associative synapse layer (lazy: only created when first used)
        self.enable_synapses = enable_synapses
        self._synapses: SynapseStore | None = None
        self._synapses_lock = threading.Lock()
        self._memory_namespace_override = memory_namespace
        self._memory_namespace: str | None = None
        self._head_fingerprint: str | None = None

    @property
    def backend_name(self) -> str:
        return self.backend_manager.backend_name

    def close(self) -> None:
        """Release backend resources (vector-store file handles).

        Windows can't delete files a process still holds open, so
        anything that removes the project directory afterwards — test
        teardown, ``neuralmind reset`` — needs this. Safe to call more
        than once; the synapse store opens its sqlite database per
        operation and holds nothing between calls.
        """
        embedder = getattr(self, "embedder", None)
        if embedder is not None and hasattr(embedder, "close"):
            try:
                embedder.close()
            except Exception:
                pass

    @property
    def memory_namespace(self) -> str:
        """The active synapse-memory namespace for this project (PRD 4).

        Resolution order: explicit constructor override →
        ``NEURALMIND_NAMESPACE`` → the backend config's ``memory_namespace``
        → ``branch:<name>`` on a non-default git branch → ``personal``.

        Long-lived processes (the daemon's warm registry, the MCP server's
        mind cache) keep one NeuralMind per project across ``git checkout``s,
        so the resolved value can't be cached forever — that would keep
        writing a switched-away branch's memory. Instead the cache is keyed
        on a ``.git/HEAD`` fingerprint (a microsecond file read, no
        subprocess): the namespace re-resolves only when the checkout
        actually changes.
        """
        if self._memory_namespace_override:
            return self._memory_namespace_override
        fingerprint = ns_mod.head_fingerprint(self.project_path)
        if self._memory_namespace is None or fingerprint != self._head_fingerprint:
            self._memory_namespace = ns_mod.resolve_namespace(
                self.project_path, config=self.backend_manager.config
            )
            self._head_fingerprint = fingerprint
        return self._memory_namespace

    @property
    def synapses(self) -> SynapseStore | None:
        """Return the associative synapse store, creating it on first use.

        Returns None when synapses are disabled. The store lives at
        ``<project>/.neuralmind/synapses.db`` so it persists across
        sessions and can be inspected or reset independently. Writes land
        in :attr:`memory_namespace`; reads default to the merged view
        documented in :mod:`neuralmind.synapses`. When a branch switch
        changes the active namespace, the store is reopened on that
        namespace so a warm daemon/MCP process keeps branch isolation
        without a restart.
        """
        if not self.enable_synapses:
            return None
        namespace = self.memory_namespace
        store = self._synapses
        if store is None or getattr(store, "namespace", namespace) != namespace:
            with self._synapses_lock:
                store = self._synapses
                if store is None or getattr(store, "namespace", namespace) != namespace:
                    store = SynapseStore(default_db_path(self.project_path), namespace=namespace)
                    self._synapses = store
        return store

    def activate(self, node_ids: list[str], strength: float = 1.0) -> int:
        """Feed an activation signal into the synapse layer.

        Hooks (UserPromptSubmit, PostToolUse) and the file watcher call
        this with the nodes that fired together so the synapse store can
        reinforce their pairwise edges. Returns the number of pairs touched,
        or 0 when synapses are disabled.
        """
        store = self.synapses
        if store is None or not node_ids:
            return 0
        try:
            return store.reinforce(node_ids, strength=strength)
        except Exception:
            return 0

    def activate_files(self, file_paths: list[str], strength: float = 1.0) -> int:
        """Resolve file paths to graph node ids and feed them as one batch.

        Used by the file watcher: when a cluster of files is edited together,
        we treat them as having co-fired and let the synapse store strengthen
        the edges between every node living in those files.

        Two parallel updates run from one call:

        - Undirected co-activation across every node inside the touched
          files (the existing Hebbian signal).
        - Directional file-level transitions (``A -> B``) for each
          consecutive pair in ``file_paths``, so callers can ask
          ``next_likely(file)`` for what typically follows. *(v0.11.0+)*
        """
        if not file_paths:
            return 0
        self._ensure_built()

        store = self.synapses
        if store is not None and len(file_paths) >= 2:
            try:
                store.record_sequence(file_paths, strength=strength)
            except Exception:
                pass

        node_ids: list[str] = []
        for path in file_paths:
            try:
                for node in self.embedder.get_file_nodes(path):
                    nid = node.get("id")
                    if nid:
                        node_ids.append(str(nid))
            except Exception:
                continue
        if len(node_ids) < 2:
            return 0
        return self.activate(node_ids, strength=strength)

    def _emit_audit(
        self,
        category: str,
        action: str,
        status: str = "success",
        target: str = "",
        details: dict | None = None,
    ) -> None:
        try:
            self.audit.append_event(
                category=category,
                action=action,
                actor="neuralmind",
                status=status,
                target=target,
                details=details or {},
            )
        except Exception:
            # Audit logging must never block primary query/build/search flows.
            pass

    def _tuned_l2_recall_k(self) -> int | None:
        """The selector's persisted L2 recall depth, or None when autotuning off.

        Read-only and gated on NEURALMIND_SELECTOR_AUTOTUNE=1: the hot query
        path must do no extra I/O by default, so we read the synapse meta key
        only when the operator has opted into the self-improvement engine.
        Returns None — meaning "keep the selector default" — when autotune is
        off, synapses are disabled, or anything goes wrong (fail-open). The
        tuner clamps before persisting and the selector clamps on read, so a
        garbage meta value can never widen recall out of bounds.
        """
        if os.environ.get("NEURALMIND_SELECTOR_AUTOTUNE") != "1":
            return None
        store = self.synapses
        if store is None:
            return None
        try:
            from .self_improve import META_KEY

            raw = store.get_meta(META_KEY)
            return int(raw) if raw is not None else None
        except Exception:
            return None

    def build(self, force: bool = False) -> dict:
        """
        Build or update the neural knowledge base.

        Loads graph.json, generates embeddings, and prepares for queries.

        Args:
            force: If True, regenerate all embeddings even if unchanged

        Returns:
            Build statistics including nodes processed and time taken
        """
        start_time = datetime.now()

        # Built-in backend: when there's no graphify output yet, generate a
        # graphify-compatible graph.json from a tree-sitter parse so that
        # `pip install neuralmind && neuralmind build` works with no separate
        # graphify install. A pre-existing graphify graph always takes priority.
        self._maybe_generate_builtin_graph(force=force)

        # Load graph
        if not self.embedder.load_graph():
            self._emit_audit(
                category="backend",
                action="build",
                status="failure",
                target=self.project_path.name,
                details={"backend": self.backend_manager.backend_name},
            )
            return {
                "success": False,
                "error": f"Could not load graph from {self.embedder.graph_path}",
                "duration_seconds": 0,
            }

        # One-time migration notice when the auto-default flipped this project
        # from chroma to turbovec (the reindex itself happens via embed_nodes).
        self._maybe_announce_turbovec_migration()

        # Team memory: inherit a committed team bundle once into `shared`, so a
        # fresh clone is seeded with the team's learned associations. This is the
        # build-path parallel of the SessionStart hook, so Cursor/Cline/generic
        # MCP agents (which don't run Claude Code hooks) inherit it too.
        self._maybe_inherit_team_memory()

        # Convert the loaded graph into the canonical, versioned IR before
        # indexing (PRD 1 FR1). Validated and written to .neuralmind/; the
        # embedder still reads graph.json, so this is a parity-checked internal
        # contract that never blocks a build.
        ir_summary = self._materialize_ir()

        # Embed nodes
        embed_stats = self.embedder.embed_nodes(force=force)

        # Initialize selector. When the selector auto-tuner is enabled
        # (NEURALMIND_SELECTOR_AUTOTUNE=1), read its persisted L2 recall depth
        # from the synapse meta table once, here, and thread it through to the
        # selector — never per get_query_context call, since the value changes
        # at most once per session (the SessionStart tuner tick). Default-off:
        # with the flag unset we don't touch the store and the selector keeps
        # its hard-coded default, so behavior is byte-identical.
        self.selector = ContextSelector(
            self.embedder,
            str(self.project_path),
            l2_recall_k=self._tuned_l2_recall_k(),
        )
        # Let L3 retrieval consult the live synapse graph (seed-based spread,
        # no extra embedder round trip — the seeds are hits already fetched).
        self.selector.synapse_recall = self._recall_for_selection
        # Traced queries use the detailed variant so the PRD 3 trace can show
        # which memory namespace drove each boost (PRD 4).
        self.selector.synapse_recall_detailed = self._recall_for_selection_detailed

        # Get final stats
        final_stats = self.embedder.get_stats()

        duration = (datetime.now() - start_time).total_seconds()

        self._build_stats = {
            "success": True,
            "project": self.project_path.name,
            "backend": self.backend_manager.backend_name,
            "nodes_total": final_stats.get("total_nodes", 0),
            "communities": final_stats.get("communities", 0),
            "nodes_added": embed_stats.get("added", 0),
            "nodes_updated": embed_stats.get("updated", 0),
            "nodes_skipped": embed_stats.get("skipped", 0),
            "db_path": final_stats.get("db_path", ""),
            "duration_seconds": round(duration, 2),
            "built_at": datetime.now().isoformat(),
        }
        if ir_summary is not None:
            self._build_stats["ir"] = ir_summary

        self._built = True
        self._emit_audit(
            category="backend",
            action="build",
            status="success",
            target=self.project_path.name,
            details={
                "backend": self.backend_manager.backend_name,
                "nodes_total": self._build_stats.get("nodes_total", 0),
            },
        )
        return self._build_stats

    # ----------------------------------------------------------------- #
    # Canonical IR (PRD 1)
    # ----------------------------------------------------------------- #
    @property
    def ir_path(self) -> Path:
        return ir_mod.project_artifact(self.project_path, ".neuralmind", self.IR_FILENAME)

    @property
    def ir_meta_path(self) -> Path:
        return ir_mod.project_artifact(self.project_path, ".neuralmind", self.IR_META_FILENAME)

    def _materialize_ir(self) -> dict | None:
        """Adapt the loaded graph into the canonical IR, validate, and persist.

        Returns a compact summary (IR metadata + validation result) for the
        build stats, or ``None`` if no graph was loaded. Never raises — IR
        materialization is observability, not a gate on the build. Validation
        *errors* are recorded in the metadata so ``stats``/``validate`` can
        surface them without failing an otherwise-working index.
        """
        graph = getattr(self.embedder, "graph", None)
        if not graph:
            return None
        try:
            index_ir = ir_mod.from_graph_json(
                graph, source_backend=self.backend_manager.backend_name
            )
            # Fold the learned synapse layer into the IR as canonical entities.
            if self.enable_synapses and self._synapses is not None:
                try:
                    index_ir.synapses = ir_mod.synapses_from_edges(
                        self._synapses.edges(min_weight=0.0, limit=5000)
                    )
                except Exception:  # pragma: no cover - synapses are optional
                    pass
            issues = ir_mod.validate_ir(index_ir)
            summary = index_ir.summary()
            summary["validation"] = ir_mod.validation_summary(issues)

            self.ir_path.parent.mkdir(parents=True, exist_ok=True)
            index_ir.write(self.ir_path)
            self.ir_meta_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
            return summary
        except Exception as exc:  # pragma: no cover - defensive; never block build
            return {"error": f"IR materialization failed: {exc}"}

    def load_ir(self) -> "ir_mod.IndexIR | None":
        """Load the persisted canonical IR for this project, if present.

        Raises :class:`ir_mod.IRError` for an unsupported (too-new) IR version
        — the one case where reading is unsafe (FR4).
        """
        if not self.ir_path.exists():
            return None
        return ir_mod.IndexIR.read(self.ir_path)

    def validate(self, *, write: bool = False) -> dict:
        """Validate this project's canonical IR (UX: ``neuralmind validate``).

        Thin wrapper over :func:`validate_project` so the programmatic API and
        the CLI share one backend-free implementation.
        """
        return validate_project(self.project_path, write=write)

    def _maybe_inherit_team_memory(self) -> None:
        """Import the committed team-memory bundle once into ``shared`` (PRD:
        team-memory). Idempotent (content-hash), off-switch
        ``NEURALMIND_TEAM_MEMORY=0``, and fail-open — inheritance must never
        break a build."""
        if not self.enable_synapses:
            return
        try:
            from .team_memory import maybe_import_team_memory

            store = self.synapses
            if store is not None:
                summary = maybe_import_team_memory(self.project_path, store)
                if summary and summary.get("synapses"):
                    print(
                        f"[neuralmind] inherited team memory → +{summary['synapses']} shared "
                        f"synapses, +{summary['transitions']} transitions "
                        "(set NEURALMIND_TEAM_MEMORY=0 to disable)"
                    )
        except Exception:
            pass

    def _maybe_announce_turbovec_migration(self) -> None:
        """Print a one-time notice when a project that previously used the chroma
        backend is being auto-reindexed into turbovec.

        v0.22 flipped the default backend to ``auto`` (turbovec when its deps are
        installed). When that resolves to turbovec on a project that still has a
        legacy ChromaDB index and whose turbovec index hasn't been built yet, the
        normal ``build`` → ``embed_nodes`` path reindexes it from graph.json. This
        just surfaces that one-time cost so it isn't a silent surprise. The old
        ChromaDB index is left in place as a fallback (selectable via
        ``backend: graph``); nothing is deleted.
        """
        import sys

        if self.backend_manager.backend_name != "turbovec":
            return
        # A prior chroma index lives at the GraphEmbedder default db path.
        legacy_chroma = self.project_path / "graphify-out" / "neuralmind_db"
        if not legacy_chroma.exists():
            return  # fresh project, not a migration
        try:
            already_indexed = self.embedder.get_stats().get("total_nodes", 0)
        except Exception:
            already_indexed = 0
        if already_indexed:
            return  # turbovec index already populated — not the first run
        # Rough first-build estimate (~25 ms/node observed in the v0.21 benchmark).
        # The node list lives on the embedder (populated by load_graph, called
        # just above in build()); NeuralMind itself has no self.nodes.
        n = len(getattr(self.embedder, "nodes", None) or [])
        est = ""
        if n:
            secs = n * 0.025
            if secs >= 90:
                est = f" (~{round(secs / 60)} min to embed {n} nodes)"
            elif secs >= 5:
                est = f" (~{round(secs)}s to embed {n} nodes)"
        print(
            "[neuralmind] auto-selected the ChromaDB-free turbovec backend; "
            f"reindexing this project from graph.json (one-time{est}). Your existing "
            "ChromaDB index is left untouched — set `backend: graph` in "
            "neuralmind-backend.yaml to switch back.",
            file=sys.stderr,
        )

    def _maybe_generate_builtin_graph(self, force: bool = False) -> None:
        """Generate ``graphify-out/graph.json`` with the built-in tree-sitter
        backend when there's no graphify output to consume.

        A graphify-produced graph always wins: we only generate when none
        exists, or — on ``force`` — when the existing graph is one *we* wrote
        (never clobber a real graphify build). Silently no-ops when tree-sitter
        isn't importable, leaving the existing "no graph" path to advise the user.
        """
        import sys

        graph_path = self.project_path / "graphify-out" / "graph.json"
        if graph_path.exists():
            if not force:
                return
            try:
                existing = json.loads(graph_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                existing = {}
            if "neuralmind.graphgen" not in str(existing.get("generated_by", "")):
                return  # force-rebuild must not overwrite a graphify graph

        from . import graphgen

        if not graphgen.is_available():
            return
        try:
            graph = graphgen.build_graph(self.project_path)
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[neuralmind] built-in graph backend failed: {exc}", file=sys.stderr)
            return

        # Only materialize a graph when there's real code to index. An empty or
        # non-Python project must keep falling through to the existing "no
        # graph" guidance rather than producing a 0-node index that silently
        # "succeeds".
        if not any(n.get("file_type") == "code" for n in graph.get("nodes", [])):
            return

        # Optional SCIP precision pass: when NEURALMIND_PRECISION is set and a
        # *.scip index is present, replace the heuristic calls/inherits edges
        # with compiler-accurate ones. Off by default — a no-op otherwise, so
        # the generated graph is byte-for-byte unchanged.
        from . import precision

        graph, pstats = precision.maybe_refine(self.project_path, graph)
        if pstats is not None:
            print(
                "[neuralmind] SCIP precision pass: "
                f"+{pstats.calls_added} calls, +{pstats.inherits_added} inherits "
                f"(replaced {pstats.heuristic_calls_removed} heuristic calls, "
                f"{pstats.heuristic_inherits_removed} inherits across "
                f"{pstats.documents} document(s))"
            )

        out_dir = self.project_path / "graphify-out"
        out_dir.mkdir(parents=True, exist_ok=True)
        graph_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")
        print(
            "[neuralmind] generated code graph via the built-in tree-sitter "
            f"backend → {graph_path}"
        )

    def update_files(self, paths) -> dict:
        """Incrementally re-index only the given changed files (built-in graph).

        Re-parses just those files into the existing ``graph.json`` (unchanged
        files keep their nodes + community ids byte-for-byte), prunes embeddings
        for removed symbols, and re-embeds — which, thanks to the embedder's
        content hashing, only touches the edited file's nodes. A fast path for
        the watcher: editing one file costs ~one file's parse + embed, not a
        whole-repo rebuild.

        Only the built-in tree-sitter graph is updated in place; a graphify
        graph is left to graphify. Returns a stats dict.
        """
        graph_path = self.project_path / "graphify-out" / "graph.json"
        if not graph_path.exists():
            return {"success": False, "error": "no graph to update; run build first"}
        try:
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return {"success": False, "error": f"could not read graph: {exc}"}
        if "neuralmind.graphgen" not in str(graph.get("generated_by", "")):
            return {
                "success": False,
                "error": "incremental update only applies to the built-in backend",
            }

        from . import graphgen

        if not graphgen.is_available():
            return {"success": False, "error": "tree-sitter not available"}

        root = self.project_path.resolve()
        indexable = graphgen.SUPPORTED_SUFFIXES | graphgen._DOC_SUFFIXES
        changed: list[str] = []
        removed: list[str] = []
        for p in paths:
            ap = Path(p)
            if not ap.is_absolute():
                ap = self.project_path / p
            try:
                rel = ap.resolve().relative_to(root).as_posix()
            except ValueError:
                continue
            if ap.suffix not in indexable:
                continue
            (changed if ap.exists() else removed).append(rel)

        if not changed and not removed:
            return {"success": True, "files_reparsed": 0, "reason": "no indexable files"}

        old_ids = {n["id"] for n in graph.get("nodes", [])}
        graph, stats = graphgen.update_files(self.project_path, graph, changed, removed)

        # Keep precise edges if the precision pass is enabled and an index exists.
        from . import precision

        graph, _ = precision.maybe_refine(self.project_path, graph)

        graph_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")

        new_ids = {n["id"] for n in graph.get("nodes", [])}
        pruned = self.embedder.delete_nodes(old_ids - new_ids)

        # Reload the graph into the embedder and re-embed (content-hash skips
        # the unchanged nodes, so only the edited file's nodes are touched).
        self.embedder.graph = {}
        self.embedder.nodes = []
        self.embedder.edges = []
        self.embedder.load_graph()
        embed_stats = self.embedder.embed_nodes(force=False)
        self._graph_stats_dirty()

        return {
            "success": True,
            "files_reparsed": stats.files_reparsed,
            "files_removed": stats.files_removed,
            "nodes_total": stats.nodes_after,
            "embedded": embed_stats.get("added", 0) + embed_stats.get("updated", 0),
            "skipped": embed_stats.get("skipped", 0),
            "pruned": pruned,
        }

    def _graph_stats_dirty(self) -> None:
        """Invalidate the selector's cached graph stats after an incremental
        update so L0/L1 reflect the new node/community counts."""
        if self.selector is not None:
            self.selector._graph_stats = None
            self.selector._l0_cache = None
            self.selector._l1_cache = None

    def _ensure_built(self):
        """Ensure the system is built before queries.

        Raises GraphNotBuiltError with an actionable message when the build
        can't produce a usable selector — almost always a missing code
        graph on a fresh project.
        """
        if not self._built or self.selector is None:
            result = self.build()
            if self.selector is None:
                graph_path = self.project_path / "graphify-out" / "graph.json"
                if not graph_path.exists():
                    raise GraphNotBuiltError(
                        f"No code graph found at {graph_path}.\n"
                        f"NeuralMind builds one automatically with its bundled "
                        f"tree-sitter backend — install the parser if it's missing:\n"
                        f"  pip install tree-sitter tree-sitter-python\n"
                        f"  neuralmind build {self.project_path}\n"
                        f"(Or generate it with graphify: `graphify update {self.project_path}`.)"
                    )
                raise GraphNotBuiltError(
                    result.get("error", "Failed to build the NeuralMind index.")
                    if isinstance(result, dict)
                    else "Failed to build the NeuralMind index."
                )

    def wakeup(self) -> ContextResult:
        """
        Get minimal wake-up context for starting a conversation.

        Returns L0 (identity) + L1 (summary) = ~600 tokens.
        Use this when initializing a new chat about the project.

        Returns:
            ContextResult with essential project context
        """
        self._ensure_built()
        result = self.selector.get_wakeup_context()
        # Mirror the query-event log: a wakeup with no follow-up query in the
        # same session is the "L0/L1 was sufficient" signal the tuner reads.
        log_wakeup_event(self.project_path, result)
        self._emit_audit(
            category="audit",
            action="wakeup",
            status="success",
            target=self.project_path.name,
            details={"tokens": result.budget.total},
        )
        return result

    def query(
        self, question: str, trace: bool = False, trace_verbose: bool = False
    ) -> ContextResult:
        """
        Get optimized context for answering a question.

        Returns all relevant layers based on the query.
        Typically ~1000-1500 tokens with 30-50x reduction.

        Args:
            question: Natural language question about the codebase
            trace: If True, attach a per-layer retrieval trace (PRD 3) to
                ``result.trace`` for explainability/debugging.
            trace_verbose: If True (with trace), keep full candidate/hit lists.

        Returns:
            ContextResult with relevant context and token budget
        """
        self._ensure_built()
        result = self.selector.get_query_context(question, trace=trace, trace_verbose=trace_verbose)
        if self.hybrid_context:
            highlights = self._build_hybrid_highlights(question, result.top_search_hits)
            if highlights:
                result.context = f"{highlights}\n\n{result.context}"
        log_query_event(self.project_path, question, result)
        self._record_recent_query(question, result)
        self._reinforce_from_query(question, result)
        self._emit_audit(
            category="audit",
            action="query",
            status="success",
            target=self.project_path.name,
            details={
                "question": question,
                "tokens": result.budget.total,
                "search_hits": result.search_hits,
                "hybrid_context": self.hybrid_context,
            },
        )
        return result

    RECENT_QUERIES_FILENAME = "recent_queries.jsonl"
    RECENT_QUERIES_MAX = 100
    # Trim when the log grows past ~2× the cap so compaction is rare;
    # 4KB/line is a safe upper bound for an entry with 12 hits.
    RECENT_QUERIES_COMPACT_BYTES = RECENT_QUERIES_MAX * 4096 * 2

    def _recent_queries_path(self) -> Path:
        return self.project_path / ".neuralmind" / self.RECENT_QUERIES_FILENAME

    def _record_recent_query(self, question: str, result: ContextResult) -> None:
        """Append the last query's retrieval state to the recent-queries log.

        Powers the graph-view UI's 'Replay last query' panel: a human can
        see which nodes the agent actually received, including ids the
        UI can highlight on the canvas. Always on (local-only data,
        readable only through the auth-gated server).

        The hot path is a single-line O_APPEND write. On POSIX that is
        atomic across processes by itself (writes < PIPE_BUF don't
        tear); Windows' CRT implements append as seek-to-end + write,
        so writes are additionally serialized by a process-local lock
        and a best-effort cross-process byte-range lock. Trimming back
        to RECENT_QUERIES_MAX is a lazy compaction step gated by file
        size and protected by the same locks — see
        ``_compact_recent_queries``.

        Gated on the same consent flag as the learning log
        (`NEURALMIND_MEMORY`): if the user opted out of persisting
        query text, we don't create a parallel persistence path here.
        """
        if not is_memory_logging_enabled():
            return
        try:
            hits = []
            for hit in (getattr(result, "top_search_hits", []) or [])[:12]:
                meta = hit.get("metadata") or {}
                hits.append(
                    {
                        "id": str(hit.get("id", "")),
                        "label": meta.get("label", hit.get("id", "")),
                        "source_file": meta.get("source_file", ""),
                        "score": round(float(hit.get("score", 0.0)), 3),
                    }
                )
            record = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "question": question,
                "tokens": int(getattr(getattr(result, "budget", None), "total", 0)),
                "reduction_ratio": round(float(getattr(result, "reduction_ratio", 0.0)), 2),
                "layers_used": list(getattr(result, "layers_used", [])),
                "communities_loaded": list(getattr(result, "communities_loaded", [])),
                "top_hits": hits,
            }
            log_path = self._recent_queries_path()
            log_path.parent.mkdir(parents=True, exist_ok=True)
            encoded = (json.dumps(record, sort_keys=True) + "\n").encode("utf-8")
            with _RECENT_QUERIES_APPEND_LOCK:
                fd = os.open(str(log_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
                locked = False
                try:
                    locked = _lock_byte0(fd)
                    os.write(fd, encoded)
                finally:
                    if locked:
                        _unlock_byte0(fd)
                    os.close(fd)
        except Exception:
            # Recording must never block the actual query.
            return
        try:
            self._compact_recent_queries(log_path)
        except Exception:
            pass

    def _compact_recent_queries(self, log_path: Path) -> None:
        """Trim the recent-queries log back to RECENT_QUERIES_MAX entries.

        Only runs when the file has grown past the size threshold, so the
        hot path stays append-only. The read-truncate-rewrite is guarded
        against another process's append by flock on POSIX and by the
        byte-0 region lock shared with ``_record_recent_query`` on
        Windows; both are best-effort — worst case is a slightly
        oversized log file (no data loss).
        """
        try:
            size = log_path.stat().st_size
        except OSError:
            return
        if size <= self.RECENT_QUERIES_COMPACT_BYTES:
            return
        try:
            import fcntl
        except ImportError:
            fcntl = None  # type: ignore[assignment]
        with _RECENT_QUERIES_APPEND_LOCK, log_path.open("r+", encoding="utf-8") as f:
            if fcntl is not None:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                except OSError:
                    pass
            locked = _lock_byte0(f.fileno())
            try:
                lines = [ln for ln in f if ln.strip()]
                if len(lines) <= self.RECENT_QUERIES_MAX:
                    return
                f.seek(0)
                f.truncate()
                f.writelines(lines[-self.RECENT_QUERIES_MAX :])
                f.flush()
            finally:
                if locked:
                    _unlock_byte0(f.fileno())
                if fcntl is not None:
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass

    def recent_queries(self, n: int = 20) -> list[dict]:
        """Return the N most-recent recorded queries, newest first."""
        log_path = self._recent_queries_path()
        if not log_path.exists():
            return []
        try:
            with log_path.open(encoding="utf-8") as f:
                lines = [line for line in f if line.strip()]
        except OSError:
            return []
        out: list[dict] = []
        for line in lines[-max(1, n) :]:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        out.reverse()
        return out

    def _reinforce_from_query(self, question: str, result: ContextResult) -> None:
        """Hebbian update: nodes co-activated by a query wire together.

        Reuses the search hits the selector already fetched for L2/L3 so
        we don't pay for a third round trip to the embedder. Falls back
        to a fresh search only if the result didn't surface any hits
        (e.g. an L0/L1-only call).
        """
        store = self.synapses
        if store is None:
            return
        hits = result.top_search_hits
        if not hits:
            try:
                hits = self.embedder.search(question, n=6)
            except Exception:
                return
        node_ids: list[str] = []
        for hit in hits[:6]:
            nid = hit.get("id")
            if nid:
                node_ids.append(str(nid))
        for comm_id in result.communities_loaded or []:
            node_ids.append(f"community_{comm_id}")
        if len(node_ids) >= 2:
            try:
                store.reinforce(node_ids)
            except Exception:
                pass

    def _build_hybrid_highlights(self, question: str, cached_hits: list[dict] | None = None) -> str:
        if cached_hits:
            results = cached_hits[: self.MAX_HYBRID_HIGHLIGHT_RESULTS]
        else:
            results = self.embedder.search(question, n=self.MAX_HYBRID_HIGHLIGHT_RESULTS)
        if not results:
            return ""
        lines = ["## Hybrid Highlights"]
        for item in results:
            metadata = item.get("metadata", {})
            label = metadata.get("label", item.get("id", "unknown"))
            source = metadata.get("source_file", "")
            score = item.get("score", 0.0)
            source_suffix = f" ({source})" if source else ""
            lines.append(f"- {label}{source_suffix} — score {score:.2f}")
        return "\n".join(lines)

    def skeleton(self, file_path: str) -> str:
        """Return a compact skeleton view of a file using graph data.

        The skeleton contains:
        - File header (community, function count)
        - Function list with line numbers and one-line rationale from the graph
        - Internal call graph (within the file)
        - Cross-file relationships (shares_data_with, imports_from edges)
        - Pointer to bypass for full source

        Args:
            file_path: Path to the source file (absolute or project-relative)

        Returns:
            Formatted skeleton text, or empty string if file is not indexed
        """
        self._ensure_built()

        nodes = self.embedder.get_file_nodes(file_path)
        if not nodes:
            return ""

        node_ids = {n["id"] for n in nodes}
        edges = self.embedder.get_file_edges(file_path, node_ids=node_ids)

        # Partition nodes
        code_nodes = [n for n in nodes if n.get("file_type") == "code"]
        rationale_nodes = [n for n in nodes if n.get("file_type") == "rationale"]

        # Map code node id → rationale text (via rationale_for edges)
        # Edge shape: {relation: "rationale_for", _src: rationale_id, _tgt: code_id, ...}
        rationale_map: dict[str, str] = {}
        for e in edges:
            if e.get("relation") != "rationale_for":
                continue
            src = e.get("_src") or e.get("source")
            tgt = e.get("_tgt") or e.get("target")
            # Find the rationale node
            rationale_node = next(
                (rn for rn in rationale_nodes if rn["id"] in (src, tgt)),
                None,
            )
            code_node = next(
                (cn for cn in code_nodes if cn["id"] in (src, tgt)),
                None,
            )
            if rationale_node and code_node:
                label = rationale_node.get("label", "").strip()
                # Rationale labels are sometimes truncated docstrings; strip trailing ellipsis
                if label:
                    rationale_map[code_node["id"]] = label[:120]

        # Separate the file-level node (source_location "L1" or label matching filename)
        file_node = next(
            (
                n
                for n in code_nodes
                if n.get("source_location") == "L1"
                or n.get("label", "").endswith((".py", ".ts", ".js", ".go", ".rs"))
            ),
            None,
        )
        function_nodes = [n for n in code_nodes if n is not file_node]

        # Sort functions by line number
        def _line_no(node: dict) -> int:
            loc = node.get("source_location", "L0")
            try:
                return int(loc.lstrip("L"))
            except ValueError:
                return 0

        function_nodes.sort(key=_line_no)

        # Build call graph (within-file calls)
        calls_map: dict[str, list[str]] = {}
        for e in edges:
            if e.get("relation") != "calls":
                continue
            # Graph stores calls as target calls source (reversed semantics per exploration)
            src = e.get("_src") or e.get("source")
            tgt = e.get("_tgt") or e.get("target")
            if src in node_ids and tgt in node_ids:
                # Display direction: caller → callee
                # Per graphify convention, _src is caller, _tgt is callee
                caller_id = src
                callee_id = tgt
                callee_node = next((n for n in function_nodes if n["id"] == callee_id), None)
                caller_node = next((n for n in function_nodes if n["id"] == caller_id), None)
                if caller_node and callee_node:
                    calls_map.setdefault(caller_node.get("label", caller_id), []).append(
                        callee_node.get("label", callee_id)
                    )

        # Cross-file edges
        cross_edges = [
            e
            for e in edges
            if e.get("relation") in ("shares_data_with", "imports_from", "implements", "uses")
            and (
                (e.get("_src") in node_ids) != (e.get("_tgt") in node_ids)
            )  # exactly one endpoint inside
        ]

        # Format output
        lines: list[str] = []
        community = nodes[0].get("community", "?")
        lines.append(f"# {file_path}  (community {community}, {len(function_nodes)} functions)")
        lines.append("")
        lines.append("## Functions")

        # Compute padding for nice alignment
        max_label = max((len(n.get("label", "")) for n in function_nodes), default=12)
        for n in function_nodes:
            loc = n.get("source_location", "L?")
            label = n.get("label", "?")
            rat = rationale_map.get(n["id"])
            if rat:
                lines.append(f"{loc:<5} {label:<{max_label}}  — {rat}")
            else:
                lines.append(f"{loc:<5} {label}")

        if calls_map:
            lines.append("")
            lines.append("## Call graph (within this file)")
            for caller, callees in calls_map.items():
                unique = sorted(set(callees))
                lines.append(f"{caller} → {', '.join(unique)}")

        if cross_edges:
            lines.append("")
            lines.append("## Cross-file")
            seen_pairs: set[tuple[str, str, str]] = set()
            for e in cross_edges[:10]:  # cap to avoid bloat
                rel = e.get("relation", "?")
                src = e.get("_src") or e.get("source")
                tgt = e.get("_tgt") or e.get("target")
                conf = e.get("confidence", "")
                score = e.get("confidence_score", "")
                pair = (src, tgt, rel)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                # Name the out-of-file endpoint
                our_ids = node_ids
                inside_id = src if src in our_ids else tgt
                outside_id = tgt if src in our_ids else src
                inside_label = next(
                    (n.get("label", inside_id) for n in nodes if n["id"] == inside_id),
                    inside_id,
                )
                score_str = f" {score}" if score else ""
                lines.append(f"{inside_label} {rel} → {outside_id} ({conf}{score_str})")

        lines.append("")
        lines.append("[Full source available: Read this file with NEURALMIND_BYPASS=1]")

        return "\n".join(lines)

    def search(self, query: str, n: int = 10, **filters) -> list[dict]:
        """
        Direct semantic search without context formatting.

        Args:
            query: Search query
            n: Number of results
            **filters: Optional filters (file_type, community)

        Returns:
            List of matching nodes with scores
        """
        self._ensure_built()
        results = self.embedder.search(query, n=n, **filters)
        self._emit_audit(
            category="audit",
            action="search",
            status="success",
            target=self.project_path.name,
            details={"query": query, "results": len(results)},
        )
        return results

    def switch_backend(self, backend: str, db_path: str | None = None) -> dict:
        previous = self.backend_manager.backend_name
        self.embedder = self.backend_manager.switch_backend(backend, db_path=db_path)
        self.selector = None
        self._built = False
        self._emit_audit(
            category="backend",
            action="switch_backend",
            status="success",
            target=self.project_path.name,
            details={"from": previous, "to": backend},
        )
        result = self.build()
        result["backend_switched_from"] = previous
        result["backend"] = self.backend_manager.backend_name
        return result

    def get_stats(self) -> dict:
        """
        Get current system statistics.

        Returns:
            Dict with node counts, communities, and build info
        """
        if not self._built:
            return {"built": False, "project": self.project_path.name}

        embed_stats = self.embedder.get_stats()
        stats = {
            "built": True,
            "project": self.project_path.name,
            "nodes": embed_stats.get("total_nodes", 0),
            "communities": embed_stats.get("communities", 0),
            "db_path": embed_stats.get("db_path", ""),
            "build_stats": self._build_stats,
        }
        # Surface the canonical IR contract version + adapter metadata (PRD 1
        # UX). Read from the persisted meta so it's available even on a stats
        # call that didn't just build.
        ir_meta = self._build_stats.get("ir")
        if ir_meta is None and self.ir_meta_path.exists():
            try:
                ir_meta = json.loads(self.ir_meta_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                ir_meta = None
        if ir_meta is not None:
            stats["ir"] = ir_meta
        if self.enable_synapses:
            try:
                stats["synapses"] = self.synapses.stats() if self.synapses else None
            except Exception:
                stats["synapses"] = None
        return stats

    def graph_data(self, synapse_min_weight: float = 0.05, synapse_limit: int = 2000) -> dict:
        """Return the full code graph for the ``serve`` graph-view UI.

        Combines structural edges (calls/imports from graph.json) with the
        learned synapse overlay. Node ids are the embedder's graph ids so
        the overlay lines up with the structural nodes. Read-only — never
        mutates the index or the synapse store.
        """
        self._ensure_built()
        raw_nodes = list(getattr(self.embedder, "nodes", []) or [])
        raw_edges = list(getattr(self.embedder, "edges", []) or [])

        nodes = []
        for n in raw_nodes:
            nid = str(n.get("id", n.get("label", "")))
            if not nid:
                continue
            nodes.append(
                {
                    "id": nid,
                    "label": n.get("label", nid),
                    "file_type": n.get("file_type", "unknown"),
                    "source_file": n.get("source_file", ""),
                    "source_location": n.get("source_location", ""),
                    "community": int(n.get("community", -1)),
                }
            )
        node_ids = {n["id"] for n in nodes}

        edges = []
        for e in raw_edges:
            src = e.get("_src") or e.get("source")
            tgt = e.get("_tgt") or e.get("target")
            if src not in node_ids or tgt not in node_ids:
                continue
            edges.append(
                {
                    "source": src,
                    "target": tgt,
                    "relation": e.get("relation", "related"),
                }
            )

        synapses = []
        store = self.synapses
        if store is not None:
            try:
                for a, b, weight, count in store.edges(
                    min_weight=synapse_min_weight, limit=synapse_limit
                ):
                    # Synapse ids can include community_* pseudo-nodes that
                    # aren't real graph nodes — keep only edges we can draw.
                    if a in node_ids and b in node_ids:
                        synapses.append(
                            {
                                "source": a,
                                "target": b,
                                "weight": round(weight, 4),
                                "activation_count": count,
                            }
                        )
            except Exception:
                pass

        return {
            "project": self.project_path.name,
            # Full absolute path so the UI can key per-project state (e.g.
            # saved canvas layouts) without collisions between two repos
            # that happen to share a basename.
            "project_path": str(self.project_path.resolve()),
            "nodes": nodes,
            "edges": edges,
            "synapses": synapses,
            "stats": {
                "nodes": len(nodes),
                "edges": len(edges),
                "synapses": len(synapses),
            },
        }

    def _recall_for_selection(
        self, seed_ids: list[str], depth: int = 2, top_k: int = 8
    ) -> list[tuple[str, float]]:
        """Seed-based spreading activation for the context selector.

        Takes node ids the selector already fetched (so no second embedder
        round trip) and returns their learned synapse neighbors. Empty on a
        cold graph or when synapses are unavailable.
        """
        store = self.synapses
        if store is None or not seed_ids:
            return []
        try:
            return store.spread(seed_ids, depth=depth, top_k=top_k)
        except Exception:
            return []

    def _recall_for_selection_detailed(
        self, seed_ids: list[str], depth: int = 2, top_k: int = 8
    ) -> tuple[list[tuple[str, float]], dict[str, dict[str, float]]]:
        """Seed-based spread that also reports per-namespace attribution.

        Same contract as :meth:`_recall_for_selection` plus a contributions
        map (``{node_id: {namespace: energy}}``). Only invoked on traced
        queries, so the untraced hot path pays nothing for attribution.
        """
        store = self.synapses
        if store is None or not seed_ids:
            return [], {}
        try:
            return store.spread_with_contributions(seed_ids, depth=depth, top_k=top_k)
        except Exception:
            return [], {}

    def synaptic_neighbors(
        self, query: str, depth: int = 2, top_k: int = 10
    ) -> list[tuple[str, float]]:
        """Return nodes related to ``query`` via spreading activation.

        Uses the embedder to seed an activation pulse at the top semantic
        matches for the query, then propagates through the learned synapse
        graph. Empty list when synapses haven't accumulated any edges yet.
        """
        store = self.synapses
        if store is None:
            return []
        self._ensure_built()
        try:
            hits = self.embedder.search(query, n=4)
        except Exception:
            return []
        seeds = [(str(hit["id"]), float(hit.get("score", 1.0))) for hit in hits if hit.get("id")]
        if not seeds:
            return []
        return store.spread(seeds, depth=depth, top_k=top_k)

    def benchmark(self, sample_queries: list[str] = None) -> dict:
        """
        Run a benchmark to measure token reduction.

        Args:
            sample_queries: Optional list of queries to test.
                           If None, uses default queries.

        Returns:
            Benchmark results with average reduction ratio
        """
        self._ensure_built()

        if sample_queries is None:
            sample_queries = [
                "How does authentication work?",
                "What are the main API endpoints?",
                "How is the database structured?",
                "What frontend components exist?",
                "How are errors handled?",
            ]

        results = []

        # Wakeup benchmark
        wakeup = self.wakeup()
        results.append(
            {
                "type": "wakeup",
                "query": None,
                "tokens": wakeup.budget.total,
                "reduction": wakeup.reduction_ratio,
            }
        )

        # Query benchmarks
        for q in sample_queries:
            result = self.query(q)
            results.append(
                {
                    "type": "query",
                    "query": q,
                    "tokens": result.budget.total,
                    "reduction": result.reduction_ratio,
                    "layers": result.layers_used,
                }
            )

        # Calculate averages
        query_results = [r for r in results if r["type"] == "query"]
        avg_tokens = sum(r["tokens"] for r in query_results) / len(query_results)
        avg_reduction = sum(r["reduction"] for r in query_results) / len(query_results)

        return {
            "project": self.project_path.name,
            "wakeup_tokens": wakeup.budget.total,
            "avg_query_tokens": round(avg_tokens, 1),
            "avg_reduction_ratio": round(avg_reduction, 1),
            "estimated_full_codebase_tokens": 50000,
            "results": results,
            "summary": f"{avg_reduction:.1f}x average token reduction",
        }

    def retrieval_probe(
        self,
        sample_size: int = 50,
        k: int = 10,
        ks: tuple[int, ...] = (1, 3, 5),
        seed: int = 0,
    ):
        """Run a label-free retrieval self-probe on this project's own symbols.

        Token reduction proves NeuralMind is *cheap* and the golden-suite
        quality eval proves the ranking is *good* on a labeled fixture — but
        neither tells a user whether retrieval finds the right file on *their*
        codebase. This does: it samples indexed symbols, synthesizes a
        natural-language query from each symbol's identity (never its id), asks
        the index to retrieve it back, and scores whether the symbol's own
        source file surfaced in the top-``k`` (see :mod:`neuralmind.probe`).

        The pure logic lives in :mod:`neuralmind.probe`; here we just inject the
        embedder's ``search`` as the retrieval round trip. Returns a
        :class:`~neuralmind.probe.ProbeReport`.
        """
        from . import probe

        self._ensure_built()
        nodes = list(getattr(self.embedder, "nodes", []) or [])
        samples = probe.sample_nodes(nodes, sample_size, seed=seed)

        def retrieve(query: str) -> list[str]:
            try:
                hits = self.embedder.search(query, n=k)
            except Exception:
                return []
            return [str(h.get("metadata", {}).get("source_file", "")) for h in hits]

        report = probe.run_probe(samples, retrieve, ks=ks, k=k, index_size=len(nodes))
        self._emit_audit(
            category="audit",
            action="probe",
            status="success",
            target=self.project_path.name,
            details={
                "sample_size": report.sample_size,
                "mrr": round(report.suite.mrr, 4),
                "answerability": round(report.suite.answerability, 4),
                "blind_spots": report.blind_spot_total,
            },
        )
        return report

    def export_context(self, query: str = None, output_path: str = None) -> str:
        """
        Export context to a file for use with other tools.

        Args:
            query: Optional query for full context. If None, exports wakeup only.
            output_path: Optional output path. Defaults to project/neuralmind_context.md

        Returns:
            Path to exported file
        """
        self._ensure_built()

        if query:
            result = self.query(query)
            context_type = "query"
        else:
            result = self.wakeup()
            context_type = "wakeup"

        if output_path is None:
            output_path = str(self.project_path / "neuralmind_context.md")

        # Build export content
        lines = [
            "# NeuralMind Context Export",
            "",
            f"**Project:** {self.project_path.name}",
            f"**Type:** {context_type}",
            f"**Query:** {query or 'N/A'}",
            f"**Tokens:** {result.budget.total}",
            f"**Reduction:** {result.reduction_ratio:.1f}x",
            f"**Layers:** {', '.join(result.layers_used)}",
            f"**Generated:** {datetime.now().isoformat()}",
            "",
            "---",
            "",
            result.context,
        ]

        with open(output_path, "w") as f:
            f.write("\n".join(lines))

        return output_path


# Convenience function for quick usage
def create_mind(project_path: str, auto_build: bool = True) -> NeuralMind:
    """
    Create and optionally build a NeuralMind instance.

    Args:
        project_path: Path to project root
        auto_build: If True, automatically build embeddings

    Returns:
        Configured NeuralMind instance
    """
    mind = NeuralMind(project_path)
    if auto_build:
        mind.build()
    return mind
