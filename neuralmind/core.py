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

from datetime import datetime
from pathlib import Path

from .audit import get_audit_trail
from .backend_manager import BackendManager
from .context_selector import ContextResult, ContextSelector
from .memory import log_query_event
from .synapses import SynapseStore, default_db_path

DEFAULT_HYBRID_HIGHLIGHT_COUNT = 3


class NeuralMind:
    """
    Adaptive Neural Knowledge System.

    Replaces static Obsidian wiki with intelligent, query-aware context.
    Achieves 6-49x token reduction through progressive disclosure.
    """

    MAX_HYBRID_HIGHLIGHT_RESULTS = 3

    def __init__(
        self,
        project_path: str,
        db_path: str = None,
        enable_reranking: bool = True,
        backend_type: str | None = None,
        hybrid_context: bool | None = None,
        enable_synapses: bool = True,
    ):
        """
        Initialize NeuralMind for a project.

        Args:
            project_path: Path to project root (where graphify-out/ lives)
            db_path: Optional custom path for ChromaDB storage
            enable_reranking: If True, apply learned patterns to rerank search results
            enable_synapses: If True, run the associative synapse layer that
                learns co-activation patterns across queries and tool calls.
        """
        self.project_path = Path(project_path)
        self.db_path = db_path
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

    @property
    def backend_name(self) -> str:
        return self.backend_manager.backend_name

    @property
    def synapses(self) -> SynapseStore | None:
        """Return the associative synapse store, creating it on first use.

        Returns None when synapses are disabled. The store lives at
        ``<project>/.neuralmind/synapses.db`` so it persists across
        sessions and can be inspected or reset independently.
        """
        if not self.enable_synapses:
            return None
        if self._synapses is None:
            self._synapses = SynapseStore(default_db_path(self.project_path))
        return self._synapses

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
        """
        if not file_paths:
            return 0
        self._ensure_built()
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

        # Embed nodes
        embed_stats = self.embedder.embed_nodes(force=force)

        # Initialize selector with reranking
        self.selector = ContextSelector(
            self.embedder, str(self.project_path), enable_reranking=self.enable_reranking
        )

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

    def _ensure_built(self):
        """Ensure the system is built before queries."""
        if not self._built or self.selector is None:
            self.build()

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
        self._emit_audit(
            category="audit",
            action="wakeup",
            status="success",
            target=self.project_path.name,
            details={"tokens": result.budget.total},
        )
        return result

    def query(self, question: str) -> ContextResult:
        """
        Get optimized context for answering a question.

        Returns all relevant layers based on the query.
        Typically ~1000-1500 tokens with 30-50x reduction.

        Args:
            question: Natural language question about the codebase

        Returns:
            ContextResult with relevant context and token budget
        """
        self._ensure_built()
        result = self.selector.get_query_context(question)
        if self.hybrid_context:
            highlights = self._build_hybrid_highlights(question, result.top_search_hits)
            if highlights:
                result.context = f"{highlights}\n\n{result.context}"
        log_query_event(self.project_path, question, result)
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

    def _build_hybrid_highlights(
        self, question: str, cached_hits: list[dict] | None = None
    ) -> str:
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
        if self.enable_synapses:
            try:
                stats["synapses"] = self.synapses.stats() if self.synapses else None
            except Exception:
                stats["synapses"] = None
        return stats

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
