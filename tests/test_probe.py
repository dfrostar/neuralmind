"""Tests for the retrieval self-probe (neuralmind.probe).

The pure logic — query synthesis, rationale extraction, sampling, scoring — is
stdlib-only and runs without the embedding deps, like the quality/synapse/IR
layers. A separate test drives NeuralMind.retrieval_probe with a fake embedder
so the wiring (rationale extraction + non-code filtering) is covered without
standing up a real vector backend.
"""

import json

from neuralmind import probe

# --------------------------------------------------------------------------- #
# humanize_label / normalize_rationale
# --------------------------------------------------------------------------- #


def test_humanize_snake_case():
    assert probe.humanize_label("authenticate_user") == "authenticate user"


def test_humanize_camel_and_pascal():
    assert probe.humanize_label("HTTPServerFactory") == "http server factory"
    assert probe.humanize_label("getUserById") == "get user by id"


def test_humanize_strips_code_extension():
    assert probe.humanize_label("auth.py") == "auth"
    assert probe.humanize_label("Widget.tsx") == "widget"


def test_humanize_dotted_qualname():
    assert probe.humanize_label("module.ClassName.method") == "module class name method"


def test_humanize_empty_and_punctuation():
    assert probe.humanize_label("") == ""
    assert probe.humanize_label("___") == ""


def test_normalize_rationale_collapses_and_trims_period():
    assert probe.normalize_rationale("  Insert a new user\n  and return it.  ") == (
        "Insert a new user and return it"
    )


def test_normalize_rationale_caps_length():
    long = "word " * 100
    out = probe.normalize_rationale(long)
    assert len(out) <= probe.MAX_RATIONALE_CHARS
    assert not out.endswith(" ")


# --------------------------------------------------------------------------- #
# extract_rationales
# --------------------------------------------------------------------------- #


def test_extract_rationales_maps_code_to_docstring():
    nodes = [
        {"id": "code1", "label": "insert_user", "file_type": "code", "source_file": "crud.py"},
        {"id": "rat1", "label": "Insert a new user.", "file_type": "rationale"},
    ]
    edges = [{"relation": "rationale_for", "_src": "rat1", "_tgt": "code1"}]
    out = probe.extract_rationales(nodes, edges)
    assert out == {"code1": "Insert a new user"}


def test_extract_rationales_handles_either_edge_direction():
    nodes = [
        {"id": "c", "label": "f", "file_type": "code", "source_file": "a.py"},
        {"id": "r", "label": "Does a thing.", "file_type": "rationale"},
    ]
    # code -> rationale direction
    out = probe.extract_rationales(
        nodes, [{"relation": "rationale_for", "source": "c", "target": "r"}]
    )
    assert out == {"c": "Does a thing"}


# --------------------------------------------------------------------------- #
# synthesize_query — rationale preferred, label/file fallback
# --------------------------------------------------------------------------- #


def test_synthesize_prefers_rationale():
    node = {"id": "c1", "label": "loadGraph", "source_file": "embedder.py"}
    q, src = probe.synthesize_query(node, {"c1": "Load the code graph from disk"})
    assert q == "Load the code graph from disk"
    assert src == probe.SOURCE_RATIONALE


def test_synthesize_falls_back_to_label():
    node = {"id": "c1", "label": "loadGraph", "source_file": "embedder.py"}
    q, src = probe.synthesize_query(node, {})  # no rationale for c1
    assert q == "load graph"
    assert src == probe.SOURCE_LABEL


def test_synthesize_falls_back_to_file_stem():
    node = {"id": "c1", "label": "___", "source_file": "src/payments/stripe.py"}
    q, src = probe.synthesize_query(node, None)
    assert q == "stripe"
    assert src == probe.SOURCE_FILE


def test_is_probeable_requires_source_file():
    assert probe.is_probeable({"id": "1", "label": "foo", "source_file": "a.py"}) is True
    assert probe.is_probeable({"id": "1", "label": "foo", "source_file": ""}) is False
    assert probe.is_probeable({"id": "1", "label": "___", "source_file": ""}) is False


# --------------------------------------------------------------------------- #
# sample_nodes
# --------------------------------------------------------------------------- #


def _nodes(n, file_type="code"):
    return [
        {"id": f"n{i}", "label": f"func_{i}", "source_file": f"f{i}.py", "file_type": file_type}
        for i in range(n)
    ]


def test_sample_is_deterministic_for_seed():
    nodes = _nodes(100)
    a = probe.sample_nodes(nodes, 10, seed=7)
    b = probe.sample_nodes(nodes, 10, seed=7)
    assert [n["id"] for n in a] == [n["id"] for n in b]
    assert len(a) == 10


