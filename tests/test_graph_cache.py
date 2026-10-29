"""The graph cache (neuralmind/graph_cache.py) changes how fast a graph loads, never what.

A hook is a new process per prompt, so it loaded the whole graph every time;
on hermes-agent that was 6 of the prompt-submit hook's 8.5 s. These tests pin
the cache's contract: the graph it returns is the graph the sources give, any
change to a source or any damage to the file falls back to the sources, small
graphs aren't cached, and a hook stopped mid-load still leaves the cache to a
background writer.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from neuralmind import graph_cache
from neuralmind import ir as ir_mod


def _graph(n: int = 3) -> dict:
    nodes = [
        {
            "label": f"f{i}",
            "file_type": "code",
            "source_file": f"m{i % 2}.py",
            "source_location": f"L{i + 1}",
            "id": f"m_f{i}",
            "community": i % 2,
            "norm_label": f"f{i}",
        }
        for i in range(n)
    ]
    links = [
        {
            "relation": "calls",
            "context": "call",
            "confidence": "EXTRACTED",
            "source_file": "m0.py",
            "source_location": "L1",
            "weight": 1.0,
            "source": "m_f0",
            "target": f"m_f{i}",
            "confidence_score": 1.0,
        }
        for i in range(1, n)
    ]
    return {
        "directed": False,
        "multigraph": False,
        "graph": {"project_kind": "code"},
        "nodes": nodes,
        "links": links,
        "hyperedges": [],
    }


@pytest.fixture
def project(tmp_path: Path, monkeypatch) -> Path:
    (tmp_path / ".neuralmind").mkdir()
    (tmp_path / ".neuralmind" / "graph.json").write_text(json.dumps(_graph()))
    # Every graph here is tiny: cache them all.
    monkeypatch.setattr(graph_cache, "CACHE_MIN_BYTES", 0)
    monkeypatch.delenv(graph_cache.CACHE_ENV, raising=False)
    return tmp_path


def _paths(project: Path) -> tuple[Path, Path]:
    return project / ".neuralmind" / "index_ir.json", project / ".neuralmind" / "graph.json"


def _cache(project: Path) -> Path:
    return project / ".neuralmind" / graph_cache.CACHE_FILENAME


def _no_sources(monkeypatch) -> None:
    def refuse(*_a, **_k):
        raise AssertionError("read the sources")

    monkeypatch.setattr(graph_cache, "_read_sources", refuse)


def _write_ir(project: Path, graph: dict) -> None:
    ir_path, _ = _paths(project)
    ir_mod.from_graph_json(graph).write(ir_path)
    # The IR is preferred when it is at least as new as graph.json.
    future = time.time() + 5
    os.utime(ir_path, (future, future))


def test_the_cached_graph_is_the_graph_the_sources_give(project, monkeypatch):
    ir_path, graph_path = _paths(project)
    first = graph_cache.load(ir_path, graph_path)
    assert first == json.loads(graph_path.read_text())
    assert _cache(project).exists()

    _no_sources(monkeypatch)
    second = graph_cache.load(ir_path, graph_path)
    # Same values in the same order: a dict's key order is part of the graph.
    assert json.dumps(second) == json.dumps(first)


def test_the_ir_path_is_cached_as_converted(project, monkeypatch):
    _write_ir(project, _graph(5))
    ir_path, graph_path = _paths(project)
    expected = ir_mod.to_graph_json(ir_mod.IndexIR.read(ir_path))
    assert json.dumps(graph_cache.load(ir_path, graph_path)) == json.dumps(expected)
    _no_sources(monkeypatch)
    assert json.dumps(graph_cache.load(ir_path, graph_path)) == json.dumps(expected)


def test_a_rewritten_source_is_read_again(project):
    ir_path, graph_path = _paths(project)
    graph_cache.load(ir_path, graph_path)
    graph_path.write_text(json.dumps(_graph(7)))
    assert len(graph_cache.load(ir_path, graph_path)["nodes"]) == 7
    # A newer IR now wins over graph.json, as without the cache.
    _write_ir(project, _graph(4))
    assert len(graph_cache.load(ir_path, graph_path)["nodes"]) == 4


def test_a_cache_from_another_neuralmind_is_not_read(project, monkeypatch):
    ir_path, graph_path = _paths(project)
    graph_cache.load(ir_path, graph_path)
    monkeypatch.setattr("neuralmind.__version__", "0.0.0-other")
    calls = []
    real = graph_cache._read_sources

    def counted(*args):
        calls.append(args)
        return real(*args)

    monkeypatch.setattr(graph_cache, "_read_sources", counted)
    graph_cache.load(ir_path, graph_path)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "body",
    [b"not marshal at all", b"", None],
    ids=["garbage", "empty-body", "not-a-graph"],
)
def test_a_damaged_cache_falls_back_to_the_sources(project, body):
    import marshal

    ir_path, graph_path = _paths(project)
    graph_cache.load(ir_path, graph_path)
    header = _cache(project).read_bytes().split(b"\n", 1)[0] + b"\n"
    payload = marshal.dumps(["a", "list"]) if body is None else body
    _cache(project).write_bytes(header + payload)
    assert graph_cache.load(ir_path, graph_path) == json.loads(graph_path.read_text())


def test_a_small_graph_is_not_cached(project, monkeypatch):
    monkeypatch.setattr(graph_cache, "CACHE_MIN_BYTES", 1 << 30)
    ir_path, graph_path = _paths(project)
    assert graph_cache.load(ir_path, graph_path)["nodes"]
    assert not _cache(project).exists()
    graph_cache.warm(ir_path, graph_path)
    assert not _cache(project).exists()
    assert graph_cache.warm_in_background(project) is False


def test_the_switch_turns_off_reading_and_writing(project, monkeypatch):
    ir_path, graph_path = _paths(project)
    graph_cache.load(ir_path, graph_path)
    graph_path.write_text(json.dumps(_graph(6)))
    stale = _cache(project).read_bytes()
    monkeypatch.setenv(graph_cache.CACHE_ENV, "0")
    assert len(graph_cache.load(ir_path, graph_path)["nodes"]) == 6
    assert _cache(project).read_bytes() == stale
    assert graph_cache.warm_in_background(project) is False


def test_no_state_directory_means_no_cache(tmp_path, monkeypatch):
    # A graphify-only project: graph.json outside a .neuralmind/ that doesn't exist.
    monkeypatch.setattr(graph_cache, "CACHE_MIN_BYTES", 0)
    (tmp_path / "graphify-out").mkdir()
    graph_path = tmp_path / "graphify-out" / "graph.json"
    graph_path.write_text(json.dumps(_graph()))
    ir_path = tmp_path / ".neuralmind" / "index_ir.json"
    assert graph_cache.load(ir_path, graph_path)["nodes"]
    assert not (tmp_path / ".neuralmind").exists()


def test_no_source_is_no_graph(tmp_path):
    assert graph_cache.load(tmp_path / "index_ir.json", tmp_path / "graph.json") is None


def test_warm_writes_only_a_missing_or_stale_cache(project, monkeypatch):
    ir_path, graph_path = _paths(project)
    graph_cache.warm(ir_path, graph_path)
    assert _cache(project).exists()
    _no_sources(monkeypatch)
    graph_cache.warm(ir_path, graph_path)  # current: no load


def test_the_backends_load_through_the_cache(project, monkeypatch):
    from neuralmind.in_memory_backend import InMemoryEmbeddingBackend

    first = InMemoryEmbeddingBackend(str(project))
    assert first.load_graph()
    _no_sources(monkeypatch)
    second = InMemoryEmbeddingBackend(str(project))
    assert second.load_graph()
    assert second.nodes == first.nodes and second.edges == first.edges


def test_the_background_writer_is_detached_and_silent(project, monkeypatch):
    started = []
    monkeypatch.setattr(
        graph_cache.subprocess, "Popen", lambda argv, **kw: started.append((argv, kw))
    )
    assert graph_cache.warm_in_background(project) is True
    argv, kw = started[0]
    assert argv[-2:] == ["neuralmind.graph_cache", str(project.resolve())]
    # Its output goes nowhere: a caller waiting on the hook's pipes would
    # otherwise wait for the writer too.
    for stream in ("stdin", "stdout", "stderr"):
        assert kw[stream] is subprocess.DEVNULL
    assert kw["start_new_session"] is True

    graph_cache.load(*_paths(project))
    started.clear()
    assert graph_cache.warm_in_background(project) is False  # current
    assert not started


def test_the_writer_process_writes_the_cache(project):
    env = dict(os.environ, PYTHONPATH=str(Path(graph_cache.__file__).parents[1]))
    env.pop(graph_cache.CACHE_ENV, None)
    # In a child, CACHE_MIN_BYTES is the real one: make the graph big enough.
    graph = _graph(3)
    graph["padding"] = "x" * graph_cache.CACHE_MIN_BYTES
    _paths(project)[1].write_text(json.dumps(graph))
    subprocess.run(
        [sys.executable, "-m", "neuralmind.graph_cache", str(project)],
        env=env,
        check=True,
        timeout=120,
    )
    assert graph_cache.load(*_paths(project)) == graph
    assert _cache(project).exists()


@pytest.mark.skipif(sys.platform == "win32", reason="flock")
def test_a_second_writer_leaves_it_to_the_first(project):
    import fcntl

    lock = project / ".neuralmind" / graph_cache.LOCK_FILENAME
    fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        assert graph_cache._main([str(project)]) == 0
        assert not _cache(project).exists()
    finally:
        os.close(fd)
    assert graph_cache._main([str(project)]) == 0
    assert _cache(project).exists()


def test_the_prompt_hook_gives_the_same_block_from_the_cache(temp_project, monkeypatch):
    from neuralmind import NeuralMind, hooks

    monkeypatch.setenv(hooks.RECALL_MIN_SIMILARITY_ENV, "0")
    monkeypatch.setattr(graph_cache, "CACHE_MIN_BYTES", 0)
    monkeypatch.setattr(graph_cache, "warm_in_background", lambda *_a: False)
    assert NeuralMind(str(temp_project)).build()["success"]
    cache = temp_project / ".neuralmind" / graph_cache.CACHE_FILENAME
    assert cache.exists()  # the build wrote it
    prompt = "How does authentication work?"

    monkeypatch.setenv(graph_cache.CACHE_ENV, "0")
    uncached = hooks._spread_for_prompt(str(temp_project), prompt)
    monkeypatch.delenv(graph_cache.CACHE_ENV)
    cache.unlink()
    missed = hooks._spread_for_prompt(str(temp_project), prompt)
    assert cache.exists()
    _no_sources(monkeypatch)
    cached = hooks._spread_for_prompt(str(temp_project), prompt)
    assert uncached and uncached == missed == cached


def test_the_prompt_hook_skips_the_structural_index(temp_project):
    from neuralmind import NeuralMind

    assert NeuralMind(str(temp_project)).build()["success"]
    full = NeuralMind(str(temp_project))
    assert full._load_existing_index()
    assert full._structural_index is not None
    lean = NeuralMind(str(temp_project))
    assert lean._load_existing_index(structural=False)
    assert lean._structural_index is None
    assert lean.selector is not None


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0, reason="POSIX modes")
def test_an_unwritable_state_directory_starts_no_writer(project, monkeypatch):
    started = []
    monkeypatch.setattr(graph_cache.subprocess, "Popen", lambda *a, **k: started.append(a))
    state = project / ".neuralmind"
    state.chmod(0o500)
    try:
        assert graph_cache.warm_in_background(project) is False
    finally:
        state.chmod(0o700)
    assert not started


def test_loading_an_index_asks_only_whether_it_has_rows(temp_project, monkeypatch):
    # get_stats() also counts every community: ~65 ms of the prompt hook on a
    # large index, to learn only that the store isn't empty.
    from neuralmind import NeuralMind

    assert NeuralMind(str(temp_project)).build()["success"]
    mind = NeuralMind(str(temp_project))

    def no_stats():
        raise AssertionError("_load_existing_index called get_stats()")

    monkeypatch.setattr(mind.embedder, "get_stats", no_stats)
    assert mind._load_existing_index()

    empty = NeuralMind(str(temp_project))
    monkeypatch.setattr(empty.embedder, "has_rows", lambda: False)
    assert not empty._load_existing_index()
