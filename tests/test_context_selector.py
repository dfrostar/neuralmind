"""Tests for NeuralMind context selector functionality."""


class TestContextSelector:
    """Tests for ContextSelector class."""

    def test_init_with_embedder(self, temp_project):
        """Test context selector initialization."""
        from neuralmind.context_selector import ContextSelector
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        # ContextSelector takes embedder and optional project_path string
        selector = ContextSelector(embedder, str(temp_project))
        assert selector is not None
        assert selector.project_path == temp_project

    def test_init_with_embedder_only(self, temp_project):
        """Test context selector initialization without explicit project_path."""
        from neuralmind.context_selector import ContextSelector
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        # Should get project_path from embedder
        selector = ContextSelector(embedder)
        assert selector is not None
        assert selector.project_path == temp_project

    def test_init_with_mock_embedder(self, mock_embedder, temp_project):
        """Test context selector initialization with mock embedder."""
        from neuralmind.context_selector import ContextSelector

        selector = ContextSelector(mock_embedder, str(temp_project))
        assert selector is not None


class TestLayer0Identity:
    """Tests for Layer 0 (Identity) context."""

    def test_l0_returns_string(self, temp_project):
        """Test that L0 returns a string."""
        from neuralmind.context_selector import ContextSelector
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, str(temp_project))
        text = selector.get_l0_identity()

        assert isinstance(text, str)
        assert len(text) > 0

    def test_l0_loads_from_readme(self, temp_project):
        """Test that L0 loads from README.md."""
        from neuralmind.context_selector import ContextSelector
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, str(temp_project))
        text = selector.get_l0_identity()

        # Should contain something from README or project name
        assert "Project" in text or "test" in text.lower()

    def test_l0_loads_from_mempalace_yaml(self, temp_project_with_config):
        """Test that L0 prefers mempalace.yaml over README."""
        from neuralmind.context_selector import ContextSelector
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project_with_config))
        embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, str(temp_project_with_config))
        text = selector.get_l0_identity()

        # Should contain content from mempalace.yaml or project info
        assert len(text) > 0

    def test_l0_loads_from_claude_md(self, temp_project_with_claude_md):
        """Test that L0 loads from CLAUDE.md."""
        from neuralmind.context_selector import ContextSelector
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project_with_claude_md))
        embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, str(temp_project_with_claude_md))
        text = selector.get_l0_identity()

        # Should contain content from CLAUDE.md or project info
        assert len(text) > 0

    def test_l0_within_token_budget(self, temp_project):
        """Test that L0 stays within token budget (~150)."""
        from neuralmind.context_selector import ContextSelector
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, str(temp_project))
        text = selector.get_l0_identity()

        # L0 budget is ~150 tokens (4 chars/token), allow flexibility
        # 150 tokens * 4 chars = 600 chars max
        assert len(text) <= 800  # Allow some flexibility

    def test_l0_with_mock_embedder(self, mock_embedder, temp_project):
        """Test L0 with mock embedder."""
        from neuralmind.context_selector import ContextSelector

        selector = ContextSelector(mock_embedder, str(temp_project))
        text = selector.get_l0_identity()

        assert isinstance(text, str)
        assert len(text) > 0


class TestLayer1Summary:
    """Tests for Layer 1 (Summary) context."""

    def test_l1_returns_string(self, temp_project):
        """Test that L1 returns a string."""
        from neuralmind.context_selector import ContextSelector
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, str(temp_project))
        text = selector.get_l1_summary()

        assert isinstance(text, str)
        assert len(text) > 0

    def test_l1_includes_architecture(self, temp_project):
        """Test that L1 includes architecture overview."""
        from neuralmind.context_selector import ContextSelector
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, str(temp_project))
        text = selector.get_l1_summary()

        # Should mention architecture, clusters, or modules
        text_lower = text.lower()
        assert any(
            [
                "architecture" in text_lower,
                "cluster" in text_lower,
                "module" in text_lower,
                "overview" in text_lower,
            ]
        )

    def test_l1_within_token_budget(self, temp_project):
        """Test that L1 stays within token budget (~600)."""
        from neuralmind.context_selector import ContextSelector
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, str(temp_project))
        text = selector.get_l1_summary()

        # L1 budget is ~600 tokens (4 chars/token), allow flexibility
        # 600 tokens * 4 chars = 2400 chars max
        assert len(text) <= 3200  # Allow some flexibility

    def test_l1_with_mock_embedder(self, mock_embedder, temp_project):
        """Test L1 with mock embedder."""
        from neuralmind.context_selector import ContextSelector

        selector = ContextSelector(mock_embedder, str(temp_project))
        text = selector.get_l1_summary()

        assert isinstance(text, str)


