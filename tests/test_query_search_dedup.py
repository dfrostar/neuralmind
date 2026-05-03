"""Regression tests for the per-query search dedup in ContextSelector.

Each call to ``mind.query()`` should hit ``embedder.search`` exactly
once now that the selector caches results across L2, L3, hybrid
highlights, and synapse reinforcement. Earlier versions did three
separate searches per query.
"""

from __future__ import annotations

from neuralmind.context_selector import ContextResult, ContextSelector, TokenBudget


class _CountingEmbedder:
    """Embedder stub that counts search calls and returns canned hits."""

    project_path = None

    def __init__(self, hits=None):
        self._hits = hits or [
            {"id": f"node_{i}", "metadata": {"label": f"node_{i}", "community": i % 3}, "score": 1.0 - i * 0.1}
            for i in range(10)
        ]
        self.search_calls = 0

    def search(self, query, n=10, **kwargs):
        self.search_calls += 1
        return self._hits[:n]

    def get_stats(self):
        return {"total_nodes": len(self._hits), "communities": 3, "community_distribution": {}}

    def get_community_summary(self, community_id, max_nodes=10):
        return {
            "type_summary": "stub",
            "nodes": [{"label": f"c{community_id}_{i}", "file_type": "function", "source_file": ""} for i in range(3)],
        }

    def load_graph(self):
        return True

    def embed_nodes(self, force=False):
        return {"added": 0, "updated": 0, "skipped": 0}


def test_get_query_context_makes_one_search(tmp_path):
    embedder = _CountingEmbedder()
    selector = ContextSelector(embedder, str(tmp_path), enable_reranking=False)
    selector.get_query_context("How does authentication work?")
    assert embedder.search_calls == 1, (
        f"selector should issue exactly one search per query; saw {embedder.search_calls}"
    )


def test_top_search_hits_surface_on_result(tmp_path):
    embedder = _CountingEmbedder()
    selector = ContextSelector(embedder, str(tmp_path), enable_reranking=False)
    result = selector.get_query_context("any prompt")
    assert isinstance(result.top_search_hits, list)
    assert len(result.top_search_hits) > 0
    # IDs from the canned embedder must be present.
    ids = [h["id"] for h in result.top_search_hits]
    assert ids[0] == "node_0"


def test_cache_clears_between_queries(tmp_path):
    embedder = _CountingEmbedder()
    selector = ContextSelector(embedder, str(tmp_path), enable_reranking=False)
    selector.get_query_context("first")
    selector.get_query_context("second")
    # One per query — never zero, never bleed-through.
    assert embedder.search_calls == 2


def test_wakeup_does_not_search(tmp_path):
    embedder = _CountingEmbedder()
    selector = ContextSelector(embedder, str(tmp_path), enable_reranking=False)
    selector.get_wakeup_context()
    # Wakeup is L0 + L1 only; no query, so no search.
    assert embedder.search_calls == 0


def test_context_result_default_top_hits_is_empty():
    # ContextResult must default to an empty list so existing callers
    # that don't pass top_search_hits still work.
    r = ContextResult(context="", budget=TokenBudget())
    assert r.top_search_hits == []
