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

from .context_selector import ContextResult, ContextSelector
from .embedder import GraphEmbedder
from .memory import log_query_event


class NeuralMind:
    """
    Adaptive Neural Knowledge System.

    Replaces static Obsidian wiki with intelligent, query-aware context.
    Achieves 6-49x token reduction through progressive disclosure.
    """

    def __init__(self, project_path: str, db_path: str = None, enable_reranking: bool = True):
        """
        Initialize NeuralMind for a project.

        Args:
            project_path: Path to project root (where graphify-out/ lives)
            db_path: Optional custom path for ChromaDB storage
            enable_reranking: If True, apply learned patterns to rerank search results
        """
        self.project_path = Path(project_path)
        self.db_path = db_path
        self.enable_reranking = enable_reranking

        # Initialize components
        self.embedder = GraphEmbedder(project_path, db_path)
        self.selector: ContextSelector | None = None

        # State tracking
        self._built = False
        self._build_stats: dict = {}

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
        return self.selector.get_wakeup_context()

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
        log_query_event(self.project_path, question, result)
        return result

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
        return self.embedder.search(query, n=n, **filters)

    def get_stats(self) -> dict:
        """
        Get current system statistics.

        Returns:
            Dict with node counts, communities, and build info
        """
        if not self._built:
            return {"built": False, "project": self.project_path.name}

        embed_stats = self.embedder.get_stats()
        return {
            "built": True,
            "project": self.project_path.name,
            "nodes": embed_stats.get("total_nodes", 0),
            "communities": embed_stats.get("communities", 0),
            "db_path": embed_stats.get("db_path", ""),
            "build_stats": self._build_stats,
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
