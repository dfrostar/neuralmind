"""Structural consistency checks for the polyglot eval fixtures (issue #173).

These tests are **stdlib-only** (json + pathlib) so they run in CI without
chromadb, tiktoken, or graphify — mirroring the synapse layer's stdlib-only
test convention. They do NOT measure retrieval quality (that needs the
embedder); they guard that the TS and Go fixtures, their hand-authored
graph.json, and their gold-module query sets stay mutually consistent so the
per-language hit-rate harness has something valid to run against later
(Epic E2.4).

If a fixture's graph schema, source files, or query set drift apart, this
fails loudly — which is the whole point of committing the fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures"

REFERENCE_GRAPH = (
    REPO_ROOT / "neuralmind" / "demo_data" / "sample_project" / "graphify-out" / "graph.json"
)

# (fixture dir, query-set file)
CASES = [
    ("sample_project_ts", "benchmark_queries_ts.json"),
    ("sample_project_go", "benchmark_queries_go.json"),
]

TOP_LEVEL_KEYS = {
    "directed",
    "multigraph",
    "graph",
    "nodes",
    "links",
    "hyperedges",
    "built_at_commit",
}
NODE_KEYS = {
    "label",
    "file_type",
    "source_file",
    "source_location",
    "id",
    "community",
    "norm_label",
}
LINK_REQUIRED = {
    "relation",
    "confidence",
    "source_file",
    "source_location",
    "weight",
    "source",
    "target",
    "confidence_score",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


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
        if src in {"<builtin>"} or node["source_location"] == "L1":
            continue
        line_no = int(node["source_location"].lstrip("L"))
        text = (FIXTURES / fixture / src).read_text().splitlines()[line_no - 1]
        base = node["label"].rstrip("()")
        assert base in text, f"{fixture}:{src}:{line_no} does not define {base!r}"


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
    """The TS/Go query sets must carry the same query ids as the Python set so
    per-language hit-rate is comparing like with like (Epic E2.4)."""
    py_ids = {q["id"] for q in _load(FIXTURES / "benchmark_queries.json")["queries"]}
    for _fixture, queryfile in CASES:
        ids = {q["id"] for q in _load(FIXTURES / queryfile)["queries"]}
        assert ids == py_ids, f"{queryfile} query ids differ from Python fixture: {ids ^ py_ids}"
