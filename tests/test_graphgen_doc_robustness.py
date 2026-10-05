"""Regression tests for the doc/schema layer of the built-in graph backend.

- A doc or schema file that isn't valid UTF-8 (a Latin-1 ``NOTES.md``) must
  not abort the whole build — it is still indexed, with U+FFFD replacements.
- Repeated incremental builds must not duplicate doc/schema edges or keep
  stale heading nodes: docs are re-extracted every build, so the previous
  graph's doc nodes/edges must not also be carried forward.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from neuralmind import graphgen

pytestmark = pytest.mark.skipif(not graphgen.is_available(), reason="tree-sitter not installed")


def _build(root: Path) -> dict:
    """Write graph.json (so the next build takes the incremental path) and load it."""
    return json.loads(graphgen.write_graph(root).read_text(encoding="utf-8"))


def _labels(graph: dict) -> set[str]:
    return {n["label"] for n in graph["nodes"]}


def _edge_triples(graph: dict, *, docs_only: bool = False) -> Counter:
    return Counter(
        (e["source"], e["target"], e["relation"])
        for e in graph["links"]
        if not (docs_only and e["source_file"].endswith(".py"))
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "pkg").mkdir(parents=True)
    (root / "a.py").write_text("def f():\n    return 1\n")
    (root / "pkg" / "mod.py").write_text("def g():\n    return 2\n")
    # Same directory as pkg/mod.py → a doc-code "describes" edge.
    (root / "pkg" / "README.md").write_text("# Pkg\n\nThe pkg module.\n")
    (root / "NOTES.md").write_text(
        "# Notes\n\nIntro.\n\n## Old Heading\n\nBody.\n\n## Gone\n\nX.\n"
    )
    (root / "schema.sql").write_text("CREATE TABLE users (id INT);\n")
    (root / "api.proto").write_text('syntax = "proto3";\nmessage Ping {\n  string id = 1;\n}\n')
    return root


# --------------------------------------------------------------------------- #
# H4 — non-UTF-8 doc/schema files
# --------------------------------------------------------------------------- #
def test_latin1_markdown_does_not_fail_build(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def f():\n    return 1\n")
    (tmp_path / "NOTES.md").write_bytes(b"# Notes\n\nCaf\xe9 au lait\n")

    graph = _build(tmp_path)

    assert "Notes" in _labels(graph)
    heading = next(n for n in graph["nodes"] if n["label"] == "Notes")
    assert heading["content_text"] == "Caf� au lait"


@pytest.mark.parametrize(
    ("name", "data", "label"),
    [
        ("schema.sql", b"-- caf\xe9\nCREATE TABLE users (id INT);\n", "TABLE:users"),
        ("api.proto", b'// caf\xe9\nsyntax = "proto3";\nmessage Ping {}\n', "message:Ping"),
        (
            "openapi.yaml",
            b"openapi: 3.0.0\ninfo:\n  title: Caf\xe9 API\n  version: '1'\n"
            b"paths:\n  /items:\n    get:\n      summary: List items\n",
            "List items",
        ),
    ],
)
def test_latin1_schema_files_do_not_fail_build(
    tmp_path: Path, name: str, data: bytes, label: str
) -> None:
    (tmp_path / "a.py").write_text("def f():\n    return 1\n")
    (tmp_path / name).write_bytes(data)

    assert label in _labels(_build(tmp_path))


def test_utf8_bom_does_not_hide_first_heading(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def f():\n    return 1\n")
    (tmp_path / "README.md").write_bytes(b"\xef\xbb\xbf# Title\n\nBody.\n")

    assert "Title" in _labels(_build(tmp_path))


# --------------------------------------------------------------------------- #
# H5 — incremental builds and doc/schema nodes/edges
# --------------------------------------------------------------------------- #
def test_no_change_rebuilds_produce_identical_graph(project: Path) -> None:
    first = _build(project)
    # Sanity: the fixture exercises doc, schema, and doc-code edges.
    relations = {e["relation"] for e in first["links"]}
    assert {"contains", "describes"} <= relations

    for _ in range(3):
        again = _build(project)
        assert len(again["nodes"]) == len(first["nodes"])
        assert len(again["links"]) == len(first["links"])
        assert _edge_triples(again) == _edge_triples(first)

    dupes = [t for t, n in _edge_triples(again).items() if n > 1]
    assert dupes == []


def test_code_change_keeps_doc_edges_exactly_once(project: Path) -> None:
    first = _build(project)
    (project / "a.py").write_text("def f():\n    return 1\n\n\ndef h():\n    return f()\n")

    again = _build(project)

    describes = [e for e in again["links"] if e["relation"] == "describes"]
    assert [(e["source"], e["target"]) for e in describes] == [("pkg_readme_md", "pkg_mod_py")]
    assert _edge_triples(again, docs_only=True) == _edge_triples(first, docs_only=True)


def test_renamed_and_removed_headings_leave_graph(project: Path) -> None:
    first = _build(project)
    assert {"Old Heading", "Gone"} <= _labels(first)

    # Same line numbers for the renamed heading; the "Gone" section is removed.
    (project / "NOTES.md").write_text("# Notes\n\nIntro.\n\n## New Heading\n\nBody.\n")
    again = _build(project)

    labels = _labels(again)
    assert "New Heading" in labels
    assert "Old Heading" not in labels
    assert "Gone" not in labels
    notes = [n for n in again["nodes"] if n["source_file"] == "NOTES.md"]
    assert len(notes) == 3  # file node + "Notes" + "New Heading"
