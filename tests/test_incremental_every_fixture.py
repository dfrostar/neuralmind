"""Every language fixture: each incremental build equals a full one, byte for byte.

The hand-written cases in ``test_incremental_matches_full.py`` cover what a
review thought to try. This sweeps every ``tests/fixtures/sample_project*``
project through the same five edits, chosen from its own graph so each
language gets them: a comment in X, the file whose functions other files
call most; Y renaming one of its functions to N, X's most-called name, so Y
gains a name other files look up; X losing N; a copy of X added; Y deleted.
Fixtures with no cross-file calls (the dynamic-import ones) get the comment,
the copy and the deletion. A fixture with no code, like the prose one
``test_pipeline_integration`` writes when it's imported, has nothing to edit.

After each edit the incremental ``graph.json`` must equal, byte for byte, a
full re-extraction of the same tree that keeps the previous ``graph.json``
(so community numbers carry over the same way), and ``update_files`` must
give the same nodes and edges, community numbers aside.
"""

from __future__ import annotations

import json
import re
import shutil
from collections import Counter
from pathlib import Path

import pytest

from neuralmind import graphgen

FIXTURES = Path(__file__).parent / "fixtures"


def _name(label: str) -> str:
    return re.split(r"::|\.", label.split("(")[0])[-1]


def _content(graph: dict) -> tuple[Counter, Counter]:
    nodes = Counter(
        json.dumps({k: v for k, v in n.items() if k != "community"}, sort_keys=True)
        for n in graph["nodes"]
    )
    return nodes, Counter(json.dumps(e, sort_keys=True) for e in graph["links"])


def _edits(graph: dict) -> list:
    nodes = {n["id"]: n for n in graph["nodes"]}
    called = Counter(
        (nodes[e["target"]]["source_file"], _name(nodes[e["target"]]["label"]))
        for e in graph["links"]
        if e["relation"] == "calls"
        and e["target"] in nodes
        and nodes[e["target"]]["source_file"] != e["source_file"]
    )
    code = sorted({n["source_file"] for n in graph["nodes"] if n["file_type"] == "code"} - {""})
    functions: dict[str, str] = {}
    for node in graph["nodes"]:
        if node["id"].endswith("_fn") and _name(node["label"]).isidentifier():
            functions.setdefault(node["source_file"], _name(node["label"]))
    x, n = called.most_common(1)[0][0] if called else (code[0], None)
    others = sorted(f for f in functions if f != x) or [f for f in code if f != x]
    y = next((f for f in others if Path(f).parent != Path(x).parent), others[0])
    comment = "\n# edited\n" if x.endswith((".py", ".rb")) else "\n// edited\n"
    copy = Path(x).with_name(Path(x).stem + "Copy" + Path(x).suffix).as_posix()

    def sub(rel: str, old: str, new: str):
        return lambda r: (r / rel).write_text(
            re.sub(rf"\b{re.escape(old)}\b", new, (r / rel).read_text())
        )

    # (what, edit, files it changes, files it removes)
    edits = [("comment", lambda r: (r / x).write_text((r / x).read_text() + comment), [x], [])]
    if n:
        edits += [
            ("a file gains a called name", sub(y, functions[y], n), [y], []),
            ("the called name is renamed", sub(x, n, n + "_renamed"), [x], []),
        ]
    return edits + [
        ("a file is added", lambda r: shutil.copy(r / x, r / copy), [copy], []),
        ("a file is deleted", lambda r: (r / y).unlink(), [], [y]),
    ]


def _has_code(fixture: Path) -> bool:
    return any(
        f.suffix in graphgen.SUPPORTED_SUFFIXES and ".neuralmind" not in f.parts
        for f in fixture.rglob("*")
    )


@pytest.mark.parametrize(
    "fixture", sorted(p.name for p in FIXTURES.glob("sample_project*") if _has_code(p))
)
def test_every_incremental_build_equals_a_full_extraction(fixture, tmp_path):
    inc, ref, watch = tmp_path / "inc", tmp_path / "ref", tmp_path / "watch"
    for d in (inc, ref, watch):
        shutil.copytree(
            FIXTURES / fixture, d, ignore=shutil.ignore_patterns(".neuralmind", "graphify-out")
        )
    graph = json.loads(graphgen.write_graph(inc).read_text())

    for what, edit, changed, removed in _edits(graph):
        for d in (inc, ref, watch):
            edit(d)
        previous = (inc / ".neuralmind" / "graph.json").read_bytes()

        incremental = graphgen.write_graph(inc).read_bytes()
        shutil.rmtree(ref / ".neuralmind", ignore_errors=True)
        (ref / ".neuralmind").mkdir()
        (ref / ".neuralmind" / "graph.json").write_bytes(previous)
        full = graphgen.write_graph(ref).read_bytes()
        assert incremental == full, what

        updated, _ = graphgen.update_files(watch, json.loads(previous), changed, removed)
        assert _content(updated) == _content(json.loads(full)), what
