"""Tests for the canonical IR contract and the graphify⇄IR adapter (PRD 1).

Stdlib-only — like the synapse layer, these run without the embedding deps.
"""

import json
from pathlib import Path

import pytest

from neuralmind import ir as ir_mod

FIXTURE_DIR = Path(__file__).parent / "fixtures"
TS_GRAPH = FIXTURE_DIR / "sample_project_ts" / "graphify-out" / "graph.json"

# Fields every downstream consumer reads off a node / edge. Round-trip parity
# is defined as equality on exactly these.
_NODE_FIELDS = (
    "id",
    "label",
    "file_type",
    "source_file",
    "source_location",
    "community",
    "norm_label",
)
_EDGE_FIELDS = (
    "relation",
    "source",
    "target",
    "weight",
    "confidence",
    "confidence_score",
    "source_file",
)


def _synthetic_graph() -> dict:
    """A minimal graphify-shaped graph: a file, two symbols, a doc, edges."""
    return {
        "directed": False,
        "multigraph": False,
        "graph": {},
        "built_at_commit": "abc123",
        "generated_by": "neuralmind.graphgen (tree-sitter)",
        "schema_version": 1,
        "nodes": [
            {
                "label": "app.py",
                "file_type": "code",
                "source_file": "app.py",
                "source_location": "L1",
                "id": "app_py",
                "community": 0,
                "norm_label": "app.py",
            },
            {
                "label": "handle",
                "file_type": "code",
                "source_file": "app.py",
                "source_location": "L10",
                "id": "app_py_handle",
                "community": 0,
                "norm_label": "handle",
            },
            {
                "label": "Server",
                "file_type": "code",
                "source_file": "app.py",
                "source_location": "L20",
                "id": "app_py_Server",
                "community": 0,
                "norm_label": "server",
            },
            {
                "label": "README.md",
                "file_type": "document",
                "source_file": "README.md",
                "source_location": "L1",
                "id": "readme_md",
                "community": 1,
                "norm_label": "readme.md",
            },
        ],
        "links": [
            {
                "relation": "contains",
                "context": "contains",
                "confidence": "EXTRACTED",
                "source_file": "app.py",
                "source_location": "L1",
                "weight": 1.0,
                "source": "app_py",
                "target": "app_py_handle",
                "confidence_score": 1.0,
            },
            {
                "relation": "calls",
                "context": "call",
                "confidence": "EXTRACTED",
                "source_file": "app.py",
                "source_location": "L12",
                "weight": 1.0,
                "source": "app_py_handle",
                "target": "app_py_Server",
                "confidence_score": 1.0,
            },
        ],
        "hyperedges": [],
    }


def _index(items, fields):
    return {
        it["id"] if "id" in fields else (it["source"], it["target"], it["relation"]): it
        for it in items
    }


# --------------------------------------------------------------------------- #
# Adapter + round-trip parity (FR1, technical req: equivalence fixtures)
# --------------------------------------------------------------------------- #


def test_from_graph_json_basic_shape():
    ir = ir_mod.from_graph_json(_synthetic_graph(), source_backend="graph")
    assert ir.ir_version == ir_mod.IR_VERSION
    assert ir.source_backend == "graph"
    assert ir.source_schema_version == 1
    assert ir.built_at_commit == "abc123"
    assert len(ir.nodes) == 4
    assert len(ir.edges) == 2
    # Coarse graphify granularity: file anchor → file, symbols → symbol, md → document.
    by_id = {n.id: n for n in ir.nodes}
    assert by_id["app_py"].kind == "file"
    assert by_id["app_py_handle"].kind == "symbol"
    assert by_id["readme_md"].kind == "document"
    # Language inferred from suffix.
    assert by_id["app_py"].language == "python"
    assert by_id["readme_md"].language == "markdown"
    # Line lifted from "L10".
    assert by_id["app_py_handle"].line == 10


