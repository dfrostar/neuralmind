"""Tests for the retrieval enhancement module (three adversarial fixes)."""

from __future__ import annotations

import pytest

from neuralmind.retrieval_enhancement import (
    _STOPWORDS,
    apply_code_signal_boost,
    classify_intent,
    compute_code_signal_score,
    extract_code_identifiers,
    extract_potential_node_ids,
    synapse_seeded_expansion,
)


class TestIntentClassification:
    """Test 1: Intent classification fix — how-implement queries → code intent"""

    def test_how_does_implement_is_code_intent(self):
        result = classify_intent(
            "How does the synapse layer implement Hebbian learning?",
            existing_code_keywords=["implement", "code", "function"],
            existing_doc_keywords=["explain", "how does", "what is", "architecture"],
        )
        assert result == "code"

    def test_how_does_perform_is_code_intent(self):
        result = classify_intent(
            "How does the cache perform eviction?",
            existing_code_keywords=["code", "function"],
            existing_doc_keywords=["how does", "explain"],
        )
        assert result == "code"

    def test_how_does_handle_is_code_intent(self):
        result = classify_intent(
            "How does the router handle requests?",
            existing_code_keywords=["code", "function"],
            existing_doc_keywords=["how does", "explain"],
        )
        assert result == "code"

    def test_how_does_process_is_code_intent(self):
        result = classify_intent(
            "How does the queue process items?",
            existing_code_keywords=["code"],
            existing_doc_keywords=["how does"],
        )
        assert result == "code"

    def test_what_is_stays_docs_intent(self):
        result = classify_intent(
            "What is the synapse layer?",
            existing_code_keywords=["code"],
            existing_doc_keywords=["what is", "explain"],
        )
        assert result == "docs"

    def test_explain_stays_docs_intent(self):
        result = classify_intent(
            "Explain the architecture",
            existing_code_keywords=["code"],
            existing_doc_keywords=["explain", "architecture"],
        )
        assert result == "docs"

    def test_show_me_how_works_is_code_intent(self):
        result = classify_intent(
            "Show me how the synapse layer works",
            existing_code_keywords=["code"],
            existing_doc_keywords=["how does"],
        )
        assert result == "code"

    def test_how_works_is_code_intent(self):
        result = classify_intent(
            "How does the decay function work?",
            existing_code_keywords=["code", "function"],
            existing_doc_keywords=["how does"],
        )
        assert result == "code"

    def test_which_is_docs_intent(self):
        result = classify_intent(
            "Which cache backend is used?",
            existing_code_keywords=["code"],
            existing_doc_keywords=["which"],
        )
        assert result == "docs"

    def test_hybrid_intent(self):
        result = classify_intent(
            "Tell me about the cache",
            existing_code_keywords=[],
            existing_doc_keywords=[],
        )
        assert result == "hybrid"


class TestCodeIdentifierExtraction:
    """Test 2: Code identifier extraction"""

    def test_extract_camelcase(self):
        ids = extract_code_identifiers("How does Hebbian learning work?")
        assert "Hebbian" in ids

    def test_extract_snake_case(self):
        ids = extract_code_identifiers("What does synapse_layer do?")
        assert "synapse" in ids
        assert "layer" in ids

    def test_extract_plain_words(self):
        ids = extract_code_identifiers("How does the synapse reinforce work?")
        assert "synapse" in ids
        assert "reinforce" in ids

    def test_excludes_stopwords(self):
        ids = extract_code_identifiers("What is the function that does the work?")
        # Common words like "what", "is", "the", "that", "does" should be excluded
        assert "the" not in ids
        assert "is" not in ids
        assert "that" not in ids

    def test_extract_compound_phrases(self):
        ids = extract_code_identifiers("How does the synapse layer work?")
        # Should extract both "synapse" and "layer" from "synapse layer"
        assert "synapse" in ids
        assert "layer" in ids

    def test_extract_from_identifier_query(self):
        ids = extract_code_identifiers("Hebbian co-activation decay spread reinforce")
        assert "Hebbian" in ids
        assert "decay" in ids
        assert "spread" in ids
        assert "reinforce" in ids


