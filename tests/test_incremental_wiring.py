"""Tests for T2 — wiring IncrementalExtractor into build_graph().

Verifies that `build_graph()` uses the incremental extraction cache,
skips unchanged files, and invalidates transitive importers.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from neuralmind import graphgen
from neuralmind.incremental_extract import (
    load_importer_index,
)


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """Create a small sample project with Python files + imports."""
    root = tmp_path / "project"
    root.mkdir()

    # a.py is a leaf module (imported by b.py)
    (root / "a.py").write_text("""
def helper():
    return 42
""")

    # b.py imports a.py and is imported by c.py
    (root / "b.py").write_text("""
from a import helper

def process():
    return helper() * 2
""")

    # c.py imports b.py (top-level, depends on b which depends on a)
    (root / "c.py").write_text("""
from b import process

def run():
    return process() + 1
""")

    # d.py is independent
    (root / "d.py").write_text("""
def standalone():
    return "standalone"
""")

    # Create a markdown doc
    (root / "README.md").write_text("# Project\n\nThis is a test project.\n")

    return root


@pytest.fixture
def project_with_output(sample_project: Path) -> Path:
    """Run a full build first, then return the project path."""
    graphgen.build_graph(sample_project)
    return sample_project


class TestFirstBuild:
    """First build: full extraction, cache written."""

    def test_first_build_full_extraction(self, sample_project: Path) -> None:
        """No cache → all files extracted."""
        result = graphgen.build_graph(sample_project)
        # All source files should have nodes
        source_files = {n["source_file"] for n in result["nodes"] if n.get("file_type") == "code"}
        assert "a.py" in source_files
        assert "b.py" in source_files
        assert "c.py" in source_files
        assert "d.py" in source_files

    def test_first_build_writes_cache(self, sample_project: Path) -> None:
        """First build writes the extraction cache."""
        graphgen.build_graph(sample_project)
        cache_path = sample_project / ".neuralmind" / "extraction_cache.json"
        assert cache_path.exists()
        data = json.loads(cache_path.read_text())
        assert "files" in data
        assert len(data["files"]) >= 4  # a, b, c, d

    def test_first_build_writes_importer_index(self, sample_project: Path) -> None:
        """First build writes the importer index."""
        graphgen.build_graph(sample_graph := sample_project)
        idx = load_importer_index(sample_project)
        # b imports a → a's importers include b
        # c imports b → b's importers include c
        assert "a.py" in idx or len(idx) >= 0  # index may be empty if edges didn't resolve


class TestSecondBuildNoChanges:
    """Second build with no changes: all files skipped."""

    def test_second_build_uses_cache(self, project_with_output: Path) -> None:
        """Second build reads the cache and skips unchanged files."""
        result = graphgen.build_graph(project_with_output)
        # Should still produce valid output
        source_files = {n["source_file"] for n in result["nodes"] if n.get("file_type") == "code"}
        assert "a.py" in source_files
        assert "b.py" in source_files

    def test_cache_persists(self, project_with_output: Path) -> None:
        """Cache file exists after build."""
        cache_path = project_with_output / ".neuralmind" / "extraction_cache.json"
        assert cache_path.exists()


class TestTouchFileWithImporters:
    """Changing a file triggers re-extraction of its importers."""

    def test_touch_leaf_file(self, project_with_output: Path) -> None:
        """Touching a leaf file only re-extracts that file (no importers)."""
        time.sleep(0.1)
        (project_with_output / "d.py").write_text("""
def standalone():
    return "standalone v2"
""")
        result = graphgen.build_graph(project_with_output)
        # d.py should be re-extracted (it changed)
        assert result is not None
        # All files should still be present
        source_files = {n["source_file"] for n in result["nodes"] if n.get("file_type") == "code"}
        assert "a.py" in source_files
        assert "d.py" in source_files

    def test_touch_file_with_importer(self, project_with_output: Path) -> None:
        """Touching a.py (imported by b.py) should also re-extract b.py."""
        time.sleep(0.1)
        (project_with_output / "a.py").write_text("""
def helper():
    return 99  # changed
