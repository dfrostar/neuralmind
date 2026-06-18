"""Structural consistency checks for the polyglot eval fixtures (issue #173).

These tests are **stdlib-only** (json + pathlib) so they run in CI without
chromadb, tiktoken, or graphify — mirroring the synapse layer's stdlib-only
test convention. They do NOT measure retrieval quality (that needs the
embedder); they guard that the TS, Go, and Rust fixtures, their
graph.json, and their gold-module query sets stay mutually consistent so the
per-language hit-rate harness has something valid to run against later
(Epic E2.4).

If a fixture's graph schema, source files, or query set drift apart, this
fails loudly — which is the whole point of committing the fixtures.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures"

# The Python fixture's real graphify output is the schema source of truth: the
# hand-authored TS/Go graphs must match its shape, so the expected key sets are
# derived from it rather than hard-coded (and drift loudly if graphify changes).
REFERENCE_GRAPH = (
    REPO_ROOT / "neuralmind" / "demo_data" / "sample_project" / "graphify-out" / "graph.json"
)

# (fixture dir, query-set file)
CASES = [
    ("sample_project_ts", "benchmark_queries_ts.json"),
    ("sample_project_go", "benchmark_queries_go.json"),
    ("sample_project_rust", "benchmark_queries_rust.json"),
]


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _reference_schema() -> tuple[set[str], set[str], set[str]]:
    """Expected (top-level, node, required-link) key sets from the reference graph."""
    ref = _load(REFERENCE_GRAPH)
    top = set(ref)
    node_keys = set().union(*(set(n) for n in ref["nodes"]))
    # Required link keys = those present on *every* link (e.g. `context` is optional).
    link_required = set.intersection(*(set(link) for link in ref["links"]))
    return top, node_keys, link_required


TOP_LEVEL_KEYS, NODE_KEYS, LINK_REQUIRED = _reference_schema()


@pytest.mark.parametrize("fixture,queryfile", CASES)
def test_graph_matches_reference_schema(fixture: str, queryfile: str) -> None:
    graph = _load(FIXTURES / fixture / "graphify-out" / "graph.json")

    assert set(graph) == TOP_LEVEL_KEYS, f"{fixture} graph top-level keys drifted"
    assert graph["directed"] is False
    assert graph["nodes"], "graph has no nodes"
    assert graph["links"], "graph has no links"

    for node in graph["nodes"]:
        assert set(node) == NODE_KEYS, f"{fixture} node keys drifted: {node.get('id')}"
        assert node["file_type"] in {"code", "rationale", "document"}

    for link in graph["links"]:
        assert LINK_REQUIRED <= set(link), f"{fixture} link missing keys: {link}"
        assert link["relation"] in {
            "contains",
            "imports_from",
            "calls",
            "rationale_for",
            "inherits",
        }


@pytest.mark.parametrize("fixture,queryfile", CASES)
def test_graph_referential_integrity(fixture: str, queryfile: str) -> None:
    graph = _load(FIXTURES / fixture / "graphify-out" / "graph.json")
    ids = {n["id"] for n in graph["nodes"]}
    for link in graph["links"]:
        assert link["source"] in ids, f"{fixture}: dangling source {link['source']}"
        assert link["target"] in ids, f"{fixture}: dangling target {link['target']}"


@pytest.mark.parametrize("fixture,queryfile", CASES)
def test_symbol_lines_point_at_real_definitions(fixture: str, queryfile: str) -> None:
    """Each code-symbol node's source_location must land on a line that
    actually mentions the symbol — keeps the hand-authored graph honest."""
    graph = _load(FIXTURES / fixture / "graphify-out" / "graph.json")
    for node in graph["nodes"]:
        if node["file_type"] != "code":
            continue
        src = node["source_file"]
        label = node["label"]
        # Skip only genuine non-symbol nodes: builtins and file-level nodes
        # (whose label is the filename). Every other code node is a real symbol
        # we DO validate — including any that lands on L1, since that signals
        # _gen_graph.py failed to locate it and must fail loudly, not be skipped.
        if src == "<builtin>" or label.endswith((".ts", ".go", ".rs")):
            continue
        line_no = int(node["source_location"].lstrip("L"))
        text = (FIXTURES / fixture / src).read_text().splitlines()[line_no - 1]
        base = label.rstrip("()")
        assert base in text, f"{fixture}:{src}:{line_no} does not define {base!r}"


@pytest.mark.parametrize("fixture,queryfile", CASES)
def test_edge_locations_point_at_real_lines(fixture: str, queryfile: str) -> None:
    """`calls`/`imports_from` edges must cite the line that actually performs
    the call or import, so the committed graph stays navigable and any future
    eval that validates relationships isn't reading stale provenance."""
    graph = _load(FIXTURES / fixture / "graphify-out" / "graph.json")
    labels = {n["id"]: n["label"] for n in graph["nodes"]}
    for link in graph["links"]:
        src = link["source_file"]
        if src == "<builtin>":
            continue
        line_no = int(link["source_location"].lstrip("L"))
        text = (FIXTURES / fixture / src).read_text().splitlines()[line_no - 1]
        if link["relation"] == "calls":
            callee = labels[link["target"]].rstrip("()")
            assert re.search(
                rf"\b{re.escape(callee)}\s*\(", text
            ), f"{fixture}:{src}:{line_no} is not a call to {callee}(): {text!r}"
        elif link["relation"] == "imports_from":
            assert (
                "import" in text
                or "from" in text
                or text.strip().startswith('"')
                or text.lstrip().startswith("use ")
            ), f"{fixture}:{src}:{line_no} is not an import line: {text!r}"


