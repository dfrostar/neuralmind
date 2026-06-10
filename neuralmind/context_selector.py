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

import os
from dataclasses import dataclass, field
from pathlib import Path

from .reranker import CooccurrenceIndex, SemanticReranker


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

    def to_dict(self) -> dict:
        return {
            "l0_identity": self.l0_identity,
            "l1_summary": self.l1_summary,
            "l2_ondemand": self.l2_ondemand,
            "l3_search": self.l3_search,
            "total": self.total,
            "wakeup": self.wakeup,
        }


@dataclass
class ContextResult:
    """Result of context selection."""

    context: str
    budget: TokenBudget
    layers_used: list[str] = field(default_factory=list)
    communities_loaded: list[int] = field(default_factory=list)
    search_hits: int = 0
    reduction_ratio: float = 0.0
    top_search_hits: list[dict] = field(default_factory=list)
    trace: dict | None = None

    @property
    def tokens(self) -> int:
        """Backward-compatible token count accessor."""
        return self.budget.total


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

    # Synapse-driven recall (see _apply_synapse_boost / get_l2_context):
    # number of top hits used to seed spreading activation, how strongly
    # learned co-activation nudges relevance, the cap on neighbors pulled
    # into L3 that vector search missed, and the minimum activation an
    # absent neighbor needs before it's worth pulling in.
    SYNAPSE_SEED_K = 3
    SYNAPSE_BOOST_WEIGHT = 0.3
    SYNAPSE_PULL_IN_MAX = 2
    SYNAPSE_PULL_IN_MIN_ENERGY = 0.15

    def __init__(self, embedder, project_path: str = None, enable_reranking: bool = True):
        """
        Initialize context selector.

        Args:
            embedder: GraphEmbedder instance with loaded embeddings
            project_path: Path to project root (for reading metadata files)
            enable_reranking: If True, apply learned patterns to rerank L3 search results
        """
        self.embedder = embedder
        # Handle project_path - can be string, Path, or get from embedder
        if project_path and project_path is not True:
            self.project_path = (
                Path(project_path) if isinstance(project_path, str) else project_path
            )
        elif hasattr(embedder, "project_path") and embedder.project_path:
            self.project_path = (
                Path(embedder.project_path)
                if isinstance(embedder.project_path, str)
                else embedder.project_path
            )
        else:
            self.project_path = Path.cwd()

        # Reranking configuration
        self.enable_reranking = enable_reranking
        self._reranker: SemanticReranker | None = None
        self._context_modules: list[str] = []

        # Optional retrieval trace (PRD 3). None = tracing off (zero overhead);
        # set per-query by get_query_context(trace=True). Every record site is
        # guarded on this, so behavior is identical when it's None.
        self._trace = None

        # Optional seed-based synapse recall, injected by NeuralMind.build().
        # Signature: (seed_node_ids: list[str]) -> list[tuple[node_id, energy]].
        # Left None here so a selector built without a synapse store (or on a
        # cold graph) behaves exactly as it did before this layer existed.
        self.synapse_recall = None

        # Cache for layer content
        self._l0_cache: str | None = None
        self._l1_cache: str | None = None
        self._graph_stats: dict | None = None

        # Per-query search cache. Cleared at the start of each
        # get_query_context call so layers can share one round trip
        # to the embedder instead of three.
        self._query_search_cache: dict[str, list[dict]] = {}
        self._query_search_max_n = 10

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count from text."""
        return len(text) // self.CHARS_PER_TOKEN

    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token limit."""
        max_chars = max_tokens * self.CHARS_PER_TOKEN
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 3] + "..."

    def _get_graph_stats(self) -> dict:
        """Get cached graph statistics."""
        if self._graph_stats is None:
            self._graph_stats = self.embedder.get_stats()
        return self._graph_stats

    def _fetch_search(self, query: str, n: int) -> list[dict]:
        """Fetch embedder search results, sharing one round trip per query.

        Vector search returns a ranked list and ``n`` only truncates it,
        so we issue one large query and slice for smaller asks. The cache
        is cleared at the start of each get_query_context call to avoid
        cross-query bleed.
        """
        cached = self._query_search_cache.get(query)
        if cached is not None and len(cached) >= n:
            return cached[:n]
        fetch_n = max(n, self._query_search_max_n)
        results = self.embedder.search(query, n=fetch_n)
        self._query_search_cache[query] = results
        if self._trace is not None:
            self._trace.record_candidates(results)
        return results[:n]

    def _get_reranker(self) -> SemanticReranker:
        """Lazy-load reranker with learned patterns."""
        if self._reranker is None:
            # Load learned patterns from project
            patterns_file = self.project_path / ".neuralmind" / "learned_patterns.json"
            index = CooccurrenceIndex.load(patterns_file)
            self._reranker = SemanticReranker(index)
        return self._reranker

    def _load_project_identity(self) -> tuple[str, str]:
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

        parts = [f"## Project: {name}", ""]

        if description:
            parts.append(description)
            parts.append("")

        parts.extend(
            [
                f"Knowledge Graph: {stats.get('total_nodes', 0)} entities, {stats.get('communities', 0)} clusters",
                "Type: Code repository with semantic indexing",
                "",
            ]
        )

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

        parts = ["## Architecture Overview", ""]

        # Summarize communities
        if community_dist:
            parts.append("### Code Clusters")
            # Sort by size, show top 10
            sorted_communities = sorted(community_dist.items(), key=lambda x: x[1], reverse=True)[
                :10
            ]

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

    def get_l2_context(self, query: str, max_communities: int = 3) -> tuple[str, list[int]]:
        """
        Layer 2: On-demand context based on query.
        Load relevant communities/modules.

        Returns:
            Tuple of (context_text, list of community IDs loaded)
        """
        # First, search to find which communities are relevant
        search_results = self._fetch_search(query, n=5)

        if not search_results:
            return "", []

        # Track module IDs for L3 reranking context
        self._context_modules = []
        for result in search_results:
            meta = result.get("metadata", {})
            # Prefer source_file, fall back to community, fall back to label
            module = (
                meta.get("source_file")
                or f"community_{meta.get('community', -1)}"
                or meta.get("label", "")
            )
            if module:
                self._context_modules.append(module)

        # Count community hits
        community_scores: dict[int, float] = {}
        for result in search_results:
            comm = result.get("metadata", {}).get("community", -1)
            score = result.get("score", 0)
            if comm >= 0:
                community_scores[comm] = community_scores.get(comm, 0) + score

        # Pull communities the agent has historically co-activated with these
        # hits into contention, even when this query's vector matches alone
        # wouldn't have surfaced them. Reinforcement records community_<id>
        # pseudo-nodes, so spreading activation can return them directly.
        # Budget-neutral: a co-activated community can win a slot by
        # outscoring a vector one, but it can't grow how many we load — the
        # cap stays at what vector search alone would have surfaced.
        vector_community_count = len(community_scores)
        vector_scores = dict(community_scores) if self._trace is not None else None
        self._boost_communities_from_synapses(search_results, community_scores)
        community_budget = min(max_communities, vector_community_count)

        # Get top communities
        top_communities = sorted(community_scores.items(), key=lambda x: x[1], reverse=True)[
            :community_budget
        ]

        if self._trace is not None and vector_scores is not None:
            self._trace.record_cluster_scores(
                vector_scores,
                community_scores,
                [c for c, _ in top_communities],
                community_budget,
            )

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

    def _synapse_disabled(self) -> bool:
        """True when synapse recall isn't wired or the kill switch is set."""
        return not self.synapse_recall or os.environ.get("NEURALMIND_SYNAPSE_INJECT") == "0"

    def _recall_energy(self, seeds: list[str]) -> dict[str, float]:
        """Spread from ``seeds`` and return {node_id: activation}, or {}."""
        if not seeds:
            return {}
        try:
            return dict(self.synapse_recall(seeds))
        except Exception:
            return {}

    def _boost_communities_from_synapses(
        self, search_results: list[dict], community_scores: dict[int, float]
    ) -> None:
        """Add co-activated communities' energy into ``community_scores``.

        Mutates ``community_scores`` in place. No-op when recall is disabled
        or the graph is cold, so cold-start L2 selection is unchanged.
        """
        if self._synapse_disabled():
            return
        seeds = [r["id"] for r in search_results[: self.SYNAPSE_SEED_K] if r.get("id")]
        for node_id, energy in self._recall_energy(seeds).items():
            if not node_id.startswith("community_"):
                continue
            try:
                comm = int(node_id[len("community_") :])
            except ValueError:
                continue
            weighted = energy * self.SYNAPSE_BOOST_WEIGHT
            community_scores[comm] = community_scores.get(comm, 0.0) + weighted
            if self._trace is not None:
                self._trace.record_synapse_boost(seeds, comm, energy, weighted)

    def _apply_synapse_boost(self, results: list[dict]) -> list[dict]:
        """Re-rank L3 hits using learned synapse co-activation.

        Budget-neutral: never grows the result count. Seeds spreading
        activation from the top hits, then (a) boosts and reorders results
        the graph activates and (b) swaps the weakest vector hits for
        strongly co-activated neighbors vector search missed — surfacing
        nodes the agent keeps using together without spending extra tokens.

        No-op (returns ``results`` unchanged) when recall isn't wired, the
        kill switch is set, or the graph is cold — so cold-start behavior is
        byte-identical to a build without a synapse store.
        """
        if self._synapse_disabled():
            return results

        seeds = [r["id"] for r in results[: self.SYNAPSE_SEED_K] if r.get("id")]
        energy = self._recall_energy(seeds)
        if not energy:
            return results

        # Work on shallow copies: _fetch_search caches and reuses these dicts,
        # so mutating score in place would compound across calls and corrupt
        # the cached vector scores. Copies keep the boost idempotent.
        results = [dict(r) for r in results]
        seed_set = set(seeds)
        present = {r.get("id") for r in results}

        # (a) Boost results already present that the graph co-activates,
        #     then reorder by score. Token-neutral (same nodes).
        boosted = False
        for r in results:
            nid = r.get("id")
            if nid in seed_set or nid not in energy:
                continue
            boost = self.SYNAPSE_BOOST_WEIGHT * energy[nid]
            r["score"] = r.get("score", 0.0) + boost
            r["_synapse_boost"] = boost
            boosted = True
        if boosted:
            results = sorted(results, key=lambda r: r.get("score", 0.0), reverse=True)

        # (b) Swap the weakest vector hits for the strongest absent neighbors.
        #     Displacement keeps the result count fixed, so the token budget
        #     is unchanged — we trade the least-relevant hits, not add to them.
        #     Requires the embedder to support id lookup; if it doesn't (e.g. a
        #     backend without get_nodes_by_ids), degrade to boost-only.
        get_nodes_by_ids = getattr(self.embedder, "get_nodes_by_ids", None)
        if not callable(get_nodes_by_ids):
            return results

        candidates = sorted(
            (
                (nid, e)
                for nid, e in energy.items()
                if nid not in present
                and not nid.startswith("community_")
                and e >= self.SYNAPSE_PULL_IN_MIN_ENERGY
            ),
            key=lambda x: x[1],
            reverse=True,
        )[: self.SYNAPSE_PULL_IN_MAX]
        if not candidates:
            return results

        # Keep at least one vector hit; only displace as many as we can fetch.
        num_swap = min(len(candidates), max(0, len(results) - 1))
        if num_swap <= 0:
            return results
        energy_by_id = dict(candidates[:num_swap])
        fetched = get_nodes_by_ids(list(energy_by_id))
        if not fetched:
            return results

        kept = results[: len(results) - len(fetched)]
        for node in fetched:
            boost = self.SYNAPSE_BOOST_WEIGHT * energy_by_id.get(node.get("id"), 0.0)
            node["score"] = boost
            node["_synapse_boost"] = boost
            node["_synapse_recalled"] = True
        return kept + fetched

    def get_l3_search(self, query: str, n: int = 4) -> tuple[str, int]:
        """
        Layer 3: Deep semantic search results.
        Optionally applies learned reranking if patterns are available.

        Returns:
            Tuple of (search_results_text, number of hits)
        """
        results = self._fetch_search(query, n=n)

        if not results:
            return "", 0

        # Apply reranking if enabled
        if self.enable_reranking:
            reranker = self._get_reranker()
            if reranker.enabled:
                results = reranker.rerank(results, context_modules=self._context_modules)

        # Fold in the live synapse graph: results the agent has historically
        # co-activated with this query's top hits get a relevance nudge, so
        # learned association — not just vector similarity — shapes ranking.
        results = self._apply_synapse_boost(results)

        if self._trace is not None:
            self._trace.record_hits(results)

        parts = ["## Search Results", ""]

        for i, result in enumerate(results, 1):
            meta = result.get("metadata", {})
            score = result.get("score", 0)
            boost = result.get("_reranker_boost", 0.0)
            synapse = result.get("_synapse_boost", 0.0)

            # Show boosts in label if applied
            boost_label = f" (+{boost:.2f} boost)" if boost > 0 else ""
            synapse_label = f" (+{synapse:.2f} synapse)" if synapse > 0 else ""
            recalled_label = " [recalled]" if result.get("_synapse_recalled") else ""

            parts.append(
                f"{i}. **{meta.get('label', 'unknown')}**{recalled_label} "
                f"(score: {score:.2f}{boost_label}{synapse_label})"
            )
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
        full_codebase_tokens: int = 50000,  # Estimated full codebase size
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

        # Drop search results from any previous call so the cache only
        # ever holds hits relevant to this specific query.
        if query:
            self._query_search_cache.clear()

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

        if self._trace is not None:
            self._trace.record_budget(layers_used, budget, reduction_ratio)

        # Surface the cached search hits so downstream layers (synapses,
        # MCP responses) can reuse them instead of re-querying the embedder.
        top_hits: list[dict] = []
        if query:
            top_hits = list(self._query_search_cache.get(query, []))

        return ContextResult(
            context="\n".join(context_parts),
            budget=budget,
            layers_used=layers_used,
            communities_loaded=communities_loaded,
            search_hits=search_hits,
            reduction_ratio=reduction_ratio,
            top_search_hits=top_hits,
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
            include_l3=False,
        )

    def get_query_context(
        self, query: str, trace: bool = False, trace_verbose: bool = False
    ) -> ContextResult:
        """
        Get full context for a specific query.
        Use this when answering a question about the codebase.

        With ``trace=True``, records a per-layer :class:`~neuralmind.trace.
        RetrievalTrace` (candidates, cluster scoring, synapse boosts, final
        hits, token budget) and attaches it to ``result.trace``.

        Returns:
            ContextResult with relevant context and search results
        """
        if trace:
            from .trace import RetrievalTrace

            self._trace = RetrievalTrace(query=query, verbose=trace_verbose)
        try:
            result = self.get_context(
                query=query,
                include_l0=True,
                include_l1=True,
                include_l2=True,
                include_l3=True,
            )
            if self._trace is not None:
                result.trace = self._trace.to_dict()
            return result
        finally:
            self._trace = None
