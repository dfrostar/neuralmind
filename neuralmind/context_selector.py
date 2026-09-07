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
from typing import Any


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


_DEFAULT_PARAM_FALLBACK = {
    "SYNAPSE_SEED_K": 3,
    "SYNAPSE_BOOST_WEIGHT": 0.3,
    "SYNAPSE_PULL_IN_MAX": 2,
    "SYNAPSE_PULL_IN_MIN_ENERGY": 0.15,
    "STRUCTURAL_SEED_K": 3,
    "STRUCTURAL_BOOST_WEIGHT": 0.35,
    "STRUCTURAL_PULL_IN_MAX": 2,
    "L0_MAX_TOKENS": 150,
    "L1_MAX_TOKENS": 600,
    "L2_MAX_TOKENS": 800,
    "L3_MAX_TOKENS": 1000,
    "SPREAD_DEPTH": 2,
    "SPREAD_DECAY": 0.6,
    "SPREAD_TOP_K": 12,
    "STRUCTURAL_HUB_DEGREE": 50,
    "DECAY_RATE_MIN": 3.0,
    "DECAY_RATE_MAX": 120.0,
}


# How close two hits must be before coverage, not score, picks the victim.
#
# Displacement has to drop someone. Between two hits the ranking cannot
# confidently separate, dropping the one whose file another survivor still
# covers is strictly better: same budget, more of the codebase represented.
# Outside that band the score is carrying real signal and is left alone.
#
# 2% is above the ~0.8% host-to-host score variation that made this ranking
# non-deterministic (PR #484, #492), which is why the fix also cures the
# bimodality — but it is deliberately not *derived* from that number. It is
# the width at which this fixture's own top-k scores cluster: the `refund`
# hits span 0.946-0.948 before the leader at 1.000. Widening it further
# regresses fact coverage, which is what the parity gate is for.
_COVERAGE_MARGIN = 0.02


def _module_of(result):
    """The source file a result belongs to, for coverage accounting."""
    meta = result.get("metadata") or {}
    return str(meta.get("source_file") or result.get("id") or "")


def _displace(results, drop_count):
    """Choose which results to displace, preserving module coverage.

    Displacement is budget-neutral: recalled neighbours take the slots of
    existing hits. The question is whose. Dropping the plain tail spends both
    slots on whichever nodes happen to sort last, and when several hits come
    from the same file that can evict a module's *only* representatives while
    keeping two of another's — losing a whole file from the context to gain
    nothing.

    That is not hypothetical; it is the failure this function was written for.
    On the `refund` fixture query the four hits are two api/routes.py nodes and
    two billing/stripe_client.py nodes. Tail-drop kept both api/routes.py rows
    and evicted both billing/stripe_client.py rows, so the query lost its one
    expected module. Which pair survived depended on a ~0.8% score difference
    that varies by host, so the same commit scored differently on different
    CPUs (PR #484, #492).

    Preferring a victim whose module is still covered by a survivor fixes both
    problems at once. The context keeps more distinct files, and the outcome
    stops depending on score differences far too small to be a ranking signal:
    a reorder within one module no longer changes which modules survive.

    Ties and the all-unique case fall back to lowest score first, so this only
    ever changes *which* equally-droppable hit goes, never how many.

    Args:
        results: Ranked hits, best first.
        drop_count: How many to displace.

    Returns:
        ``(kept, dropped)``; ``kept`` preserves the input ordering.
    """
    survivors = list(results)
    dropped = []
    for _ in range(max(0, drop_count)):
        if not survivors:
            break
        covered = {}
        for r in survivors:
            mod = _module_of(r)
            covered[mod] = covered.get(mod, 0) + 1
        # Weakest first, and among equals the lowest id, so the choice is a
        # function of the data rather than of dict or input ordering.
        order = sorted(
            range(len(survivors)),
            key=lambda i: (
                float(survivors[i].get("score") or 0.0),
                str(survivors[i].get("id") or ""),
            ),
        )
        # Only rearrange within the band where ranking cannot confidently
        # separate the candidates. Outside it the score is real signal, and
        # trading a materially better hit for coverage costs more facts than
        # the extra file is worth — measured, not assumed: an unbounded
        # version of this preference took the parity gate's faithfulness
        # delta from +0.041 to -0.006.
        weakest = float(survivors[order[0]].get("score") or 0.0)
        ceiling = weakest + _COVERAGE_MARGIN * abs(weakest)
        victim = next(
            (
                i
                for i in order
                if float(survivors[i].get("score") or 0.0) <= ceiling
                and covered.get(_module_of(survivors[i]), 0) > 1
            ),
            order[0],
        )
        dropped.append(survivors.pop(victim))
    return survivors, dropped


