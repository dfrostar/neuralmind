"""Incremental builds notice every changed file, not just ones with a newer mtime.

A file comes back with an *older* mtime after ``mv backup.py a.py``, ``cp -p``,
an archive restore or a checkout of an older revision; the build must still
re-extract it.
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