def test_sample_size_zero_returns_all_sorted():
    nodes = _nodes(5)
    out = probe.sample_nodes(nodes, 0)
    assert len(out) == 5
    assert [n["id"] for n in out] == sorted(n["id"] for n in out)


def test_sample_skips_unprobeable():
    nodes = _nodes(3) + [{"id": "x", "label": "y", "source_file": "", "file_type": "code"}]
    out = probe.sample_nodes(nodes, 0)
    assert all(n["source_file"] for n in out)
    assert "x" not in {n["id"] for n in out}


def test_sample_prefers_code_but_falls_back():
    docs = [{"id": "d1", "label": "readme", "source_file": "README.md", "file_type": "doc"}]
    # No code nodes -> fall back to the doc node rather than returning nothing.
    out = probe.sample_nodes(docs, 0)
    assert {n["id"] for n in out} == {"d1"}


def test_sample_prefers_documented_when_enough():
    nodes = _nodes(10)
    rationales = {f"n{i}": "does a thing" for i in range(4)}  # only 4 documented
    # Asking for 3 -> should draw only from the 4 documented symbols.
    out = probe.sample_nodes(nodes, 3, seed=1, rationales=rationales)
    assert all(n["id"] in rationales for n in out)


def test_sample_uses_full_pool_when_too_few_documented():
    nodes = _nodes(10)
    rationales = {"n0": "does a thing"}  # only 1 documented, need 5
    out = probe.sample_nodes(nodes, 5, seed=1, rationales=rationales)
    assert len(out) == 5  # not restricted to the single documented node


# --------------------------------------------------------------------------- #
# run_probe
# --------------------------------------------------------------------------- #


def test_run_probe_perfect_retrieval_records_sources():
    samples = _nodes(4)
    rationales = {"n0": "alpha", "n1": "beta"}  # 2 of 4 documented
    by_query = {}
    for n in samples:
        q, _ = probe.synthesize_query(n, rationales)
        by_query[q] = [n["source_file"]]
    report = probe.run_probe(samples, lambda q: by_query[q], index_size=10, rationales=rationales)
    assert report.suite.answerability == 1.0
    assert report.suite.mrr == 1.0
    assert report.blind_spots == []
    assert report.index_size == 10
    assert report.sample_size == 4
    assert report.query_sources == {probe.SOURCE_RATIONALE: 2, probe.SOURCE_LABEL: 2}


def test_run_probe_records_blind_spots():
    samples = _nodes(3)
    report = probe.run_probe(samples, lambda q: ["wrong.py"], index_size=3)
    assert report.suite.answerability == 0.0
    assert report.blind_spot_total == 3
    assert len(report.blind_spots) == 3
    spot = report.blind_spots[0]
    assert set(spot) == {"id", "label", "source_file", "query", "query_source"}


def test_run_probe_blind_spot_list_is_capped():
    samples = _nodes(probe.MAX_BLIND_SPOTS + 5)
    report = probe.run_probe(samples, lambda q: ["nope.py"], index_size=999)
    assert report.blind_spot_total == probe.MAX_BLIND_SPOTS + 5
    assert len(report.blind_spots) == probe.MAX_BLIND_SPOTS  # capped


def test_report_to_dict_is_json_safe():
    samples = _nodes(2)
    report = probe.run_probe(samples, lambda q: [samples[0]["source_file"]], index_size=2)
    blob = json.dumps(report.to_dict())
    parsed = json.loads(blob)
    assert parsed["suite"] == "self-probe"
    assert parsed["index_size"] == 2
    assert "mean_recall" in parsed
    assert "blind_spots" in parsed
    assert "query_sources" in parsed


# --------------------------------------------------------------------------- #
# NeuralMind.retrieval_probe wiring (fake embedder, no vector backend)
# --------------------------------------------------------------------------- #


class _FakeEmbedder:
    """Fake embedder honoring ``file_type``: the probe asks for code hits
    directly, so a rationale node that matches its own text must never be
    returned for a ``file_type="code"`` search."""

    def __init__(self, nodes, edges):
        self.nodes = nodes
        self.edges = edges

    def search(self, query, n=10, file_type=None, **_):
        # The rationale node for the matching code would rank first on its own
        # text — but a file_type="code" search must exclude it at the source.
        pool = [x for x in self.nodes if file_type is None or x.get("file_type") == file_type]
        ranked = []
        for node in pool:
            if node.get("file_type") == "rationale" and node.get("label") == query:
                ranked.insert(0, node)
        for node in pool:
            if node.get("file_type") == "code" and query.split()[0] in node.get("label", ""):
                ranked.append(node)
        for node in pool:
            if node not in ranked:
                ranked.append(node)
        return [
            {
                "id": x["id"],
                "metadata": {
                    "source_file": x.get("source_file", ""),
                    "file_type": x.get("file_type", "code"),
                },
            }
            for x in ranked[:n]
        ]