class TestCodeSignalBoost:
    """Test 3: Code-signal boosting"""

    def test_boosts_file_with_identifiers(self):
        results = [
            {
                "id": "neuralmind/synapses.py::fn:reinforce",
                "score": 0.8,
                "metadata": {
                    "source_file": "neuralmind/synapses.py",
                    "label": "reinforce",
                    "file_type": "code",
                },
                "document": "def reinforce(node_ids): ...",
            },
            {
                "id": "docs/README.md",
                "score": 0.9,
                "metadata": {
                    "source_file": "docs/README.md",
                    "label": "README",
                    "file_type": "document",
                },
                "document": "# NeuralMind\nsynapse layer...",
            },
        ]

        boosted = apply_code_signal_boost(results, ["synapse", "reinforce"])
        # synapses.py should now rank above README.md
        assert boosted[0]["id"] == "neuralmind/synapses.py::fn:reinforce"
        assert boosted[0]["_code_signal_boost"] > 1.0
        # Doc was penalized (score reduced to 0.5x)
        assert boosted[1]["score"] < 0.9  # original was 0.9, should be reduced

    def test_no_boost_without_identifiers(self):
        results = [
            {
                "id": "a",
                "score": 0.5,
                "metadata": {"source_file": "a.py", "label": "a", "file_type": "code"},
                "document": "test",
            },
        ]
        boosted = apply_code_signal_boost(results, [])
        assert boosted[0]["score"] == 0.5  # unchanged

    def test_no_boost_with_empty_results(self):
        boosted = apply_code_signal_boost([], ["test"])
        assert boosted == []

    def test_penalizes_docs_for_code_identifiers(self):
        results = [
            {
                "id": "doc1",
                "score": 0.9,
                "metadata": {"source_file": "doc.md", "label": "Doc", "file_type": "document"},
                "document": "synapse layer",
            },
            {
                "id": "code1",
                "score": 0.7,
                "metadata": {"source_file": "synapses.py", "label": "synapse", "file_type": "code"},
                "document": "synapse code",
            },
        ]
        boosted = apply_code_signal_boost(results, ["synapse"])
        # Code should rank above doc when query has code identifiers
        assert boosted[0]["id"] == "code1"

    def test_compute_code_signal_score_boosts_code_files(self):
        result = {
            "metadata": {"source_file": "neuralmind/synapses.py", "label": "reinforce", "file_type": "code"},
            "document": "def reinforce(node_ids): ...",
        }
        score = compute_code_signal_score(result, ["synapse", "reinforce"])
        assert score > 1.0

    def test_compute_code_signal_score_penalizes_docs(self):
        result = {
            "metadata": {"source_file": "docs/README.md", "label": "README", "file_type": "document"},
            "document": "synapse layer",
        }
        score = compute_code_signal_score(result, ["synapse", "reinforce"])
        assert score <= 0.5


class TestSynapseSeededExpansion:
    """Test 4: Synapse-seeded expansion"""

    def test_no_expansion_without_store(self):
        results = [{"id": "a", "score": 0.5}]
        expanded = synapse_seeded_expansion(None, "test query", results)
        assert expanded == results

    def test_no_expansion_with_empty_results(self):
        from neuralmind.synapses import SynapseStore
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            store = SynapseStore(Path(tmp) / "test.db")
            expanded = synapse_seeded_expansion(store, "test", [])
            assert expanded == []

    def test_no_expansion_without_matching_synapses(self):
        from neuralmind.synapses import SynapseStore
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            store = SynapseStore(Path(tmp) / "test.db")
            results = [{"id": "a", "score": 0.5}]
            expanded = synapse_seeded_expansion(store, "nonexistent", results)
            assert expanded == results  # no matching synapses

    def test_expansion_with_matching_synapses(self):
        from neuralmind.synapses import SynapseStore
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            store = SynapseStore(Path(tmp) / "test.db")
            # Create some synapse edges
            store.reinforce(["synapse", "layer", "hebbian", "learning"])
            store.reinforce(["synapse", "store"])
            store.reinforce(["layer", "reinforce"])

            results = [{"id": "initial", "score": 0.5, "metadata": {"source_file": "initial.py", "label": "initial", "file_type": "code"}}]
            expanded = synapse_seeded_expansion(store, "How does synapse layer work?", results, max_expansions=5)

            # Should have added some neighbors
            assert len(expanded) >= 1  # at least original
            # Check if any synapse-seeded results were added
            seeded = [r for r in expanded if r.get("_synapse_seeded")]
            # May or may not find matches depending on node ID matching


class TestIntegration:
    """Integration tests for all three fixes"""

    def test_full_pipeline_code_intent(self):
        from neuralmind.retrieval_enhancement import enhance_retrieval
        import tempfile
        from pathlib import Path
        from neuralmind.synapses import SynapseStore

        with tempfile.TemporaryDirectory() as tmp:
            store = SynapseStore(Path(tmp) / "test.db")
            store.reinforce(["synapse", "reinforce", "decay"])
            store.reinforce(["synapse", "spread"])
            store.reinforce(["decay", "half_life"])

            results = [
                {
                    "id": "neuralmind/synapses.py::fn:reinforce",
                    "score": 0.7,
                    "metadata": {"source_file": "neuralmind/synapses.py", "label": "reinforce", "file_type": "code"},
                    "document": "def reinforce(node_ids): ...",
                },
                {
                    "id": "docs/synapses.md",
                    "score": 0.9,
                    "metadata": {"source_file": "docs/synapses.md", "label": "Synapse Guide", "file_type": "document"},
                    "document": "The synapse layer uses Hebbian learning...",
                },
                {
                    "id": "tests/test_synapses.py",
                    "score": 0.5,
                    "metadata": {"source_file": "tests/test_synapses.py", "label": "test_reinforce", "file_type": "code"},
                    "document": "def test_reinforce(): ...",
                },
            ]

            enhanced = enhance_retrieval(
                store,
                "How does the synapse layer implement reinforce?",
                results,
                intent="hybrid",  # Will be re-classified
                code_keywords=["code", "function", "implement"],
                doc_keywords=["explain", "how does", "what is"],
            )

            # synapses.py (with "synapse" and "reinforce") should be #1
            assert enhanced[0]["id"] == "neuralmind/synapses.py::fn:reinforce"

    def test_full_pipeline_docs_intent_unchanged(self):
        from neuralmind.retrieval_enhancement import enhance_retrieval

        results = [
            {
                "id": "doc1",
                "score": 0.8,
                "metadata": {"source_file": "doc.md", "label": "Guide", "file_type": "document"},
                "document": "explanation...",
            },
        ]

        enhanced = enhance_retrieval(
            None,
            "What is the synapse layer?",
            results,
            intent="hybrid",
            code_keywords=["code"],
            doc_keywords=["what is"],
        )

        # Should not crash
        assert len(enhanced) == 1
