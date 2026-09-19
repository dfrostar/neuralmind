"""context_budget.py — Fixed-context budget management for NeuralMind.

Extends the L0-L3 progressive disclosure with lean-ctx-style budget
accounting: a fixed per-session token budget, proactive expansion of
relevant archived context, and budget warnings when approaching limits.

The budget is enforced at query time: if the assembled context would
exceed the budget, lower-priority layers are trimmed first (L3 search
results, then L2 on-demand modules), preserving the L0+L1 wake-up
context that the agent needs to orient itself.

Budget accounting is per-query, not cumulative — each query gets a fresh
budget. The session-level budget is tracked separately by the caller
(e.g., the agent's session manager) via the `SessionBudget` class.

Design:
- Fixed per-session context budget (default 8000 tokens, matching lean-ctx)
- Proactive expansion: inject relevant archived context into later tool
  responses when the query result is below budget
- Budget warnings: log when context exceeds 80% of budget
- Layer trimming: L3 → L2 → L1 → L0 (never trim L0 identity)
- Token counting: tiktoken with graceful fallback to char-based estimation
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Default budget (matches lean-ctx's 8000-token default)
DEFAULT_CONTEXT_BUDGET_TOKENS = 8000

# Proactive expansion defaults
DEFAULT_PROACTIVE_EXPANSION = True
DEFAULT_PROACTIVE_EXPANSION_BUDGET = 2000
DEFAULT_PROACTIVE_EXPANSION_MAX_AGE_SECS = 3600
DEFAULT_PROACTIVE_EXPANSION_THRESHOLD = 0.6

# Budget warning threshold (log when context exceeds this fraction)
BUDGET_WARNING_FRACTION = 0.8


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


def _env_bool(name: str, default: bool) -> bool:
    """Read a bool from the environment, falling back on unset/malformed."""
    val = os.environ.get(name, "").strip().lower()
    if val in ("1", "true", "yes", "on"):
        return True
    if val in ("0", "false", "no", "off"):
        return False
    return default


@dataclass
class BudgetConfig:
    """Configuration for context budget management."""

    budget_tokens: int = _env_int("NEURALMIND_CONTEXT_BUDGET_TOKENS", DEFAULT_CONTEXT_BUDGET_TOKENS)
    proactive_expansion: bool = _env_bool(
        "NEURALMIND_PROACTIVE_EXPANSION", DEFAULT_PROACTIVE_EXPANSION
    )
    proactive_expansion_budget_tokens: int = _env_int(
        "NEURALMIND_PROACTIVE_EXPANSION_BUDGET_TOKENS", DEFAULT_PROACTIVE_EXPANSION_BUDGET
    )
    proactive_expansion_max_age_secs: int = _env_int(
        "NEURALMIND_PROACTIVE_EXPANSION_MAX_AGE_SECS", DEFAULT_PROACTIVE_EXPANSION_MAX_AGE_SECS
    )
    proactive_expansion_threshold: float = _env_float(
        "NEURALMIND_PROACTIVE_EXPANSION_THRESHOLD", DEFAULT_PROACTIVE_EXPANSION_THRESHOLD
    )
    budget_warning_fraction: float = _env_float(
        "NEURALMIND_BUDGET_WARNING_FRACTION", BUDGET_WARNING_FRACTION
    )


@dataclass
class BudgetReport:
    """Report of budget usage for a single query."""

    budget_tokens: int
    used_tokens: int
    remaining_tokens: int
    fraction_used: float
    warning_issued: bool
    layers_trimmed: list[str] = field(default_factory=list)
    proactive_expansions: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "budget_tokens": self.budget_tokens,
            "used_tokens": self.used_tokens,
            "remaining_tokens": self.remaining_tokens,
            "fraction_used": self.fraction_used,
            "warning_issued": self.warning_issued,
            "layers_trimmed": self.layers_trimmed,
            "proactive_expansions": self.proactive_expansions,
            "timestamp": self.timestamp,
        }


@dataclass
class SessionBudget:
    """Track budget usage across multiple queries in a session.

    The session budget is a soft limit — it warns but does not block.
    Individual queries still get their own fresh budget from BudgetConfig.
    """

    config: BudgetConfig = field(default_factory=BudgetConfig)
    total_used_tokens: int = 0
    query_count: int = 0
    warning_count: int = 0
    max_tokens_seen: int = 0
    started_at: float = field(default_factory=time.time)

    def record_query(self, report: BudgetReport) -> None:
        """Record a query's budget usage."""
        self.total_used_tokens += report.used_tokens
        self.query_count += 1
        if report.warning_issued:
            self.warning_count += 1
        self.max_tokens_seen = max(self.max_tokens_seen, report.used_tokens)

    @property
    def average_tokens_per_query(self) -> float:
        if self.query_count == 0:
            return 0.0
        return self.total_used_tokens / self.query_count

    def to_dict(self) -> dict:
        return {
            "total_used_tokens": self.total_used_tokens,
            "query_count": self.query_count,
            "warning_count": self.warning_count,
            "max_tokens_seen": self.max_tokens_seen,
            "average_tokens_per_query": self.average_tokens_per_query,
            "elapsed_secs": time.time() - self.started_at,
        }


