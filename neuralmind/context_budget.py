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


# The header each layer of an assembled context starts with. L0 (identity)
# is whatever precedes the first of them.
LAYER_HEADERS: dict[str, str] = {
    "L1": "## Architecture Overview",
    "L2": "## Relevant Code Areas",
    "L3": "## Search Results",
}

# Trimmed first to last. L0 is never trimmed.
TRIM_ORDER: tuple[str, ...] = ("L3", "L2", "L1")


def _find_line_start(text: str, marker: str, start: int) -> int:
    """Index of the first ``marker`` at or after ``start`` that begins a line."""
    pos = text.find(marker, start)
    while pos > 0 and text[pos - 1] != "\n":
        pos = text.find(marker, pos + 1)
    return pos


def split_layers(
    context: str, layer_markers: dict[str, str] | None = None
) -> list[tuple[str, str]]:
    """Split an assembled context into ``(layer, text)`` sections, in order.

    Each marker (default :data:`LAYER_HEADERS`) begins the first line of its
    layer; the text before the first marker found is ``L0``. Markers are
    looked for in the order given, each after the one before it. Joining the
    texts with a newline gives back ``context``.
    """
    markers = LAYER_HEADERS if layer_markers is None else layer_markers
    cuts: list[tuple[str, int]] = []
    start = 0
    for layer, marker in markers.items():
        pos = _find_line_start(context, marker, start) if marker else -1
        if pos >= 0:
            cuts.append((layer, pos))
            start = pos + len(marker)
    sections: list[tuple[str, str]] = []
    layer, begin = "L0", 0
    for next_layer, pos in cuts:
        if pos > 0:
            sections.append((layer, context[begin : pos - 1]))  # drop the joining newline
        layer, begin = next_layer, pos
    sections.append((layer, context[begin:]))
    return sections


def _join_layers(sections: list[tuple[str, str]]) -> str:
    return "\n".join(text for _, text in sections)


def _shrink_section(sections: list[tuple[str, str]], i: int, fits) -> list[tuple[str, str]]:
    """``sections`` with section ``i`` cut to the most whole lines that fit.

    A section cut back to its header line alone is emptied (dropped).
    """
    name, text = sections[i]
    lines = text.split("\n")

    def with_lines(k: int) -> list[tuple[str, str]]:
        kept = "\n".join(lines[:k]).rstrip("\n")
        if not any(line.strip() for line in lines[1:k]):
            kept = ""  # a header with nothing under it says nothing
        return [*sections[:i], (name, kept), *sections[i + 1 :]]

    lo, hi = 0, len(lines)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if fits(with_lines(mid)):
            lo = mid
        else:
            hi = mid - 1
    return with_lines(lo)


def fit_layers(
    sections: list[tuple[str, str]],
    budget_tokens: int,
    *,
    order: tuple[str, ...] = TRIM_ORDER,
    render=None,
) -> tuple[list[tuple[str, str]], list[str]]:
    """Trim ``(layer, text)`` sections until ``render(sections)`` fits the budget.

    The layers named in ``order`` are trimmed in that order, each from its end
    and at whole lines, before the next one is touched; a layer cut back to
    its header line alone is dropped. Any other layer (L0) is never trimmed,
    so the result can still exceed a budget that L0 alone exceeds.
    ``render`` joins the sections into the context (default: newline-joined).

    Returns:
        (kept sections in their original order, layers trimmed in the order
        they were trimmed).
    """
    render = render or _join_layers

    def fits(candidate: list[tuple[str, str]]) -> bool:
        return count_tokens(render(candidate)) <= budget_tokens

    secs = [(name, text) for name, text in sections if text]
    trimmed: list[str] = []
    for layer in order:
        for i in range(len(secs) - 1, -1, -1):
            if fits(secs):
                break
            if secs[i][0] == layer:
                secs = _shrink_section(secs, i, fits)
                if layer not in trimmed:
                    trimmed.append(layer)
        secs = [(name, text) for name, text in secs if text]
    return secs, trimmed


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

    Each layer is trimmed from its end at whole lines, and dropped once only
    its header would be left; what remains is returned in L0 → L3 order. A
    context whose L0 alone exceeds the budget is returned as L0.

    Args:
        context: The assembled context string.
        budget_tokens: Maximum tokens allowed.
        layer_markers: Optional dict mapping layer names (``L1``/``L2``/``L3``)
            to the line each layer starts with; the text before the first of
            them is L0. Defaults to :data:`LAYER_HEADERS`, the headers
            NeuralMind's own context uses. A context with none of the
            markers has no layers to drop and is cut at the budget.

    Returns:
        (trimmed_context, layers_trimmed) where layers_trimmed lists the
        layers that were cut or removed, in the order they were trimmed.
    """
    current_tokens = count_tokens(context)
    if current_tokens <= budget_tokens:
        return context, []

    sections = split_layers(context, layer_markers)
    if any(name != "L0" for name, _ in sections):
        kept, layers_trimmed = fit_layers(sections, budget_tokens)
        return _join_layers(kept), layers_trimmed

    # No layer structure: truncate from the end.
    low, high = 0, len(context)
    while low < high:
        mid = (low + high + 1) // 2
        if count_tokens(context[:mid]) <= budget_tokens:
            low = mid
        else:
            high = mid - 1
    return context[:low], ["L3"]


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
