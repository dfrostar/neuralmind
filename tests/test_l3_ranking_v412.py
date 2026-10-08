"""v4.12.0 L3 ranking passes: file diversity and test-file demotion."""

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
    for name in ("NEURALMIND_L3_K", "NEURALMIND_L3_FILE_DECAY", "NEURALMIND_TEST_FILE_FACTOR"):
        monkeypatch.delenv(name, raising=False)


# --------------------------------------------------------------------------- #
# File diversity
# --------------------------------------------------------------------------- #
ONE_FILE = [hit(f"crud{i}", "users/crud.py", 1.0 - i / 100) for i in range(10)] + [
    hit("conn", "db/connection.py", 0.80)
]


def test_one_file_no_longer_takes_every_slot(tmp_path):
    # The self-benchmark's user-storage shape: users/crud.py filled all eight.
    sel = ContextSelector(StubEmbedder(tmp_path, ONE_FILE), str(tmp_path))
    sel.get_l3_search("how are users stored")
    files = [h["metadata"]["source_file"] for h in sel._last_l3_boosted]
    assert len(files) == 8
    assert "db/connection.py" in files
    assert files[0] == "users/crud.py"  # the top hit keeps its place


def test_diversity_off_restores_the_old_ranking(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_L3_FILE_DECAY", "1")
    sel = ContextSelector(StubEmbedder(tmp_path, ONE_FILE), str(tmp_path))
    sel.get_l3_search("how are users stored")
    assert {h["metadata"]["source_file"] for h in sel._last_l3_boosted} == {"users/crud.py"}


def test_each_files_first_hit_keeps_its_order():
    ranked = [hit("a1", "a.py", 0.9), hit("a2", "a.py", 0.85), hit("b1", "b.py", 0.6)]
    out = cs._diversify_files(ranked, 0.6)
    assert [h["id"] for h in out] == ["a1", "b1", "a2"]
    assert out[2]["score"] == pytest.approx(0.85 * 0.6)
    assert ranked[1]["score"] == 0.85  # the input (the search cache) is untouched


# --------------------------------------------------------------------------- #
# Test-file demotion
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "path,is_test",
    [
        ("tests/test_synapses.py", True),
        ("pkg/server_test.go", True),
        ("src/app.spec.ts", True),
        ("src/__tests__/b.js", True),
        ("conftest.py", True),
        ("neuralmind/synapses.py", False),
        ("click/testing.py", False),  # click's CliRunner module is product code
        ("src/latest.py", False),
        ("evals/testing_tools.py", False),
    ],
)
def test_test_file_detection(path, is_test):
    assert cs._is_test_file(path) is is_test


def test_tests_rank_below_the_code_they_test(tmp_path):
    ranked = [
        hit("t1", "tests/test_synapses.py", 0.95),
        hit("t2", "tests/test_decay.py", 0.93),
        hit("impl", "neuralmind/synapses.py", 0.90),
    ]
    sel = ContextSelector(StubEmbedder(tmp_path, ranked), str(tmp_path))
    sel.get_l3_search("how does the synapse store decay edges")
    assert sel._last_l3_boosted[0]["metadata"]["source_file"] == "neuralmind/synapses.py"


def test_a_question_about_tests_keeps_them(tmp_path):
    ranked = [hit("t1", "tests/test_synapses.py", 0.95), hit("impl", "neuralmind/synapses.py", 0.9)]
    sel = ContextSelector(StubEmbedder(tmp_path, ranked), str(tmp_path))
    sel.get_l3_search("which test covers synapse decay")
    assert sel._last_l3_boosted[0]["metadata"]["source_file"] == "tests/test_synapses.py"
