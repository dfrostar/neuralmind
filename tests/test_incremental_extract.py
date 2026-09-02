"""Tests for G4 — incremental re-extraction."""

from neuralmind.incremental_extract import IncrementalExtractor


class TestIncrementalExtractor:
    def test_scan_detects_new_files(self, tmp_path):
        # Create fixture files
        (tmp_path / "a.py").write_text(
            """
def foo():
    pass
"""
        )
        extractor = IncrementalExtractor(str(tmp_path))
        added, modified, deleted = extractor.scan_files(tmp_path, suffixes=frozenset({".py"}))
        assert len(added) == 1

    def test_scan_detects_modified_files(self, tmp_path):
        # Create file and add to cache
        test_file = tmp_path / "a.py"
        test_file.write_text(
            """
def foo():
    pass
"""
        )
        extractor = IncrementalExtractor(str(tmp_path))
        extractor.update_cache(["a.py"], tmp_path)

        # Modify file
        import time

        time.sleep(0.1)
        test_file.write_text(
            """
def bar():
    pass
"""
        )

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
