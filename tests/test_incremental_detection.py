"""Incremental builds notice every change a full rebuild would.

A file comes back with an *older* mtime after ``mv backup.py a.py``, ``cp -p``,
an archive restore or a checkout of an older revision; the build must still
re-extract it. And a newly added file can satisfy an import or call an
unchanged file couldn't resolve before, so that file's edges into the new one
must appear without a full rebuild.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from neuralmind.incremental_extract import IncrementalExtractor

PY = frozenset({".py"})


def _cached(root: Path, rel: str, content: str) -> IncrementalExtractor:
    (root / rel).write_text(content, encoding="utf-8")
    extractor = IncrementalExtractor(root)
    extractor.update_cache([rel], root)
    return extractor


def _set_mtime(path: Path, mtime: float) -> None:
    os.utime(path, (mtime, mtime))


class TestScanFiles:
    def test_replaced_by_a_file_with_an_older_mtime(self, tmp_path):
        extractor = _cached(tmp_path, "a.py", "def old_name(): pass\n")
        backup = tmp_path / "a_restore.txt"
        backup.write_text("def new_name(): pass\n", encoding="utf-8")
        _set_mtime(backup, time.time() - 3600)
        os.replace(backup, tmp_path / "a.py")  # like `mv backup a.py`

        assert extractor.scan_files(tmp_path, PY)[1] == ["a.py"]

    def test_size_change_with_the_cached_mtime(self, tmp_path):
        extractor = _cached(tmp_path, "a.py", "x = 1\n")
        cached_mtime = extractor._cache["a.py"].mtime
        (tmp_path / "a.py").write_text("x = 12345\n", encoding="utf-8")
        _set_mtime(tmp_path / "a.py", cached_mtime)

        assert extractor.scan_files(tmp_path, PY)[1] == ["a.py"]

    def test_touched_but_unchanged_is_not_modified_and_not_rehashed(self, tmp_path):
        extractor = _cached(tmp_path, "a.py", "x = 1\n")
        _set_mtime(tmp_path / "a.py", time.time() - 7200)

        assert extractor.scan_files(tmp_path, PY) == ([], [], [])
        # The cache now holds the new mtime, on disk too, so the next scan
        # trusts it instead of hashing the file again.
        reloaded = IncrementalExtractor(tmp_path)
        assert reloaded._cache["a.py"].mtime == (tmp_path / "a.py").stat().st_mtime

    def test_cache_without_sizes_still_loads(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        legacy = IncrementalExtractor(tmp_path)
        legacy.update_cache(["a.py"], tmp_path)
        data = json.loads(legacy.cache_path.read_text(encoding="utf-8"))
        for entry in data["files"]:
            entry.pop("size", None)
        legacy.cache_path.write_text(json.dumps(data), encoding="utf-8")

        extractor = IncrementalExtractor(tmp_path)
        assert "a.py" in extractor._cache
        assert extractor.scan_files(tmp_path, PY) == ([], [], [])


@pytest.fixture
def graphgen():
    from neuralmind import graphgen

    if not graphgen.is_available():
        pytest.skip("tree-sitter not installed")
    return graphgen


def _labels(graph: dict, rel: str) -> set[str]:
    return {n["label"] for n in graph["nodes"] if n.get("source_file") == rel}


def test_build_picks_up_a_file_restored_with_an_older_mtime(tmp_path, graphgen):
    (tmp_path / "a.py").write_text("def old_name():\n    pass\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("def x():\n    pass\n", encoding="utf-8")
    graphgen.write_graph(tmp_path)

    backup = tmp_path / "a_restore.txt"
    backup.write_text("def new_name():\n    pass\n", encoding="utf-8")
    _set_mtime(backup, time.time() - 3600)
    os.replace(backup, tmp_path / "a.py")
    graph = json.loads(graphgen.write_graph(tmp_path).read_text(encoding="utf-8"))

    assert "new_name()" in _labels(graph, "a.py")
    assert "old_name()" not in _labels(graph, "a.py")


class TestNewFileReferences:
    def _project(self, root: Path) -> IncrementalExtractor:
        (root / "a.py").write_text("from d import newfn\n\ndef main():\n    newfn()\n")
        (root / "b.py").write_text("def unrelated():\n    return 1\n")
        (root / "z.py").write_text("from a import main\n\ndef run():\n    main()\n")
        extractor = IncrementalExtractor(root)
        extractor.update_cache(["a.py", "b.py", "z.py"], root)
        return extractor

    def test_files_that_mention_the_new_module_are_re_extracted(self, tmp_path, graphgen):
        extractor = self._project(tmp_path)
        (tmp_path / "d.py").write_text("def newfn():\n    pass\n")

        changed = extractor.get_changed_with_dependents(tmp_path, PY, {"a.py": ["z.py"]})

        # a.py names the new module; z.py imports a.py, whose nodes are rebuilt.
        assert sorted(changed) == ["a.py", "d.py", "z.py"]

    def test_a_reference_to_a_symbol_the_new_file_defines(self, tmp_path, graphgen):
        extractor = self._project(tmp_path)
        (tmp_path / "helpers.py").write_text("def unrelated():\n    pass\n")

        changed = extractor.get_changed_with_dependents(tmp_path, PY, {})

        assert sorted(changed) == ["b.py", "helpers.py"]


def _edges(graph: dict) -> list[tuple[str, str, str]]:
    return sorted((e["relation"], e["source"], e["target"]) for e in graph["links"])


def test_build_links_unchanged_files_to_a_new_file(tmp_path, graphgen):
    (tmp_path / "a.py").write_text("from d import newfn\n\ndef main():\n    newfn()\n")
    (tmp_path / "z.py").write_text("from a import main\n\ndef run():\n    main()\n")
    (tmp_path / "c.py").write_text("def other():\n    return 2\n")
    graphgen.write_graph(tmp_path)

    (tmp_path / "d.py").write_text("def newfn():\n    pass\n")
    incremental = json.loads(graphgen.write_graph(tmp_path).read_text(encoding="utf-8"))
    edges = _edges(incremental)
    assert ("imports_from", "a_py", "d_py") in edges
    assert ("calls", "a_py__main_fn", "d_py__newfn_fn") in edges

    for state in ("graph.json", "extraction_cache.json", "importer_index.json"):
        (tmp_path / ".neuralmind" / state).unlink(missing_ok=True)
    fresh = json.loads(graphgen.write_graph(tmp_path).read_text(encoding="utf-8"))
    assert edges == _edges(fresh)