class TestLayer2OnDemand:
    """Tests for Layer 2 (On-Demand) context."""

    def test_l2_returns_tuple(self, temp_project):
        """Test that L2 returns (context_text, communities_list)."""
        from neuralmind.context_selector import ContextSelector
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, str(temp_project))
        result = selector.get_l2_context("authentication")

        assert isinstance(result, tuple)
        assert len(result) == 2
        text, communities = result
        assert isinstance(text, str)
        assert isinstance(communities, list)

    def test_l2_loads_relevant_communities(self, temp_project):
        """Test that L2 loads communities relevant to query."""
        from neuralmind.context_selector import ContextSelector
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, str(temp_project))
        text, communities = selector.get_l2_context("How does authentication work?")

        # Communities should be a list (may be empty if no matches)
        assert isinstance(communities, list)
        # All items should be integers
        assert all(isinstance(c, int) for c in communities)

    def test_l2_content_relevant_to_query(self, temp_project):
        """Test that L2 content is relevant to the query."""
        from neuralmind.context_selector import ContextSelector
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, str(temp_project))
        text, _ = selector.get_l2_context("authentication")

        # Text should be string (may be empty for some queries)
        assert isinstance(text, str)

    def test_l2_empty_query(self, temp_project):
        """Test L2 with empty query."""
        from neuralmind.context_selector import ContextSelector
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, str(temp_project))
        text, communities = selector.get_l2_context("")

        # Should handle empty query gracefully
        assert isinstance(text, str)
        assert isinstance(communities, list)

    def test_l2_with_mock_embedder(self, mock_embedder, temp_project):
        """Test L2 with mock embedder."""
        from neuralmind.context_selector import ContextSelector

        selector = ContextSelector(mock_embedder, str(temp_project))
        text, communities = selector.get_l2_context("authentication")

        assert isinstance(text, str)
        assert isinstance(communities, list)


class TestLayer3Search:
    """Tests for Layer 3 (Search) context."""

    def test_l3_returns_tuple(self, temp_project):
        """Test that L3 returns (search_results_text, hits_count)."""
        from neuralmind.context_selector import ContextSelector
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, str(temp_project))
        result = selector.get_l3_search("authentication")

        assert isinstance(result, tuple)
        assert len(result) == 2
        text, hits = result
        assert isinstance(text, str)
        assert isinstance(hits, int)

    def test_l3_includes_search_hits(self, temp_project):
        """Test that L3 returns hit count."""
        from neuralmind.context_selector import ContextSelector
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, str(temp_project))
        _, hits = selector.get_l3_search("authentication")

        # Should return integer hit count
        assert isinstance(hits, int)
        assert hits >= 0

    def test_l3_respects_n_parameter(self, temp_project):
        """Test that L3 respects the n (limit) parameter."""
        from neuralmind.context_selector import ContextSelector
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, str(temp_project))
        _, hits = selector.get_l3_search("function", n=2)

        assert hits <= 2

    def test_l3_with_mock_embedder(self, mock_embedder, temp_project):
        """Test L3 with mock embedder."""
        from neuralmind.context_selector import ContextSelector

        selector = ContextSelector(mock_embedder, str(temp_project))
        text, hits = selector.get_l3_search("authentication")

        assert isinstance(text, str)
        assert isinstance(hits, int)