def test_clusters_derived_from_communities():
    ir = ir_mod.from_graph_json(_synthetic_graph())
    cluster_ids = {c.id for c in ir.clusters}
    assert cluster_ids == {0, 1}
    sizes = {c.id: c.size for c in ir.clusters}
    assert sizes[0] == 3 and sizes[1] == 1


def test_round_trip_preserves_consumed_fields():
    graph = _synthetic_graph()
    ir = ir_mod.from_graph_json(graph)
    back = ir_mod.to_graph_json(ir)

    orig_nodes = _index(graph["nodes"], _NODE_FIELDS)
    back_nodes = _index(back["nodes"], _NODE_FIELDS)
    assert set(orig_nodes) == set(back_nodes)
    for nid, orig in orig_nodes.items():
        for f in _NODE_FIELDS:
            assert back_nodes[nid][f] == orig[f], f"node {nid}.{f}"

    # Edges round-trip under the same container key ("links").
    assert "links" in back
    orig_edges = _index(graph["links"], _EDGE_FIELDS)
    back_edges = _index(back["links"], _EDGE_FIELDS)
    assert set(orig_edges) == set(back_edges)
    for key, orig in orig_edges.items():
        for f in _EDGE_FIELDS:
            assert back_edges[key][f] == orig[f], f"edge {key}.{f}"


def test_round_trip_preserves_top_level_metadata():
    graph = _synthetic_graph()
    back = ir_mod.to_graph_json(ir_mod.from_graph_json(graph))
    for k in ("directed", "multigraph", "built_at_commit", "generated_by", "schema_version"):
        assert back[k] == graph[k]
    assert "_edge_key" not in back  # internal bookkeeping must not leak


def test_round_trip_preserves_unknown_fields():
    """A non-standard producer field survives graph → IR → graph in extra."""
    graph = _synthetic_graph()
    graph["nodes"][1]["custom_score"] = 0.42
    back = ir_mod.to_graph_json(ir_mod.from_graph_json(graph))
    node = next(n for n in back["nodes"] if n["id"] == "app_py_handle")
    assert node["custom_score"] == 0.42


def test_edges_container_key_round_trips():
    """A graph using the 'edges' key (not 'links') round-trips under 'edges'."""
    graph = _synthetic_graph()
    graph["edges"] = graph.pop("links")
    ir = ir_mod.from_graph_json(graph)
    back = ir_mod.to_graph_json(ir)
    assert "edges" in back and "links" not in back
    assert len(back["edges"]) == 2


@pytest.mark.skipif(not TS_GRAPH.exists(), reason="TS graphify fixture missing")
def test_round_trip_on_real_graphify_fixture():
    graph = json.loads(TS_GRAPH.read_text())
    ir = ir_mod.from_graph_json(graph)
    assert len(ir.nodes) == len(graph["nodes"])
    assert len(ir.edges) == len(graph["links"])
    back = ir_mod.to_graph_json(ir)

    orig_nodes = _index(graph["nodes"], _NODE_FIELDS)
    back_nodes = _index(back["nodes"], _NODE_FIELDS)
    assert set(orig_nodes) == set(back_nodes)
    for nid, orig in orig_nodes.items():
        for f in _NODE_FIELDS:
            assert back_nodes[nid][f] == orig[f], f"node {nid}.{f}"
    # The IR validates clean on a real graphify graph.
    assert not ir_mod.has_errors(ir_mod.validate_ir(ir))


# --------------------------------------------------------------------------- #
# Serialization round-trip
# --------------------------------------------------------------------------- #


def test_index_ir_serialization_round_trip(tmp_path):
    ir = ir_mod.from_graph_json(_synthetic_graph())
    path = tmp_path / "index_ir.json"
    ir.write(path)
    reloaded = ir_mod.IndexIR.read(path)
    assert reloaded.to_dict() == ir.to_dict()


