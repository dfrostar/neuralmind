"""Tests for G4 — incremental re-extraction + dangling edge prune."""

from __future__ import annotations

from neuralmind.incremental_extract import (
    IncrementalExtractor,
    build_importer_index_from_graph,
    load_importer_index,
    save_importer_index,
)


class TestIncrementalExtractor:
    def test_scan_detects_new_files(self, tmp_path):
        (tmp_path / "a.py").write_text("def foo(): pass")
        extractor = IncrementalExtractor(str(tmp_path))
        added, modified, deleted = extractor.scan_files(tmp_path, suffixes=frozenset({".py"}))
        assert len(added) == 1

    def test_scan_detects_modified_files(self, tmp_path):
        test_file = tmp_path / "a.py"
        test_file.write_text("def foo(): pass")
        extractor = IncrementalExtractor(str(tmp_path))
        extractor.update_cache(["a.py"], tmp_path)
        import time

        time.sleep(0.1)
        test_file.write_text("def bar(): pass")
        added, modified, deleted = extractor.scan_files(tmp_path, suffixes=frozenset({".py"}))
        assert "a.py" in modified

    def test_scan_detects_deleted_files(self, tmp_path):
        test_file = tmp_path / "a.py"
        test_file.write_text("x")
        extractor = IncrementalExtractor(str(tmp_path))
        extractor.update_cache(["a.py"], tmp_path)
        test_file.unlink()
        added, modified, deleted = extractor.scan_files(tmp_path, suffixes=frozenset({".py"}))
        assert "a.py" in deleted

    def test_update_and_save_cache(self, tmp_path):
        extractor = IncrementalExtractor(str(tmp_path))
        test_file = tmp_path / "x.py"
        test_file.write_text("y")
        extractor.update_cache(["x.py"], tmp_path)
        assert "x.py" in extractor._cache

    def test_stats(self, tmp_path):
        extractor = IncrementalExtractor(str(tmp_path))
        stats = extractor.stats()
        assert "n_cached" in stats
        assert "cache_file" in stats


class TestImporterIndex:
    def test_build_importer_index_from_graph_basic(self):
        graph = {
            "nodes": [
                {"id": "a_py", "file_type": "code", "source_file": "a.py"},
                {"id": "b_py", "file_type": "code", "source_file": "b.py"},
            ],
            "links": [
                {"relation": "imports_from", "source": "a_py", "target": "b_py"},
            ],
        }
        index = build_importer_index_from_graph(graph)
        assert "b.py" in index
        assert "a.py" in index["b.py"]

    def test_build_importer_index_excludes_same_file(self):
        graph = {
            "nodes": [
                {"id": "a_py", "file_type": "code", "source_file": "a.py"},
            ],
            "links": [
                {"relation": "contains", "source": "a_py__fn", "target": "a_py"},
            ],
        }
        index = build_importer_index_from_graph(graph)
        # Same-file edges should not appear
        assert not any("a.py" in getters for getters in index.values())

    def test_build_importer_index_ignores_unknown_relations(self):
        graph = {
            "nodes": [
                {"id": "a_py", "file_type": "code", "source_file": "a.py"},
                {"id": "b_py", "file_type": "code", "source_file": "b.py"},
            ],
            "links": [
                {"relation": "relates_to", "source": "a_py", "target": "b_py"},
            ],
        }
        index = build_importer_index_from_graph(graph)
        assert index == {}

    def test_save_and_load_round_trip(self, tmp_path):
        index = {"b.py": ["a.py"], "d.py": ["c.py"]}
        save_importer_index(str(tmp_path), index)
        loaded = load_importer_index(str(tmp_path))
        assert loaded == index

    def test_load_returns_empty_on_missing(self, tmp_path):
        loaded = load_importer_index(str(tmp_path))
        assert loaded == {}

    def test_get_changed_with_dependents_adds_importers(self, tmp_path):
        # a.py exists (changed), b.py imports a.py
        (tmp_path / "a.py").write_text("x")
        (tmp_path / "b.py").write_text("y")
        extractor = IncrementalExtractor(str(tmp_path))
        extractor.update_cache(["a.py", "b.py"], tmp_path)
        # Modify a.py
        import time

        time.sleep(0.1)
        (tmp_path / "a.py").write_text("z")
        result = extractor.get_changed_with_dependents(
            tmp_path,
            suffixes=frozenset({".py"}),
            importer_index={"a.py": ["b.py"]},
        )
        assert "a.py" in result
        assert "b.py" in result

    def test_get_changed_with_dependents_skip_unknown_importer(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        extractor = IncrementalExtractor(str(tmp_path))
        # importer_index references a file not on disk
        result = extractor.get_changed_with_dependents(
            tmp_path,
            suffixes=frozenset({".py"}),
            importer_index={"nonexistent.py": ["unknown.py"]},
        )
        assert isinstance(result, list)