def _resolve_params(project_path):
    """Fail-open registry read. Returns the effective param map.

    When the registry cannot be imported or persisted values are
    unreadable, returns the defaults (matches legacy class constants).
    """
    try:
        from .tuning import resolve_effective

        return resolve_effective(project_path)
    except Exception:
        return dict(_DEFAULT_PARAM_FALLBACK)


def _adversarial_retrieval_enabled() -> bool:
    """Whether the v3.9.0 adversarial-retrieval pass runs (opt-in, default off).

    It regressed the faithfulness A/B it was measured by, so it stays behind
    this switch rather than shipping on by default or having the gate relaxed
    to accommodate it.
    """
    return os.environ.get("NEURALMIND_ADVERSARIAL_RETRIEVAL", "0") == "1"


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

    # Structural recall (see _apply_structural_expansion): the static code
    # graph's callers/callees/base classes for the top hits. Boost weight is
    # >= the synapse weight because structural edges are precise (compiler- or
    # AST-derived), not learned. Same budget-neutral displacement discipline:
    # a pulled-in structural neighbor replaces the weakest vector hit, never
    # adds to the count.
    STRUCTURAL_SEED_K = 3
    STRUCTURAL_BOOST_WEIGHT = 0.35
    STRUCTURAL_PULL_IN_MAX = 2

    # L2 recall depth — how many community summaries L2 surfaces per query
    # (the budget cap on get_l2_context). Historically a hard-coded 3; the
    # self-improvement engine's selector auto-tuner (neuralmind/self_improve.py)
    # can override it per project via the l2_recall_k constructor arg, clamped
    # to [L2_RECALL_K_MIN, L2_RECALL_K_MAX]. Default-off: when autotune isn't
    # enabled, build() never reads the persisted value and the default stands.
    L2_RECALL_K_DEFAULT = 3
    L2_RECALL_K_MIN = 2
    L2_RECALL_K_MAX = 6

    def __init__(self, embedder, project_path: str = None, l2_recall_k: int | None = None):
        """
        Initialize context selector.

        Args:
            embedder: GraphEmbedder instance with loaded embeddings
            project_path: Path to project root (for reading metadata files)
            l2_recall_k: Optional override for the L2 recall depth (number of
                community summaries surfaced per query). When None, the
                hard-coded L2_RECALL_K_DEFAULT is used — so a selector built
                without the autotuner behaves exactly as before. Clamped
                defensively to [L2_RECALL_K_MIN, L2_RECALL_K_MAX].
        """
        self.embedder = embedder
        if l2_recall_k is None:
            self.l2_recall_k = self.L2_RECALL_K_DEFAULT
        else:
            self.l2_recall_k = max(
                self.L2_RECALL_K_MIN, min(int(l2_recall_k), self.L2_RECALL_K_MAX)
            )
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

        # Registry-aware parameter reads (C2): at runtime the selector
        # reads effective values (defaults + persisted overrides) from the
        # tuneable-parameter registry. When nothing has been persisted the
        # effective value equals the class constant below — so existing
        # behavior is byte-compatible. Fail-open: any lookup error falls
        # back to the registry default.
        self._params = _resolve_params(project_path)
        p = self._params
        self._l0_max_tokens = int(p["L0_MAX_TOKENS"])
        self._l1_max_tokens = int(p["L1_MAX_TOKENS"])
        self._l2_max_tokens = int(p["L2_MAX_TOKENS"])
        self._l3_max_tokens = int(p["L3_MAX_TOKENS"])
        self._synapse_seed_k = int(p["SYNAPSE_SEED_K"])
        self._synapse_boost_weight = p["SYNAPSE_BOOST_WEIGHT"]
        self._synapse_pull_in_max = int(p["SYNAPSE_PULL_IN_MAX"])
        self._synapse_pull_in_min_energy = p["SYNAPSE_PULL_IN_MIN_ENERGY"]
        self._structural_seed_k = int(p["STRUCTURAL_SEED_K"])
        self._structural_boost_weight = p["STRUCTURAL_BOOST_WEIGHT"]
        self._structural_pull_in_max = int(p["STRUCTURAL_PULL_IN_MAX"])

        # Optional retrieval trace (PRD 3). None = tracing off (zero overhead);
        # set per-query by get_query_context(trace=True). Every record site is
        # guarded on this, so behavior is identical when it's None.
        self._trace = None

        # Optional seed-based synapse recall, injected by NeuralMind.build().
        # Signature: (seed_node_ids: list[str]) -> list[tuple[node_id, energy]].
        # Left None here so a selector built without a synapse store (or on a
        # cold graph) behaves exactly as it did before this layer existed.
        self.synapse_recall = None
        # Optional traced variant (PRD 4): same seeds, returns
        # (ranked, {node_id: {namespace: energy}}) so the retrieval trace can
        # attribute each boost to the memory namespace that drove it. Only
        # consulted when a trace is active.
        self.synapse_recall_detailed = None
        self._synapse_store: Any = None  # For synapse-seeded expansion
        self._structural_index: Any = None  # For dependency graph expansion

        # Optional structural recall, injected by NeuralMind.build().
        # Signature: (seed_node_ids: list[str]) -> list[tuple[node_id, weight]].
        # Returns the static code graph's callers/callees/base classes of the
        # seeds. Left None so a selector built without a structural index (or on
        # a graph with no structural edges) behaves exactly as before.
        self.structural_recall = None

        # Cache for layer content
        self._l0_cache: str | None = None
        self._l1_cache: str | None = None
        self._graph_stats: dict | None = None

        # Per-query search cache. Cleared at the start of each
        # get_query_context call so layers can share one round trip
        # to the embedder instead of three.
        self._query_search_cache: dict[str, list[dict]] = {}
        self._query_search_max_n = 10

    # RRF constant — rank 60 contribution = 1/61 ≈ 0.016.  Lower values
    # weight the top positions more aggressively; 60 is the de-facto standard.
    RRF_K = 60

    def _rrf_merge(
        self,
        vec_results: list[dict[str, Any]],
        kw_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Merge vector and BM25 result lists via Reciprocal Rank Fusion.

        Budget-neutral: the output has at most max(len(vec), len(kw)) unique
        nodes, deduplicated by id, so we never add tokens to the budget
        relative to the vector-only baseline.
        """
        scores: dict[str, float] = {}
        by_id: dict[str, dict[str, Any]] = {}

        for rank, r in enumerate(vec_results):
            nid = r.get("id", "")
            scores[nid] = scores.get(nid, 0.0) + 1.0 / (self.RRF_K + rank + 1)
            by_id.setdefault(nid, r)

        for rank, r in enumerate(kw_results):
            nid = r.get("id", "")
            scores[nid] = scores.get(nid, 0.0) + 1.0 / (self.RRF_K + rank + 1)
            if nid not in by_id:
                by_id[nid] = r
            else:
                # Annotate that both signals agree — visible in --trace output
                by_id[nid] = dict(by_id[nid])
                by_id[nid]["_hybrid_kw_rank"] = rank + 1

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        # Normalise RRF score into [0, 1] so downstream score comparisons
        # stay meaningful (same range as the old pure-vector score).
        max_score = ranked[0][1] if ranked else 1.0
        results = []
        for nid, rrf in ranked:
            node = dict(by_id[nid])
            node["score"] = rrf / max_score
            node["_rrf_score"] = rrf
            results.append(node)
        return results

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
        """Fetch search results, sharing one round trip per query.

        When the embedder supports BM25 and NEURALMIND_BM25 != 0, the
        vector results are merged with keyword results via Reciprocal Rank
        Fusion before caching — so code-specific queries like "UserService"
        score exact-name matches above semantically similar but textually
        distant nodes. The merge is budget-neutral: the output length is
        capped at max(n, _query_search_max_n) unique nodes.
        """
        cached = self._query_search_cache.get(query)
        if cached is not None and len(cached) >= n:
            return cached[:n]
        fetch_n = max(n, self._query_search_max_n)
        vec_results = self.embedder.search(query, n=fetch_n)

        # Hybrid: merge with BM25 when the backend supports it
        bm25_search = getattr(self.embedder, "bm25_search", None)
        if callable(bm25_search) and os.environ.get("NEURALMIND_BM25") != "0":
            kw_results = bm25_search(query, n=fetch_n)
            if kw_results and isinstance(kw_results, list):
                merged = self._rrf_merge(vec_results, kw_results)
                results = merged[:fetch_n]
            else:
                results = vec_results
        else:
            results = vec_results

        self._query_search_cache[query] = results
        if self._trace is not None:
            self._trace.record_candidates(results)
        return results[:n]

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

        self._l0_cache = self._truncate_to_tokens("\n".join(parts), self._l0_max_tokens)
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

        self._l1_cache = self._truncate_to_tokens("\n".join(parts), self._l1_max_tokens)
        return self._l1_cache

    def get_l2_context(
        self, query: str, max_communities: int | None = None
    ) -> tuple[str, list[int]]:
        """
        Layer 2: On-demand context based on query.
        Load relevant communities/modules.

        ``max_communities`` defaults to :attr:`l2_recall_k` (the auto-tunable
        recall depth) when not passed explicitly, so the persisted tuner value
        flows through here without a per-call store read.

        Returns:
            Tuple of (context_text, list of community IDs loaded)
        """
        if max_communities is None:
            max_communities = self.l2_recall_k
        # First, search to find which communities are relevant
        search_results = self._fetch_search(query, n=5)

        if not search_results:
            return "", []

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

                # Include snippet text for documents
                snippet = node.get("text", "")[:120]
                if snippet:
                    parts.append(f'  "{snippet}"')

            parts.append("")

        context = self._truncate_to_tokens("\n".join(parts), self._l2_max_tokens)
        return context, loaded_communities

    def _synapse_disabled(self) -> bool:
        """True when synapse recall isn't wired or the kill switch is set."""
        return not self.synapse_recall or os.environ.get("NEURALMIND_SYNAPSE_INJECT") == "0"

    def _structural_disabled(self) -> bool:
        """True when structural recall isn't wired or the kill switch is set."""
        return not self.structural_recall or os.environ.get("NEURALMIND_STRUCTURAL") == "0"

    def _recall_energy(self, seeds: list[str]) -> dict[str, float]:
        """Spread from ``seeds`` and return {node_id: activation}, or {}."""
        if not seeds:
            return {}
        try:
            return dict(self.synapse_recall(seeds))
        except Exception:
            return {}

    def _recall_energy_traced(
        self, seeds: list[str]
    ) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
        """Traced recall: energies plus per-namespace attribution (PRD 4).

        Falls back to the plain recall (empty attribution) when the detailed
        hook isn't wired, so a selector built against an older core still
        traces boosts — just without namespace breakdowns.
        """
        if not seeds:
            return {}, {}
        if self.synapse_recall_detailed is not None:
            try:
                ranked, contributions = self.synapse_recall_detailed(seeds)
                return dict(ranked), contributions
            except Exception:
                return {}, {}
        return self._recall_energy(seeds), {}

    def _boost_communities_from_synapses(
        self, search_results: list[dict], community_scores: dict[int, float]
    ) -> None:
        """Add co-activated communities' energy into ``community_scores``.

        Mutates ``community_scores`` in place. No-op when recall is disabled
        or the graph is cold, so cold-start L2 selection is unchanged.
        """
        if self._synapse_disabled():
            return
        seeds = [r["id"] for r in search_results[: self._synapse_seed_k] if r.get("id")]
        if self._trace is not None:
            energies, contributions = self._recall_energy_traced(seeds)
        else:
            energies, contributions = self._recall_energy(seeds), {}
        for node_id, energy in energies.items():
            if not node_id.startswith("community_"):
                continue
            try:
                comm = int(node_id[len("community_") :])
            except ValueError:
                continue
            weighted = energy * self._synapse_boost_weight
            community_scores[comm] = community_scores.get(comm, 0.0) + weighted
            if self._trace is not None:
                self._trace.record_synapse_boost(
                    seeds,
                    comm,
                    energy,
                    weighted,
                    namespace_contribution=contributions.get(node_id),
                )

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

        seeds = [r["id"] for r in results[: self._synapse_seed_k] if r.get("id")]
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
            boost = self._synapse_boost_weight * energy[nid]
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
                and e >= self._synapse_pull_in_min_energy
            ),
            key=lambda x: x[1],
            reverse=True,
        )[: self._synapse_pull_in_max]
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

        kept, _ = _displace(results, len(fetched))
        for node in fetched:
            boost = self._synapse_boost_weight * energy_by_id.get(node.get("id"), 0.0)
            node["score"] = boost
            node["_synapse_boost"] = boost
            node["_synapse_recalled"] = True
        return kept + fetched

    def _apply_structural_expansion(self, results: list[dict]) -> list[dict]:
        """Fold the static code graph's wiring into L3 hits.

        Budget-neutral, and a structural analogue of :meth:`_apply_synapse_boost`.
        Seeds from the top hits, asks the structural index for their
        callers/callees/base classes, then (a) boosts and reorders results the
        graph already surfaced and (b) swaps the weakest vector hits for
        strongly-wired neighbors vector search missed — so an edit query that
        lands on a function also pulls in its callers, without spending extra
        tokens.

        No-op (returns ``results`` unchanged) when recall isn't wired, the kill
        switch is set, or the graph has no structural edges — so behavior is
        byte-identical to a build without structural edges. Runs *before* the
        synapse boost: structure is precise and claims a displacement slot
        first, then learned co-activation re-ranks what remains.
        """
        if self._structural_disabled():
            return results

        seeds = [r["id"] for r in results[: self._structural_seed_k] if r.get("id")]
        if not seeds:
            return results
        try:
            recalled = dict(self.structural_recall(seeds))
        except Exception:
            return results
        if not recalled:
            return results

        # Shallow copies: _fetch_search caches and reuses these dicts, so
        # mutating score in place would corrupt the cached vector scores.
        results = [dict(r) for r in results]
        seed_set = set(seeds)
        present = {r.get("id") for r in results}

        # (a) Boost results already present that the structural graph wires to
        #     a seed, then reorder. Token-neutral (same nodes).
        boosted = False
        for r in results:
            nid = r.get("id")
            if nid in seed_set or nid not in recalled:
                continue
            boost = self._structural_boost_weight * recalled[nid]
            r["score"] = r.get("score", 0.0) + boost
            r["_structural_boost"] = boost
            boosted = True
        if boosted:
            results = sorted(results, key=lambda r: r.get("score", 0.0), reverse=True)

        # (b) Swap the weakest vector hits for the strongest absent structural
        #     neighbors. Displacement keeps the count fixed → token-neutral.
        get_nodes_by_ids = getattr(self.embedder, "get_nodes_by_ids", None)
        if not callable(get_nodes_by_ids):
            return results

        candidates = sorted(
            ((nid, w) for nid, w in recalled.items() if nid not in present),
            key=lambda x: x[1],
            reverse=True,
        )[: self._structural_pull_in_max]
        if not candidates:
            return results

        num_swap = min(len(candidates), max(0, len(results) - 1))
        if num_swap <= 0:
            return results
        weight_by_id = dict(candidates[:num_swap])
        fetched = get_nodes_by_ids(list(weight_by_id))
        if not fetched:
            return results

        kept, _ = _displace(results, len(fetched))
        for node in fetched:
            boost = self._structural_boost_weight * weight_by_id.get(node.get("id"), 0.0)
            node["score"] = boost
            node["_structural_boost"] = boost
            node["_structural_recalled"] = True
        return kept + fetched

    def _detect_intent(self, query: str) -> str:
        """Detect query intent: 'code', 'docs', or 'hybrid'."""
        query_lower = query.lower()

        # Code-framed indicators
        code_keywords = [
            "implement",
            "function",
            "class",
            "method",
            "code",
            "source",
            "file",
            "def ",
            "class ",
            "import ",
            "from ",
            "module",
            "component",
            "handler",
            "service",
            "controller",
            "model",
            "route",
            "endpoint",
            "api",
            "config",
            "constant",
            "type",
            "interface",
            "schema",
            "query",
            "mutation",
            "migration",
        ]
        code_extensions = [
            ".py",
            ".ts",
            ".js",
            ".java",
            ".go",
            ".rs",
            ".rb",
            ".php",
            ".swift",
            ".kt",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".cs",
            ".scala",
            ".m",
            ".mm",
        ]

        # Doc-framed indicators
        doc_keywords = [
            "explain",
            "what is",
            "how does",
            "documentation",
            "readme",
            "guide",
            "tutorial",
            "why",
            "when should",
            "concept",
            "overview",
            "architecture",
            "design",
            "pattern",
            "principle",
            "best practice",
            "introduction",
        ]

        # Check for code indicators
        code_score = 0
        for kw in code_keywords:
            if kw in query_lower:
                code_score += 1
        for ext in code_extensions:
            if ext in query_lower:
                code_score += 2  # File extension is strong signal

        # Check for doc indicators
        doc_score = 0
        for kw in doc_keywords:
            if kw in query_lower:
                doc_score += 1

        # Check for file path patterns (strong code signal)
        import re

        if re.search(r"[a-zA-Z0-9_/\\]+\.[a-zA-Z]{2,4}\b", query):
            code_score += 3
        if re.search(r"\b(def|class|function|method|func)\s+\w+", query):
            code_score += 3

        # Classify
        threshold = float(os.environ.get("NEURALMIND_INTENT_THRESHOLD", "0.6"))
        if code_score > doc_score * (1 + threshold):
            return "code"
        if doc_score > code_score * (1 + threshold):
            return "docs"
        return "hybrid"

    def _apply_intent_boost(self, results: list[dict], intent: str) -> list[dict]:
        """Apply type-aware boost based on query intent."""
        if intent == "hybrid":
            return results

        # Boost factors (configurable via env vars)
        code_boost = float(os.environ.get("NEURALMIND_CODE_BOOST", "3.0"))
        doc_boost = float(os.environ.get("NEURALMIND_DOC_BOOST", "2.0"))
        for result in results:
            meta = result.get("metadata", {})
            file_type = meta.get("file_type", "")
            source_file = meta.get("source_file", "")

            # Determine if node is code or doc (mutually exclusive)
            is_doc = file_type in ("rationale", "document") or source_file.endswith(
                (".md", ".markdown", ".txt", ".rst", ".org")
            )
            is_code = not is_doc and (file_type == "code" or bool(source_file))

            if intent == "code":
                if is_code:
                    result["score"] = result.get("score", 0) * code_boost
                    result["_intent_boost"] = code_boost
                else:
                    result["score"] = result.get("score", 0) * 0.5
                    result["_intent_boost"] = 0.5
            elif intent == "docs":
                if is_doc:
                    result["score"] = result.get("score", 0) * doc_boost
                    result["_intent_boost"] = doc_boost
                else:
                    result["score"] = result.get("score", 0) * 0.7
                    result["_intent_boost"] = 0.7

        # Re-rank by boosted score
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return results

    def get_l3_search(self, query: str, n: int = 4) -> tuple[str, int]:
        """
        Layer 3: Deep semantic search results.
        Applies live synapse co-activation boosts when the graph is warm.
        Applies type-aware re-ranking based on query intent.

        Returns:
            Tuple of (search_results_text, number of hits)
        """
        results = self._fetch_search(query, n=n)

        if not results:
            return "", 0

        # Fold in the static structural graph first: pull a query hit's
        # callers/callees/base classes into contention (precise, day-one
        # wiring). Runs before the synapse boost so structure claims a
        # displacement slot, then learned association re-ranks what remains.
        results = self._apply_structural_expansion(results)

        # Fold in the live synapse graph: results the agent has historically
        # co-activated with this query's top hits get a relevance nudge, so
        # learned association — not just vector similarity — shapes ranking.
        results = self._apply_synapse_boost(results)

        # Apply type-aware re-ranking based on query intent
        intent = self._detect_intent(query)
        results = self._apply_intent_boost(results, intent)

        # Apply adversarial retrieval enhancements:
        # 1. Re-classify intent (how-implement → code intent)
        # 2. Code-signal boost for implementation queries
        # 3. Synapse-seeded expansion for co-implemented neighbors
        #
        # Both passes below *grow* the hit list — synapse-seeded expansion
        # returns ``existing + new`` and the two-pass source search appends its
        # matches. They exist to re-rank implementation files into view, not to
        # enlarge the payload, so the count is held flat across the block and
        # extra hits have to displace weaker ones on score. Letting it grow
        # pushed L3 to its token cap: v3.9.0 shipped +22% tokens per query, and
        # because the faithfulness A/B scores NeuralMind against a
        # *matched-budget* naive baseline, a fatter slice hands that baseline
        # the same fatter budget (naive recall 0.532 → 0.621, delta +0.041 →
        # -0.065).
        _pre_enhancement_hits = len(results)
        # v3.9.0's adversarial-retrieval pass is opt-in until it clears the
        # faithfulness gate on its own merits. As shipped it was net-negative
        # on the A/B (18 queries: +1 improved, 3 regressed) and inflated the
        # slice 22%, which is what took the gate from +0.041 to -0.065. The
        # code and its tests stay; set NEURALMIND_ADVERSARIAL_RETRIEVAL=1 to
        # enable it. See docs/releases/RELEASE_NOTES_v3.9.0.md.
        if _adversarial_retrieval_enabled():
            try:
                from .retrieval_enhancement import (
                    apply_code_signal_boost,
                    extract_code_identifiers,
                    synapse_seeded_expansion,
                )
                from .retrieval_enhancement import (
                    classify_intent as _enhanced_classify_intent,
                )

                corrected_intent = _enhanced_classify_intent(
                    query,
                    existing_code_keywords=[
                        "implement",
                        "function",
                        "class",
                        "method",
                        "code",
                        "source",
                        "file",
                        "module",
                        "component",
                        "handler",
                        "service",
                        "controller",
                        "model",
                        "route",
                        "endpoint",
                        "api",
                        "config",
                        "constant",
                        "type",
                        "interface",
                        "schema",
                    ],
                    existing_doc_keywords=[
                        "explain",
                        "what is",
                        "how does",
                        "documentation",
                        "readme",
                        "guide",
                        "tutorial",
                        "why",
                        "when should",
                        "concept",
                        "overview",
                        "architecture",
                        "design",
                        "pattern",
                        "principle",
                        "best practice",
                        "introduction",
                    ],
                )

                identifiers = extract_code_identifiers(query)

                # Apply code-signal boost for code-intent queries
                if corrected_intent == "code" and identifiers:
                    results = apply_code_signal_boost(results, identifiers)

                # Apply synapse-seeded expansion
                if self.synapse_recall is not None and identifiers:
                    store = getattr(self, "_synapse_store", None)
                    if store is not None:
                        results = synapse_seeded_expansion(store, query, results, max_expansions=3)

                # Re-apply intent boost with corrected intent (BEFORE two-pass retrieval)
                # This ensures docstrings are penalized before we add implementation files
                if corrected_intent != intent and corrected_intent != "hybrid":
                    results = self._apply_intent_boost(results, corrected_intent)

                # Apply two-pass retrieval for code-intent queries (AFTER intent boost)
                # This surfaces implementation files that vector search misses
                if corrected_intent == "code" and identifiers and self.embedder is not None:
                    try:
                        from .retrieval_enhancement import (
                            _extract_code_snippet,
                            _search_source_files,
                        )

                        source_results = _search_source_files(self.embedder, identifiers, top_k=5)
                        if source_results:
                            # For source file matches, extract code snippets
                            for sr in source_results:
                                snippet = _extract_code_snippet(
                                    self.embedder, sr.get("id", ""), identifiers
                                )
                                if snippet:
                                    sr["document"] = (
                                        snippet  # Replace generic document with actual code snippet
                                    )
                                # Boost implementation file scores ABOVE docstrings with synapse boost
                                # Docstrings get ~3.75 (1.0 base + 2.25 synapse), so we need >4.0
                                sr["score"] = max(sr.get("score", 0.5), 4.5)

                            # Merge source file results, avoiding duplicates
                            existing_ids = {r.get("id") for r in results}
                            for sr in source_results:
                                if sr.get("id") not in existing_ids:
                                    results.append(sr)
                                    existing_ids.add(sr.get("id"))

                            # Re-sort by score after adding two-pass results
                            results.sort(key=lambda r: r.get("score", 0), reverse=True)

                            # Option B: Apply additional boost to code results after two-pass.
                            # Two-pass results are hardcoded at 4.5, but docstrings in code files
                            # get misclassified as code by _apply_intent_boost and receive 3x+synapse.
                            # Give all code results an extra 2x to ensure implementation files win.
                            if corrected_intent == "code":
                                for r in results:
                                    is_code = r.get("metadata", {}).get("file_type") == "code"
                                    is_doc = r.get("metadata", {}).get("file_type") in (
                                        "rationale",
                                        "document",
                                    )
                                    if is_code and not is_doc:
                                        r["score"] = r.get("score", 1.0) * 2.0
                                results.sort(key=lambda r: r.get("score", 0), reverse=True)
                    except Exception:
                        pass

            except Exception:
                pass  # Fail open — use unenhanced results

        # Hold the slice flat: enhancement re-ranks, it does not enlarge.
        # Sort before slicing — synapse_seeded_expansion returns ``existing +
        # new`` without re-ordering, and the only other sorts in the block are
        # conditional on corrected_intent, so on a query whose intent is
        # unchanged and not "code" nothing re-orders and a positional slice
        # would drop exactly the appended hits. Ranking here is what actually
        # makes the extra hits compete rather than be discarded.
        if _pre_enhancement_hits and len(results) > _pre_enhancement_hits:
            results.sort(key=lambda r: r.get("score", 0), reverse=True)
            results = results[:_pre_enhancement_hits]

        # Stash the post-boost hits so ContextResult.top_search_hits (and the
        # relevance sidecar built from it) carry the same synapse_boost /
        # recalled signals — and any recall-swapped-in nodes — that the
        # rendered L3 context shows, not the pre-boost vector cache.
        self._last_l3_boosted = results

        if self._trace is not None:
            self._trace.record_hits(results)

        parts = ["## Search Results", ""]

        for i, result in enumerate(results, 1):
            meta = result.get("metadata", {})
            score = result.get("score", 0)
            synapse = result.get("_synapse_boost", 0.0)
            structural = result.get("_structural_boost", 0.0)

            # Show synapse / structural boosts in the label when applied.
            synapse_label = f" (+{synapse:.2f} synapse)" if synapse > 0 else ""
            structural_label = f" (+{structural:.2f} structural)" if structural > 0 else ""
            if result.get("_structural_recalled"):
                recalled_label = " [wired]"
            elif result.get("_synapse_recalled"):
                recalled_label = " [recalled]"
            else:
                recalled_label = ""

            parts.append(
                f"{i}. **{meta.get('label', 'unknown')}**{recalled_label} "
                f"(score: {score:.2f}{structural_label}{synapse_label})"
            )
            parts.append(f"   Type: {meta.get('file_type', 'unknown')}")
            parts.append(f"   File: {meta.get('source_file', 'unknown')}")
            snippet = result.get("document", "")[:150]
            if snippet:
                parts.append(f'   "{snippet}"')
            parts.append("")

        context = self._truncate_to_tokens("\n".join(parts), self._l3_max_tokens)
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
            # Reset the boosted-hit snapshot; get_l3_search repopulates it.
            self._last_l3_boosted = []

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

        # Surface the search hits so downstream layers (synapses, MCP
        # responses, the relevance sidecar) can reuse them instead of
        # re-querying the embedder. Prefer the post-boost L3 hits (carrying
        # synapse_boost / recalled signals); fall back to the pre-boost vector
        # cache when L3 didn't run this call.
        top_hits: list[dict] = []
        if query:
            boosted = getattr(self, "_last_l3_boosted", None)
            top_hits = list(boosted) if boosted else list(self._query_search_cache.get(query, []))

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
        self, query: str, trace: bool = False, trace_verbose: bool = False, query_type: str = "auto"
    ) -> ContextResult:
        """
        Get full context for a specific query.
        Use this when answering a question about the codebase.

        With ``trace=True``, records a per-layer retrieval trace.

        Args:
            query: Natural language query
            trace: If True, attach a per-layer retrieval trace
            trace_verbose: If True (with trace), keep full candidate/hit lists
            query_type: Filter results — 'code', 'docs', or 'auto' (default)

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
            # Apply type-aware re-ranking based on query intent
            if query_type != "auto":
                intent = self._detect_intent(query)
                result.top_search_hits = self._apply_intent_boost(result.top_search_hits, intent)
            if self._trace is not None:
                result.trace = self._trace.to_dict()
            return result
        finally:
            self._trace = None