def count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """Count tokens in text using tiktoken, with char-based fallback.

    Falls back to len(text) // 4 (approximate chars-per-token for English)
    when tiktoken is not installed or the encoding is unavailable.
    """
    if not text:
        return 0
    try:
        import tiktoken

        try:
            enc = tiktoken.get_encoding(encoding_name)
        except Exception:
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        # Fallback: ~4 chars per token for English text
        return max(1, len(text) // 4)


def estimate_context_tokens(context: str) -> int:
    """Estimate the token count of an assembled context string."""
    return count_tokens(context)


def trim_context_to_budget(
    context: str,
    budget_tokens: int,
    layer_markers: dict[str, str] | None = None,
) -> tuple[str, list[str]]:
    """Trim context to fit within budget, removing lower-priority layers first.

    Layer priority (highest to lowest):
    - L0: Identity (project name, description) — never trimmed
    - L1: Summary (architecture, main components) — trimmed only if critical
    - L2: On-demand modules — trimmed before L1
    - L3: Search results — trimmed first

    Args:
        context: The assembled context string.
        budget_tokens: Maximum tokens allowed.
        layer_markers: Optional dict mapping layer names to marker strings
            that delimit each layer in the context. If provided, layers are
            split and reassembled in priority order.

    Returns:
        (trimmed_context, layers_trimmed) where layers_trimmed lists the
        layer names that were removed.
    """
    current_tokens = count_tokens(context)
    if current_tokens <= budget_tokens:
        return context, []

    layers_trimmed: list[str] = []

    if layer_markers:
        # Split context by layer markers
        sections: list[tuple[str, str]] = []  # (layer_name, content)
        remaining = context
        for layer_name, marker in layer_markers.items():
            if marker in remaining:
                parts = remaining.split(marker, 1)
                if len(parts) == 2:
                    sections.append((layer_name, parts[1]))
                    remaining = parts[0]

        # Priority order: L3 first (trim search results), then L2, then L1
        priority_order = ["L3", "L2", "L1"]

        for layer in priority_order:
            if current_tokens <= budget_tokens:
                break
            for i, (name, content) in enumerate(sections):
                if name == layer and content.strip():
                    # Remove this layer
                    sections[i] = (name, "")
                    layers_trimmed.append(layer)
                    # Reassemble
                    context = "".join(content for _, content in sections)
                    current_tokens = count_tokens(context)
                    break

    # If still over budget, truncate from the end (L3 search results)
    if current_tokens > budget_tokens:
        # Binary search for the truncation point
        low, high = 0, len(context)
        while low < high:
            mid = (low + high + 1) // 2
            if count_tokens(context[:mid]) <= budget_tokens:
                low = mid
            else:
                high = mid - 1
        context = context[:low]
        if "L3" not in layers_trimmed:
            layers_trimmed.append("L3")

    return context, layers_trimmed


def check_budget_warning(
    used_tokens: int, budget_tokens: int, warning_fraction: float = BUDGET_WARNING_FRACTION
) -> bool:
    """Check if budget usage exceeds the warning threshold.

    Returns True if a warning should be issued.
    """
    return used_tokens >= budget_tokens * warning_fraction


def format_budget_report(report: BudgetReport) -> str:
    """Format a budget report for logging/display."""
    return (
        f"[context_budget] used={report.used_tokens}/{report.budget_tokens} "
        f"({report.fraction_used:.0%}) remaining={report.remaining_tokens} "
        f"trimmed={report.layers_trimmed} expansions={report.proactive_expansions}"
    )
