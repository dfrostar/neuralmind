"""Regression tests: node ids stay distinct, and the file walk stays in bounds.

- ``_slug`` folds case, punctuation and non-ASCII, so two different files or
  symbols could mint the same node id and one silently vanished (``api/v1.py``
  and ``api_v1.py`` shared a file node; ``docs/安装.md`` and ``docs/使用.md``
  both became ``docs_md``). Colliding entities now get distinct ids; every id
  that never collided stays byte-identical (learned synapse memory is keyed by
  node id).
- Outside git (or with ``respect_gitignore: false``) the directory walk
  followed symlinked directories anywhere: a link to an outside directory
  pulled foreign files into the index and ``src/loop -> ..`` recursed until
  the path got too long.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuralmind import graphgen

pytestmark = pytest.mark.skipif(not graphgen.is_available(), reason="tree-sitter not installed")


def _write(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


def _ids(graph: dict) -> set[str]:
    return {n["id"] for n in graph["nodes"]}


def _file_node(graph: dict, rel: str) -> dict:
    """The file-level node of ``rel`` (the one that contains its other nodes)."""
    ids = {n["id"]: n for n in graph["nodes"]}
    roots = [
        n
        for n in graph["nodes"]
        if n["source_file"] == rel
        and not any(e["target"] == n["id"] and e["relation"] == "contains" for e in graph["links"])
        and n["file_type"] in ("code", "document")
        and not n["id"].startswith("ext__")
    ]
    assert len(roots) == 1, (rel, [r["id"] for r in roots], sorted(ids))
    return roots[0]


def _assert_contains_stays_in_file(graph: dict) -> None:
    by_id = {n["id"]: n for n in graph["nodes"]}
    for e in graph["links"]:
        if e["relation"] != "contains":
            continue
        assert by_id[e["source"]]["source_file"] == e["source_file"], e
        assert by_id[e["target"]]["source_file"] == e["source_file"], e


def _build(root: Path) -> dict:
    """Write graph.json (so the next build takes the incremental path) and load it."""
    return json.loads(graphgen.write_graph(root).read_text(encoding="utf-8"))


def _fresh(root: Path, scratch: Path) -> dict:
    """A from-scratch build of ``root``'s sources (no previous graph or cache)."""
    import shutil

    shutil.copytree(root, scratch, ignore=shutil.ignore_patterns(".neuralmind"))
    return graphgen.build_graph(scratch)


def _shape(graph: dict) -> tuple[set, set]:
    nodes = {(n["id"], n["label"], n["source_file"]) for n in graph["nodes"]}
    edges = {(e["relation"], e["source"], e["target"]) for e in graph["links"]}
    return nodes, edges


# --------------------------------------------------------------------------- #
# Node ids never collide
# --------------------------------------------------------------------------- #
_COLLIDING_FILES = {
    "api/v1.py": "def handler_v1(): pass\n",
    "api_v1.py": "def handler_flat(): pass\n",
    "my-mod.py": "def dash(): pass\n",
    "my_mod.py": "def under(): pass\n",
    "docs/安装.md": "# 安装\ninstall steps\n",
    "docs/使用.md": "# 使用\nusage steps\n",
    "app.py": "def main(): pass\n",
}


def test_colliding_paths_get_their_own_file_nodes(tmp_path: Path) -> None:
    graph = graphgen.build_graph(_write(tmp_path, _COLLIDING_FILES))
    file_ids = {rel: _file_node(graph, rel)["id"] for rel in _COLLIDING_FILES}
    assert len(set(file_ids.values())) == len(file_ids), file_ids
    _assert_contains_stays_in_file(graph)
    labels = {n["label"] for n in graph["nodes"]}
    assert {"handler_v1()", "handler_flat()", "dash()", "under()", "安装", "使用"} <= labels
    # Disambiguated ids keep the extension last (domain classification keys on it).
    assert file_ids["api/v1.py"].endswith("_py") and file_ids["api_v1.py"].endswith("_py")
    assert file_ids["docs/安装.md"].endswith("_md")
    # An all-non-ASCII stem keeps its characters rather than a bare hash.
    assert file_ids["docs/安装.md"] == "docs_安装_md"
    assert file_ids["docs/使用.md"] == "docs_使用_md"