def test_summary_reports_counts_and_coverage():
    ir = ir_mod.from_graph_json(_synthetic_graph(), source_backend="graph")
    s = ir.summary()
    assert s["nodes"] == 4 and s["edges"] == 2 and s["clusters"] == 2
    assert s["ir_version"] == ir_mod.IR_VERSION
    assert s["coverage"] == ir_mod.COVERAGE_COARSE
    assert s["node_kinds"]["symbol"] == 2
    assert s["languages"]["python"] == 3


# --------------------------------------------------------------------------- #
# Validation (FR5)
# --------------------------------------------------------------------------- #


def test_validate_clean_graph_has_no_errors():
    ir = ir_mod.from_graph_json(_synthetic_graph())
    issues = ir_mod.validate_ir(ir)
    assert not ir_mod.has_errors(issues)


def test_validate_flags_dangling_edge():
    ir = ir_mod.from_graph_json(_synthetic_graph())
    ir.edges.append(ir_mod.IREdge(relation="calls", source="app_py", target="ghost_node"))
    issues = ir_mod.validate_ir(ir)
    assert ir_mod.has_errors(issues)
    codes = {i.code for i in issues}
    assert "dangling_edge_target" in codes


def test_validate_flags_missing_endpoint():
    ir = ir_mod.from_graph_json(_synthetic_graph())
    ir.edges.append(ir_mod.IREdge(relation="calls", source="app_py", target=""))
    issues = ir_mod.validate_ir(ir)
    assert any(i.code == "edge_missing_endpoint" for i in issues)


def test_validate_flags_duplicate_node_id():
    ir = ir_mod.from_graph_json(_synthetic_graph())
    ir.nodes.append(ir_mod.IRNode(id="app_py", kind="file", label="dup"))
    issues = ir_mod.validate_ir(ir)
    assert any(i.code == "duplicate_node_id" for i in issues)


def test_validate_flags_unknown_kind_as_warning():
    ir = ir_mod.from_graph_json(_synthetic_graph())
    ir.nodes.append(ir_mod.IRNode(id="weird", kind="quasar", label="weird", source_file="app.py"))
    # connect it so it isn't also flagged as orphaned
    ir.edges.append(ir_mod.IREdge(relation="contains", source="app_py", target="weird"))
    issues = ir_mod.validate_ir(ir)
    assert not ir_mod.has_errors(issues)
    assert any(i.code == "unknown_node_kind" and i.severity == "warning" for i in issues)


def test_validate_flags_orphaned_node():
    ir = ir_mod.from_graph_json(_synthetic_graph())
    ir.nodes.append(ir_mod.IRNode(id="lonely", kind="symbol", label="lonely"))
    issues = ir_mod.validate_ir(ir)
    assert any(i.code == "orphaned_node" and "lonely" in i.message for i in issues)


def test_validation_summary_shape():
    ir = ir_mod.from_graph_json(_synthetic_graph())
    ir.edges.append(ir_mod.IREdge(relation="calls", source="x", target="y"))
    summary = ir_mod.validation_summary(ir_mod.validate_ir(ir))
    assert summary["ok"] is False
    assert summary["errors"] >= 1
    assert isinstance(summary["issues"], list)


# --------------------------------------------------------------------------- #
# Version compatibility (FR3, FR4)
# --------------------------------------------------------------------------- #


def test_unsupported_future_version_raises_on_load():
    payload = ir_mod.from_graph_json(_synthetic_graph()).to_dict()
    payload["ir_version"] = 999
    with pytest.raises(ir_mod.IRError) as exc:
        ir_mod.IndexIR.from_dict(payload)
    assert "999" in str(exc.value)


def test_validate_reports_unsupported_version():
    ir = ir_mod.from_graph_json(_synthetic_graph())
    ir.ir_version = 999
    issues = ir_mod.validate_ir(ir)
    assert any(i.code == "unsupported_version" for i in issues)


def test_migrate_payload_passthrough_current_version():
    payload = ir_mod.from_graph_json(_synthetic_graph()).to_dict()
    assert ir_mod.migrate_payload(payload) is payload