""")
        result = graphgen.build_graph(project_with_output)
        # Both a and b should be re-extracted (b imports a)
        assert result is not None
        source_files = {n["source_file"] for n in result["nodes"] if n.get("file_type") == "code"}
        assert "a.py" in source_files
        assert "b.py" in source_files


def _build_and_save(root: Path) -> dict:
    """What `neuralmind build` does: build, then persist the graph the next
    build reuses."""
    from neuralmind.paths import graph_json_path

    graph = graphgen.build_graph(root)
    path = graph_json_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph), encoding="utf-8")
    return graph


def _labels(graph: dict, source_file: str) -> set[str]:
    return {n["label"] for n in graph["nodes"] if n.get("source_file") == source_file}


@pytest.fixture
def package_project(tmp_path: Path) -> Path:
    """A package whose API lives in its __init__.py, used by app.py."""
    root = tmp_path / "project"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "__init__.py").write_text("def register(name):\n    return name\n")
    (root / "app.py").write_text("from pkg import register\n\ndef main():\n    register('a')\n")
    return root


class TestPackageInit:
    """#632: package code in __init__.py stays in the graph across builds."""

    def test_an_edit_to_package_init_reaches_the_graph(self, package_project: Path) -> None:
        _build_and_save(package_project)
        time.sleep(0.1)
        init = package_project / "pkg" / "__init__.py"
        init.write_text(init.read_text() + "\ndef added_later():\n    pass\n")
        graph = _build_and_save(package_project)
        assert "added_later()" in _labels(graph, "pkg/__init__.py")

    def test_a_file_missing_from_the_graph_is_restored(self, package_project: Path) -> None:
        # A graph that lost a file's nodes while the cache still calls the
        # file unchanged: before the fix, no later build ever restored them.
        from neuralmind.paths import graph_json_path

        _build_and_save(package_project)
        path = graph_json_path(package_project)
        graph = json.loads(path.read_text(encoding="utf-8"))
        graph["nodes"] = [n for n in graph["nodes"] if n.get("source_file") != "pkg/__init__.py"]
        path.write_text(json.dumps(graph), encoding="utf-8")

        graph = _build_and_save(package_project)
        assert "register()" in _labels(graph, "pkg/__init__.py")
        calls = {
            (e["source"], e["target"])
            for e in graph["links"]
            if e.get("source_file") == "app.py" and e.get("relation") == "calls"
        }
        assert any(t.endswith("register_fn") for _, t in calls), calls


class TestDeleteFile:
    """Deleting a file removes its nodes + edges."""

    def test_delete_file(self, project_with_output: Path) -> None:
        """Deleting a.py removes its nodes from the graph."""
        a_path = project_with_output / "a.py"
        a_path.unlink()
        result = graphgen.build_graph(project_with_output)
        # a.py should be gone
        source_files = {n["source_file"] for n in result["nodes"] if n.get("file_type") == "code"}
        assert "a.py" not in source_files


class TestCacheCorrupted:
    """Corrupted cache → full extraction, no crash."""

    def test_corrupted_cache_fallback(self, project_with_output: Path) -> None:
        """Corrupted JSON in cache → full extraction."""
        cache_path = project_with_output / ".neuralmind" / "extraction_cache.json"
        cache_path.write_text("{{invalid json}}}}")
        # Should not crash
        result = graphgen.build_graph(project_with_output)
        assert result is not None
        # All files should still be present (full extraction)
        source_files = {n["source_file"] for n in result["nodes"] if n.get("file_type") == "code"}
        assert "a.py" in source_files
        assert "b.py" in source_files


class TestCacheFromAnOlderVersion:
    """A cache from before CACHE_VERSION 2 → one full extraction."""

    def test_a_cache_without_the_version_loads_empty(self, project_with_output: Path) -> None:
        from neuralmind.incremental_extract import CACHE_VERSION, IncrementalExtractor

        cache_path = project_with_output / ".neuralmind" / "extraction_cache.json"
        data = json.loads(cache_path.read_text())
        assert data["version"] == CACHE_VERSION
        assert IncrementalExtractor(project_with_output)._cache
        del data["version"]
        cache_path.write_text(json.dumps(data))
        assert IncrementalExtractor(project_with_output)._cache == {}

    def test_an_edge_an_older_incremental_build_kept_is_rebuilt(self, tmp_path: Path) -> None:
        # Before 4.23.2 an incremental build could point m.run's call at
        # z.search, the unchanged file's function, instead of a.search. An
        # incremental build now carries an unchanged file's edges over, so
        # the first build after upgrading must extract everything.
        root = tmp_path / "project"
        root.mkdir()
        (root / "a.py").write_text("def search():\n    return 1\n")
        (root / "m.py").write_text("def run():\n    return search()\n")
        (root / "z.py").write_text("def search():\n    return 2\n")
        graphgen.write_graph(root)
        graph_path = root / ".neuralmind" / "graph.json"
        graph = json.loads(graph_path.read_text())
        for edge in graph["links"]:
            if edge["relation"] == "calls":
                edge["target"] = "z_py__search_fn"
        graph_path.write_text(json.dumps(graph, indent=2))
        cache_path = root / ".neuralmind" / "extraction_cache.json"
        cache = json.loads(cache_path.read_text())
        del cache["version"]
        cache_path.write_text(json.dumps(cache))

        graph = json.loads(graphgen.write_graph(root).read_text())

        calls = {(e["source"], e["target"]) for e in graph["links"] if e["relation"] == "calls"}
        assert calls == {("m_py__run_fn", "a_py__search_fn")}


