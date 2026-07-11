"""Tests for the reuse-vs-rewrite feedback loop (NeuralMind.record_edit_activity).

When an agent edits a file, identifiers in the new code that name a symbol
defined elsewhere in the graph are a *reuse* signal: the edited file and the
reused definitions co-fired, so their synapse edges get reinforced and future
retrieval surfaces what was actually reused.
"""

from __future__ import annotations


def _build_mind(temp_project):
    from neuralmind import NeuralMind

    mind = NeuralMind(str(temp_project))
    mind.build()
    return mind


class TestRecordEditActivity:
    def test_reuse_reinforces_existing_symbols(self, temp_project):
        """New code referencing existing external symbols co-activates them."""
        mind = _build_mind(temp_project)
        # api/routes.py defines api_router (node_6). The edit reaches for
        # authenticate_user (node_1) and create_task (node_4) from other files.
        result = mind.record_edit_activity(
            "api/routes.py",
            "def handler():\n    authenticate_user()\n    create_task()\n",
        )
        assert set(result["reused"]) == {"authenticate_user", "create_task"}
        assert result["pairs"] > 0

        # The synapse store now links api_router to the reused definitions.
        neighbors = dict(mind.synapses.neighbors("node_6", k=10))
        assert "node_1" in neighbors
        assert "node_4" in neighbors

    def test_no_reuse_when_only_new_symbols(self, temp_project):
        """Edits that don't touch existing symbols reinforce nothing."""
        mind = _build_mind(temp_project)
        result = mind.record_edit_activity(
            "api/routes.py",
            "def brand_new_helper():\n    return 42\n",
        )
        assert result["reused"] == []
        assert result["pairs"] == 0

    def test_empty_inputs_are_safe(self, temp_project):
        mind = _build_mind(temp_project)
        empty = {"reused": [], "possible_dupes": [], "pairs": 0}
        assert mind.record_edit_activity("", "authenticate_user()") == empty
        assert mind.record_edit_activity("api/routes.py", "") == empty

    def test_returns_possible_dupes_list(self, temp_project):
        """The possible-duplication field is always a list (MVP reports only)."""
        mind = _build_mind(temp_project)
        result = mind.record_edit_activity("api/routes.py", "User = 1\n")
        assert isinstance(result["possible_dupes"], list)


class TestSymbolNameNormalization:
    """Generated graphs label functions with signature punctuation; the reuse
    index must key on the bare identifier so edited code's tokens can match."""

    def test_strips_signature_punctuation(self):
        from neuralmind import NeuralMind

        # Real fixtures carry labels like "login_endpoint()" — without
        # normalization the bare token "login_endpoint" never matched.
        assert NeuralMind._symbol_name("login_endpoint()") == "login_endpoint"
        assert NeuralMind._symbol_name("getConnection()") == "getConnection"
        assert NeuralMind._symbol_name("authenticate_user") == "authenticate_user"
        assert NeuralMind._symbol_name("Routes.php") == "Routes"
        assert NeuralMind._symbol_name("") == ""
