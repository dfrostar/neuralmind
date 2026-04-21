"""
hybrid_context.py — Hybrid Retrieval vs Long-Context Strategy
=============================================================

Intelligently chooses between:
1. NeuralMind retrieval (~800 tokens, fast, cheap)
2. Long-context with full code (~50K tokens, slow, expensive)
3. Hybrid (optimized context + full codebase fallback)

Why this matters:
- Token prices dropped 80% (2024-2025)
- Context windows grew 20,000x (512 → 10M tokens)
- BUT latency is still 1s for RAG vs 30-60s for long-context
- AND "lost in the middle" problem persists (accuracy drops 10-20%)

NeuralMind stays competitive by:
- Being the *fast* option (1s vs 30-60s)
- Being the *accurate* option (no lost-in-middle)
- Being the *cost-flexible* option (user chooses)

Configuration:
  [context]
  strategy = "hybrid"  # "retrieval", "long-context", or "hybrid"

  [context.retrieval]
  enabled = true
  max_tokens = 1500

  [context.long_context]
  enabled = true
  max_tokens = 50000
  include_full_codebase = false

  [context.hybrid]
  auto_switch_threshold = 0.8  # If confidence < 80%, augment with more context
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .context_selector import ContextResult


class ContextStrategy(Enum):
    """Context retrieval strategy."""

    RETRIEVAL = "retrieval"  # NeuralMind only
    LONG_CONTEXT = "long_context"  # Full codebase
    HYBRID = "hybrid"  # Smart combination


@dataclass
class ContextMetrics:
    """Metrics about retrieved context."""

    confidence: float  # 0.0-1.0, how confident in answer?
    relevance: float  # 0.0-1.0, are results relevant?
    coverage: float  # 0.0-1.0, how much of the answer space covered?
    latency_ms: float  # How long did retrieval take?


@dataclass
class HybridContextConfig:
    """Configuration for hybrid context strategy."""

    strategy: ContextStrategy = ContextStrategy.HYBRID
    auto_switch_enabled: bool = True
    auto_switch_threshold: float = 0.75  # If confidence < 75%, expand context
    max_retrieval_tokens: int = 1500
    max_long_context_tokens: int = 50000


class HybridContextSelector:
    """Intelligently select context strategy."""

    def __init__(self, config: HybridContextConfig | None = None):
        """
        Initialize hybrid context selector.

        Args:
            config: Context configuration
        """
        self.config = config or HybridContextConfig()

    def evaluate_retrieval_result(
        self, result: ContextResult
    ) -> ContextMetrics:
        """
        Evaluate quality of retrieval results.

        Returns metrics to decide if we need more context.
        """
        # Confidence: based on reduction ratio and coverage
        # Higher reduction = higher confidence (we're very targeted)
        # Lower reduction = lower confidence (had to load lots)
        confidence = min(1.0, result.reduction_ratio / 50.0)

        # Relevance: based on search hit scores
        # If search found relevant results, confidence is high
        relevance = min(1.0, result.search_hits / 10.0)

        # Coverage: rough estimate based on layers loaded
        # More layers = more coverage
        layers_count = len(result.layers_used) if hasattr(result, "layers_used") else 0
        coverage = min(1.0, layers_count / 4.0)

        return ContextMetrics(
            confidence=confidence,
            relevance=relevance,
            coverage=coverage,
            latency_ms=0.0,  # Would be populated by caller
        )

    def should_augment_context(self, metrics: ContextMetrics) -> bool:
        """
        Decide if we should augment context with more data.

        Returns True if confidence is too low and we should load more.
        """
        if not self.config.auto_switch_enabled:
            return False

        # If confidence is too low, load more context
        return metrics.confidence < self.config.auto_switch_threshold

    def suggest_strategy(self, metrics: ContextMetrics) -> ContextStrategy:
        """
        Suggest best strategy based on metrics.

        Returns the recommended strategy.
        """
        if metrics.confidence > 0.9:
            # High confidence: use fast retrieval
            return ContextStrategy.RETRIEVAL

        if metrics.confidence > 0.6:
            # Medium confidence: hybrid approach
            return ContextStrategy.HYBRID

        # Low confidence: load full context
        return ContextStrategy.LONG_CONTEXT

    def build_hybrid_context(
        self,
        retrieval_result: ContextResult,
        full_codebase: str,
    ) -> tuple[str, dict[str, Any]]:
        """
        Build hybrid context combining retrieval + long-context fallback.

        Strategy:
        1. Start with NeuralMind retrieval (~800 tokens)
        2. If confidence low, add "summary" layer with full architecture
        3. If very low, add full codebase with caveat about lost-in-middle

        Returns:
            (context_string, metadata)
        """
        metrics = self.evaluate_retrieval_result(retrieval_result)

        if metrics.confidence > 0.8:
            # Just use retrieval result
            return (
                retrieval_result.context,
                {
                    "strategy": "retrieval",
                    "confidence": metrics.confidence,
                    "tokens": retrieval_result.tokens,
                },
            )

        # Build hybrid context
        parts = [retrieval_result.context]

        if metrics.confidence < 0.75:
            # Add a note about potential coverage
            parts.append(
                "\n---\n"
                "Note: Limited context retrieved. If the answer above seems incomplete, "
                "the full codebase is available but may have 'lost in the middle' effects "
                "(accuracy drops for mid-document information). Consider:\n"
                "- Asking a more specific question\n"
                "- Using neuralmind skeleton <file> for file structure\n"
                "- Or reviewing full source with NEURALMIND_BYPASS=1\n"
                "---\n"
            )

        if metrics.confidence < 0.6:
            # Append start of full codebase with warning
            full_codebase_truncated = full_codebase[: self.config.max_long_context_tokens]
            parts.append(
                "\n\nFull Codebase (truncated, may have accuracy degradation with long context):\n"
            )
            parts.append(full_codebase_truncated)

        context_string = "\n".join(parts)

        return (
            context_string,
            {
                "strategy": "hybrid",
                "confidence": metrics.confidence,
                "retrieval_tokens": retrieval_result.tokens,
                "augmented_with_full_context": metrics.confidence < 0.6,
            },
        )


# ============================================================================
# LLM Cost Comparison Helper
# ============================================================================


@dataclass
class CostEstimate:
    """Cost estimate for a query."""

    retrieval_cost: float  # Using NeuralMind
    long_context_cost: float  # Using full codebase
    time_estimate_retrieval_s: float
    time_estimate_long_context_s: float
    recommended_strategy: ContextStrategy
    savings_percent: float  # % savings with retrieval


def estimate_query_cost(
    retrieval_tokens: int,
    full_context_tokens: int,
    input_price_per_mtok: float = 0.05,  # $0.05 per 1M input tokens
    output_tokens: int = 500,
    output_price_per_mtok: float = 0.15,  # $0.15 per 1M output tokens
) -> CostEstimate:
    """
    Estimate costs for retrieval vs long-context.

    Args:
        retrieval_tokens: Tokens needed for NeuralMind retrieval
        full_context_tokens: Tokens for full codebase
        input_price_per_mtok: Input token price per 1M tokens
        output_tokens: Expected output tokens
        output_price_per_mtok: Output token price per 1M tokens

    Returns:
        CostEstimate with pricing and time estimates
    """
    # Calculate costs
    retrieval_input_cost = (retrieval_tokens / 1_000_000) * input_price_per_mtok
    retrieval_output_cost = (output_tokens / 1_000_000) * output_price_per_mtok
    retrieval_total = retrieval_input_cost + retrieval_output_cost

    long_context_input_cost = (full_context_tokens / 1_000_000) * input_price_per_mtok
    long_context_output_cost = (output_tokens / 1_000_000) * output_price_per_mtok
    long_context_total = long_context_input_cost + long_context_output_cost

    # Time estimates (rough heuristics)
    # RAG: 1s (local search) + 2s (LLM) = 3s total
    # Long-context: 30-60s (LLM processing)
    retrieval_time = 3.0
    long_context_time = 45.0

    # Recommendation
    if retrieval_total < long_context_total * 0.5:
        recommended = ContextStrategy.RETRIEVAL
    elif retrieval_total < long_context_total * 0.8:
        recommended = ContextStrategy.HYBRID
    else:
        recommended = ContextStrategy.LONG_CONTEXT

    savings = (1.0 - retrieval_total / long_context_total) * 100 if long_context_total > 0 else 0

    return CostEstimate(
        retrieval_cost=retrieval_total,
        long_context_cost=long_context_total,
        time_estimate_retrieval_s=retrieval_time,
        time_estimate_long_context_s=long_context_time,
        recommended_strategy=recommended,
        savings_percent=savings,
    )


def print_cost_analysis(estimate: CostEstimate) -> None:
    """Pretty-print cost analysis."""
    print("\n" + "=" * 70)
    print("CONTEXT STRATEGY COST ANALYSIS")
    print("=" * 70)
    print(f"\nNeuralMind Retrieval:")
    print(f"  Cost: ${estimate.retrieval_cost:.6f}")
    print(f"  Time: ~{estimate.time_estimate_retrieval_s:.0f}s")
    print(f"\nFull Long-Context:")
    print(f"  Cost: ${estimate.long_context_cost:.6f}")
    print(f"  Time: ~{estimate.time_estimate_long_context_s:.0f}s")
    print(f"\nSavings with Retrieval: {estimate.savings_percent:.0f}%")
    print(f"Recommended: {estimate.recommended_strategy.value}")
    print("=" * 70 + "\n")
