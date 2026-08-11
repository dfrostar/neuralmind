"""query_handler.py — Query, wakeup, search, and highlight operations.

Extracted from NeuralMind to separate the read-side query pipeline
from the build/ingest orchestration.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .context_selector import ContextResult

logger = logging.getLogger(__name__)


class QueryHandler:
    """Handles query, wakeup, search, and highlight operations."""

    def __init__(self, mind) -> None:
        self._mind = mind

    def wakeup(self) -> "ContextResult":
        """Generate wake-up context for a new session."""
        from .context_selector import ContextResult
        selector = self._mind.selector
        if selector is None:
            return ContextResult(context="", tokens=0, reduction_ratio=1.0, hits=[])
        return selector.wakeup()

    def search(self, query: str, n: int = 10, **filters) -> list[dict]:
        """Search the index for matching nodes."""
        if self._mind.embedder is None:
            return []
        try:
            return self._mind.embedder.search(query, n=n, **filters)
        except Exception:
            logger.debug("search failed", exc_info=True)
            return []

    def skeleton(self, file_path: str) -> str:
        """Get the skeleton view of a file."""
        return self._mind.querying.skeleton(self._mind, file_path)

    def build_hybrid_highlights(self, question: str, cached_hits: list[dict] | None = None) -> str:
        """Build hybrid highlights for a question."""
        return self._mind.querying.build_hybrid_highlights(self._mind, question, cached_hits)

    def query(self, question: str, **kwargs) -> "ContextResult":
        """Run a full query with synapse reinforcement."""
        from .context_selector import ContextResult
        from .querying import build_hybrid_highlights

        selector = self._mind.selector
        if selector is None:
            return ContextResult(context="", tokens=0, reduction_ratio=1.0, hits=[])

        # Get base result from selector
        result = selector.query(question, **kwargs)

        # Reinforce synapses if enabled
        if self._mind.synapse_client.has_store():
            try:
                self._mind._reinforce_from_query(question, result)
            except Exception:
                logger.debug("query reinforcement failed", exc_info=True)

        return result