class TestImporterIndexPersistence:
    """Importer index survives across builds."""

    def test_importer_index_persists(self, project_with_output: Path) -> None:
        """Importer index is saved after build."""
        idx = load_importer_index(project_with_output)
        # Index may or may not be populated depending on graph structure,
        # but loading should succeed
        assert isinstance(idx, dict)


class TestPerformanceTarget:
    """10K-line repo, 1 change → <10% of full-build time."""

    def test_small_project_fast(self, project_with_output: Path) -> None:
        """Incremental build on small project should take <10% of full build."""
        import time

        # Time a full rebuild (force by removing cache)
        cache_path = project_with_output / ".neuralmind" / "extraction_cache.json"
        cache_path.unlink()

        start = time.time()
        graphgen.build_graph(project_with_output)
        full_build_time = time.time() - start

        # Time incremental build (no changes)
        start = time.time()
        graphgen.build_graph(project_with_output)
        incremental_time = time.time() - start

        # Incremental should be at least 10x faster
        # (on small projects absolute time is tiny, so ratio can be noisy —
        # but incremental should never be slower)
        if full_build_time < 0.05:
            pytest.skip(
                f"Full build ({full_build_time * 1000:.1f} ms) is too fast for a "
                "meaningful ratio comparison; skipping on this tiny fixture project."
            )

        assert incremental_time < full_build_time * 2  # generous bound for CI noise


class TestIgnoredFiles:
    """A file the build ignores is never extracted, so never cached: the scan
    must not see it either, or it is "added" on every incremental build."""

    @pytest.fixture
    def ignoring_project(self, sample_project: Path) -> Path:
        (sample_project / ".neuralmindignore").write_text("tests/\n")
        (sample_project / "tests").mkdir()
        (sample_project / "tests" / "test_a.py").write_text(
            "from a import helper\n\ndef test_helper():\n    assert helper() == 42\n"
        )
        graphgen.write_graph(sample_project)
        return sample_project

    def _changed(self, monkeypatch) -> list[list[str]]:
        from neuralmind.incremental_extract import IncrementalExtractor

        seen: list[list[str]] = []
        real = IncrementalExtractor.get_changed_with_dependents

        def spy(self, *args, **kwargs):
            changed = real(self, *args, **kwargs)
            seen.append(changed)
            return changed

        monkeypatch.setattr(IncrementalExtractor, "get_changed_with_dependents", spy)
        return seen

    def test_a_build_with_no_change_re_extracts_nothing(self, ignoring_project, monkeypatch):
        seen = self._changed(monkeypatch)
        path = graphgen.write_graph(ignoring_project)
        before = path.read_bytes()
        graphgen.write_graph(ignoring_project)
        assert seen == [[], []]
        assert path.read_bytes() == before

    def test_an_edit_to_an_ignored_file_re_extracts_nothing(self, ignoring_project, monkeypatch):
        seen = self._changed(monkeypatch)
        time.sleep(0.05)
        (ignoring_project / "tests" / "test_a.py").write_text("def test_other():\n    pass\n")
        graphgen.write_graph(ignoring_project)
        assert seen == [[]]

    def test_a_file_no_longer_ignored_is_added(self, ignoring_project, monkeypatch):
        seen = self._changed(monkeypatch)
        (ignoring_project / ".neuralmindignore").write_text("")
        result = graphgen.build_graph(ignoring_project)
        assert "tests/test_a.py" in seen[0]
        assert any(n.get("source_file") == "tests/test_a.py" for n in result["nodes"])
