"""Tests for the SCIP precision pass backend (PRD 2 G2)."""

from __future__ import annotations

from neuralmind.scip_backend import (
    ScipBackend,
    ScipConfig,
    apply_scip_if_available,
    is_scip_available,
)


class TestScipConfig:
    def test_defaults(self):
        config = ScipConfig()
        assert config.enabled is False
        assert config.index_path is None
        assert config.fallback_to_tree_sitter is True


class TestScipBackend:
    def test_disabled_by_default(self):
        backend = ScipBackend()
        assert backend.is_available is False

    def test_stats(self):
        backend = ScipBackend()
        stats = backend.stats()
        assert stats["enabled"] is False
        assert "go" in stats["languages"]
        assert "rust" in stats["languages"]
        assert "java" in stats["languages"]

    def test_refine_when_disabled(self):
        backend = ScipBackend()
        graph = {"nodes": [], "links": []}
        out, stats = backend.refine_graph(graph)
        assert out == graph
        assert stats is None

    def test_detect_languages(self):
        langs = ScipBackend.detect_languages()
        assert langs == {"go", "rust", "java", "c", "cpp"}


class TestApplyScipIfAvailable:
    def test_noop_when_disabled(self):
        graph = {"nodes": [{"id": "n1", "label": "foo"}], "links": []}
        out, stats = apply_scip_if_available(graph, enabled=False)
        assert out == graph
        assert stats is None


class TestIsScipAvailable:
    def test_unavailable_by_default(self):
        assert is_scip_available() is False
