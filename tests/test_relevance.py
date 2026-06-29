"""Tests for the structured relevance sidecar (neuralmind.relevance)."""

from __future__ import annotations

from neuralmind.relevance import SIDECAR_VERSION, build_relevance_sidecar


class TestBuildRelevanceSidecar:
    def _hits(self):
        return [
            {
                "id": "node_1",
                "score": 0.9,
                "_synapse_boost": 0.1,
                "_synapse_recalled": True,
                "metadata": {
                    "label": "authenticate_user",
                    "source_file": "auth/handlers.py",
                    "node_id": "node_1",
                },
            },
            {
                "id": "node_2",
                "score": 0.5,
                "_synapse_boost": 0.0,
                "_synapse_recalled": False,
                "metadata": {
                    "label": "hash_password",
                    "source_file": "auth/crypto.py",
                    "node_id": "node_2",
                },
            },
        ]

    def test_shape_and_version(self):
        sidecar = build_relevance_sidecar(self._hits())
        assert sidecar["version"] == SIDECAR_VERSION
        assert set(sidecar["files"]) == {"auth/handlers.py", "auth/crypto.py"}

    def test_per_node_signals_preserved(self):
        sidecar = build_relevance_sidecar(self._hits())
        node = sidecar["files"]["auth/handlers.py"]["nodes"][0]
        assert node["node_id"] == "node_1"
        assert node["label"] == "authenticate_user"
        assert node["score"] == 0.9
        assert node["synapse_boost"] == 0.1
        assert node["recalled"] is True
        # No `mind` passed → line spans omitted, never crash.
        assert "lines" not in node

    def test_max_score_per_file(self):
        hits = self._hits() + [
            {
                "id": "node_1b",
                "score": 0.95,
                "metadata": {
                    "label": "login",
                    "source_file": "auth/handlers.py",
                    "node_id": "node_1b",
                },
            }
        ]
        sidecar = build_relevance_sidecar(hits)
        assert sidecar["files"]["auth/handlers.py"]["max_score"] == 0.95

    def test_max_score_handles_negative_scores(self):
        """A file whose scores are all negative reports the max, not 0.0."""
        hits = [
            {
                "id": "n1",
                "score": -0.5,
                "metadata": {"label": "a", "source_file": "f.py", "node_id": "n1"},
            },
            {
                "id": "n2",
                "score": -0.2,
                "metadata": {"label": "b", "source_file": "f.py", "node_id": "n2"},
            },
        ]
        sidecar = build_relevance_sidecar(hits)
        assert sidecar["files"]["f.py"]["max_score"] == -0.2

    def test_empty_and_none_inputs(self):
        assert build_relevance_sidecar(None) == {"version": SIDECAR_VERSION, "files": {}}
        assert build_relevance_sidecar([]) == {"version": SIDECAR_VERSION, "files": {}}

    def test_hits_without_source_file_skipped(self):
        sidecar = build_relevance_sidecar([{"id": "x", "score": 0.4, "metadata": {}}])
        assert sidecar["files"] == {}


class TestRelevanceFromQuery:
    """Integration: the sidecar built from a real ContextResult."""

    def test_sidecar_from_real_query(self, temp_project):
        from neuralmind import NeuralMind

        mind = NeuralMind(str(temp_project))
        mind.build()
        result = mind.query("How does authentication work?")
        sidecar = build_relevance_sidecar(result.top_search_hits, mind)

        assert sidecar["version"] == SIDECAR_VERSION
        # Every file entry carries a numeric max_score and node list.
        for entry in sidecar["files"].values():
            assert isinstance(entry["max_score"], (int, float))
            assert isinstance(entry["nodes"], list)
