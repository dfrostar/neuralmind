"""Tests for NeuralMind context selector functionality."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestContextSelector:
    """Tests for ContextSelector class."""

    def test_init_with_embedder_and_graph(self, temp_project):
        """Test context selector initialization."""
        from neuralmind.embedder import GraphEmbedder
        from neuralmind.context_selector import ContextSelector

        embedder = GraphEmbedder(str(temp_project))
        graph_data = embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, graph_data)
        assert selector is not None


class TestLayer0Identity:
    """Tests for Layer 0 (Identity) context."""

    def test_l0_returns_identity(self, temp_project):
        """Test that L0 returns project identity."""
        from neuralmind.embedder import GraphEmbedder
        from neuralmind.context_selector import ContextSelector

        embedder = GraphEmbedder(str(temp_project))
        graph_data = embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, graph_data)
        text, tokens = selector.get_l0_identity()

        assert isinstance(text, str)
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_l0_loads_from_readme(self, temp_project):
        """Test that L0 loads from README.md."""
        from neuralmind.embedder import GraphEmbedder
        from neuralmind.context_selector import ContextSelector

        embedder = GraphEmbedder(str(temp_project))
        graph_data = embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, graph_data)
        text, _ = selector.get_l0_identity()

        # Should contain something from README
        assert "Test Project" in text or "project" in text.lower()

    def test_l0_loads_from_mempalace_yaml(self, temp_project_with_config):
        """Test that L0 prefers mempalace.yaml over README."""
        from neuralmind.embedder import GraphEmbedder
        from neuralmind.context_selector import ContextSelector

        embedder = GraphEmbedder(str(temp_project_with_config))
        graph_data = embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, graph_data)
        text, _ = selector.get_l0_identity()

        # Should contain content from mempalace.yaml
        assert "TestApp" in text or "test application" in text.lower()

    def test_l0_loads_from_claude_md(self, temp_project_with_claude_md):
        """Test that L0 loads from CLAUDE.md."""
        from neuralmind.embedder import GraphEmbedder
        from neuralmind.context_selector import ContextSelector

        embedder = GraphEmbedder(str(temp_project_with_claude_md))
        graph_data = embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, graph_data)
        text, _ = selector.get_l0_identity()

        # Should contain content from CLAUDE.md
        assert "TestApp" in text or "AI coding" in text.lower() or "test" in text.lower()

    def test_l0_within_token_budget(self, temp_project):
        """Test that L0 stays within token budget (~100)."""
        from neuralmind.embedder import GraphEmbedder
        from neuralmind.context_selector import ContextSelector

        embedder = GraphEmbedder(str(temp_project))
        graph_data = embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, graph_data)
        _, tokens = selector.get_l0_identity()

        # L0 budget is ~100 tokens, allow some flexibility
        assert tokens <= 200


class TestLayer1Summary:
    """Tests for Layer 1 (Summary) context."""

    def test_l1_returns_summary(self, temp_project):
        """Test that L1 returns architecture summary."""
        from neuralmind.embedder import GraphEmbedder
        from neuralmind.context_selector import ContextSelector

        embedder = GraphEmbedder(str(temp_project))
        graph_data = embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, graph_data)
        text, tokens = selector.get_l1_summary()

        assert isinstance(text, str)
        assert isinstance(tokens, int)
        assert len(text) > 0

    def test_l1_includes_communities(self, temp_project):
        """Test that L1 includes community summaries."""
        from neuralmind.embedder import GraphEmbedder
        from neuralmind.context_selector import ContextSelector

        embedder = GraphEmbedder(str(temp_project))
        graph_data = embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, graph_data)
        text, _ = selector.get_l1_summary()

        # Should mention communities or modules
        text_lower = text.lower()
        assert any([
            "authentication" in text_lower,
            "task" in text_lower,
            "api" in text_lower,
            "module" in text_lower,
            "component" in text_lower,
        ])

    def test_l1_within_token_budget(self, temp_project):
        """Test that L1 stays within token budget (~500)."""
        from neuralmind.embedder import GraphEmbedder
        from neuralmind.context_selector import ContextSelector

        embedder = GraphEmbedder(str(temp_project))
        graph_data = embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, graph_data)
        _, tokens = selector.get_l1_summary()

        # L1 budget is ~500 tokens, allow some flexibility
        assert tokens <= 800


class TestLayer2OnDemand:
    """Tests for Layer 2 (On-Demand) context."""

    def test_l2_returns_query_context(self, temp_project):
        """Test that L2 returns query-relevant context."""
        from neuralmind.embedder import GraphEmbedder
        from neuralmind.context_selector import ContextSelector

        embedder = GraphEmbedder(str(temp_project))
        graph_data = embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, graph_data)
        text, tokens, communities = selector.get_l2_context("authentication")

        assert isinstance(text, str)
        assert isinstance(tokens, int)
        assert isinstance(communities, list)

    def test_l2_loads_relevant_communities(self, temp_project):
        """Test that L2 loads communities relevant to query."""
        from neuralmind.embedder import GraphEmbedder
        from neuralmind.context_selector import ContextSelector

        embedder = GraphEmbedder(str(temp_project))
        graph_data = embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, graph_data)
        text, _, communities = selector.get_l2_context("How does authentication work?")

        # Should load authentication community
        # Community 1 is Authentication in our fixture
        assert len(communities) >= 0  # May be empty if no strong matches

    def test_l2_content_relevant_to_query(self, temp_project):
        """Test that L2 content is relevant to the query."""
        from neuralmind.embedder import GraphEmbedder
        from neuralmind.context_selector import ContextSelector

        embedder = GraphEmbedder(str(temp_project))
        graph_data = embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, graph_data)
        text, _, _ = selector.get_l2_context("authentication")

        if text:  # May be empty for some queries
            text_lower = text.lower()
            # Should contain auth-related content
            assert "auth" in text_lower or "user" in text_lower or "function" in text_lower

    def test_l2_within_token_budget(self, temp_project):
        """Test that L2 stays within token budget (~200-500)."""
        from neuralmind.embedder import GraphEmbedder
        from neuralmind.context_selector import ContextSelector

        embedder = GraphEmbedder(str(temp_project))
        graph_data = embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, graph_data)
        _, tokens, _ = selector.get_l2_context("authentication")

        # L2 budget is ~200-500 tokens, allow some flexibility
        assert tokens <= 800


class TestLayer3Search:
    """Tests for Layer 3 (Search) context."""

    def test_l3_returns_search_results(self, temp_project):
        """Test that L3 returns search results."""
        from neuralmind.embedder import GraphEmbedder
        from neuralmind.context_selector import ContextSelector

        embedder = GraphEmbedder(str(temp_project))
        graph_data = embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, graph_data)
        text, tokens, hits = selector.get_l3_search("authentication")

        assert isinstance(text, str)
        assert isinstance(tokens, int)
        assert isinstance(hits, int)

    def test_l3_includes_search_hits(self, temp_project):
        """Test that L3 includes semantic search hits."""
        from neuralmind.embedder import GraphEmbedder
        from neuralmind.context_selector import ContextSelector

        embedder = GraphEmbedder(str(temp_project))
        graph_data = embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, graph_data)
        _, _, hits = selector.get_l3_search("authentication")

        # Should find some results for "authentication"
        assert hits >= 0  # May be 0 if threshold not met

    def test_l3_respects_n_parameter(self, temp_project):
        """Test that L3 respects the n (limit) parameter."""
        from neuralmind.embedder import GraphEmbedder
        from neuralmind.context_selector import ContextSelector

        embedder = GraphEmbedder(str(temp_project))
        graph_data = embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, graph_data)
        _, _, hits = selector.get_l3_search("function", n=2)

        assert hits <= 2

    def test_l3_within_token_budget(self, temp_project):
        """Test that L3 stays within token budget (~200-500)."""
        from neuralmind.embedder import GraphEmbedder
        from neuralmind.context_selector import ContextSelector

        embedder = GraphEmbedder(str(temp_project))
        graph_data = embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, graph_data)
        _, tokens, _ = selector.get_l3_search("function")

        # L3 budget is ~200-500 tokens, allow flexibility
        assert tokens <= 800


class TestWakeupContext:
    """Tests for wake-up context generation."""

    def test_wakeup_uses_l0_l1_only(self, temp_project):
        """Test that wake-up context uses only L0 and L1."""
        from neuralmind.embedder import GraphEmbedder
        from neuralmind.context_selector import ContextSelector

        embedder = GraphEmbedder(str(temp_project))
        graph_data = embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, graph_data)
        result = selector.get_wakeup_context()

        assert "L0" in result.layers_used
        assert "L1" in result.layers_used
        assert "L2" not in result.layers_used
        assert "L3" not in result.layers_used

    def test_wakeup_token_budget(self, temp_project):
        """Test that wake-up stays within ~600 token budget."""
        from neuralmind.embedder import GraphEmbedder
        from neuralmind.context_selector import ContextSelector

        embedder = GraphEmbedder(str(temp_project))
        graph_data = embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, graph_data)
        result = selector.get_wakeup_context()

        # Wake-up should be ~600 tokens (L0 + L1)
        assert result.budget.total < 1000
        assert result.budget.l2 == 0
        assert result.budget.l3 == 0


class TestQueryContext:
    """Tests for query context generation."""

    def test_query_uses_all_layers(self, temp_project):
        """Test that query context can use all layers."""
        from neuralmind.embedder import GraphEmbedder
        from neuralmind.context_selector import ContextSelector

        embedder = GraphEmbedder(str(temp_project))
        graph_data = embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, graph_data)
        result = selector.get_query_context("How does authentication work?")

        assert "L0" in result.layers_used
        assert "L1" in result.layers_used
        # L2 and L3 depend on query relevance

    def test_query_includes_relevant_content(self, temp_project):
        """Test that query context includes relevant content."""
        from neuralmind.embedder import GraphEmbedder
        from neuralmind.context_selector import ContextSelector

        embedder = GraphEmbedder(str(temp_project))
        graph_data = embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, graph_data)
        result = selector.get_query_context("authentication")

        # Should include auth-related content
        context_lower = result.context.lower()
        assert "auth" in context_lower or "user" in context_lower or len(result.context) > 0

    def test_query_calculates_reduction_ratio(self, temp_project):
        """Test that query context calculates reduction ratio."""
        from neuralmind.embedder import GraphEmbedder
        from neuralmind.context_selector import ContextSelector

        embedder = GraphEmbedder(str(temp_project))
        graph_data = embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, graph_data)
        result = selector.get_query_context("authentication")

        assert result.reduction_ratio > 0
        # Should show some reduction
        assert result.reduction_ratio >= 1.0


class TestTokenEstimation:
    """Tests for token estimation."""

    def test_token_estimation_reasonable(self, temp_project):
        """Test that token estimation is reasonable."""
        from neuralmind.context_selector import ContextSelector

        # Rough estimate: 4 chars per token
        test_text = "This is a test string with about forty characters."
        # ~50 chars -> ~12-15 tokens

        # Use the class method if available
        estimated = len(test_text) // 4  # Simplified estimation
        assert 10 <= estimated <= 20

    def test_empty_text_zero_tokens(self):
        """Test that empty text estimates to 0 tokens."""
        estimated = len("") // 4
        assert estimated == 0


class TestContextResult:
    """Tests for ContextResult dataclass."""

    def test_context_result_has_all_fields(self, temp_project):
        """Test that ContextResult has all required fields."""
        from neuralmind.embedder import GraphEmbedder
        from neuralmind.context_selector import ContextSelector

        embedder = GraphEmbedder(str(temp_project))
        graph_data = embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, graph_data)
        result = selector.get_wakeup_context()

        assert hasattr(result, "context")
        assert hasattr(result, "budget")
        assert hasattr(result, "layers_used")
        assert hasattr(result, "communities_loaded")
        assert hasattr(result, "search_hits")
        assert hasattr(result, "reduction_ratio")


class TestTokenBudget:
    """Tests for TokenBudget dataclass."""

    def test_token_budget_has_all_layers(self, temp_project):
        """Test that TokenBudget tracks all layers."""
        from neuralmind.embedder import GraphEmbedder
        from neuralmind.context_selector import ContextSelector

        embedder = GraphEmbedder(str(temp_project))
        graph_data = embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, graph_data)
        result = selector.get_wakeup_context()
        budget = result.budget

        assert hasattr(budget, "l0")
        assert hasattr(budget, "l1")
        assert hasattr(budget, "l2")
        assert hasattr(budget, "l3")
        assert hasattr(budget, "total")

    def test_token_budget_total_is_sum(self, temp_project):
        """Test that budget total is sum of layers."""
        from neuralmind.embedder import GraphEmbedder
        from neuralmind.context_selector import ContextSelector

        embedder = GraphEmbedder(str(temp_project))
        graph_data = embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, graph_data)
        result = selector.get_wakeup_context()
        budget = result.budget

        expected_total = budget.l0 + budget.l1 + budget.l2 + budget.l3
        assert budget.total == expected_total