def test_retrieval_probe_wiring_uses_rationale_and_filters_noncode():
    from neuralmind.core import NeuralMind

    nodes = [
        {"id": "c0", "label": "insert", "file_type": "code", "source_file": "crud.py"},
        {
            "id": "r0",
            "label": "insert a record",
            "file_type": "rationale",
            "source_file": "crud.py",
        },
        {"id": "c1", "label": "fetch", "file_type": "code", "source_file": "read.py"},
        {"id": "r1", "label": "fetch a record", "file_type": "rationale", "source_file": "read.py"},
    ]
    edges = [
        {"relation": "rationale_for", "_src": "r0", "_tgt": "c0"},
        {"relation": "rationale_for", "_src": "r1", "_tgt": "c1"},
    ]
    mind = NeuralMind.__new__(NeuralMind)  # bypass heavy __init__
    mind.embedder = _FakeEmbedder(nodes, edges)
    mind.project_path = __import__("pathlib").Path(".")
    mind._ensure_built = lambda: None
    mind._emit_audit = lambda **_: None

    report = mind.retrieval_probe(sample_size=0, k=5)
    # Both code symbols were queried by their rationale text…
    assert report.query_sources.get(probe.SOURCE_RATIONALE) == 2
    # …and retrieved because the search is filtered to code at the backend
    # (the rationale node that matches its own text is never returned).
    assert report.suite.answerability == 1.0
    assert report.blind_spot_total == 0
    # index_size counts only code nodes (2), not the rationale pseudo-nodes.
    assert report.index_size == 2


class _ABCOnlyEmbedder:
    """Backend that only honors the base ``search(query, n, where=...)``
    contract — it raises TypeError on the ``file_type`` keyword, exercising the
    probe's over-fetch-and-filter fallback."""

    def __init__(self, nodes):
        self.nodes = nodes
        self.edges = []

    def search(self, query, n=10, where=None):
        ranked = [x for x in self.nodes if x.get("file_type") == "code"]
        ranked += [x for x in self.nodes if x.get("file_type") != "code"]
        return [
            {
                "id": x["id"],
                "metadata": {"source_file": x["source_file"], "file_type": x["file_type"]},
            }
            for x in ranked[:n]
        ]


def test_retrieval_probe_falls_back_when_backend_rejects_file_type():
    from neuralmind.core import NeuralMind

    nodes = [
        {"id": "c0", "label": "insert", "file_type": "code", "source_file": "crud.py"},
        {
            "id": "r0",
            "label": "insert a record",
            "file_type": "rationale",
            "source_file": "crud.py",
        },
    ]
    mind = NeuralMind.__new__(NeuralMind)
    mind.embedder = _ABCOnlyEmbedder(nodes)
    mind.project_path = __import__("pathlib").Path(".")
    mind._ensure_built = lambda: None
    mind._emit_audit = lambda **_: None

    # search(file_type=...) -> TypeError -> over-fetch + python-side code filter;
    # the code node is still retrieved, so the symbol isn't a blind spot.
    report = mind.retrieval_probe(sample_size=0, k=5)
    assert report.index_size == 1
    assert report.blind_spot_total == 0


def test_retrieval_probe_no_code_nodes_samples_nothing():
    # Retrieval is hard-filtered to code; a docs-only project has nothing
    # answerable, so the probe must sample nothing (n_queries == 0) rather than
    # sample non-code symbols and score them all as blind spots.
    from neuralmind.core import NeuralMind

    docs = [{"id": "d0", "label": "readme", "file_type": "doc", "source_file": "README.md"}]
    mind = NeuralMind.__new__(NeuralMind)
    mind.embedder = _FakeEmbedder(docs, [])
    mind.project_path = __import__("pathlib").Path(".")
    mind._ensure_built = lambda: None
    mind._emit_audit = lambda **_: None

    report = mind.retrieval_probe(sample_size=0, k=5)
    assert report.sample_size == 0
    assert report.index_size == 0
    assert report.suite.n_queries == 0


def test_retrieval_probe_rejects_bad_arguments():
    from neuralmind.core import NeuralMind

    mind = NeuralMind.__new__(NeuralMind)
    mind.embedder = _FakeEmbedder([], [])
    mind.project_path = __import__("pathlib").Path(".")
    mind._ensure_built = lambda: None
    mind._emit_audit = lambda **_: None

    import pytest

    with pytest.raises(ValueError):
        mind.retrieval_probe(k=0)
    with pytest.raises(ValueError):
        mind.retrieval_probe(sample_size=-1)