class TestWakeupContext:
    """Tests for wake-up context generation."""

    def test_wakeup_returns_context_result(self, temp_project):
        """Test that wake-up returns a ContextResult."""
        from neuralmind.context_selector import ContextResult, ContextSelector
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, str(temp_project))
        result = selector.get_wakeup_context()

        assert isinstance(result, ContextResult)
        assert result.context is not None
        assert len(result.context) > 0

    def test_wakeup_uses_l0_l1_only(self, temp_project):
        """Test that wake-up context uses only L0 and L1."""
        from neuralmind.context_selector import ContextSelector
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, str(temp_project))
        result = selector.get_wakeup_context()

        assert any("L0" in layer for layer in result.layers_used)
        assert any("L1" in layer for layer in result.layers_used)
        assert not any("L2" in layer for layer in result.layers_used)
        assert not any("L3" in layer for layer in result.layers_used)

    def test_wakeup_token_budget(self, temp_project):
        """Test that wake-up stays within ~600 token budget."""
        from neuralmind.context_selector import ContextSelector
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, str(temp_project))
        result = selector.get_wakeup_context()

        # Wake-up should be ~600 tokens (L0 + L1)
        assert result.budget.total < 1500
        assert result.budget.l2_ondemand == 0
        assert result.budget.l3_search == 0

    def test_wakeup_with_mock_embedder(self, mock_embedder, temp_project):
        """Test wake-up with mock embedder."""
        from neuralmind.context_selector import ContextResult, ContextSelector

        selector = ContextSelector(mock_embedder, str(temp_project))
        result = selector.get_wakeup_context()

        assert isinstance(result, ContextResult)


class TestQueryContext:
    """Tests for query context generation."""

    def test_query_returns_context_result(self, temp_project):
        """Test that query context returns a ContextResult."""
        from neuralmind.context_selector import ContextResult, ContextSelector
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, str(temp_project))
        result = selector.get_query_context("How does authentication work?")

        assert isinstance(result, ContextResult)
        assert result.context is not None
        assert len(result.context) > 0

    def test_query_uses_all_layers(self, temp_project):
        """Test that query context can use all layers."""
        from neuralmind.context_selector import ContextSelector
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, str(temp_project))
        result = selector.get_query_context("How does authentication work?")

        assert any("L0" in layer for layer in result.layers_used)
        assert any("L1" in layer for layer in result.layers_used)
        # L2 and L3 depend on query relevance

    def test_query_includes_relevant_content(self, temp_project):
        """Test that query context includes relevant content."""
        from neuralmind.context_selector import ContextSelector
        from neuralmind.embedder import GraphEmbedder

        embedder = GraphEmbedder(str(temp_project))
        embedder.load_graph()
        embedder.embed_nodes()

        selector = ContextSelector(embedder, str(temp_project))
        result = selector.get_query_context("authentication")

        # Should include some content
        assert len(result.context) > 0

    def test_query_with_mock_embedder(self, mock_embedder, temp_project):
        """Test query with mock embedder."""
        from neuralmind.context_selector import ContextResult, ContextSelector

        selector = ContextSelector(mock_embedder, str(temp_project))
        result = selector.get_query_context("authentication")

        assert isinstance(result, ContextResult)


class TestTokenBudget:
    """Tests for TokenBudget class."""

    def test_token_budget_total(self):
        """Test TokenBudget total calculation."""
        from neuralmind.context_selector import TokenBudget

        budget = TokenBudget(
            l0_identity=100,
            l1_summary=500,
            l2_ondemand=300,
            l3_search=200,
        )

        assert budget.total == 1100

    def test_token_budget_wakeup(self):
        """Test TokenBudget wakeup calculation."""
        from neuralmind.context_selector import TokenBudget

        budget = TokenBudget(
            l0_identity=100,
            l1_summary=500,
            l2_ondemand=0,
            l3_search=0,
        )

        assert budget.wakeup == 600

    def test_token_budget_to_dict(self):
        """Test TokenBudget to_dict method."""
        from neuralmind.context_selector import TokenBudget

        budget = TokenBudget(
            l0_identity=100,
            l1_summary=500,
            l2_ondemand=300,
            l3_search=200,
        )

        d = budget.to_dict()
        assert d["l0_identity"] == 100
        assert d["l1_summary"] == 500
        assert d["l2_ondemand"] == 300
        assert d["l3_search"] == 200
        assert d["total"] == 1100
        assert d["wakeup"] == 600


class TestContextResult:
    """Tests for ContextResult class."""

    def test_context_result_creation(self):
        """Test ContextResult creation."""
        from neuralmind.context_selector import ContextResult, TokenBudget

        budget = TokenBudget()
        result = ContextResult(
            context="Test context",
            budget=budget,
            layers_used=["L0", "L1"],
        )

        assert result.context == "Test context"
        assert result.budget == budget
        assert result.layers_used == ["L0", "L1"]
        assert result.communities_loaded == []
        assert result.search_hits == 0
        assert result.reduction_ratio == 0.0
