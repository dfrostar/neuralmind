"""
context_selector.py — Intelligent Context Selection for Token Reduction
========================================================================

Implements progressive disclosure to achieve 6-49x token reduction.
Only loads what's needed for the current query/task.

Layers:
- L0: Identity (~100 tokens) - project name, description, key facts
- L1: Summary (~500 tokens) - high-level architecture, main components
- L2: On-Demand (~200-500 each) - specific modules/communities as needed
- L3: Deep Search (variable) - semantic search results

Token Budget Management:
- Wake-up: L0 + L1 = ~600 tokens
- Per-query: L2 relevant context + L3 search = ~500-1000 tokens
- Total context: ~1100-1600 tokens vs full codebase (50K+ tokens)
- Reduction ratio: 30-50x typical
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field


@dataclass
class TokenBudget:
    """Track token usage across layers."""
    l0_identity: int = 0
    l1_summary: int = 0
    l2_ondemand: int = 0
    l3_search: int = 0
    
    @property
    def total(self) -> int:
        return self.l0_identity + self.l1_summary + self.l2_ondemand + self.l3_search
    
    @property
    def wakeup(self) -> int:
        return self.l0_identity + self.l1_summary
    
    def to_dict(self) -> Dict:
        return {
            "l0_identity": self.l0_identity,
            "l1_summary": self.l1_summary,
            "l2_ondemand": self.l2_ondemand,
            "l3_search": self.l3_search,
            "total": self.total,
            "wakeup": self.wakeup
        }


@dataclass
class ContextResult:
    """Result of context selection."""
    context: str
    budget: TokenBudget
    layers_used: List[str] = field(default_factory=list)
    communities_loaded: List[int] = field(default_factory=list)
    search_hits: int = 0
    reduction_ratio: float = 0.0


class ContextSelector:
    """
    Intelligent context selection for massive token reduction.
    
    Usage:
        selector = ContextSelector(embedder)
        result = selector.get_context("How does authentication work?")
        print(result.context)  # Compact, relevant context
        print(result.budget)   # Token usage breakdown
    """
    
    # Token limits per layer
    L0_MAX_TOKENS = 150
    L1_MAX_TOKENS = 600
    L2_MAX_TOKENS = 800
    L3_MAX_TOKENS = 1000
    
    # Chars per token estimate
    CHARS_PER_TOKEN = 4
    
    def __init__(self, embedder, project_path: str = None):
        """
        Initialize context selector.
        
        Args:
            embedder: GraphEmbedder instance with loaded embeddings
            project_path: Path to project root (for reading metadata files)
        """
        self.embedder = embedder
        # Handle project_path - can be string, Path, or get from embedder
        if project_path and project_path is not True:
            self.project_path = Path(project_path) if isinstance(project_path, str) else project_path
        elif hasattr(embedder, 'project_path') and embedder.project_path:
            self.project_path = Path(embedder.project_path) if isinstance(embedder.project_path, str) else embedder.project_path
        else:
            self.project_path = Path.cwd()
        
        # Cache for layer content
        self._l0_cache: Optional[str] = None
        self._l1_cache: Optional[str] = None
        self._graph_stats: Optional[Dict] = None
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count from text."""
        return len(text) // self.CHARS_PER_TOKEN
    
    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token limit."""
        max_chars = max_tokens * self.CHARS_PER_TOKEN
        if len(text) <= max_chars:
            return text
        return text[:max_chars-3] + "..."
    
    def _get_graph_stats(self) -> Dict:
        """Get cached graph statistics."""
        if self._graph_stats is None:
            self._graph_stats = self.embedder.get_stats()
        return self._graph_stats
    
    def _load_project_identity(self) -> Tuple[str, str]:
        """
        Load project identity from various sources.
        
        Returns:
            Tuple of (project_name, project_description)
        """
        name = self.project_path.name
        description = ""
        
        # Try mempalace.yaml
        mempalace_yaml = self.project_path / "mempalace.yaml"
        if mempalace_yaml.exists():
            try:
                import yaml
                with open(mempalace_yaml) as f:
                    data = yaml.safe_load(f)
                    if data:
                        name = data.get("wing", data.get("project", {}).get("name", name))
                        description = data.get("description", "")
            except Exception:
                pass
        
        # Try CLAUDE.md
        claude_md = self.project_path / "CLAUDE.md"
        if claude_md.exists() and not description:
            try:
                with open(claude_md) as f:
                    content = f.read()
                    # Extract first paragraph as description
                    lines = content.strip().split("\n")
                    for line in lines:
                        if line.strip() and not line.startswith("#"):
                            description = line.strip()[:200]
                            break
            except Exception:
                pass
        
        # Try README.md
        readme = self.project_path / "README.md"
        if readme.exists() and not description:
            try:
                with open(readme) as f:
                    content = f.read()
                    lines = content.strip().split("\n")
                    for line in lines:
                        if line.strip() and not line.startswith("#"):
                            description = line.strip()[:200]
                            break
            except Exception:
                pass
        
        return name, description
    
    def get_l0_identity(self) -> str:
        """
        Layer 0: Project identity (~100 tokens).
        Always loaded. "Who am I?"
        """
        if self._l0_cache is not None:
            return self._l0_cache
        
        name, description = self._load_project_identity()
        stats = self._get_graph_stats()
        
        parts = [
            f"## Project: {name}",
            ""
        ]
        
        if description:
            parts.append(description)
            parts.append("")
        
        parts.extend([
            f"Knowledge Graph: {stats.get('total_nodes', 0)} entities, {stats.get('communities', 0)} clusters",
            f"Type: Code repository with semantic indexing",
            ""
        ])
        
        self._l0_cache = self._truncate_to_tokens("\n".join(parts), self.L0_MAX_TOKENS)
        return self._l0_cache
    
    def get_l1_summary(self) -> str:
        """
        Layer 1: Essential summary (~500 tokens).
        Always loaded. High-level architecture.
        """
        if self._l1_cache is not None:
            return self._l1_cache
        
        stats = self._get_graph_stats()
        community_dist = stats.get("community_distribution", {})
        
        parts = [
            "## Architecture Overview",
            ""
        ]
        
        # Summarize communities
        if community_dist:
            parts.append("### Code Clusters")
            # Sort by size, show top 10
            sorted_communities = sorted(
                community_dist.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:10]
            
            for comm_id, count in sorted_communities:
                # Get sample nodes from this community
                comm_summary = self.embedder.get_community_summary(int(comm_id), max_nodes=5)
                type_info = comm_summary.get("type_summary", "mixed")
                sample_labels = [n["label"] for n in comm_summary.get("nodes", [])[:3]]
                samples = ", ".join(sample_labels) if sample_labels else "various"
                parts.append(f"- Cluster {comm_id} ({count} entities): {type_info} — {samples}")
            
            parts.append("")
        
        # Try to load GRAPH_REPORT.md summary
        graph_report = self.project_path / "graphify-out" / "GRAPH_REPORT.md"
        if graph_report.exists():
            try:
                with open(graph_report) as f:
                    content = f.read()
                    # Extract executive summary (first 1000 chars)
                    if "## " in content:
                        sections = content.split("## ")
                        for section in sections[1:3]:  # First couple sections
                            header, *body = section.split("\n", 1)
                            if body:
                                parts.append(f"### {header}")
                                parts.append(body[0][:400])
                                parts.append("")
            except Exception:
                pass
        
        self._l1_cache = self._truncate_to_tokens("\n".join(parts), self.L1_MAX_TOKENS)
        return self._l1_cache
    
    def get_l2_context(self, query: str, max_communities: int = 3) -> Tuple[str, List[int]]:
        """
        Layer 2: On-demand context based on query.
        Load relevant communities/modules.
        
        Returns:
            Tuple of (context_text, list of community IDs loaded)
        """
        # First, search to find which communities are relevant
        search_results = self.embedder.search(query, n=20)
        
        if not search_results:
            return "", []
        
        # Count community hits
        community_scores: Dict[int, float] = {}
        for result in search_results:
            comm = result.get("metadata", {}).get("community", -1)
            score = result.get("score", 0)
            if comm >= 0:
                community_scores[comm] = community_scores.get(comm, 0) + score
        
        # Get top communities
        top_communities = sorted(
            community_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:max_communities]
        
        if not top_communities:
            return "", []
        
        parts = ["## Relevant Code Areas", ""]
        loaded_communities = []
        
        for comm_id, score in top_communities:
            comm_summary = self.embedder.get_community_summary(comm_id, max_nodes=10)
            loaded_communities.append(comm_id)
            
            parts.append(f"### Cluster {comm_id} (relevance: {score:.2f})")
            parts.append(f"Contains: {comm_summary.get('type_summary', 'mixed entities')}")
            parts.append("")
            
            # List key entities
            for node in comm_summary.get("nodes", [])[:7]:
                label = node.get("label", "unknown")
                ftype = node.get("file_type", "")
                source = node.get("source_file", "")
                if source:
                    source = source.split("/")[-1]  # Just filename
                parts.append(f"- {label} ({ftype}) — {source}")
            
            parts.append("")
        
        context = self._truncate_to_tokens("\n".join(parts), self.L2_MAX_TOKENS)
        return context, loaded_communities
    
    def get_l3_search(self, query: str, n: int = 10) -> Tuple[str, int]:
        """
        Layer 3: Deep semantic search results.
        
        Returns:
            Tuple of (search_results_text, number of hits)
        """
        results = self.embedder.search(query, n=n)
        
        if not results:
            return "", 0
        
        parts = ["## Search Results", ""]
        
        for i, result in enumerate(results, 1):
            meta = result.get("metadata", {})
            score = result.get("score", 0)
            
            parts.append(f"{i}. **{meta.get('label', 'unknown')}** (score: {score:.2f})")
            parts.append(f"   Type: {meta.get('file_type', 'unknown')}")
            parts.append(f"   File: {meta.get('source_file', 'unknown')}")
            parts.append("")
        
        context = self._truncate_to_tokens("\n".join(parts), self.L3_MAX_TOKENS)
        return context, len(results)
    
    def get_context(
        self, 
        query: str = None,
        include_l0: bool = True,
        include_l1: bool = True,
        include_l2: bool = True,
        include_l3: bool = True,
        full_codebase_tokens: int = 50000  # Estimated full codebase size
    ) -> ContextResult:
        """
        Get optimized context for a query with massive token reduction.
        
        Args:
            query: Natural language query (required for L2/L3)
            include_l0: Include identity layer
            include_l1: Include summary layer
            include_l2: Include on-demand context
            include_l3: Include search results
            full_codebase_tokens: Estimated tokens if loading full codebase
        
        Returns:
            ContextResult with optimized context and token budget
        """
        budget = TokenBudget()
        context_parts = []
        layers_used = []
        communities_loaded = []
        search_hits = 0
        
        # L0: Identity (always fast)
        if include_l0:
            l0 = self.get_l0_identity()
            budget.l0_identity = self._estimate_tokens(l0)
            context_parts.append(l0)
            layers_used.append("L0:Identity")
        
        # L1: Summary (always fast, cached)
        if include_l1:
            l1 = self.get_l1_summary()
            budget.l1_summary = self._estimate_tokens(l1)
            context_parts.append(l1)
            layers_used.append("L1:Summary")
        
        # L2: On-demand (requires query)
        if include_l2 and query:
            l2, comms = self.get_l2_context(query)
            if l2:
                budget.l2_ondemand = self._estimate_tokens(l2)
                context_parts.append(l2)
                communities_loaded = comms
                layers_used.append(f"L2:OnDemand({len(comms)} clusters)")
        
        # L3: Deep search (requires query)
        if include_l3 and query:
            l3, hits = self.get_l3_search(query)
            if l3:
                budget.l3_search = self._estimate_tokens(l3)
                context_parts.append(l3)
                search_hits = hits
                layers_used.append(f"L3:Search({hits} results)")
        
        # Calculate reduction ratio
        reduction_ratio = full_codebase_tokens / budget.total if budget.total > 0 else 0
        
        return ContextResult(
            context="\n".join(context_parts),
            budget=budget,
            layers_used=layers_used,
            communities_loaded=communities_loaded,
            search_hits=search_hits,
            reduction_ratio=reduction_ratio
        )
    
    def get_wakeup_context(self) -> ContextResult:
        """
        Get minimal wake-up context (L0 + L1 only).
        Use this when starting a new conversation.
        
        Returns:
            ContextResult with ~600 tokens of essential context
        """
        return self.get_context(
            query=None,
            include_l0=True,
            include_l1=True,
            include_l2=False,
            include_l3=False
        )
    
    def get_query_context(self, query: str) -> ContextResult:
        """
        Get full context for a specific query.
        Use this when answering a question about the codebase.
        
        Returns:
            ContextResult with relevant context and search results
        """
        return self.get_context(
            query=query,
            include_l0=True,
            include_l1=True,
            include_l2=True,
            include_l3=True
        )