def test_non_colliding_ids_are_unchanged(tmp_path: Path) -> None:
    graph = graphgen.build_graph(
        _write(
            tmp_path,
            {
                "app.py": "class Foo:\n    def run(self): pass\ndef main(): pass\nX = 1\n",
                "docs/安装.md": "# 安装\nsteps\n",
                "calc.py": "def 计算():\n    pass\n",
            },
        )
    )
    assert {
        "app_py",
        "app_py__foo_cls",
        "app_py__foo_cls__run_fn",
        "app_py__main_fn",
        "app_py__x_sym",
        "docs_md",
        "docs_md__h1",
        "calc_py",
        "calc_py___fn",
    } <= _ids(graph)


def test_colliding_symbols_in_one_file_get_their_own_nodes(tmp_path: Path) -> None:
    graph = graphgen.build_graph(
        _write(
            tmp_path,
            {
                "calc.py": (
                    "def 计算():\n    pass\n"
                    "def 处理():\n    pass\n"
                    "class Foo:\n    def run(self): pass\n"
                    "class foo:\n    def walk(self): pass\n"
                ),
            },
        )
    )
    labels = {n["label"]: n["id"] for n in graph["nodes"]}
    assert {"计算()", "处理()", "Foo", "foo", "run()", "walk()"} <= set(labels)
    assert len({labels[k] for k in ("计算()", "处理()")}) == 2
    assert len({labels[k] for k in ("Foo", "foo")}) == 2
    # First definition keeps the id it always had.
    assert labels["计算()"] == "calc_py___fn"
    assert labels["Foo"] == "calc_py__foo_cls"
    assert labels["处理()"] == "calc_py__处理_fn"
    # Each method hangs off its own class.
    assert labels["run()"].startswith(labels["Foo"] + "__")
    assert labels["walk()"].startswith(labels["foo"] + "__")
    _assert_contains_stays_in_file(graph)


def test_ruby_bang_method_does_not_merge_with_its_plain_twin(tmp_path: Path) -> None:
    if not graphgen.language_available("ruby"):
        pytest.skip("tree-sitter-ruby not installed")
    graph = graphgen.build_graph(
        _write(tmp_path, {"m.rb": "class A\n  def save\n  end\n  def save!\n  end\nend\n"})
    )
    labels = {n["label"]: n["id"] for n in graph["nodes"]}
    assert labels["save()"] == "m_rb__a_cls__save_fn"
    assert labels["save!()"] != labels["save()"]


def test_file_ids_do_not_depend_on_which_collider_came_first(tmp_path: Path) -> None:
    rels = ["api/v1.py", "api_v1.py", "API/V1.py"]
    forward = graphgen._file_id_overrides(tmp_path, rels)
    backward = graphgen._file_id_overrides(tmp_path, list(reversed(rels)))
    assert forward == backward
    assert len(set(forward.values())) == 3


def test_incremental_build_matches_full_build_when_a_collider_appears(tmp_path: Path) -> None:
    root = _write(
        tmp_path / "p",
        {"api_v1.py": "def handler(): pass\n", "app.py": "import api_v1\n"},
    )
    first = _build(root)
    assert "api_v1_py" in _ids(first)

    _write(root, {"api/v1.py": "def other(): pass\n"})
    incremental = _build(root)
    assert _shape(incremental) == _shape(_fresh(root, tmp_path / "fresh1"))
    assert "api_v1_py" not in _ids(incremental)

    (root / "api" / "v1.py").unlink()
    reverted = _build(root)
    assert _shape(reverted) == _shape(_fresh(root, tmp_path / "fresh2"))
    assert "api_v1_py" in _ids(reverted)
    assert ("imports_from", "app_py", "api_v1_py") in _shape(reverted)[1]


def test_update_files_renames_a_file_that_gains_a_collider(tmp_path: Path) -> None:
    root = _write(
        tmp_path,
        {"api_v1.py": "def handler(): pass\n", "app.py": "import api_v1\n"},
    )
    graph = graphgen.build_graph(root)
    _write(root, {"api/v1.py": "def other(): pass\n"})

    updated, _ = graphgen.update_files(root, graph, ["api/v1.py"])
    assert _shape(updated) == _shape(graphgen.build_graph(root))
    flat = _file_node(updated, "api_v1.py")["id"]
    # app.py's import edge follows api_v1.py to its new id.
    assert ("imports_from", "app_py", flat) in _shape(updated)[1]

    (root / "api" / "v1.py").unlink()
    reverted, _ = graphgen.update_files(root, updated, [], ["api/v1.py"])
    assert _shape(reverted) == _shape(graphgen.build_graph(root))
    assert ("imports_from", "app_py", "api_v1_py") in _shape(reverted)[1]


