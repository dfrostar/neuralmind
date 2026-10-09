"""Example scripts rank below the code they demonstrate (follow-up to v4.12.0).

On a freshly built index of pallets/click, "which files in this repo handle
parsing command-line options?" led with ``examples/repo/repo.py``, and four of
14 questions about Click led with an example script: v4.12.0 ranks test files
below the code they test, but not examples. These tests pin the example
demotion, the questions that turn it off, and two fixes to the test-file
demotion it shares code with: a question that names a test asks about tests,
and only the part of a path inside the project says what a file is.
"""

from __future__ import annotations

import pytest

from neuralmind import context_selector as cs
from neuralmind.context_selector import ContextSelector


def hit(nid, sf, score, file_type="code"):
    return {
        "id": nid,
        "document": "",
        "score": score,
        "metadata": {"label": nid, "file_type": file_type, "source_file": sf, "node_id": nid},
    }


class StubEmbedder:
    def __init__(self, project, ranked):
        self.project_path = str(project)
        self._ranked = ranked

    def search(self, query, n=5, **_):
        return [dict(h, metadata=dict(h["metadata"])) for h in self._ranked[:n]]

    def bm25_search(self, query, n=10):
        return []


@pytest.fixture(autouse=True)
def _defaults(monkeypatch):
    for name in (
        "NEURALMIND_L3_K",
        "NEURALMIND_L3_FILE_DECAY",
        "NEURALMIND_TEST_FILE_FACTOR",
        "NEURALMIND_EXAMPLE_FILE_FACTOR",
    ):
        monkeypatch.delenv(name, raising=False)


def files(sel):
    return [h["metadata"]["source_file"] for h in sel._last_l3_boosted]


# The click shape: an example script and a test docstring outscore core.py.
CLICK = [
    hit("repo_cli", "examples/repo/repo.py", 0.95, "rationale"),
    hit("raw_mode", "tests/test_termui.py", 0.93, "rationale"),
    hit("make_parser", "src/click/core.py", 0.90, "rationale"),
    hit("parser", "src/click/parser.py", 0.70, "rationale"),
]
QUESTION = "which files in this repo handle parsing command-line options?"


@pytest.mark.parametrize(
    "path,is_example",
    [
        ("examples/repo/repo.py", True),
        ("docs/examples/basic.py", True),
        ("demos/app.js", True),
        ("samples/x.go", True),
        ("demo/index.js", True),
        ("example/app.py", True),
        ("src/click/core.py", False),
        ("src/example.py", False),  # a module named example is project code
        ("tests/test_examples.py", False),
        # Java packages are folders: Spring Initializr's default is com.example.demo.
        ("src/main/java/com/example/demo/DemoApplication.java", False),
        ("app/src/main/kotlin/com/sample/app/Main.kt", False),
    ],
)
def test_example_file_detection(path, is_example):
    assert cs._is_example_file(path) is is_example


def test_examples_rank_below_the_code_they_use(tmp_path):
    sel = ContextSelector(StubEmbedder(tmp_path, CLICK), str(tmp_path))
    sel.get_l3_search(QUESTION)
    assert files(sel)[0] == "src/click/core.py"
    example = next(h for h in sel._last_l3_boosted if h["id"] == "repo_cli")
    assert example["_example_file"] and example["score"] == pytest.approx(0.95 * 0.5)


