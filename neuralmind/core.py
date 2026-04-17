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
from .config import CONFIG
from .embedder import GraphEmbedder


class NeuralMind:
    """
    Adaptive Neural Knowledge System.

    Replaces static Obsidian wiki with intelligent, query-aware context.
    Achieves 6-49x token reduction through progressive disclosure.
    """

    def __init__(self, project_path: str, db_path: str = None):
        """
        Initialize NeuralMind for a project.

        Args:
            project_path: Path to project root (where graphify-out/ lives)
            db_path: Optional custom path for ChromaDB storage
        """
        self.project_path = Path(project_path)
        self.db_path = db_path

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

        # Initialize selector
        self.selector = ContextSelector(self.embedder, str(self.project_path))

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
        return self.selector.get_query_context(question)

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
