"""
reranker.py — Cooccurrence-Based Semantic Reranking
====================================================

Analyzes learned module cooccurrence patterns and reranks search results
to prioritize modules that frequently appear together in similar queries.

This implements the active learning stage of brain-like learning:
- Collection (v0.3.0): Memory logs queries + retrieved modules
- Learning (v0.3.2): Analyzes cooccurrence patterns
- Reranking (v0.3.2): Applies patterns to improve retrieval
"""

import json
from pathlib import Path
from typing import Any


class CooccurrenceIndex:
    """
    Loads and queries learned module cooccurrence patterns.

    Patterns are stored as JSON with module pairs and their cooccurrence counts.
    Example: {"auth|validation": 5, "db|cache": 3, ...}
    """

    def __init__(self):
        """Initialize empty index."""
        self.cooccurrence: dict[str, int] = {}
        self.module_frequency: dict[str, int] = {}
        self.metadata: dict[str, Any] = {}
        self._is_valid = False

    @classmethod
    def load(cls, path: Path | str) -> "CooccurrenceIndex":
        """
        Load learned patterns from JSON file.

        Args:
            path: Path to learned_patterns.json

        Returns:
            CooccurrenceIndex instance (empty if file not found/invalid)
        """
        index = cls()

        try:
            path = Path(path)
            if not path.exists():
                return index

            with open(path) as f:
                data = json.load(f)

            index.cooccurrence = data.get("cooccurrence", {})
            index.module_frequency = data.get("module_frequency", {})
            index.metadata = data.get("metadata", {})
            index._is_valid = len(index.cooccurrence) > 0

        except Exception:
            # Graceful failure: return empty index
            pass

        return index

    def score_pair(self, module_a: str, module_b: str) -> float:
        """
        Get normalized cooccurrence score for two modules.

        Score is normalized to 0-1 based on max cooccurrence count.

        Args:
            module_a: Module identifier
            module_b: Module identifier

        Returns:
            Float 0-1 representing cooccurrence strength
        """
        if not self._is_valid:
            return 0.0

        # Canonicalize pair (order doesn't matter)
        pair = "|".join(sorted([module_a, module_b]))
        count = self.cooccurrence.get(pair, 0)

        if not count:
            return 0.0

        # Normalize to 0-1 range
        max_count = max(self.cooccurrence.values()) if self.cooccurrence else 1
        return min(count / max(max_count, 1), 1.0)

    def get_top_cooccurrences(
        self, module: str, n: int = 5
    ) -> list[tuple[str, float]]:
        """
        Get modules that most frequently co-occur with a given module.

        Args:
            module: Module identifier
            n: Number of results to return

        Returns:
            List of (module_id, score) tuples sorted by score descending
        """
        if not self._is_valid:
            return []

        related: dict[str, float] = {}

        # Find all pairs involving this module
        for pair_str, count in self.cooccurrence.items():
            parts = pair_str.split("|")
            if len(parts) != 2:
                continue

            module_x, module_y = parts
            if module_x == module:
                related[module_y] = count
            elif module_y == module:
                related[module_x] = count

        # Normalize and sort
        max_count = max(related.values()) if related else 1
        scored = [
            (mod, count / max(max_count, 1)) for mod, count in related.items()
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        return scored[:n]

    def is_valid(self) -> bool:
        """Check if index has learned patterns."""
        return self._is_valid

    def pattern_count(self) -> int:
        """Get number of learned patterns."""
        return len(self.cooccurrence)


class SemanticReranker:
    """
    Applies learned module patterns to rerank semantic search results.

    Reranking works by:
    1. Scoring each result based on cooccurrence with other retrieved modules
    2. Boosting results that relate to already-selected context
    3. Re-sorting by combined semantic + learned score
    """

    def __init__(self, cooccurrence_index: CooccurrenceIndex | None = None):
        """
        Initialize reranker with optional learned patterns.

        Args:
            cooccurrence_index: Patterns to use for reranking (optional)
        """
        self.index = cooccurrence_index or CooccurrenceIndex()
        self.enabled = self.index.is_valid()

    def rerank(
        self,
        results: list[dict[str, Any]],
        context_modules: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Rerank search results using learned patterns.

        Applies boost factor to results based on cooccurrence with context.

        Args:
            results: List of search results from embedder.search()
                    Expected keys: id, text, metadata, distance/score
            context_modules: Optional list of modules already selected (from L0/L1/L2)

        Returns:
            Reranked list of results (or original if no patterns available)
        """
        if not self.enabled or not results:
            return results

        context_modules = context_modules or []

        # Extract module IDs from results
        result_modules: dict[int, str] = {}
        for i, result in enumerate(results):
            # Try to extract module from metadata or ID
            mod = self._extract_module_id(result)
            if mod:
                result_modules[i] = mod

        if not result_modules:
            return results

        # Compute boost for each result
        boosts: dict[int, float] = {}
        for i, module in result_modules.items():
            boost = 0.0

            # Boost for cooccurrence with context modules
            for ctx_module in context_modules:
                score = self.index.score_pair(module, ctx_module)
                boost = max(boost, score)

            # Boost for cooccurrence with other results
            for j, other_module in result_modules.items():
                if i != j:
                    score = self.index.score_pair(module, other_module)
                    boost = max(boost, score)

            boosts[i] = boost

        # Rerank: combine semantic score with learned boost
        reranked = []
        for i, result in enumerate(results):
            boost = boosts.get(i, 0.0)
            # Existing score (from embedder): use 'distance' or 'score' key
            original_score = result.get("distance") or result.get("score", 0.5)

            # Combined score: boost amplifies semantic relevance
            # Boost range is 0-1, so combined score is 1.0-2.0x original
            combined_score = original_score * (1.0 + 0.3 * boost)

            # Store boost for debugging if needed
            result["_reranker_boost"] = boost
            result["_combined_score"] = combined_score
            reranked.append(result)

        # Sort by combined score (higher is better for distance, lower for similarity)
        # Assume distance metric (higher distance = lower relevance)
        reranked.sort(key=lambda r: r.get("_combined_score", 0))

        return reranked

    def measure_savings(
        self, original_results: list[dict], reranked_results: list[dict]
    ) -> dict[str, Any]:
        """
        Measure token impact of reranking.

        Estimates how many tokens could be saved by using top results from reranked order.

        Args:
            original_results: Original semantic search results
            reranked_results: After reranking

        Returns:
            Dict with estimated token delta
        """
        if not original_results or not reranked_results:
            return {"estimated_savings_tokens": 0, "estimated_savings_pct": 0.0}

        # Simplified metric: if top result changed to a more relevant one
        original_top = original_results[0] if original_results else None
        reranked_top = reranked_results[0] if reranked_results else None

        boost_applied = False
        if original_top and reranked_top:
            original_id = original_top.get("id")
            reranked_id = reranked_top.get("id")
            boost_applied = original_id != reranked_id

        # Rough estimate: better ranking saves ~50-100 tokens per result
        if boost_applied:
            return {
                "estimated_savings_tokens": 75,
                "estimated_savings_pct": 0.1,
                "reason": "Top result reranked to higher relevance",
            }

        return {"estimated_savings_tokens": 0, "estimated_savings_pct": 0.0}

    @staticmethod
    def _extract_module_id(result: dict[str, Any]) -> str | None:
        """
        Extract module identifier from search result.

        Tries: metadata.source_file, metadata.community, id field

        Args:
            result: Search result dict from embedder

        Returns:
            Module ID or None
        """
        if not result:
            return None

        # Try metadata first
        metadata = result.get("metadata", {})
        if isinstance(metadata, dict):
            # Source file is most specific
            source = metadata.get("source_file")
            if source:
                return str(source)

            # Community is also useful
            community = metadata.get("community")
            if community is not None:
                return f"community_{community}"

        # Fall back to ID
        result_id = result.get("id")
        if result_id:
            return str(result_id)

        return None
