"""Tests for neuralmind.paths — centralized artifact path resolution."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from neuralmind.paths import (
    CANONICAL_DIR,
    LEGACY_DIR,
    canonical_artifact,
    graph_html_path,
    graph_json_path,
    graph_report_path,
    ir_meta_path,
    ir_path,
    legacy_artifact,
    migrate_legacy_artifacts,
    vector_db_path,
)


class TestCanonicalArtifact:
    """Tests for canonical_artifact() — the single choke point for new writes."""

    def test_returns_path_under_neuralmind(self, tmp_path: Path) -> None:
        result = canonical_artifact(tmp_path, "graph.json")
        assert result == tmp_path / CANONICAL_DIR / "graph.json"

    def test_returns_path_with_multiple_parts(self, tmp_path: Path) -> None:
        result = canonical_artifact(tmp_path, "neuralmind_db", "store.sqlite")
        assert result == tmp_path / CANONICAL_DIR / "neuralmind_db" / "store.sqlite"

    def test_refuses_path_traversal(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="escapes project root"):
            canonical_artifact(tmp_path, "..", "..", "etc", "passwd")

    def test_refuses_absolute_path_in_parts(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="escapes project root"):
            canonical_artifact(tmp_path, "/etc", "passwd")

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        result = canonical_artifact(str(tmp_path), "graph.json")
        assert result == tmp_path / CANONICAL_DIR / "graph.json"


class TestLegacyArtifact:
    """Tests for legacy_artifact() — reading pre-v4.2.0 artifacts."""

    def test_returns_path_under_graphify_out(self, tmp_path: Path) -> None:
        result = legacy_artifact(tmp_path, "graph.json")
        assert result == tmp_path / LEGACY_DIR / "graph.json"

    def test_refuses_path_traversal(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="escapes project root"):
            legacy_artifact(tmp_path, "..", "..", "etc", "passwd")


class TestGraphJsonPath:
    """Tests for graph_json_path() — canonical-first, legacy-fallback."""

    def test_prefers_canonical(self, tmp_path: Path) -> None:
        canonical = tmp_path / CANONICAL_DIR
        canonical.mkdir()
        (canonical / "graph.json").write_text("{}")
        legacy = tmp_path / LEGACY_DIR
        legacy.mkdir()
        (legacy / "graph.json").write_text("{}")
        assert graph_json_path(tmp_path) == canonical / "graph.json"

    def test_falls_back_to_legacy(self, tmp_path: Path) -> None:
        legacy = tmp_path / LEGACY_DIR
        legacy.mkdir()
        (legacy / "graph.json").write_text("{}")
        assert graph_json_path(tmp_path) == legacy / "graph.json"

    def test_returns_canonical_when_neither_exists(self, tmp_path: Path) -> None:
        # Canonical is the default for new projects
        assert graph_json_path(tmp_path) == tmp_path / CANONICAL_DIR / "graph.json"


class TestIrPaths:
    """Tests for IR path helpers — always canonical."""

    def test_ir_path(self, tmp_path: Path) -> None:
        assert ir_path(tmp_path) == tmp_path / CANONICAL_DIR / "index_ir.json"

    def test_ir_meta_path(self, tmp_path: Path) -> None:
        assert ir_meta_path(tmp_path) == tmp_path / CANONICAL_DIR / "ir_meta.json"


class TestVectorDbPath:
    """Tests for vector_db_path() — canonical-first, legacy-fallback."""

    def test_prefers_canonical_turbovec(self, tmp_path: Path) -> None:
        canonical = tmp_path / CANONICAL_DIR / "neuralmind_turbovec"
        canonical.mkdir(parents=True)
        legacy = tmp_path / LEGACY_DIR / "neuralmind_turbovec"
        legacy.mkdir(parents=True)
        assert vector_db_path(tmp_path, "turbovec") == canonical

    def test_falls_back_to_legacy_turbovec(self, tmp_path: Path) -> None:
        legacy = tmp_path / LEGACY_DIR / "neuralmind_turbovec"
        legacy.mkdir(parents=True)
        assert vector_db_path(tmp_path, "turbovec") == legacy

    def test_chroma_backend(self, tmp_path: Path) -> None:
        canonical = tmp_path / CANONICAL_DIR / "neuralmind_db"
        canonical.mkdir(parents=True)
        assert vector_db_path(tmp_path, "chroma") == canonical

    def test_chroma_falls_back_to_legacy(self, tmp_path: Path) -> None:
        legacy = tmp_path / LEGACY_DIR / "neuralmind_db"
        legacy.mkdir(parents=True)
        assert vector_db_path(tmp_path, "chroma") == legacy


class TestGraphReportPath:
    """Tests for graph_report_path() — canonical-first, legacy-fallback."""

    def test_prefers_canonical(self, tmp_path: Path) -> None:
        canonical = tmp_path / CANONICAL_DIR
        canonical.mkdir()
        (canonical / "GRAPH_REPORT.md").write_text("report")
        legacy = tmp_path / LEGACY_DIR
        legacy.mkdir()
        (legacy / "GRAPH_REPORT.md").write_text("report")
        assert graph_report_path(tmp_path) == canonical / "GRAPH_REPORT.md"

    def test_falls_back_to_legacy(self, tmp_path: Path) -> None:
        legacy = tmp_path / LEGACY_DIR
        legacy.mkdir()
        (legacy / "GRAPH_REPORT.md").write_text("report")
        assert graph_report_path(tmp_path) == legacy / "GRAPH_REPORT.md"


class TestGraphHtmlPath:
    """Tests for graph_html_path() — canonical-first, legacy-fallback."""

    def test_prefers_canonical(self, tmp_path: Path) -> None:
        canonical = tmp_path / CANONICAL_DIR
        canonical.mkdir()
        (canonical / "graph.html").write_text("<html>")
        legacy = tmp_path / LEGACY_DIR
        legacy.mkdir()
        (legacy / "graph.html").write_text("<html>")
        assert graph_html_path(tmp_path) == canonical / "graph.html"

    def test_falls_back_to_legacy(self, tmp_path: Path) -> None:
        legacy = tmp_path / LEGACY_DIR
        legacy.mkdir()
        (legacy / "graph.html").write_text("<html>")
        assert graph_html_path(tmp_path) == legacy / "graph.html"


class TestMigrateLegacyArtifacts:
    """Tests for migrate_legacy_artifacts() — one-time migration."""

    def test_moves_graph_json(self, tmp_path: Path) -> None:
        legacy = tmp_path / LEGACY_DIR
        legacy.mkdir()
        (legacy / "graph.json").write_text("{}")
        result = migrate_legacy_artifacts(tmp_path)
        assert "graph.json" in result["migrated"]
        assert (tmp_path / CANONICAL_DIR / "graph.json").exists()
        assert not (legacy / "graph.json").exists()

    def test_moves_neuralmind_turbovec(self, tmp_path: Path) -> None:
        legacy = tmp_path / LEGACY_DIR / "neuralmind_turbovec"
        legacy.mkdir(parents=True)
        (legacy / "store.sqlite").write_text("data")
        result = migrate_legacy_artifacts(tmp_path)
        assert "neuralmind_turbovec" in result["migrated"]
        assert (tmp_path / CANONICAL_DIR / "neuralmind_turbovec" / "store.sqlite").exists()

    def test_skips_already_migrated(self, tmp_path: Path) -> None:
        legacy = tmp_path / LEGACY_DIR
        legacy.mkdir()
        (legacy / "graph.json").write_text("{}")
        canonical = tmp_path / CANONICAL_DIR
        canonical.mkdir()
        (canonical / "graph.json").write_text("{}")
        result = migrate_legacy_artifacts(tmp_path)
        assert "graph.json" in result["skipped"]
        assert "graph.json" not in result["migrated"]

    def test_no_legacy_dir(self, tmp_path: Path) -> None:
        result = migrate_legacy_artifacts(tmp_path)
        assert result == {"migrated": [], "skipped": [], "errors": []}

    def test_skips_hidden_files(self, tmp_path: Path) -> None:
        legacy = tmp_path / LEGACY_DIR
        legacy.mkdir()
        (legacy / ".graphify_labels.json").write_text("{}")
        (legacy / "graph.json").write_text("{}")
        result = migrate_legacy_artifacts(tmp_path)
        assert ".graphify_labels.json" not in result["migrated"]
        assert "graph.json" in result["migrated"]

    def test_moves_multiple_artifacts(self, tmp_path: Path) -> None:
        legacy = tmp_path / LEGACY_DIR
        legacy.mkdir()
        (legacy / "graph.json").write_text("{}")
        (legacy / "GRAPH_REPORT.md").write_text("report")
        (legacy / "graph.html").write_text("<html>")
        result = migrate_legacy_artifacts(tmp_path)
        assert len(result["migrated"]) == 3
        assert (tmp_path / CANONICAL_DIR / "graph.json").exists()
        assert (tmp_path / CANONICAL_DIR / "GRAPH_REPORT.md").exists()
        assert (tmp_path / CANONICAL_DIR / "graph.html").exists()
