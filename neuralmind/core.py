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
import logging
import os
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from neuralmind.state_dir import ensure_parent_dir
from neuralmind.storage_guard import enforce_storage_policy

from . import ir as ir_mod
from . import namespaces as ns_mod
from . import paths as paths_mod
from . import querying, synapse_feedback
from . import recent_queries as recent_queries_log
from .audit import get_audit_trail
from .backend_manager import BackendManager
from .context_selector import ContextResult, ContextSelector, TokenBudget
from .memory import is_memory_logging_enabled, log_query_event, log_wakeup_event
from .paths import graph_json_path
from .query_handler import QueryHandler
from .structural import BLAST_VIEW_RELATION, StructuralIndex
from .synapse_client import SynapseClient
from .synapse_dynamics import SynapseDynamics
from .synapses import SynapseStore, default_db_path

logger = logging.getLogger(__name__)

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


_RATIONALE_SUFFIX = "__rationale"


def _synapse_node(node_id: str) -> str:
    """The node a search hit stands for in the synapse graph.

    ``<id>__rationale`` holds ``<id>``'s docstring or comment, so it is often
    the closest semantic match to a prompt. Synapses form between the code
    nodes the agent reads and edits, though, so the rationale node has no
    edges: seeding from it recalls nothing.
    """
    if node_id.endswith(_RATIONALE_SUFFIX) and len(node_id) > len(_RATIONALE_SUFFIX):
        return node_id[: -len(_RATIONALE_SUFFIX)]
    return node_id


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
    graph_path = paths_mod.graph_json_path(project_path)
    ir_path = paths_mod.ir_path(project_path)
    ir_meta_path = paths_mod.ir_meta_path(project_path)

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
        scope: str = "all",
    ):
        """
        Initialize NeuralMind for a project.

        Args:
            project_path: Path to project root (where .neuralmind/ lives). It
                must be an existing directory; otherwise ProjectNotFoundError.
            db_path: Optional custom path for ChromaDB storage
            enable_synapses: If True, run the associative synapse layer that
                learns co-activation patterns across queries and tool calls.
            memory_namespace: Explicit synapse-memory namespace (PRD 4). When
                None, resolved from NEURALMIND_NAMESPACE / the backend config's
                ``memory_namespace`` / the current git branch / ``personal``.
            scope: Index scope — 'all' (default), 'code', 'content', or 'docs'.
        """
        # A path that isn't an existing directory is an error, not a new
        # project: the backend and audit trail below would otherwise create
        # <path>/.neuralmind/ for a mistyped path.
        self.project_path = paths_mod.require_project_dir(project_path)
        self.scope = scope
        # Before anything can write index or synapse state: a project that
        # sets security.require_encrypted_storage refuses an unverified volume.
        enforce_storage_policy(self.project_path)
        self.db_path = db_path
        self.backend_manager = BackendManager(
            project_path=str(self.project_path), db_path=db_path, backend=backend_type, scope=scope
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

        # Build notices (graph source, freshness, purge warnings). They go to
        # notice_stream — stderr unless a caller sets it — never stdout by
        # default, which the MCP server uses for JSON-RPC.
        self.notice_stream = None
        self._notices: list[str] = []
        self._graph_info: dict | None = None

        # Associative synapse layer (lazy: only created when first used)
        self.enable_synapses = enable_synapses
        self._synapses: SynapseStore | None = None
        self._synapses_lock = threading.Lock()
        # Read-only queries (learn=False / NEURALMIND_NO_LEARN=1) read the
        # learned layer through a mode=ro store. The flag is per thread so a
        # read-only eval never silences a concurrent learning query.
        self._read_only_local = threading.local()
        self._read_only_synapses: SynapseStore | None = None
        self._synapse_client: SynapseClient | None = None
        self._dynamics: SynapseDynamics | None = None
        self._query_handler: QueryHandler | None = None
        self._memory_namespace_override = memory_namespace
        self._memory_namespace: str | None = None
        self._head_fingerprint: str | None = None

        # Structural edge index (calls/inherits/imports from graph.json). Built
        # from the loaded graph at build() time; None until then or when the
        # NEURALMIND_STRUCTURAL kill switch is set.
        self._structural_index: StructuralIndex | None = None

        # Medical retriever for prose projects (lazy: built on first prose query)
        self._medical_retriever: Any | None = None

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
        if self._reading_only():
            return self._read_only_store()
        namespace = self.memory_namespace
        store = self._synapses
        if store is None or getattr(store, "namespace", namespace) != namespace:
            with self._synapses_lock:
                store = self._synapses
                if store is None or getattr(store, "namespace", namespace) != namespace:
                    store = SynapseStore(default_db_path(self.project_path), namespace=namespace)
                    self._synapses = store
        return store

    def _reading_only(self) -> bool:
        """True inside a read-only query, or process-wide via NEURALMIND_NO_LEARN=1."""
        from .learning import learning_disabled

        return learning_disabled() or bool(getattr(self._read_only_local, "depth", 0))

    def _read_only_store(self) -> SynapseStore | None:
        """The synapse store opened ``mode=ro``; None before anything was learned."""
        namespace = self.memory_namespace
        store = self._read_only_synapses
        if store is None or store.namespace != namespace:
            try:
                store = SynapseStore(
                    default_db_path(self.project_path), namespace=namespace, read_only=True
                )
            except (FileNotFoundError, OSError, ValueError):
                return None
            store._embedder = self.embedder  # type: ignore[attr-defined]
            self._read_only_synapses = store
        return store

    @contextmanager
    def _read_only(self):
        """Within this block, synapse reads go through the read-only store."""
        local = self._read_only_local
        local.depth = getattr(local, "depth", 0) + 1
        try:
            yield
        finally:
            local.depth -= 1

    @property
    def synapse_client(self) -> SynapseClient:
        """Return the synapse client, creating it on first use."""
        if self._synapse_client is None:
            self._synapse_client = SynapseClient(self.synapses, Path(self.project_path))
        return self._synapse_client

    @property
    def dynamics(self) -> SynapseDynamics | None:
        """Return the SOTA synapse dynamics wrapper, creating it on first use.

        The dynamics layer wraps the raw SynapseStore with six modern
        brain-inspired techniques (lateral inhibition, STC, SAMPL,
        resource-dependent STDP, FOK gating, replay consolidation).

        Returns None when synapses are disabled.
        """
        if not self.enable_synapses or self.synapses is None:
            return None
        if self._dynamics is None:
            self._dynamics = SynapseDynamics(self.synapses)
        return self._dynamics

    @property
    def query_handler(self) -> QueryHandler:
        """Return the query handler, creating it on first use."""
        if self._query_handler is None:
            self._query_handler = QueryHandler(self)
        return self._query_handler

    def activate(self, node_ids: list[str], strength: float = 1.0) -> int:
        """Feed an activation signal into the synapse layer."""
        return self.synapse_client.activate(node_ids, strength=strength)

    def dynamics_reinforce(self, node_ids: list[str], strength: float = 1.0) -> int:
        """Reinforce synapses using SOTA dynamics (STC, resource STDP, replay).

        Uses the full SynapseDynamics wrapper which applies synaptic tagging,
        resource-dependent competition, and replay queueing in addition to
        standard Hebbian reinforcement.
        """
        if self.dynamics is None:
            return self.activate(node_ids, strength=strength)
        return self.dynamics.reinforce(node_ids, strength=strength)

    def dynamics_spread(
        self, seeds: list[tuple[str, float]] | list[str], depth: int = 2, top_k: int = 12
    ) -> list[tuple[str, float]]:
        """Spread activation with lateral inhibition and FOK gating.

        Returns top-k nodes ranked by accumulated activation after lateral
        inhibition sharpens the activation landscape. Returns empty list if
        the feeling-of-knowing gate determines no relevant context exists.
        """
        if self.dynamics is None:
            if self.synapses is None:
                return []
            return self.synapses.spread(seeds, depth=depth, top_k=top_k)
        return self.dynamics.spread(seeds, depth=depth, top_k=top_k)

    def dynamics_stats(self) -> dict | None:
        """Return current dynamics state for monitoring."""
        if self.dynamics is None:
            return None
        return self.dynamics.dynamics_stats()

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

    def detect_compliance(self, file_paths: list[str]) -> list[dict]:
        """Scan ``file_paths`` for compliance annotations and reinforce synapse
        edges between code nodes and referenced controls.

        Returns a list of detected annotations::

            [
                {"file": "...", "control_id": "AC.L2-3.1.1",
                 "framework": "CMMC", "label": "..."},
                ...
            ]
        """
        from neuralmind.compliance_matcher import (
            compliance_synapse_key,
            find_compliance_annotations_in_file,
        )

        results: list[dict] = []
        if self.synapses is None:
            return results

        for fp in file_paths:
            matches = find_compliance_annotations_in_file(fp)
            if not matches:
                continue

            # Find node IDs for the code in this file
            file_node_ids: list[str] = []
            try:
                for node in getattr(self.embedder, "nodes", None) or []:
                    if node.get("source_file", "") == fp or str(
                        node.get("source_file", "")
                    ).startswith(str(Path(fp).relative_to(self.project_path))):
                        nid = node.get("id")
                        if nid:
                            file_node_ids.append(str(nid))
            except Exception:
                logger.debug("file node lookup failed for %s", fp, exc_info=True)

            if not file_node_ids:
                continue

            for match in matches:
                ctrl_id = match["control_id"]
                framework = match["framework"]
                syn_key = compliance_synapse_key(ctrl_id, framework)

                # Reinforce each code node against the compliance control
                try:
                    self.synapses.reinforce(file_node_ids + [syn_key], strength=0.8)
                except Exception:
                    logger.debug("compliance synapse reinforce failed", exc_info=True)

                results.append(
                    {
                        "file": fp,
                        "control_id": ctrl_id,
                        "framework": framework,
                        "label": match["label"],
                    }
                )

        return results

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

    def build(
        self,
        force: bool = False,
        *,
        regenerate_graph: bool = False,
        strict: bool = False,
        prune: bool = False,
    ) -> dict:
        """
        Build or update the neural knowledge base.

        Resolves which graph.json to use (generating the built-in one when
        that's the source), checks it against the files on disk, embeds its
        nodes, removes vectors for nodes no longer in the graph, and prepares
        for queries.

        Args:
            force: If True, regenerate all embeddings even if unchanged
            regenerate_graph: Always rebuild ``.neuralmind/graph.json`` with
                the built-in tree-sitter backend, whatever graph exists.
            strict: Stop before embedding (``exit_code`` 3) when the graph
                FAILs the freshness check.
            prune: Purge orphaned vectors even past the 50% safety valve.

        Returns:
            Build statistics including nodes processed and time taken. Also
            ``graph`` (which graph was used), ``freshness`` (the freshness
            report) and ``notices`` (every notice the build printed).
        """
        start_time = datetime.now()
        self._notices = []

        # Load .neuralmind.yaml config
        from neuralmind.neuralmind_config import NeuralmindConfig

        self._neuralmind_config = NeuralmindConfig.load(self.project_path)

        # Pick the graph source and, when it's ours, (re)generate it from a
        # tree-sitter parse so `pip install neuralmind && neuralmind build`
        # works with no separate graphify install.
        graph_info = self._resolve_graph(regenerate=regenerate_graph)
        graph_path = Path(graph_info["path"])
        self._graph_info = graph_info
        if graph_info.get("error"):
            self._notify(f"Graph: {self._display_path(graph_path)} — {graph_info['error']}")
            return {
                "success": False,
                "error": graph_info["error"],
                "graph": self._graph_info_for_result(graph_info),
                "notices": list(self._notices),
                "duration_seconds": 0,
            }
        self._point_embedder_at(graph_path)
        self._notify(self._graph_line(graph_info))
        gitignore_notice = self._maybe_announce_gitignore(graph_info)

        # Freshness: compare the graph with the files on disk, both ways,
        # before spending time embedding it. Never silent when it isn't OK.
        from .freshness import FAIL as FRESHNESS_FAIL
        from .freshness import OK as FRESHNESS_OK
        from .freshness import graph_freshness

        freshness = None
        try:
            freshness = graph_freshness(self.project_path, graph_path)
        except Exception:  # pragma: no cover - diagnostic must never block a build
            freshness = None
        if freshness is not None and freshness.status != FRESHNESS_OK:
            self._notify(freshness.render(str(self.project_path)))
            if strict and freshness.status == FRESHNESS_FAIL:
                return {
                    "success": False,
                    "exit_code": 3,
                    "error": "code graph failed the freshness check (--strict)",
                    "graph": self._graph_info_for_result(graph_info),
                    "freshness": freshness.to_dict(),
                    "notices": list(self._notices),
                    "duration_seconds": round((datetime.now() - start_time).total_seconds(), 2),
                }

        # The embedder prefers .neuralmind/index_ir.json when it's newer than
        # graph.json. The IR is derived from whichever graph the last build
        # used, so after a source switch (e.g. back to an older graphify graph)
        # it would replay the previous graph. Drop it; this build rewrites it.
        previous_graph = (self._read_build_status().get("graph") or {}).get("path")
        current_graph = self._graph_info_for_result(graph_info)["path"]
        if previous_graph and previous_graph != current_graph:
            for derived in (self.ir_path, self.ir_meta_path):
                try:
                    derived.unlink()
                except OSError:
                    pass

        # Load graph
        self.embedder.graph = {}
        self.embedder.nodes = []
        self.embedder.edges = []
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

        # Purge vectors for nodes that left the graph, so search can't return
        # code that no longer exists. Every build, not only --force.
        purge = self._purge_orphans(prune=prune)

        # Measure the baseline every reduction ratio divides: the tokens of
        # the files this index covers (see neuralmind.baseline).
        from . import baseline as baseline_mod

        try:
            measured_baseline = baseline_mod.measure_graph_files(
                self.project_path, getattr(self.embedder, "graph", None) or {}
            )
            baseline_mod.save(self.project_path, measured_baseline)
        except Exception:  # pragma: no cover - a ratio's denominator never blocks a build
            measured_baseline = None

        self._init_query_state()

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

        # Seed synapse edges from business context documents (N-13).
        # Creates Hebbian edges between ingested business content and
        # code symbols they reference. Integrated in build() so it covers
        # daemon rebuilds too — not just ingest_document().
        _synapse_business_count = 0
        if self.enable_synapses:
            try:
                store = self.synapses
                if store is not None:
                    all_nodes = self._scan_all_nodes()
                    _synapse_business_count = store.seed_from_documents(all_nodes)
                    if _synapse_business_count == 0 and any(
                        n.get("metadata", {}).get("content_category") == "business_context"
                        for n in all_nodes
                    ):
                        import logging

                        logger = logging.getLogger(__name__)
                        logger.warning(
                            "seed_from_documents: business nodes present but 0 edges seeded "
                            "(check matching algorithm or stopword list)"
                        )
            except Exception:
                import logging

                logger = logging.getLogger(__name__)
                logger.exception("seed_from_documents failed during build")

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
            "nodes_removed": purge.get("removed", 0),
            "db_path": final_stats.get("db_path", ""),
            "duration_seconds": round(duration, 2),
            "built_at": datetime.now().isoformat(),
            "graph": self._graph_info_for_result(graph_info),
            "notices": list(self._notices),
        }
        if purge.get("skipped_orphans"):
            self._build_stats["orphans_kept"] = purge["skipped_orphans"]
        if measured_baseline:
            self._build_stats["baseline_tokens"] = measured_baseline["tokens"]
        if freshness is not None:
            self._build_stats["freshness"] = freshness.to_dict()
        # The graph this index was embedded from, so read paths can tell when
        # it has been regenerated since (graphify update, a pull) without a build.
        from . import l3_slots
        from .freshness import graph_fingerprint

        status_updates: dict = {
            "graph": {
                **self._build_stats["graph"],
                "fingerprint": graph_fingerprint(graph_info["path"]),
            },
            # Stamps caches derived from this index (the unified BM25 index),
            # one key per scope so a scoped build can't stale the default one.
            l3_slots.generation_key(self.scope): self._build_stats["built_at"],
        }
        if gitignore_notice:
            status_updates["gitignore_notice"] = True
        self._record_build_status(status_updates)
        self._write_unified_bm25()
        if _structural_edge_count:
            self._build_stats["structural_edges"] = _structural_edge_count
        if _structural_synapse_count:
            self._build_stats["structural_synapses"] = _structural_synapse_count
        if _synapse_business_count:
            self._build_stats["business_synapses"] = _synapse_business_count
        if ir_summary is not None:
            self._build_stats["ir"] = ir_summary

        self._built = True
        audit_details = {
            "backend": self.backend_manager.backend_name,
            "nodes_total": self._build_stats.get("nodes_total", 0),
        }
        if _synapse_business_count:
            audit_details["business_synapses"] = _synapse_business_count
        self._emit_audit(
            category="backend",
            action="build",
            status="success",
            target=self.project_path.name,
            details=audit_details,
        )
        return self._build_stats

    def _maybe_announce_gitignore(self, info: dict) -> bool:
        """Say once what honoring ``.gitignore`` keeps out of the index.

        v4.5.0 started indexing only what git covers, which changes results
        for existing projects. The first build of a built-in graph prints the
        counts and how to opt out; ``build_status.json`` records that it was
        shown. Returns True when the notice is settled (shown, or nothing to
        show) so the build can record it.
        """
        if info.get("kind") != "built-in":
            return False
        if self._read_build_status().get("gitignore_notice"):
            return False
        config = getattr(self, "_neuralmind_config", None)
        if config is not None and not config.respect_gitignore:
            return True
        from . import graphgen
        from .ignore import summarize_exclusions

        try:
            excluded = graphgen.gitignore_exclusions(self.project_path)
        except Exception:
            return False
        if excluded:
            self._notify(
                f"Honoring .gitignore (new in v4.5.0): {summarize_exclusions(excluded)} kept "
                "out of the index. Set respect_gitignore: false in .neuralmind.yaml to index "
                "them, or list paths under include_ignored."
            )
        return True

    def _graph_line(self, info: dict) -> str:
        """``Graph: .neuralmind/graph.json (built-in, incremental, 8,351 nodes)``"""
        kind = info.get("kind", "unknown")
        action = info.get("action", "")
        bits = [kind]
        if action:
            bits.append(action)
        if info.get("nodes"):
            bits.append(f"{info['nodes']:,} nodes")
        return f"Graph: {self._display_path(Path(info['path']))} ({', '.join(bits)})"

    def _graph_info_for_result(self, info: dict) -> dict:
        out = {
            "path": self._display_path(Path(info["path"])),
            "kind": info.get("kind", "unknown"),
            "action": info.get("action", ""),
            "nodes": info.get("nodes", 0),
        }
        if info.get("replaced"):
            out["replaced"] = info["replaced"]
        return out

    def _purge_orphans(self, prune: bool = False) -> dict:
        """Delete stored vectors whose node left the graph.

        Only vectors this build's graph would have written are candidates —
        content ingested with ``ingest``/``ingest-content`` lives in the same
        store without being in the graph and is never touched. When the
        orphans exceed half the store the graph has probably shrunk by mistake
        (wrong path, empty parse), so the purge is skipped with a warning
        unless ``prune`` is set.
        """
        finder = getattr(self.embedder, "orphaned_node_ids", None)
        deleter = getattr(self.embedder, "delete_nodes", None)
        if not callable(finder) or not callable(deleter):
            return {"removed": 0}
        try:
            orphans, stored = finder()
        except Exception:
            return {"removed": 0}
        if not orphans:
            return {"removed": 0}
        if stored and len(orphans) > 0.5 * stored and not prune:
            self._notify(
                f"[neuralmind] {len(orphans):,} of {stored:,} stored vectors are not in the "
                "graph — more than half the store, so they were kept. If the graph source "
                "changed on purpose (or the graph really shrank), rerun with --prune to "
                "remove them; otherwise check the graph path."
            )
            return {"removed": 0, "skipped_orphans": len(orphans)}
        try:
            removed = int(deleter(sorted(orphans)) or 0)
        except Exception:
            removed = 0
        return {"removed": removed}

    def _init_query_state(self) -> None:
        """Set up everything a query needs from the loaded graph.

        Shared by ``build()`` and the read-only load path, so a query against
        an existing index sees exactly what it would after a build — without
        regenerating the graph or touching the vector store.
        """
        # Detect project_kind (prose vs code) from the loaded graph
        # before creating the selector so it can use the right strategy.
        graph = getattr(self.embedder, "graph", None)
        if graph:
            # The graph structure has a top-level "graph" key that contains the project_kind
            graph_meta = graph.get("graph", {})
            self.project_kind = (
                graph_meta.get("project_kind", "code") if isinstance(graph_meta, dict) else "code"
            )
        else:
            self.project_kind = "code"

        # If config explicitly sets mode, honor it
        config = getattr(self, "_neuralmind_config", None)
        if config is None:
            from neuralmind.neuralmind_config import NeuralmindConfig

            config = self._neuralmind_config = NeuralmindConfig.load(self.project_path)
        if config.mode != "auto":
            self.project_kind = config.mode

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
            project_kind=self.project_kind,
        )
        # Reduction ratios divide by the measured size of the code the index
        # covers (neuralmind.baseline) — the same baseline benchmark, savings and
        # cost use — or the labelled 50K estimate before anything is measured.
        try:
            from . import baseline as baseline_mod

            self.selector.baseline_tokens = int(baseline_mod.resolve(self.project_path)["tokens"])
        except Exception:
            self.selector.baseline_tokens = None
        # Let L3 retrieval consult the live synapse graph (seed-based spread,
        # no extra embedder round trip — the seeds are hits already fetched).
        self.selector.synapse_recall = self._recall_for_selection
        # Traced queries use the detailed variant so the PRD 3 trace can show
        # which memory namespace drove each boost (PRD 4).
        self.selector.synapse_recall_detailed = self._recall_for_selection_detailed
        # Synapse-seeded expansion asks for the store on each query, so a
        # read-only query gets the mode=ro store rather than the writable one.
        self.selector.synapse_store_provider = lambda: self.synapses
        # Pass the synapse store directly for synapse-seeded expansion
        if self.synapses is not None:
            self.selector._synapse_store = self.synapses
            # Also pass the embedder so synapse-seeded expansion can fetch node data
            self.synapses._embedder = self.embedder
        # Pass the structural index for dependency graph expansion
        if hasattr(self, "_structural_index") and self._structural_index is not None:
            self.selector._structural_index = self._structural_index

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

    # ----------------------------------------------------------------- #
    # Canonical IR (PRD 1)
    # ----------------------------------------------------------------- #
    @property
    def ir_path(self) -> Path:
        return ir_mod.project_artifact(self.project_path, ".neuralmind", IR_FILENAME)

    @property
    def ir_meta_path(self) -> Path:
        return ir_mod.project_artifact(self.project_path, ".neuralmind", IR_META_FILENAME)

    def _scan_all_nodes(self) -> list[dict]:
        """Return all indexed nodes from the vector store.

        Uses the persisted vector store (ChromaDB or TurboVec SQLite) — not the
        transient ``embedder.nodes`` list — so a fresh process can still retrieve
        business context nodes from a prior ingestion.
        """
        try:
            return self.embedder.get_all_nodes()
        except Exception:
            return []

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

            ensure_parent_dir(self.ir_path)
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

    def ingest_document(
        self, file_path: str | Path, content_type: str = "auto", root: Path | None = None
    ) -> dict:
        """Ingest an arbitrary document as first-class content nodes.

        Parses PDF/Markdown/text files into ContentNode objects that embed
        alongside code in the same vector space. Large documents are chunked
        automatically for finer-grained retrieval.

        Args:
            file_path: Path to the document file or directory.
            content_type: Type hint ('pdf', 'markdown', 'text', or 'auto' to sniff).
            root: Root directory for path validation. If None, uses CWD.

        Returns:
            Dict with node_count, chunk_count, embed stats, or an error dict.
        """
        from neuralmind.document_ingestion import ingest_directory, parse_document

        file_path = Path(file_path)

        if not file_path.exists():
            return {"error": f"File not found: {file_path}"}

        # Build if not already built
        if not self._built:
            result = self.build()
            if not result.get("success"):
                return {"error": f"Build required before ingestion: {result.get('error')}"}

        try:
            if file_path.is_dir():
                content_nodes = [n.to_graph_node() for n in ingest_directory(file_path)]
            else:
                # If content_type is explicitly specified (not "auto"), pass it through
                if content_type != "auto":
                    content_nodes = [
                        n.to_graph_node()
                        for n in parse_document(file_path, root=root, content_type=content_type)
                    ]
                else:
                    content_nodes = [
                        n.to_graph_node() for n in parse_document(file_path, root=root)
                    ]
        except (ValueError, RuntimeError) as exc:
            return {"error": str(exc)}

        if not content_nodes:
            return {"error": "No content extracted from file", "node_count": 0}

        # Same rule as `neuralmind ingest`: a file inside the project whose
        # prose the code graph already holds is skipped (ingesting it stored a
        # second copy under its absolute path, so the text came back twice in
        # query context), and any other file inside the project is stored
        # under the project-relative path every graph node uses.
        # A graph file edited since the last build isn't stored either: an
        # ingest would sit beside the graph's old text rather than replace it,
        # so it's reported as needing `neuralmind build`.
        from neuralmind.document_ingestion import (
            graph_prose_files,
            graph_prose_is_current,
            project_relative_path,
        )

        graph_files = graph_prose_files(self.embedder.nodes, self.project_path)
        current: dict[str, bool] = {}
        kept: list[dict] = []
        for cn in content_nodes:
            meta = cn.get("metadata") if isinstance(cn.get("metadata"), dict) else {}
            source = cn.get("source_file") or meta.get("source") or ""
            rel = project_relative_path(Path(source), self.project_path) if source else None
            if rel is not None:
                if rel in graph_files:
                    if rel not in current:
                        current[rel] = graph_prose_is_current(
                            graph_files[rel], self.project_path / rel
                        )
                    continue
                cn["source_file"] = rel
                if meta:
                    meta["source"] = rel
            kept.append(cn)
        content_nodes = kept
        already_indexed = sorted(rel for rel, ok in current.items() if ok)
        needs_build = sorted(rel for rel, ok in current.items() if not ok)
        if not content_nodes:
            return {
                "success": True,
                "node_count": 0,
                "file_path": str(file_path),
                "already_indexed": already_indexed,
                "needs_build": needs_build,
                "message": (
                    "The code graph indexes this file, but it changed since the last "
                    "build; run `neuralmind build` to index the edit."
                    if needs_build
                    else "The code graph already indexes this file's text; "
                    "`neuralmind build` keeps it current."
                ),
            }

        # Sync content nodes into the embedder's node list so BM25 sees them
        existing_ids = {n.get("id", "") for n in self.embedder.nodes}
        for cn in content_nodes:
            cid = cn.get("id", "")
            if cid not in existing_ids:
                self.embedder.nodes.append(cn)

        # Seed synapse edges between related CMMC practices
        if self.enable_synapses:
            try:
                store = self.synapses
                if store is not None:
                    practice_ids = [
                        cn.get("id", "")
                        for cn in content_nodes
                        if cn.get("id", "").startswith("cmc:")
                    ]
                    if len(practice_ids) > 1:
                        store.reinforce(practice_ids)
            except Exception:
                pass

        # Embed the content nodes (includes BM25 rebuild)
        stats = self.embedder.embed_content(content_nodes)

        # Seed synapse edges from documentation so ingested documents
        # (README.md, docs/architecture.md) create architectural
        # relationships in the Hebbian graph — not just searchable nodes.
        # Gated on NEURALMIND_LLM_SEED=1 + ANTHROPIC_API_KEY; fail-open.
        synapse_doc_edges = 0
        if self.enable_synapses:
            try:
                store = self.synapses
                if store is not None:
                    synapse_doc_edges = store.seed_from_documentation(self.project_path)
                    # Warn if seeding was gated off (silent otherwise)
                    if synapse_doc_edges == 0:
                        import os

                        if os.environ.get("NEURALMIND_LLM_SEED") != "1":
                            print(
                                "  ℹ Doc synapse seeding disabled (set NEURALMIND_LLM_SEED=1 + ANTHROPIC_API_KEY to enable)"
                            )
                        elif not os.environ.get("ANTHROPIC_API_KEY"):
                            print("  ℹ Doc synapse seeding needs ANTHROPIC_API_KEY")
            except Exception:
                pass

        self._emit_audit(
            category="content_ingestion",
            action="ingest_document",
            status="success",
            target=self.project_path.name,
            details={
                "node_count": len(content_nodes),
                "file_path": str(file_path),
                "embed_stats": stats,
                "synapse_doc_edges": synapse_doc_edges,
            },
        )

        return {
            "success": True,
            "node_count": len(content_nodes),
            "file_path": str(file_path),
            "embed_stats": stats,
            "synapse_doc_edges": synapse_doc_edges,
            "already_indexed": already_indexed,
            "needs_build": needs_build,
        }

    def ingest_cmmc(self, registry_path: str | Path) -> dict:
        """Ingest the CMMC practice registry as first-class content nodes.

        Reads the JSON registry at ``registry_path`` (110 CMMC Level 2
        practices with id, title, description, guide, domain), converts
        each to a ``ContentNode``, and embeds it alongside the code
        graph.

        After ingestion, ``neuralmind query \"What is AC.L2-3.1.1?\"``
        returns the practice alongside relevant code.

        Returns a dict with node_count and embed stats, or an error dict.
        """
        from neuralmind.content_node import ContentNode

        registry_path = Path(registry_path)
        if not registry_path.exists():
            return {"error": f"Registry file not found: {registry_path}"}

        try:
            practices = json.loads(registry_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return {"error": f"Failed to parse registry: {exc}"}

        if not isinstance(practices, list):
            # Could be a dict with a practices key
            if isinstance(practices, dict):
                practices = practices.get("practices", practices.get("controls", [practices]))

        content_nodes = []
        for p in practices:
            node = ContentNode.from_cmmc_practice(p)
            content_nodes.append(node.to_graph_node())

        # Build if not already built
        if not self._built:
            result = self.build()
            if not result.get("success"):
                return {"error": f"Build required before ingestion: {result.get('error')}"}

        # Embed the content nodes
        stats = self.embedder.embed_content(content_nodes)

        # Seed synapse edges between related CMMC practices
        if self.enable_synapses:
            try:
                store = self.synapses
                if store is not None:
                    store.seed_from_cmmc_practices(content_nodes)
            except Exception:
                pass

        self._emit_audit(
            category="content_ingestion",
            action="ingest_cmmc",
            status="success",
            target=self.project_path.name,
            details={
                "node_count": len(content_nodes),
                "embed_stats": stats,
            },
        )

        return {
            "success": True,
            "node_count": len(content_nodes),
            "embed_stats": stats,
            "registry": registry_path.name,
        }

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
                    self._notify(
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
                    self._notify(
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
        # A prior chroma index may live at either the canonical path or the
        # legacy graphify-out/ path (pre-consolidation projects). Detection
        # checks both; only the canonical path is used for new writes.
        from .paths import canonical_artifact, legacy_artifact

        legacy_chroma = canonical_artifact(self.project_path, "neuralmind_db")
        if not legacy_chroma.exists():
            legacy_chroma = legacy_artifact(self.project_path, "neuralmind_db")
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

    # ----------------------------------------------------------------- #
    # Build notices
    # ----------------------------------------------------------------- #
    def _notify(self, message: str) -> None:
        """Report a build notice without touching stdout.

        Notices go to :attr:`notice_stream` — stderr unless a caller (the
        ``build`` CLI) points it at stdout — and are kept on the build result
        under ``notices``. Never stdout by default: the MCP server speaks
        JSON-RPC on stdout, and a stray line there corrupts the stream.
        """
        import sys

        self._notices.append(message)
        stream = self.notice_stream if self.notice_stream is not None else sys.stderr
        try:
            print(message, file=stream)
        except Exception:
            pass

    def _read_build_status(self) -> dict:
        path = paths_mod.canonical_artifact(self.project_path, "build_status.json")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write_unified_bm25(self) -> None:
        """Write the docs + code BM25 index the query path fuses (v4.6.0)."""
        if getattr(self, "project_kind", "code") == "prose":
            return
        try:
            from . import l3_slots

            if not l3_slots.unified_bm25_enabled():
                return
            catalog = l3_slots.NodeCatalog.from_embedder(self.embedder)
            l3_slots.unified_bm25_index(self.project_path, catalog, rebuild=True, scope=self.scope)
            if getattr(self, "selector", None) is not None:
                self.selector._unified_bm25 = None  # reload on the next query
        except Exception:  # pragma: no cover - a keyword index never blocks a build
            logger.debug("unified BM25 index not written", exc_info=True)

    def _record_build_status(self, updates: dict) -> None:
        """Merge ``updates`` into ``.neuralmind/build_status.json``."""
        path = paths_mod.canonical_artifact(self.project_path, "build_status.json")
        if not path.parent.exists():
            return
        status = self._read_build_status()
        status.update(updates)
        try:
            path.write_text(json.dumps(status, indent=2), encoding="utf-8")
        except OSError:
            pass

    # ----------------------------------------------------------------- #
    # Graph source (which graph.json the index is built from)
    # ----------------------------------------------------------------- #
    def _display_path(self, path: Path) -> str:
        try:
            return path.relative_to(self.project_path).as_posix()
        except ValueError:
            return str(path)

    def _generate_builtin_graph(self) -> dict | None:
        """Write ``.neuralmind/graph.json`` from the built-in tree-sitter backend.

        ``graphgen`` reuses unchanged nodes/edges by content hash and only
        re-extracts what changed plus transitive importers, so calling this on
        every build is cheap. Returns the graph, or None when tree-sitter isn't
        importable, the parse failed, or the project has nothing to index.
        """
        from . import graphgen

        if not graphgen.is_available():
            return None
        try:
            graph = graphgen.build_graph(self.project_path)
        except Exception as exc:  # pragma: no cover - defensive
            self._notify(f"[neuralmind] built-in graph backend failed: {exc}")
            return None

        # Only materialize a graph when there's real content to index. An empty
        # project keeps falling through to the existing "no graph" guidance
        # rather than producing a 0-node index that silently "succeeds".
        # Books are document-only (markdown chapters, reports) — accept any node.
        if not graph.get("nodes"):
            self._builtin_graph_empty = True
            return None

        # Optional SCIP precision pass: when NEURALMIND_PRECISION is set and a
        # *.scip index is present, replace the heuristic calls/inherits edges
        # with compiler-accurate ones. Off by default — a no-op otherwise, so
        # the generated graph is byte-for-byte unchanged.
        from . import precision

        graph, pstats = precision.maybe_refine(self.project_path, graph)
        if pstats is not None:
            self._notify(
                "[neuralmind] SCIP precision pass: "
                f"+{pstats.calls_added} calls, +{pstats.inherits_added} inherits "
                f"(replaced {pstats.heuristic_calls_removed} heuristic calls, "
                f"{pstats.heuristic_inherits_removed} inherits across "
                f"{pstats.documents} document(s))"
            )

        out_path = paths_mod.canonical_artifact(self.project_path, "graph.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")
        return graph

    def _point_embedder_at(self, graph_path: Path) -> None:
        """Make the embedder read ``graph_path`` (it caches its path at init)."""
        try:
            self.embedder.graph_path = graph_path
        except (AttributeError, TypeError):
            pass  # backends that resolve the path on every read

    def _resolve_graph(self, regenerate: bool = False) -> dict:
        """Decide which graph.json this build uses, generating it when ours.

        Honors ``graph_source`` in ``.neuralmind.yaml``:

        * ``auto`` — the canonical built-in graph when present, else a
          graphify graph. A graphify graph that FAILs the freshness check is
          replaced by a built-in graph (``graphify-out/`` is never written).
          If the previous build used the built-in graph and it has since
          disappeared, the build stops rather than silently falling back to
          a graphify graph.
        * ``builtin`` — always the tree-sitter graph; ``graphify-out/`` is
          never read.
        * ``graphify`` — only ``graphify-out/graph.json``; an error if absent.

        ``regenerate`` (``build --regenerate-graph``) always runs the
        tree-sitter backend. Returns ``{"path", "kind", "action", "nodes"}``
        plus ``"error"`` when the build can't proceed.
        """
        from .freshness import FAIL as FRESHNESS_FAIL
        from .freshness import graph_freshness, graph_source_kind

        setting = paths_mod.graph_source_setting(self.project_path)
        canonical = paths_mod.graph_json_path(self.project_path, "builtin")
        legacy = paths_mod.graph_json_path(self.project_path, "graphify")
        legacy_rel = self._display_path(legacy)
        canonical_rel = self._display_path(canonical)

        def _legacy_label() -> str:
            try:
                g = json.loads(legacy.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return "unreadable"
            report = graph_freshness(self.project_path, legacy)
            kind = graph_source_kind(g if isinstance(g, dict) else {}, legacy)
            if report is not None and report.graph_date:
                return f"{kind}, {report.graph_date}"
            return kind

        def _builtin(action: str) -> dict:
            self._builtin_graph_empty = False
            graph = self._generate_builtin_graph()
            if graph is None:
                if canonical.exists() and self._builtin_graph_empty:
                    # Every indexable file is gone: the previous graph now
                    # describes deleted code, and reusing it would keep
                    # serving it. Stop rather than call that index current.
                    return {
                        "path": canonical,
                        "kind": "built-in",
                        "action": action,
                        "nodes": 0,
                        "error": (
                            "the project has no indexable files left, so "
                            f"{self._display_path(canonical)} describes code that no longer "
                            "exists. Add source files, or delete .neuralmind/ to drop the index."
                        ),
                    }
                if canonical.exists() and action != "regenerated":
                    nodes = self._count_nodes(canonical)
                    return {
                        "path": canonical,
                        "kind": "built-in",
                        "action": "existing",
                        "nodes": nodes,
                    }
                return {
                    "path": canonical,
                    "kind": "built-in",
                    "action": action,
                    "nodes": 0,
                    "error": (
                        "the built-in graph backend needs tree-sitter and at least one "
                        "indexable file — pip install tree-sitter tree-sitter-python"
                    ),
                }
            return {
                "path": canonical,
                "kind": "built-in",
                "action": action,
                "nodes": len(graph.get("nodes", [])),
            }

        if regenerate:
            if setting == "graphify":
                return {
                    "path": legacy,
                    "kind": "graphify",
                    "action": "read-only",
                    "nodes": 0,
                    "error": (
                        "--regenerate-graph builds the tree-sitter graph, but "
                        ".neuralmind.yaml sets graph_source: graphify. Set it to auto "
                        "or builtin first."
                    ),
                }
            ignored = _legacy_label() if legacy.exists() else ""
            info = _builtin("regenerated")
            if "error" not in info:
                note = f"Graph source: built-in (tree-sitter), {info['nodes']:,} nodes."
                if ignored:
                    note += f" Ignoring {legacy_rel} ({ignored})."
                self._notify(note)
            return info

        if setting == "graphify":
            if not legacy.exists():
                return {
                    "path": legacy,
                    "kind": "graphify",
                    "action": "read-only",
                    "nodes": 0,
                    "error": (
                        f"graph_source: graphify is set, but {legacy_rel} doesn't exist. "
                        "Run graphify, or set graph_source: auto in .neuralmind.yaml."
                    ),
                }
            return {
                "path": legacy,
                "kind": "graphify",
                "action": "read-only",
                "nodes": self._count_nodes(legacy),
            }

        if setting == "builtin":
            return _builtin("incremental" if canonical.exists() else "generated")

        # --- auto ---------------------------------------------------------
        if canonical.exists():
            try:
                existing = json.loads(canonical.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                existing = {}
            if "neuralmind.graphgen" not in str(existing.get("generated_by", "")):
                # A graph someone else wrote into .neuralmind/ — never clobber.
                return {
                    "path": canonical,
                    "kind": graph_source_kind(existing, canonical),
                    "action": "read-only",
                    "nodes": len(existing.get("nodes", []) or []),
                }
            return _builtin("incremental")

        if not legacy.exists():
            return _builtin("generated")

        # Only a graphify graph is present.
        previous = self._read_build_status().get("graph") or {}
        if previous.get("kind") == "built-in":
            return {
                "path": legacy,
                "kind": "graphify",
                "action": "read-only",
                "nodes": 0,
                "error": (
                    f"the last build used the built-in graph at {canonical_rel}, which "
                    f"is gone; only {legacy_rel} ({_legacy_label()}) remains. NeuralMind "
                    "won't switch graph source silently. Run `neuralmind build "
                    f"{self.project_path} --regenerate-graph` to rebuild the built-in "
                    "graph, or set graph_source: graphify in .neuralmind.yaml to use the "
                    "graphify graph."
                ),
            }

        report = graph_freshness(self.project_path, legacy)
        from . import graphgen

        # Swap only when there's code on disk to parse: a graph whose files
        # are simply absent (a sparse checkout, a graph-only fixture) would be
        # replaced by an empty graph, which is worse than the warning.
        if (
            report is not None
            and report.status == FRESHNESS_FAIL
            and report.indexable_count > 0
            and graphgen.is_available()
        ):
            self._notify(
                f"{legacy_rel} failed the freshness check, so this build uses the built-in graph:"
            )
            self._notify(report.render(str(self.project_path)))
            info = _builtin("generated")
            if "error" not in info:
                self._notify(
                    f"Graph source: built-in (tree-sitter), {info['nodes']:,} nodes. "
                    f"{legacy_rel} is left untouched; set graph_source: graphify in "
                    ".neuralmind.yaml to keep using it."
                )
                info["replaced"] = report.to_dict()
            return info

        return {
            "path": legacy,
            "kind": "graphify",
            "action": "read-only",
            "nodes": report.node_count if report is not None else self._count_nodes(legacy),
        }

    @staticmethod
    def _count_nodes(graph_path: Path) -> int:
        try:
            return len(json.loads(graph_path.read_text(encoding="utf-8")).get("nodes", []) or [])
        except (OSError, ValueError, AttributeError):
            return 0

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
        graph_path = graph_json_path(self.project_path)
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

        from .neuralmind_config import NeuralmindConfig

        root = self.project_path.resolve()
        indexable = graphgen.SUPPORTED_SUFFIXES | graphgen._DOC_SUFFIXES
        # Files the full build would index (.gitignore, .neuralmindignore, the
        # default ignores and .neuralmind.yaml include/exclude applied), so an
        # edit to an excluded file can't slip it back into the graph.
        config = NeuralmindConfig.load(root)
        allowed = {
            f.relative_to(root).as_posix()
            for f in config.apply_globs(
                root, graphgen._iter_files(root, graphgen._DEFAULT_IGNORES, indexable)
            )
        }
        known = {n.get("source_file") for n in graph.get("nodes", [])}
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
            if ap.exists() and rel in allowed:
                changed.append(rel)
            elif rel in known or not ap.exists():
                removed.append(rel)

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

        # Restamp the index the way build() does: record the updated graph's
        # fingerprint (else every load reports the index out of step) and a new
        # index generation, which invalidates the caches stamped with the old
        # one; then rewrite the unified BM25 index so removed symbols stop
        # matching keywords and added ones start.
        from . import l3_slots
        from .freshness import graph_fingerprint

        self._record_build_status(
            {
                "graph": {
                    **(self._read_build_status().get("graph") or {}),
                    "path": self._display_path(graph_path),
                    "kind": "built-in",
                    "action": "incremental",
                    "nodes": stats.nodes_after,
                    "fingerprint": graph_fingerprint(graph_path),
                },
                l3_slots.generation_key(self.scope): datetime.now().isoformat(),
            }
        )
        self._write_unified_bm25()
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
        update so L0/L1 reflect the new node/community counts, and the node
        catalog and keyword indexes derived from the old nodes reload."""
        if self.selector is not None:
            self.selector._graph_stats = None
            self.selector._l0_cache = None
            self.selector._l1_cache = None
            self.selector._catalog = None
            self.selector._code_bm25 = None
            self.selector._unified_bm25 = None
            self.selector._hub_stats_cache = None

    def _ensure_built(self):
        """Make the index ready for a query without rebuilding it.

        Read paths (query, search, wakeup, the MCP tools) load an existing
        index as it stands: no graph regeneration, no embedding pass, no
        output. Only a project with no index at all is built here — the
        first-run convenience — and that build's notices go to stderr.
        A stale index is reported by the freshness check (``doctor``,
        ``health``, the MCP wakeup header), never silently rebuilt.

        Raises GraphNotBuiltError with an actionable message when the build
        can't produce a usable selector — almost always a missing code
        graph on a fresh project.
        """
        if self._built and self.selector is not None:
            return
        if self._load_existing_index():
            return
        result = self.build()
        if self.selector is None:
            ir_path = self.project_path / ".neuralmind" / "index_ir.json"
            graph_path = graph_json_path(self.project_path)
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

    def ensure_ready(self) -> dict:
        """Load the existing index for reading, or build one if there is none.

        What read commands and long-lived servers call instead of
        :meth:`build`: an index that's already built is loaded as it stands
        (no graph regeneration, no embedding pass, no output), so a stale
        index is reported by the freshness check rather than silently
        rebuilt. Returns ``{"success": True, "loaded": True}`` for a load,
        or the build result.
        """
        if self._built and self.selector is not None:
            return {"success": True, "loaded": True}
        if self._load_existing_index():
            return {"success": True, "loaded": True}
        from .learning import learning_disabled

        if learning_disabled():
            # NEURALMIND_NO_LEARN=1 promises nothing is written; a build writes
            # the graph, the vectors and structural synapses.
            return {
                "success": False,
                "error": "no index, and NEURALMIND_NO_LEARN=1 forbids building one",
            }
        return self.build()

    def _load_existing_index(self) -> bool:
        """Load an already-built index for querying. False when there is none.

        Reads the graph the embedder points at and checks the vector store has
        rows; never writes anything. Prints one stderr line only if loading
        takes over two seconds.
        """
        import sys

        try:
            total = int((self.embedder.get_stats() or {}).get("total_nodes", 0) or 0)
        except Exception:
            return False
        if total <= 0:
            return False

        def _slow_notice() -> None:
            try:
                print(f"Loading index ({total:,} nodes)...", file=sys.stderr)
            except Exception:
                pass

        timer = threading.Timer(2.0, _slow_notice)
        timer.daemon = True
        timer.start()
        try:
            if not getattr(self.embedder, "nodes", None):
                if not self.embedder.load_graph():
                    return False
            self._init_query_state()
        except Exception:
            self.selector = None
            return False
        finally:
            timer.cancel()
        self._built = True
        self._report_graph_mismatch()
        return True

    def _report_graph_mismatch(self) -> None:
        """One notice when the graph changed after the build that embedded it.

        Read paths never rebuild, so the stored vectors keep describing the
        old graph until ``neuralmind build`` runs: new nodes can't be found
        and removed ones still come back. Silent when they match.
        """
        try:
            from .freshness import index_graph_mismatch

            reason = index_graph_mismatch(self.project_path)
        except Exception:
            return
        if reason:
            self._notify(
                f"[neuralmind] Index out of step: {reason}, so queries use the vectors "
                f"of the previous build. Run: neuralmind build {self.project_path}"
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
        self,
        question: str,
        trace: bool = False,
        trace_verbose: bool = False,
        query_type: str = "auto",
        context_budget: int | None = None,
        learn: bool | None = None,
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
            query_type: 'code' ranks source code first, 'docs' documentation
                first, in place of the intent detected from the question;
                'auto' detects it (default).
            context_budget: Optional token budget. If provided, the assembled
                context is trimmed to fit within this budget by removing
                lower-priority layers (L3 → L2 → L1). L0 identity is never trimmed.
            learn: False makes the query read-only: synapse recall still boosts
                results (so the context is what a normal query would get), but
                nothing is reinforced or logged, and the synapse database is
                opened ``mode=ro``. None (default) learns unless
                ``NEURALMIND_NO_LEARN=1``. Evals and benchmarks pass False so
                they never train on their own test.

        Returns:
            ContextResult with relevant context and token budget
        """
        from .learning import should_learn

        if not should_learn(learn):
            with self._read_only():
                return self._run_query(
                    question, trace, trace_verbose, query_type, context_budget, learn=False
                )
        return self._run_query(
            question, trace, trace_verbose, query_type, context_budget, learn=True
        )

    def _run_query(
        self,
        question: str,
        trace: bool,
        trace_verbose: bool,
        query_type: str,
        context_budget: int | None,
        *,
        learn: bool,
    ) -> ContextResult:
        if learn:
            self._ensure_built()
        else:
            self._ensure_loaded_read_only()

        # Route prose/mixed projects through MedicalRetriever.
        # ContextSelector remains the code path (unchanged).
        if self.project_kind in ("prose", "mixed"):
            result = self._query_prose(question)
        else:
            result = self.selector.get_query_context(
                question,
                trace=trace,
                trace_verbose=trace_verbose,
                query_type=query_type,
                context_budget=context_budget,
            )
        if self.hybrid_context:
            highlights = self._build_hybrid_highlights(question, result.top_search_hits)
            if highlights and context_budget and context_budget > 0 and result.layer_texts:
                # The highlights count against the budget too: the layers
                # make room for them (L3, then L2, then L1), then the
                # highlights themselves are cut; L0 is never trimmed.
                self.selector.fit_to_budget(result, context_budget, prefix=highlights)
            elif highlights:
                result.context = f"{highlights}\n\n{result.context}"
                self.selector.count_prefix(result, highlights)
        if learn:
            log_query_event(self.project_path, question, result)
            self._record_recent_query(question, result)
            self._reinforce_from_query(question, result)
        # The audit trail records every query, read-only or not: it is the
        # compliance record of what was asked, not part of the learned layer.
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
                "learn": learn,
            },
        )
        return result

    def _ensure_loaded_read_only(self) -> None:
        """Load the existing index for a read-only query; never build.

        A read-only query must not write anything a build would (graph,
        vectors, structural synapses), so a project with no index is an error
        here rather than a first-run build.
        """
        if self._built and self.selector is not None:
            return
        if not self._load_existing_index():
            raise GraphNotBuiltError(
                f"No index for {self.project_path}. Read-only queries never build — "
                f"run `neuralmind build {self.project_path}` first."
            )

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

    def _get_medical_retriever(self):
        """Lazy-initialize MedicalRetriever for prose projects."""
        if self._medical_retriever is None:
            from neuralmind.medical_retriever import MedicalRetriever

            chapters_dir = self.project_path / paths_mod.PROSE_CHAPTERS_DIR
            self._medical_retriever = MedicalRetriever(
                project_path=str(self.project_path),
                chapter_dir=str(chapters_dir),
            )
            self._medical_retriever.build()
        return self._medical_retriever

    def _query_prose(self, question: str) -> ContextResult:
        """Query using MedicalRetriever for prose/mixed projects.

        Formats results into ContextResult for API compatibility with
        the code path. Includes confidence flags in the output context.
        Also reinforces the synapse layer with the retrieved chapters so
        cross-session learning applies to prose content too.
        """
        mr = self._get_medical_retriever()
        result = mr.query(question, top_k=5)

        # Reinforce synapses with retrieved chapters (prose path)
        if self.synapse_client.has_store() and result.chapters:
            try:
                chapter_ids = [
                    ch.get("chapter_id", ch.get("source_file", ""))
                    for ch in result.chapters
                    if ch.get("chapter_id") or ch.get("source_file")
                ]
                if chapter_ids and self.dynamics is not None:
                    self.dynamics.reinforce_prose(
                        chapter_ids=chapter_ids,
                        query_terms=[question],
                    )
            except Exception:
                logger.debug("prose synapse reinforcement failed", exc_info=True)

        # Build TokenBudget from MedicalRetriever metrics
        budget = TokenBudget(
            l0_identity=0,
            l1_summary=0,
            l2_ondemand=0,
            l3_search=len(result.chapters) * 200,  # ~200 tokens per chapter
        )

        return ContextResult(
            context=result.context,
            budget=budget,
            layers_used=["medical_retriever"],
            search_hits=len(result.chapters),
            reduction_ratio=10.0,  # estimated; prose docs are small
            top_search_hits=[
                {
                    "source_file": ch["source_file"],
                    "chapter_name": ch.get("chapter_name", ""),
                    "score": ch["score"],
                    "confidence": ch.get("confidence_label", "HIGH"),
                }
                for ch in result.chapters
            ],
            trace=None,
        )

    def skeleton(self, file_path: str) -> str:
        """Return a compact skeleton view of a file using graph data.

        See :func:`neuralmind.querying.skeleton`.
        """
        self._ensure_built()
        return querying.skeleton(self, file_path)

    def search(self, query: str, n: int = 10, learn: bool | None = None, **filters) -> list[dict]:
        """
        Direct semantic search without context formatting.

        Args:
            query: Search query
            n: Number of results
            learn: False runs read-only (never builds; see :meth:`query`).
                Search itself reinforces nothing either way.
            **filters: Optional filters (file_type, community)

        Returns:
            List of matching nodes with scores
        """
        from .learning import should_learn

        learning = should_learn(learn)
        if learning:
            self._ensure_built()
        else:
            self._ensure_loaded_read_only()
        results = self.embedder.search(query, n=n, **filters)
        self._emit_audit(
            category="audit",
            action="search",
            status="success",
            target=self.project_path.name,
            details={"query": query, "results": len(results), "learn": learning},
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
            logger.debug("_recall_for_selection spread failed", exc_info=True)
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
            logger.debug("_recall_for_selection_detailed spread failed", exc_info=True)
            return [], {}

    def synaptic_neighbors(
        self, query: str, depth: int = 2, top_k: int = 10
    ) -> list[tuple[str, float]]:
        """Return nodes related to ``query`` via spreading activation.

        Uses the embedder to seed an activation pulse at the top semantic
        matches for the query, then propagates through the learned synapse
        graph. Empty list when synapses haven't accumulated any edges yet.
        """
        return self.synaptic_recall(query, depth=depth, top_k=top_k)[0]

    def synaptic_recall(
        self, query: str, depth: int = 2, top_k: int = 10
    ) -> tuple[list[tuple[str, float]], float]:
        """:meth:`synaptic_neighbors`, plus how well ``query`` matched the code.

        The second value is the similarity of the best semantic match (0.0
        when nothing matched). Spreading activation from a poor match only
        spreads noise, so the prompt-time hook abstains below a threshold.
        """
        store = self.synapses
        if store is None:
            return [], 0.0
        self._ensure_built()
        try:
            hits = self.embedder.search(query, n=4)
        except Exception:
            return [], 0.0
        seeds: dict[str, float] = {}
        for hit in hits:
            if not hit.get("id"):
                continue
            node_id = _synapse_node(str(hit["id"]))
            score = float(hit.get("score", 1.0))
            # A code node and its own rationale can both match: one seed.
            seeds[node_id] = max(score, seeds.get(node_id, score))
        if not seeds:
            return [], 0.0
        return store.spread(list(seeds.items()), depth=depth, top_k=top_k), max(seeds.values())

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

    def benchmark(self, sample_queries: list[str] = None, *, naive_50k: bool = False) -> dict:
        """
        Run a benchmark to measure token reduction.

        Each ratio is the measured size of the code the index covers
        (``full_codebase_tokens``) over the tokens a question costs, so it
        scales with the repository. ``legacy_avg_reduction_ratio`` is the same
        run against the fixed 50,000-token estimate
        (``estimated_full_codebase_tokens``) that every ratio used before
        v4.5.0, so older results stay comparable.

        Args:
            sample_queries: Optional list of queries to test. If None, uses the
                questions in the project's ``.neuralmind.eval.yaml`` when there
                is one, else five generic questions.
            naive_50k: Divide by the fixed 50,000-token estimate instead of the
                measured token count of the code the index covers (for
                comparison with pre-v4.5.0 numbers).

        Returns:
            Benchmark results with average reduction ratio, and the baseline
            it was computed against (``baseline``).
        """
        from . import baseline as baseline_mod

        self._ensure_built()
        base = baseline_mod.resolve(self.project_path, naive_50k=naive_50k)
        if base["source"] != "measured" and not naive_50k:
            # An index built before the baseline existed has nothing cached.
            # The graph is loaded, so measure it now rather than fall back to
            # the fixed estimate; nothing is written.
            measured = baseline_mod.measure_graph_files(
                self.project_path, getattr(self.embedder, "graph", None) or {}
            )
            if measured["tokens"] > 0:
                base = baseline_mod.describe(measured)
        legacy_tokens = baseline_mod.NAIVE_BASELINE_TOKENS

        question_source = "argument"
        if sample_queries is None:
            from .project_eval import load_questions

            try:
                project_questions = load_questions(self.project_path)
            except Exception:
                project_questions = []
            if project_questions:
                sample_queries = [q.q for q in project_questions]
                question_source = "project eval"
            else:
                question_source = "generic"
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
                "reduction": baseline_mod.ratio(base["tokens"], wakeup.budget.total),
                "legacy_reduction": baseline_mod.ratio(legacy_tokens, wakeup.budget.total),
            }
        )

        # Query benchmarks — read-only: a benchmark measures retrieval, and
        # must not train the synapse layer it is measuring.
        for q in sample_queries:
            result = self.query(q, learn=False)
            results.append(
                {
                    "type": "query",
                    "query": q,
                    "tokens": result.budget.total,
                    "reduction": baseline_mod.ratio(base["tokens"], result.budget.total),
                    "legacy_reduction": baseline_mod.ratio(legacy_tokens, result.budget.total),
                    "layers": result.layers_used,
                }
            )

        # Calculate averages
        query_results = [r for r in results if r["type"] == "query"]
        avg_tokens = sum(r["tokens"] for r in query_results) / len(query_results)
        avg_reduction = sum(r["reduction"] for r in query_results) / len(query_results)
        avg_legacy = sum(r["legacy_reduction"] for r in query_results) / len(query_results)

        return {
            "project": self.project_path.name,
            "wakeup_tokens": wakeup.budget.total,
            "avg_query_tokens": round(avg_tokens, 1),
            "avg_reduction_ratio": round(avg_reduction, 1),
            "full_codebase_tokens": base["tokens"],
            "legacy_avg_reduction_ratio": round(avg_legacy, 1),
            "estimated_full_codebase_tokens": legacy_tokens,
            "baseline": base,
            "questions": question_source,
            "results": results,
            "summary": (f"{avg_reduction:.1f}x average token reduction vs {base['label']}"),
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
        auto_build: If True, load the existing index — or build one when
            the project has none. An existing index is never rebuilt here.

    Returns:
        Configured NeuralMind instance
    """
    mind = NeuralMind(project_path)
    if auto_build:
        mind.ensure_ready()
    return mind
