"""Additional focused tests for core module uncovered APIs."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from neuralmind.context_selector import ContextResult, TokenBudget


class FakeGraphEmbedder:
    """Minimal embedder to avoid external embedding downloads in unit tests."""

    def __init__(self, project_path, db_path=None):
        self.project_path = Path(project_path)
        self.db_path = db_path or str(self.project_path / "graphify-out" / "neuralmind_db")
        self.graph_path = self.project_path / "graphify-out" / "graph.json"

    def load_graph(self):
        return True

    def embed_nodes(self, force=False):
        return {"added": 0, "updated": 0, "skipped": 0}

    def get_stats(self):
        return {
            "total_nodes": 0,
            "communities": 0,
            "db_path": self.db_path,
        }

    def search(self, query, n=10, **filters):
        return []


class TestCreateMind:
    """Tests for create_mind helper."""

    def test_create_mind_auto_build_true_calls_build(self, tmp_path, monkeypatch):
        from neuralmind import core

        monkeypatch.setattr(core, "GraphEmbedder", FakeGraphEmbedder)
        build_spy = MagicMock(return_value={"success": True})
        monkeypatch.setattr(core.NeuralMind, "build", build_spy)

        mind = core.create_mind(str(tmp_path), auto_build=True)

        assert isinstance(mind, core.NeuralMind)
        build_spy.assert_called_once()

    def test_create_mind_auto_build_false_skips_build(self, tmp_path, monkeypatch):
        from neuralmind import core

        monkeypatch.setattr(core, "GraphEmbedder", FakeGraphEmbedder)
        build_spy = MagicMock(return_value={"success": True})
        monkeypatch.setattr(core.NeuralMind, "build", build_spy)

        mind = core.create_mind(str(tmp_path), auto_build=False)

        assert isinstance(mind, core.NeuralMind)
        build_spy.assert_not_called()


class TestExportContext:
    """Tests for context export behavior."""

    def test_export_context_defaults_to_wakeup_and_default_path(self, tmp_path, monkeypatch):
        from neuralmind.core import NeuralMind

        monkeypatch.setattr("neuralmind.core.GraphEmbedder", FakeGraphEmbedder)
        mind = NeuralMind(str(tmp_path))
        mind._built = True

        wakeup_result = ContextResult(
            context="Wakeup content",
            budget=TokenBudget(l0_identity=10, l1_summary=20),
            layers_used=["L0:Identity", "L1:Summary"],
            reduction_ratio=25.0,
        )
        selector = SimpleNamespace(
            get_wakeup_context=MagicMock(return_value=wakeup_result),
            get_query_context=MagicMock(),
        )
        mind.selector = selector

        output = mind.export_context()
        content = Path(output).read_text()

        assert output == str(tmp_path / "neuralmind_context.md")
        assert "**Type:** wakeup" in content
        assert "**Query:** N/A" in content
        assert "Wakeup content" in content
        selector.get_wakeup_context.assert_called_once()
        selector.get_query_context.assert_not_called()

    def test_export_context_query_uses_query_context_and_custom_output(self, tmp_path, monkeypatch):
        from neuralmind.core import NeuralMind

        monkeypatch.setattr("neuralmind.core.GraphEmbedder", FakeGraphEmbedder)
        mind = NeuralMind(str(tmp_path))
        mind._built = True

        query_result = ContextResult(
            context="Query content",
            budget=TokenBudget(l0_identity=10, l1_summary=20, l2_ondemand=30, l3_search=5),
            layers_used=["L0:Identity", "L1:Summary", "L2:OnDemand", "L3:Search"],
            reduction_ratio=12.5,
        )
        selector = SimpleNamespace(
            get_wakeup_context=MagicMock(),
            get_query_context=MagicMock(return_value=query_result),
        )
        mind.selector = selector

        custom_output = tmp_path / "custom_context.md"
        output = mind.export_context(query="How auth works?", output_path=str(custom_output))
        content = custom_output.read_text()

        assert output == str(custom_output)
        assert "**Type:** query" in content
        assert "**Query:** How auth works?" in content
        assert "Query content" in content
        selector.get_query_context.assert_called_once_with("How auth works?")
        selector.get_wakeup_context.assert_not_called()
