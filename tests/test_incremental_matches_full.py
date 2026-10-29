"""An incremental build, and the watcher's ``update_files``, give the graph a full build gives.

Calls resolve by name, to the first project function of that name in build
order, so which files an incremental build re-extracts, and in what order it
registers the rest, decides where a call points. Each test edits a small
project, then compares the incremental graph with a fresh full build of the
same tree. Community numbers aside: an incremental build keeps each unchanged
file's number by design.
"""

from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path

import pytest

from neuralmind import graphgen


def _content(graph: dict) -> tuple[Counter, Counter]:
    nodes = Counter(
        json.dumps({k: v for k, v in n.items() if k != "community"}, sort_keys=True)
        for n in graph["nodes"]
    )
    links = Counter(json.dumps(e, sort_keys=True) for e in graph["links"])
    return nodes, links


def _full(root: Path, tmp_path: Path) -> dict:
    fresh = tmp_path / "fresh"
    shutil.copytree(root, fresh)
    shutil.rmtree(fresh / ".neuralmind", ignore_errors=True)
    return json.loads(graphgen.write_graph(fresh).read_text())


def _calls(graph: dict) -> list[tuple[str, str]]:
    return sorted((e["source"], e["target"]) for e in graph["links"] if e["relation"] == "calls")


def _write(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    _write(
        root,
        {
            "a.py": 'def load():\n    return "a"\n',
            "b.py": 'def load():\n    return "b"\n',
            "c.py": "import a\n\n\ndef run():\n    return load()\n",
            "m.py": "def helper():\n    return 1\n",
            "n.py": "import m\n\n\ndef use():\n    return helper()\n",
        },
    )
    graphgen.write_graph(root)
    return root


def _edit(root: Path, rel: str, text: str) -> None:
    time.sleep(0.01)  # a new mtime, even on a coarse clock
    (root / rel).write_text(text)


class TestBuild:
    def test_a_call_keeps_the_target_a_full_build_gives(self, project, tmp_path):
        # Editing a.py re-extracts it. Registering the unchanged b.py's `load`
        # first, as incremental builds did, pointed c.run at b.load.
        _edit(project, "a.py", 'def load():\n    return "a2"\n')
        graph = json.loads(graphgen.write_graph(project).read_text())
        assert ("c_py__run_fn", "a_py__load_fn") in _calls(graph)
        assert _content(graph) == _content(_full(project, tmp_path))

    def test_a_new_same_named_function_takes_over_calls_in_unedited_files(self, project, tmp_path):
        # m.py's helper() serves n.use. A `helper` added to a file that sorts
        # first takes that call over in a full build, though n.py is unedited.
        _edit(project, "b.py", 'def load():\n    return "b"\n\n\ndef helper():\n    return 2\n')
        graph = json.loads(graphgen.write_graph(project).read_text())
        assert ("n_py__use_fn", "b_py__helper_fn") in _calls(graph)
        assert _content(graph) == _content(_full(project, tmp_path))

    def test_removing_the_function_a_call_used_hands_it_to_the_next(self, project, tmp_path):
        _edit(project, "a.py", "def other():\n    return 0\n")
        graph = json.loads(graphgen.write_graph(project).read_text())
        assert ("c_py__run_fn", "b_py__load_fn") in _calls(graph)
        assert _content(graph) == _content(_full(project, tmp_path))

    def test_an_edit_inside_a_function_keeps_the_calls_into_it(self, project, tmp_path):
        _edit(project, "m.py", "def helper():\n    return 42\n")
        graph = json.loads(graphgen.write_graph(project).read_text())
        assert ("n_py__use_fn", "m_py__helper_fn") in _calls(graph)
        assert _content(graph) == _content(_full(project, tmp_path))

    def test_file_nodes_come_in_a_full_build_s_order(self, project, tmp_path):
        # The doc-code coupling takes the first 50 pairs in node order.
        _edit(project, "a.py", 'def load():\n    return "a3"\n')
        graph = json.loads(graphgen.write_graph(project).read_text())
        full = _full(project, tmp_path)

        def files(g: dict) -> list[str]:
            return [
                n["source_file"] for n in g["nodes"] if n["id"] == graphgen._slug(n["source_file"])
            ]

        assert files(graph) == files(full)


class TestUpdateFiles:
    def _update(self, root: Path, changed: list[str], removed: list[str] | None = None) -> dict:
        path = root / ".neuralmind" / "graph.json"
        graph, _ = graphgen.update_files(root, json.loads(path.read_text()), changed, removed)
        return graph

    def test_a_call_keeps_the_target_a_full_build_gives(self, project, tmp_path):
        _edit(project, "a.py", 'def load():\n    return "a2"\n')
        _edit(project, "c.py", "import a\n\n\ndef run():\n    return load() + 1\n")
        graph = self._update(project, ["a.py", "c.py"])
        assert ("c_py__run_fn", "a_py__load_fn") in _calls(graph)
        assert _content(graph) == _content(_full(project, tmp_path))

    def test_a_new_same_named_function_takes_over_calls_in_unedited_files(self, project, tmp_path):
        _edit(project, "b.py", 'def load():\n    return "b"\n\n\ndef helper():\n    return 2\n')
        graph = self._update(project, ["b.py"])
        assert ("n_py__use_fn", "b_py__helper_fn") in _calls(graph)
        assert _content(graph) == _content(_full(project, tmp_path))

    def test_a_deleted_file_hands_its_calls_to_the_next(self, project, tmp_path):
        (project / "a.py").unlink()
        graph = self._update(project, [], ["a.py"])
        assert ("c_py__run_fn", "b_py__load_fn") in _calls(graph)
        assert _content(graph) == _content(_full(project, tmp_path))


def test_a_synthetic_external_class_is_not_registered_by_name():
    # Extraction links to ext__ stand-ins (a base class from a package) but
    # never registers them, so a re-parsed `extends EventEmitter` must not
    # find one as a candidate beside the project's own class.
    b = graphgen._GraphBuilder()
    graphgen._register_node_symbol(
        b,
        {
            "id": "ext__eventemitter_cls",
            "label": "EventEmitter",
            "file_type": "code",
            "source_file": "x.tsx",
        },
    )
    assert b.class_by_name == {}


def test_an_edit_inside_a_function_re_extracts_only_that_file(project, monkeypatch):
    # n.py imports m.py. The build keeps n.py's edge into m.helper, which
    # comes back under the same id, so n.py isn't re-extracted: the
    # transitive importer closure that did it was most of a large repository.
    from neuralmind.incremental_extract import IncrementalExtractor

    seen: list[list[str]] = []
    real = IncrementalExtractor.get_changed_with_dependents

    def spy(self, *args, **kwargs):
        seen.append(real(self, *args, **kwargs))
        return seen[-1]

    monkeypatch.setattr(IncrementalExtractor, "get_changed_with_dependents", spy)
    _edit(project, "m.py", "def helper():\n    return 43\n")
    graph = json.loads(graphgen.write_graph(project).read_text())
    assert seen == [["m.py"]]
    assert ("n_py__use_fn", "m_py__helper_fn") in _calls(graph)
