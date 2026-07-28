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
from datetime import datetime
from pathlib import Path

from . import ir as ir_mod
from . import namespaces as ns_mod
from . import querying, synapse_feedback
from . import recent_queries as recent_queries_log
from .audit import get_audit_trail
from .backend_manager import BackendManager
from .context_selector import ContextResult, ContextSelector
from .memory import is_memory_logging_enabled, log_query_event, log_wakeup_event
from .structural import BLAST_VIEW_RELATION, StructuralIndex
from .synapses import SynapseStore, default_db_path

DEFAULT_HYBRID_HIGHLIGHT_COUNT = 3

# Canonical IR artifacts (PRD 1), under <project>/.neuralmind/.
IR_FILENAME = "index_ir.json"
IR_META_FILENAME = "ir_meta.json"


def _env_int(name: str, default: int) -> int:
    """Read an int from the environment, falling back on unset/malformed."""
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    """Read a float from the environment, falling back on unset/malformed."""
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


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

    # Strength of the reuse-feedback co-activation (Edit/Write hook). Kept
    # below the default reinforce strength of 1.0: the signal is heuristic
    # (identifier-token cross-reference, not static resolution), so we nudge
    # the synapse weight gently and let decay wash out false positives.
    REUSE_FEEDBACK_STRENGTH = 0.5

    def __init__(
        self,
        project_path: str,
        db_path: str = None,
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
            enable_synapses: If True, run the associative synapse layer that
                learns co-activation patterns across queries and tool calls.
            memory_namespace: Explicit synapse-memory namespace (PRD 4). When
                None, resolved from NEURALMIND_NAMESPACE / the backend config's
                ``memory_namespace`` / the current git branch / ``personal``.
        """
        self.project_path = Path(project_path)
        self.db_path = db_path
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

        # Structural edge index (calls/inherits/imports from graph.json). Built
        # from the loaded graph at build() time; None until then or when the
        # NEURALMIND_STRUCTURAL kill switch is set.
        self._structural_index: StructuralIndex | None = None

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
        """Co-activate every node in the touched files as one batch.

        See :func:`neuralmind.synapse_feedback.activate_files`.
        """
        return synapse_feedback.activate_files(self, file_paths, strength=strength)

    @classmethod
    def _symbol_name(cls, label: str) -> str:
        """Bare identifier for a graph label. See
        :func:`neuralmind.synapse_feedback.symbol_name`."""
        return synapse_feedback.symbol_name(label)

    def record_edit_activity(self, file_path: str, new_code: str) -> dict:
        """Learn from an Edit/Write reuse signal.

        See :func:`neuralmind.synapse_feedback.record_edit_activity`.
        """
        return synapse_feedback.record_edit_activity(self, file_path, new_code)

    def deactivate_files(self, file_paths: list[str]) -> int:
        """Accelerate synapse decay for nodes in deleted files.

        See :func:`neuralmind.synapse_feedback.deactivate_files`.
        """
        return synapse_feedback.deactivate_files(self, file_paths)

    def _emit_audit(
        self,
        category: str,
        action: str,
        status: str = "success",
        target: str = "",
        details: dict | None = None,
        actor: str | None = None,
        actor_role: str = "",
        ip_address: str = "",
    ) -> None:
        try:
            self.audit.append_event(
                category=category,
                action=action,
                actor=actor,
                status=status,
                target=target,
                details=details or {},
                actor_role=actor_role,
                ip_address=ip_address,
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
                "error": f"No index found (tried {self.embedder.ir_path} and {self.embedder.graph_path})",
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

        # Wave 3 C3 integration: run the population tuner if its schedule gate
        # fires (weekly by default). Runs after team memory so the incumbent
        # config is current. Gated on NEURALMIND_TUNER_ENABLED=1.
        self._maybe_run_tuner()

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

        # Structural edge index — precise, day-one code wiring (calls/inherits/
        # imports) from graph.json, built from the edges the embedder already
        # loaded. It powers the always-on structural query surface
        # (structural_neighbors / blast_radius / the CLI + MCP tools). Kill
        # switch: NEURALMIND_STRUCTURAL=0 skips it entirely.
        #
        # Folding structural neighbors into L3 retrieval is a *separate*,
        # opt-in switch (NEURALMIND_STRUCTURAL_RECALL=1). It interacts with the
        # tuned synapse reranker — on some graphs the structural signal is
        # strong enough to saturate top-k recall and crowd out the learned
        # signal — so default retrieval stays byte-identical and the synapse
        # layer's measured lift is preserved. The query tools carry the
        # headline value with zero retrieval risk.
        if os.environ.get("NEURALMIND_STRUCTURAL") != "0":
            self._structural_index = StructuralIndex(
                hub_degree=_env_int("NEURALMIND_STRUCTURAL_HUB_DEGREE", 50)
            )
            self._structural_index.build_from_edges(
                getattr(self.embedder, "edges", None) or [],
                min_confidence=_env_float("NEURALMIND_STRUCTURAL_MIN_CONFIDENCE", 0.0),
            )
            if os.environ.get("NEURALMIND_STRUCTURAL_RECALL") == "1":
                self.selector.structural_recall = self._structural_for_selection
        else:
            self._structural_index = None

        # Persist structural edges to the synapse store so they survive
        # rebuilds (the in-memory StructuralIndex is lost on process exit).
        # Fail-open: persistence is non-critical observability.
        # Access `self.synapses` (property) to lazy-init the store — `self._synapses`
        # is None until first accessed.
        _structural_edge_count = 0
        if self.enable_synapses:
            try:
                store = self.synapses
                if store is not None:
                    edges = getattr(self.embedder, "edges", None) or []
                    _structural_edge_count = store.persist_structural_edges(edges)
            except Exception:
                pass

        # Type verification pass — augment structural graph with type metadata.
        # Fail-open: type inference is observability, not a gate on the build.
        _type_risk_count = 0
        if self.enable_synapses:
            try:
                from . import type_verifier

                tv = type_verifier.TypeVerifier(self.project_path)
                graph = getattr(self.embedder, "graph", None)
                if graph:
                    tv.augment_graph(graph)
                    tv._last_graph = graph
                    store = self.synapses
                    if store is not None:
                        tv.persist_type_edges(store)
            except Exception:
                pass  # fail-open

        # Seed synapse weights from the structural graph so the learned
        # association layer starts with real architectural signal instead of
        # waiting weeks for co-activation to accumulate. Fail-open: seeding
        # is non-critical — a failure here must not break the build.
        _structural_synapse_count = 0
        if self.enable_synapses:
            try:
                store = self.synapses
                if store is not None:
                    _structural_synapse_count = store.seed_from_structural()
                    # Bootstrap bundle seeding if --bootstrap flag provided
                    bundle_path = getattr(self, "_bootstrap_bundle_path", None)
                    if bundle_path is not None:
                        store.seed_from_bundle(bundle_path)
            except Exception:
                pass

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
        if _structural_edge_count:
            self._build_stats["structural_edges"] = _structural_edge_count
        if _structural_synapse_count:
            self._build_stats["structural_synapses"] = _structural_synapse_count
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
        return ir_mod.project_artifact(self.project_path, ".neuralmind", IR_FILENAME)

    @property
    def ir_meta_path(self) -> Path:
        return ir_mod.project_artifact(self.project_path, ".neuralmind", IR_META_FILENAME)

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
            from neuralmind import __version__ as _nm_version  # lazy: avoids circular import

            summary["neuralmind_version"] = _nm_version

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

    def _maybe_run_tuner(self) -> None:
        """Run the population tuner if its schedule gate fires.

        Gated on ``NEURALMIND_TUNER_ENABLED=1``. Runs in the build hook so
        it gets exercised on ``neuralmind build`` and ``neuralmind watch``
        wake events. Fail-open: any tuner failure is logged and swallowed.
        """
        import os

        if os.environ.get("NEURALMIND_TUNER_ENABLED") != "1":
            return
        try:
            from .tuner import PopulationTuner

            tuner = PopulationTuner(project_path=self.project_path)
            if tuner.should_run():
                result = tuner.run_generation()
                if result is not None and result.promoted:
                    print(
                        f"[neuralmind] tuner promoted new config "
                        f"(fitness {result.best_fitness:.4f})"
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
            f"[neuralmind] generated code graph via the built-in tree-sitter backend → {graph_path}"
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
                ir_path = self.project_path / ".neuralmind" / "index_ir.json"
                graph_path = self.project_path / "graphify-out" / "graph.json"
                if not ir_path.exists() and not graph_path.exists():
                    raise GraphNotBuiltError(
                        f"No code graph found at {ir_path} or {graph_path}.\n"
                        f"NeuralMind builds one automatically with its bundled "
                        f"tree-sitter backend — install the parser if it's missing:\n"
                        f"  pip install tree-sitter tree-sitter-python\n"
                        f"  neuralmind build {self.project_path}\n"
                        f"(Or generate it with graphify: `graphify update {self.project_path}.`)"
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
        """Append the query's retrieval state to the replay log.

        Gated on the same consent flag as the learning log
        (`NEURALMIND_MEMORY`): if the user opted out of persisting
        query text, we don't create a parallel persistence path here.
        See :func:`neuralmind.recent_queries.append_query_record`.
        """
        if not is_memory_logging_enabled():
            return
        recent_queries_log.append_query_record(
            self._recent_queries_path(),
            question,
            result,
            max_entries=self.RECENT_QUERIES_MAX,
            compact_bytes=self.RECENT_QUERIES_COMPACT_BYTES,
        )

    def recent_queries(self, n: int = 20) -> list[dict]:
        """Return the N most-recent recorded queries, newest first."""
        return recent_queries_log.read_recent(self._recent_queries_path(), n)

    def _reinforce_from_query(self, question: str, result: ContextResult) -> None:
        """Hebbian update: nodes co-activated by a query wire together.

        See :func:`neuralmind.synapse_feedback.reinforce_from_query`.
        """
        synapse_feedback.reinforce_from_query(self, question, result)

    def _build_hybrid_highlights(self, question: str, cached_hits: list[dict] | None = None) -> str:
        return querying.build_hybrid_highlights(self, question, cached_hits)

    def skeleton(self, file_path: str) -> str:
        """Return a compact skeleton view of a file using graph data.

        See :func:`neuralmind.querying.skeleton`.
        """
        self._ensure_built()
        return querying.skeleton(self, file_path)

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

        See :func:`neuralmind.querying.graph_data`.
        """
        self._ensure_built()
        return querying.graph_data(
            self, synapse_min_weight=synapse_min_weight, synapse_limit=synapse_limit
        )

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

    # ----------------------------------------------------------------- #
    # Structural graph (calls / inherits / imports — precise, day-one)
    # ----------------------------------------------------------------- #

    def _ensure_structural_index(self) -> StructuralIndex | None:
        """Return the structural index, building it on demand if needed.

        ``build()`` wires it, but a caller may reach a structural method on a
        freshly loaded graph (e.g. the daemon serving one query). Rebuild from
        the embedder's loaded edges when absent, honoring the kill switch.
        """
        if os.environ.get("NEURALMIND_STRUCTURAL") == "0":
            return None
        if self._structural_index is None:
            edges = getattr(self.embedder, "edges", None)
            if not edges:
                # Graph may not be loaded yet on a lazy path.
                try:
                    self.embedder.load_graph()
                    edges = getattr(self.embedder, "edges", None)
                except Exception:
                    edges = None
            index = StructuralIndex(hub_degree=_env_int("NEURALMIND_STRUCTURAL_HUB_DEGREE", 50))
            index.build_from_edges(
                edges or [],
                min_confidence=_env_float("NEURALMIND_STRUCTURAL_MIN_CONFIDENCE", 0.0),
            )
            self._structural_index = index
        return self._structural_index

    def _structural_for_selection(self, seed_ids: list[str]) -> list[tuple[str, float]]:
        """Structural neighbors of already-fetched hits, for L3 expansion.

        Same contract as :meth:`_recall_for_selection` but sourced from the
        static structural graph (callers/callees/base classes) rather than the
        learned synapse graph. Empty when the index is cold or disabled.
        """
        index = self._structural_index
        if index is None or not seed_ids:
            return []
        try:
            return index.recall(seed_ids)
        except Exception:
            return []

    def _resolve_node_id(self, query_or_id: str, resolve: bool) -> str | None:
        """Turn a symbol name / NL query into a graph node id.

        With ``resolve=False`` the input is treated as a literal node id. With
        ``resolve=True`` (default for the CLI/MCP ergonomic path) the closest
        semantic hit is used, preferring an actual code node over a rationale/
        documentation node — structural questions are about code, and a
        rationale node carries no calls/inherits edges. Falls back to the raw
        top hit when only non-code nodes match.
        """
        if not resolve:
            return query_or_id
        try:
            hits = self.embedder.search(query_or_id, n=5)
        except Exception:
            return None
        if not hits:
            return None
        for hit in hits:
            file_type = (hit.get("metadata") or {}).get("file_type", "")
            node_id = hit.get("id", "")
            if file_type == "code" and node_id and not str(node_id).endswith("__rationale"):
                return str(node_id)
        return str(hits[0]["id"]) if hits[0].get("id") else None

    def structural_neighbors(
        self,
        query_or_id: str,
        relations: list[str] | None = None,
        resolve: bool = True,
    ) -> dict:
        """Return the typed structural neighborhood of a symbol.

        Answers "what calls / inherits / imports this?" from the static code
        graph. ``relations=None`` returns the default views (callers, callees,
        bases, subclasses, importers); pass raw relation names (``"calls"``,
        ``"inherits"``, ``"imports"``, or ``"all"``) to widen. Returns
        ``{"node_id": ..., "neighbors": {view: [ids]}}``; ``neighbors`` is
        empty for a leaf/unknown node or a disabled index.
        """
        self._ensure_built()
        index = self._ensure_structural_index()
        node_id = self._resolve_node_id(query_or_id, resolve)
        if index is None or node_id is None:
            return {"node_id": node_id, "neighbors": {}}
        return {"node_id": node_id, "neighbors": index.neighbors(node_id, relations)}

    def blast_radius(self, query_or_id: str, depth: int = 2, resolve: bool = True) -> dict:
        """Return the transitive reverse-dependency set of a symbol.

        Everything that (transitively) calls, imports, subclasses, or
        implements the symbol — the code a change to it could break. Depth
        bounds the number of hops. Returns ``{"node_id": ..., "depth": ...,
        "blast_radius": [ids]}``.
        """
        self._ensure_built()
        index = self._ensure_structural_index()
        node_id = self._resolve_node_id(query_or_id, resolve)
        if index is None or node_id is None:
            return {"node_id": node_id, "depth": depth, "blast_radius": []}
        return {
            "node_id": node_id,
            "depth": depth,
            "blast_radius": index.blast_radius(node_id, depth=depth),
        }

    def impact(self, symbol: str, depth: int = 1) -> dict:
        """Reverse-dependency ("blast radius") lookup, agent-friendly framing.

        A friendlier-named, richer-output entry point over the same
        structural index :meth:`blast_radius` uses — each dependent row
        carries which hop and which relation (``calls``/``inherits``/
        ``imports_from``/``implements``) connects it, not just its id.
        ``symbol`` may be an exact node id or a natural-language description;
        ``resolution`` in the response reports which happened (``"exact"``,
        ``"semantic"``, or ``"none"``).
        """
        self._ensure_built()
        index = self._ensure_structural_index()

        resolution = "none"
        node_id: str | None = None
        try:
            if self.embedder.get_nodes_by_ids([symbol]):
                node_id, resolution = symbol, "exact"
        except Exception:
            pass
        if node_id is None:
            resolved = self._resolve_node_id(symbol, resolve=True)
            if resolved is not None:
                node_id, resolution = resolved, "semantic"

        relations = sorted(set(BLAST_VIEW_RELATION.values()))
        if index is None or node_id is None:
            return {
                "symbol": symbol,
                "depth": depth,
                "relations": relations,
                "resolution": "none",
                "resolved_node": node_id,
                "dependents": [],
                "count": 0,
            }
        dependents = index.blast_radius_detail(node_id, depth=depth)
        return {
            "symbol": symbol,
            "depth": depth,
            "relations": relations,
            "resolution": resolution,
            "resolved_node": node_id,
            "dependents": dependents,
            "count": len(dependents),
        }

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
        neither tells a user whether retrieval finds the right code on *their*
        codebase. This does: it samples indexed symbols, queries each by its
        **rationale** (the docstring/intent text, which doesn't contain the
        symbol name — a real natural-language→code test rather than a
        string-match tautology; falls back to a humanized name), asks the index
        to retrieve it back, and scores whether the symbol's source file
        surfaced in the top-``k`` (see :mod:`neuralmind.probe`).

        The pure logic lives in :mod:`neuralmind.probe`; here we inject the
        embedder's ``search`` (filtered to code) as the retrieval round trip.
        Returns a :class:`~neuralmind.probe.ProbeReport`.
        """
        from . import probe

        # Validate up front: ``k < 1`` would score every symbol as a miss
        # (answerability always 0), and a negative ``sample_size`` would be
        # silently treated as "all" and trigger an accidental full-repo probe.
        if k < 1:
            raise ValueError(f"k must be >= 1 (got {k})")
        if sample_size < 0:
            raise ValueError(f"sample_size must be >= 0 (got {sample_size}; 0 means 'all')")

        self._ensure_built()
        nodes = list(getattr(self.embedder, "nodes", []) or [])
        edges = list(getattr(self.embedder, "edges", []) or [])
        # Query symbols by their docstring/intent (rationale) when available —
        # that text doesn't contain the symbol name, so it's a real NL→code
        # test, not a string-match tautology. Falls back to the humanized name.
        rationales = probe.extract_rationales(nodes, edges)
        # "Sampled X of Y indexed symbols" should count only what the probe can
        # actually draw from — code nodes — not rationale/document pseudo-nodes.
        code_node_count = sum(1 for n in nodes if n.get("file_type") == "code")
        # Retrieval is hard-filtered to code, so a project with no code nodes has
        # nothing answerable: sample nothing (n_queries == 0 → the CLI prints the
        # "no probeable symbols" guidance) rather than sampling non-code symbols
        # that could never be retrieved and scoring them all as blind spots.
        if code_node_count == 0:
            samples: list[dict] = []
        else:
            samples = probe.sample_nodes(nodes, sample_size, seed=seed, rationales=rationales)

        def retrieve(query: str) -> list[str]:
            # Ask the backend for code hits directly: a rationale-sourced query
            # can rank rationale/document nodes above its own code, so a fixed
            # over-fetch-then-filter window could miss the file even when a
            # code-only top-k would contain it. The built-in backends accept the
            # ``file_type`` keyword; a backend that only implements the base
            # ``search(query, n, where=...)`` contract raises TypeError, so fall
            # back to over-fetching and filtering to code here. Real backend /
            # index errors still propagate (we only catch the signature
            # mismatch) rather than being scored as a retrieval blind spot.
            try:
                hits = self.embedder.search(query, n=k, file_type="code")
            except TypeError:
                raw = self.embedder.search(query, n=k * 4)
                code = [h for h in raw if h.get("metadata", {}).get("file_type") == "code"]
                hits = (code or raw)[:k]
            return [str(h.get("metadata", {}).get("source_file", "")) for h in hits]

        report = probe.run_probe(
            samples, retrieve, ks=ks, k=k, index_size=code_node_count, rationales=rationales
        )
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
                "query_sources": report.query_sources,
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