def test_update_files_repairs_a_graph_that_merged_two_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A graph from before the fix holds one file node for two colliding files;
    touching either must not leave the other's symbols orphaned."""
    root = _write(
        tmp_path,
        {
            "api/v1.py": "def handler_v1(): pass\n",
            "api_v1.py": "def handler_flat(): pass\n",
            "app.py": "import api_v1\n",
        },
    )
    with monkeypatch.context() as m:
        m.setattr(graphgen, "_file_id_overrides", lambda root, rels: {})  # the old ids
        merged = graphgen.build_graph(root)
    assert "api_v1_py" in _ids(merged)

    updated, _ = graphgen.update_files(root, merged, ["api/v1.py"])
    assert _shape(updated) == _shape(graphgen.build_graph(root))


def test_doc_code_coupling_reaches_disambiguated_code_files(tmp_path: Path) -> None:
    graph = graphgen.build_graph(
        _write(
            tmp_path,
            {
                "pkg/README.md": "# Pkg\n",
                "pkg/a-b.py": "def f(): pass\n",
                "pkg/a_b.py": "def g(): pass\n",
            },
        )
    )
    described = {e["target"] for e in graph["links"] if e["relation"] == "describes"}
    assert {_file_node(graph, "pkg/a-b.py")["id"], _file_node(graph, "pkg/a_b.py")["id"]} <= (
        described
    )


# --------------------------------------------------------------------------- #
# The walk stays inside the project
# --------------------------------------------------------------------------- #
def _symlink(link: Path, target: str | Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported here")


@pytest.fixture
def linked_project(tmp_path: Path) -> Path:
    outside = _write(tmp_path / "outside", {"secret_mod.py": "def outside_fn(): pass\n"})
    root = _write(
        tmp_path / "proj",
        {"src/app.py": "def f(): pass\n", "lib/util.py": "def g(): pass\n"},
    )
    _symlink(root / "src" / "loop", "..")  # a loop back to the project root
    _symlink(root / "ext", outside)  # a directory outside the project
    _symlink(root / "a_alias", root / "lib")  # an alias of a real directory
    return root


def _rels(root: Path, files: list[Path]) -> list[str]:
    return [f.relative_to(root).as_posix() for f in files]


def test_walk_skips_outside_links_and_loops(linked_project: Path) -> None:
    root = linked_project
    files = _rels(root, graphgen._walk_files(root, graphgen._DEFAULT_IGNORES, {".py"}, ()))
    # Each real file once, under its real path; nothing from outside.
    assert files == ["lib/util.py", "src/app.py"]


def test_build_outside_git_ignores_outside_links(linked_project: Path) -> None:
    graph = graphgen.build_graph(linked_project)
    assert {n["source_file"] for n in graph["nodes"]} == {"lib/util.py", "src/app.py"}


def test_respect_gitignore_false_ignores_outside_links(linked_project: Path) -> None:
    root = linked_project
    (root / ".neuralmind.yaml").write_text("respect_gitignore: false\n")
    files = _rels(root, graphgen._iter_source_files(root, graphgen._DEFAULT_IGNORES))
    assert files == ["lib/util.py", "src/app.py"]


def test_link_to_an_unwalked_directory_inside_the_project_is_followed(tmp_path: Path) -> None:
    """A link into the project whose target isn't otherwise walked (here an
    ignored directory) still contributes its files, under the link's path."""
    root = _write(tmp_path, {"node_modules/pkg/mod.py": "def m(): pass\n", "app.py": ""})
    _symlink(root / "vendored", root / "node_modules" / "pkg")
    files = _rels(root, graphgen._walk_files(root, graphgen._DEFAULT_IGNORES, {".py"}, ()))
    assert files == ["app.py", "vendored/mod.py"]
