"""Tests for the retrieval self-probe (neuralmind.probe).

The pure logic — query synthesis, sampling, scoring — is stdlib-only and runs
without the embedding deps, like the quality/synapse/IR layers. A separate
test drives NeuralMind.retrieval_probe with a fake embedder so the wiring is
covered without standing up a real vector backend.
"""

import json

from neuralmind import probe

# --------------------------------------------------------------------------- #
# humanize_label
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


# --------------------------------------------------------------------------- #
# synthesize_query / is_probeable
# --------------------------------------------------------------------------- #


def test_synthesize_prefers_label():
    node = {"label": "loadGraph", "source_file": "core/embedder.py"}
    assert probe.synthesize_query(node) == "load graph"


def test_synthesize_falls_back_to_file_stem():
    node = {"label": "___", "source_file": "src/payments/stripe.py"}
    assert probe.synthesize_query(node) == "stripe"


def test_is_probeable_requires_source_file():
    assert probe.is_probeable({"label": "foo", "source_file": "a.py"}) is True
    assert probe.is_probeable({"label": "foo", "source_file": ""}) is False
    assert probe.is_probeable({"label": "___", "source_file": ""}) is False


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


# --------------------------------------------------------------------------- #
# run_probe
# --------------------------------------------------------------------------- #


def test_run_probe_perfect_retrieval():
    samples = _nodes(4)
    # A retriever that always returns the matching file first.
    by_query = {probe.synthesize_query(n): [n["source_file"]] for n in samples}
    report = probe.run_probe(samples, lambda q: by_query[q], index_size=10)
    assert report.suite.answerability == 1.0
    assert report.suite.mrr == 1.0
    assert report.blind_spots == []
    assert report.blind_spot_total == 0
    assert report.index_size == 10
    assert report.sample_size == 4


def test_run_probe_records_blind_spots():
    samples = _nodes(3)
    # Retriever never returns the right file -> all blind spots.
    report = probe.run_probe(samples, lambda q: ["wrong.py"], index_size=3)
    assert report.suite.answerability == 0.0
    assert report.blind_spot_total == 3
    assert len(report.blind_spots) == 3
    spot = report.blind_spots[0]
    assert set(spot) == {"id", "label", "source_file", "query"}


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


# --------------------------------------------------------------------------- #
# NeuralMind.retrieval_probe wiring (fake embedder, no vector backend)
# --------------------------------------------------------------------------- #


class _FakeEmbedder:
    """Minimal embedder: returns the file whose stem matches the query words."""

    def __init__(self, nodes):
        self.nodes = nodes

    def search(self, query, n=10, **_):
        # Rank the node whose humanized label equals the query first.
        out = []
        for node in self.nodes:
            if probe.humanize_label(node["label"]) == query:
                out.insert(0, node)
            else:
                out.append(node)
        return [{"id": x["id"], "metadata": {"source_file": x["source_file"]}} for x in out[:n]]


def test_retrieval_probe_wiring(monkeypatch):
    from neuralmind.core import NeuralMind

    nodes = _nodes(6)
    mind = NeuralMind.__new__(NeuralMind)  # bypass heavy __init__
    mind.embedder = _FakeEmbedder(nodes)
    mind.project_path = __import__("pathlib").Path(".")
    mind._ensure_built = lambda: None
    mind._emit_audit = lambda **_: None

    report = mind.retrieval_probe(sample_size=0, k=5)
    assert report.sample_size == 6
    assert report.index_size == 6
    # Each label is unique, so the fake retriever ranks the right file first.
    assert report.suite.answerability == 1.0
    assert report.suite.mrr == 1.0