def test_factor_one_restores_the_old_order(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_EXAMPLE_FILE_FACTOR", "1")
    sel = ContextSelector(StubEmbedder(tmp_path, CLICK), str(tmp_path))
    sel.get_l3_search(QUESTION)
    assert files(sel)[0] == "examples/repo/repo.py"


@pytest.mark.parametrize("question", ["show me an example of a command group", "the repo demo"])
def test_a_question_asking_for_an_example_keeps_them(tmp_path, question):
    sel = ContextSelector(StubEmbedder(tmp_path, CLICK), str(tmp_path))
    sel.get_l3_search(question)
    assert files(sel)[0] == "examples/repo/repo.py"


def test_a_test_under_examples_is_demoted_once():
    out = cs._demote_examples(
        cs._demote_tests([hit("t", "examples/app/tests/test_app.py", 1.0)], "how", 0.5),
        "how",
        0.5,
    )
    assert out[0]["score"] == pytest.approx(0.5) and "_example_file" not in out[0]


@pytest.mark.parametrize(
    "question",
    [
        "where is test_parse_option() defined?",
        "fix the failing parse_test.go case",
        "why does cart.test.ts time out?",
        "what does UserServiceTest cover?",
    ],
)
def test_naming_a_test_asks_about_tests(question):
    assert cs._asks_about_tests(question)


@pytest.mark.parametrize("question", ["who won the contest?", "the latest release", QUESTION])
def test_words_containing_test_do_not(question):
    assert not cs._asks_about_tests(question)


@pytest.mark.parametrize(
    "path,root,is_test,is_example",
    [
        ("/home/me/examples/click/src/click/core.py", "/home/me/examples/click", False, False),
        ("/home/me/tests/app/src/app/core.py", "/home/me/tests/app", False, False),
        ("/home/me/examples/click/tests/test_core.py", "/home/me/examples/click/", True, False),
        ("/home/me/proj/examples/demo.py", "/home/me/proj", False, True),
        ("C:/work/examples/app/src/core.py", "C:\\work\\examples\\app", False, False),
        ("src/click/core.py", "/home/me/examples/click", False, False),
    ],
)
def test_layout_is_judged_inside_the_project(path, root, is_test, is_example):
    assert cs._is_test_file(path, root) is is_test
    assert cs._is_example_file(path, root) is is_example


def test_absolute_graph_paths_under_an_examples_checkout(tmp_path):
    root = tmp_path / "examples" / "proj"
    root.mkdir(parents=True)
    ranked = [hit(f"c{i}", str(root / "src" / f"m{i}.py"), 1 - i / 10) for i in range(4)]
    sel = ContextSelector(StubEmbedder(root, ranked), str(root))
    sel.get_l3_search("where is m0 parsed")
    assert not any(h.get("_example_file") or h.get("_test_file") for h in sel._last_l3_boosted)


# --------------------------------------------------------------------------- #
# Review follow-ups (#625)
# --------------------------------------------------------------------------- #
def test_a_named_test_under_examples_is_not_demoted_as_an_example():
    """The test exemption holds whatever folder the test lives in."""
    out = cs._demote_examples(
        cs._demote_tests(
            [hit("t", "examples/app/tests/test_app.py", 1.0)], "why does test_app.py fail?", 0.5
        ),
        "why does test_app.py fail?",
        0.5,
    )
    assert out[0]["score"] == pytest.approx(1.0)
    assert "_example_file" not in out[0] and "_test_file" not in out[0]


class RecallEmbedder(StubEmbedder):
    """Adds id lookup, so recall can pull absent neighbours in."""

    def __init__(self, project, ranked, extra):
        super().__init__(project, ranked)
        self._extra = {h["id"]: h for h in extra}

    def get_nodes_by_ids(self, ids):
        return [dict(self._extra[i], metadata=dict(self._extra[i]["metadata"])) for i in ids]


SEARCHED = [
    hit("a", "src/pkg/a.py", 0.9),
    hit("b", "src/pkg/b.py", 0.8),
    hit("c", "src/pkg/c.py", 0.7),
]
NEIGHBOURS = [hit("demo", "examples/demo/run.py", 0.0), hit("impl", "src/pkg/impl.py", 0.0)]


def recalled_ids(sel):
    return {h["id"] for h in sel._last_l3_boosted if h.get("_synapse_recalled")}


def test_synapse_recall_demotes_an_example_neighbour_before_its_threshold(tmp_path):
    # Both clear the 0.15 pull-in threshold, but the example only at full weight.
    sel = ContextSelector(RecallEmbedder(tmp_path, SEARCHED, NEIGHBOURS), str(tmp_path))
    sel.synapse_recall = lambda seeds: [("demo", 0.25), ("impl", 0.25)]
    sel.get_l3_search("how is the cache warmed")
    assert recalled_ids(sel) == {"impl"}


def test_synapse_recall_keeps_an_example_the_question_asks_for(tmp_path):
    sel = ContextSelector(RecallEmbedder(tmp_path, SEARCHED, NEIGHBOURS), str(tmp_path))
    sel.synapse_recall = lambda seeds: [("demo", 0.25), ("impl", 0.25)]
    sel.get_l3_search("show me an example of warming the cache")
    assert recalled_ids(sel) == {"demo", "impl"}


def test_structural_recall_orders_the_code_before_an_example(tmp_path, monkeypatch):
    monkeypatch.delenv("NEURALMIND_STRUCTURAL", raising=False)
    monkeypatch.setenv("NEURALMIND_L3_K", "2")
    sel = ContextSelector(RecallEmbedder(tmp_path, SEARCHED, NEIGHBOURS), str(tmp_path))
    # The example is wired more strongly, but there's one slot to give.
    sel.structural_recall = lambda seeds: [("demo", 0.9), ("impl", 0.6)]
    sel.get_l3_search("how is the cache warmed")
    wired = [h["id"] for h in sel._last_l3_boosted if h.get("_structural_recalled")]
    assert wired == ["impl"]
    monkeypatch.setenv("NEURALMIND_EXAMPLE_FILE_FACTOR", "1")
    sel = ContextSelector(RecallEmbedder(tmp_path, SEARCHED, NEIGHBOURS), str(tmp_path))
    sel.structural_recall = lambda seeds: [("demo", 0.9), ("impl", 0.6)]
    sel.get_l3_search("how is the cache warmed")
    assert [h["id"] for h in sel._last_l3_boosted if h.get("_structural_recalled")] == ["demo"]


def test_a_present_examples_recall_boost_is_demoted(tmp_path):
    ranked = SEARCHED + [hit("ex", "examples/demo/run.py", 0.6)]
    sel = ContextSelector(RecallEmbedder(tmp_path, ranked, []), str(tmp_path))
    sel.synapse_recall = lambda seeds: [("ex", 0.5)]
    sel.get_l3_search("how is the cache warmed")
    ex = next(h for h in sel._last_l3_boosted if h["id"] == "ex")
    assert ex["_synapse_boost"] == pytest.approx(sel._synapse_boost_weight * 0.5 * 0.5)