@pytest.mark.parametrize("fixture,queryfile", CASES)
def test_expected_modules_exist_in_graph_and_on_disk(fixture: str, queryfile: str) -> None:
    graph = _load(FIXTURES / fixture / "graphify-out" / "graph.json")
    queries = _load(FIXTURES / queryfile)
    source_files = {n["source_file"] for n in graph["nodes"]}

    assert queries["queries"], "query set is empty"
    for item in queries["queries"]:
        assert item["expected_modules"], f"{item['id']} has no expected modules"
        for module in item["expected_modules"]:
            assert module in source_files, f"{queryfile}:{item['id']} -> {module} not in graph"
            assert (FIXTURES / fixture / module).exists(), f"{module} missing on disk"


def test_query_sets_mirror_python_fixture_shape() -> None:
    """The TS/Go query sets must mirror the Python set's ids, questions, shapes
    and learning seed so per-language hit-rate compares like with like (Epic
    E2.4). Only `expected_modules` legitimately differs (per-language paths)."""
    py = _load(FIXTURES / "benchmark_queries.json")
    py_by_id = {q["id"]: q for q in py["queries"]}
    for _fixture, queryfile in CASES:
        data = _load(FIXTURES / queryfile)
        by_id = {q["id"]: q for q in data["queries"]}
        assert set(by_id) == set(
            py_by_id
        ), f"{queryfile} query ids differ from Python fixture: {set(by_id) ^ set(py_by_id)}"
        # Compare the seed history (the signal that matters); the sibling
        # `_comment` is human prose and may be worded per-language.
        assert (data.get("learning_seed") or {}).get("history") == (
            py.get("learning_seed") or {}
        ).get("history"), f"{queryfile} learning_seed history differs from the Python fixture"
        for qid, pq in py_by_id.items():
            assert (
                by_id[qid]["question"] == pq["question"]
            ), f"{queryfile}:{qid} question drifted from the Python fixture"
            assert (
                by_id[qid]["shape"] == pq["shape"]
            ), f"{queryfile}:{qid} shape drifted from the Python fixture"
            assert by_id[qid]["expected_modules"], f"{queryfile}:{qid} has no expected_modules"
