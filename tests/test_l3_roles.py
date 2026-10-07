"""v4.10.0: the project's own code competes with its tests, examples and docs.

Indexed from its root, a repository's tests, example scripts and doc headings
outrank the code they are about, and they filled all four L3 slots for "which
files in this repo handle parsing command-line options?" on pallets/click.
These tests pin the three parts of the fix (the library-code floor, the role
weights, L2's member order), that each is a no-op when only the project's code
is indexed, and that ``NEURALMIND_L3_ROLES=0`` restores the old ranking.
"""

from __future__ import annotations

import pytest

from neuralmind import l3_slots
from neuralmind.context_selector import ContextSelector
from neuralmind.retrieval_enhancement import DOC_SIGNAL, apply_code_signal_boost

FLAGS = (
    "NEURALMIND_L3_ROLES",
    "NEURALMIND_L3_PER_FILE",
    "NEURALMIND_DOC_HANDOFF",
    "NEURALMIND_HUB_DAMPEN",
    "NEURALMIND_BM25_CODE",
    "NEURALMIND_INTENT_RULES",
    "NEURALMIND_BM25",
    "NEURALMIND_BM25_UNIFIED",
    "NEURALMIND_INTENT_POOL",
)


@pytest.fixture(autouse=True)
def _clean_flags(monkeypatch):
    for name in FLAGS:
        monkeypatch.delenv(name, raising=False)


def hit(nid, sf, score, file_type="code", community=0):
    return {
        "id": nid,
        "document": nid,
        "score": score,
        "metadata": {
            "label": nid,
            "file_type": file_type,
            "source_file": sf,
            "community": community,
        },
    }


class StubEmbedder:
    """Fixed ranked search results, no BM25, and community members in index order."""

    def __init__(self, project, ranked, members=()):
        self.project_path = str(project)
        self._ranked = ranked
        self._members = list(members)
        self.summary_calls = []

    def search(self, query, n=5, **_):
        return [dict(h, metadata=dict(h["metadata"])) for h in self._ranked[:n]]

    def bm25_search(self, query, n=10):
        return []

    def get_community_summary(self, community_id, max_nodes=20):
        self.summary_calls.append(max_nodes)
        nodes = [m for m in self._members if m["community"] == community_id][:max_nodes]
        types: dict[str, int] = {}
        for m in nodes:
            types[m["file_type"]] = types.get(m["file_type"], 0) + 1
        return {
            "community": community_id,
            "node_count": len(nodes),
            "type_summary": ", ".join(f"{v} {k}s" for k, v in types.items()),
            "nodes": [dict(m, text="") for m in nodes],
        }


def member(nid, sf, community=0, file_type="code"):
    return {
        "id": nid,
        "label": nid,
        "file_type": file_type,
        "source_file": sf,
        "community": community,
    }


def l3_files(sel):
    return [h["metadata"]["source_file"] for h in sel._last_l3_boosted]


# The Click shape: an example script, a test docstring and a doc heading take
# the top four; the code that parses options waits at ranks 5 and 8.
CLICK = [
    hit("repo_cli", "examples/repo/repo.py", 1.0, "rationale"),
    hit("raw_mode", "tests/test_termui.py", 0.957, "rationale"),
    hit("repo_copy", "examples/repo/repo.py", 0.567, "rationale"),
    hit("options_doc", "docs/parameters.md", 0.52, "document"),
    hit("command_doc", "src/click/core.py", 0.48, "rationale"),
    hit("escape_doc", "docs/arguments.md", 0.446, "document"),
    hit("child_doc", "docs/complex.md", 0.446, "document"),
    hit("make_parser", "src/click/core.py", 0.416, "rationale"),
    hit("repo_commit", "examples/repo/repo.py", 0.416, "rationale"),
    hit("parse_test", "tests/test_commands.py", 0.39),
]
QUESTION = "which files in this repo handle parsing command-line options?"


# --------------------------------------------------------------------------- #
# Roles
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "path, kind",
    [
        ("tests/test_termui.py", "test"),
        ("tests/fixtures/app.py", "test"),
        ("pkg/test_utils.py", "test"),
        ("pkg/conftest.py", "test"),
        ("cmd/server/handler_test.go", "test"),
        ("web/src/cart.test.ts", "test"),
        ("web/src/cart.spec.js", "test"),
        ("src/test/java/app/UserServiceTest.java", "test"),
        ("examples/repo/repo.py", "example"),
        ("docs/examples/basic.py", "example"),
        ("src/click/testing.py", ""),  # the project ships it
        ("src/click/core.py", ""),
        ("neuralmind/context_selector.py", ""),
        ("contest.py", ""),
    ],
)
def test_support_kind_by_layout(path, kind):
    assert l3_slots.support_kind(path) == kind


def test_a_question_can_ask_for_tests_or_examples():
    assert l3_slots.asked_kinds("how can I test a click command?") == {"test"}
    assert l3_slots.asked_kinds("show me an example of a group") == {"example"}
    assert l3_slots.asked_kinds(QUESTION) == frozenset()


def test_role_of_a_hit():
    assert l3_slots.role(hit("d", "docs/parameters.md", 1, "document")) == l3_slots.DOC
    assert l3_slots.role(hit("t", "tests/test_x.py", 1)) == l3_slots.SUPPORT
    assert l3_slots.role(hit("t", "tests/test_x.py", 1), frozenset({"test"})) == l3_slots.SOURCE
    assert l3_slots.role(hit("e", "examples/x.py", 1, "rationale")) == l3_slots.SUPPORT
    assert l3_slots.role(hit("c", "src/x.py", 1, "rationale")) == l3_slots.SOURCE


def test_role_weights():
    third = l3_slots.ROLE_WEIGHT
    for intent in ("code", "docs", "hybrid"):
        assert l3_slots.role_weight(l3_slots.SOURCE, intent) == 1.0
        assert l3_slots.role_weight(l3_slots.SUPPORT, intent) == third
    assert l3_slots.role_weight(l3_slots.DOC, "code") == third
    assert l3_slots.role_weight(l3_slots.DOC, "docs") == 1.0
    assert l3_slots.role_weight(l3_slots.DOC, "hybrid") == 1.0


def test_roles_on_by_default(monkeypatch):
    assert l3_slots.roles_enabled()
    monkeypatch.setenv("NEURALMIND_L3_ROLES", "0")
    assert not l3_slots.roles_enabled()


# --------------------------------------------------------------------------- #
# L3: the floor and the weights
# --------------------------------------------------------------------------- #
def test_off_restores_the_old_ranking(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_L3_ROLES", "0")
    sel = ContextSelector(StubEmbedder(tmp_path, CLICK), str(tmp_path))
    sel.get_l3_search(QUESTION, query_type="code")
    assert "src/click/core.py" not in l3_files(sel)
    assert l3_files(sel)[0] == "examples/repo/repo.py"


def test_the_code_takes_slots_and_ranks_first(tmp_path):
    sel = ContextSelector(StubEmbedder(tmp_path, CLICK), str(tmp_path))
    _, n = sel.get_l3_search(QUESTION, query_type="code")
    files = l3_files(sel)
    assert n == 4  # budget-neutral: the floor swaps, never adds
    assert files[:2] == ["src/click/core.py", "src/click/core.py"]
    assert {h["id"] for h in sel._last_l3_boosted if h.get("_source_slot")} == {
        "command_doc",
        "make_parser",
    }


def test_the_floor_gives_up_a_covered_file_first(tmp_path):
    sel = ContextSelector(StubEmbedder(tmp_path, CLICK), str(tmp_path))
    sel.get_l3_search(QUESTION, query_type="code")
    ids = {h["id"] for h in sel._last_l3_boosted}
    # examples/repo/repo.py had two hits, so both of its slots went before
    # the only test and the only doc lost theirs.
    assert "repo_cli" not in ids and "repo_copy" not in ids
    assert {"raw_mode", "options_doc"} <= ids


def test_the_floor_prefers_a_file_not_yet_shown(tmp_path):
    ranked = [
        hit("t1", "tests/test_a.py", 0.9),
        hit("t2", "tests/test_b.py", 0.8),
        hit("t3", "tests/test_c.py", 0.7),
        hit("a1", "app/a.py", 0.6),
        hit("a2", "app/a.py", 0.5),
        hit("b1", "app/b.py", 0.4),
    ]
    sel = ContextSelector(StubEmbedder(tmp_path, ranked), str(tmp_path))
    sel.get_l3_search("where is a parsed", query_type="code")
    files = l3_files(sel)
    assert "app/b.py" in files and files.count("app/a.py") == 1


def test_docs_intent_owes_the_code_one_slot(tmp_path):
    ranked = [hit(f"d{i}", f"docs/{i}.md", 1 - i / 10, "document") for i in range(4)]
    ranked += [hit("impl", "app/orders.py", 0.5), hit("impl2", "app/cart.py", 0.45)]
    sel = ContextSelector(StubEmbedder(tmp_path, ranked), str(tmp_path))
    sel.get_l3_search("explain the ordering guide", query_type="docs")
    files = l3_files(sel)
    assert files.count("app/orders.py") == 1 and "app/cart.py" not in files
    assert files[0].startswith("docs/")  # docs intent still ranks docs first


def test_no_code_in_the_search_means_no_swap(tmp_path):
    ranked = [hit(f"t{i}", f"tests/test_{i}.py", 1 - i / 10) for i in range(6)]
    sel = ContextSelector(StubEmbedder(tmp_path, ranked), str(tmp_path))
    _, n = sel.get_l3_search("where is x parsed", query_type="code")
    assert n == 4 and not any(h.get("_source_slot") for h in sel._last_l3_boosted)


def test_a_test_question_keeps_its_tests_but_still_gets_the_code(tmp_path):
    ranked = [
        hit("t1", "tests/test_testing.py", 1.0),
        hit("t2", "tests/test_stream.py", 0.9),
        hit("d1", "docs/testing.md", 0.8, "document"),
        hit("d2", "docs/quickstart.md", 0.7, "document"),
        hit("runner", "src/click/testing.py", 0.6, "rationale"),
    ]
    sel = ContextSelector(StubEmbedder(tmp_path, ranked), str(tmp_path))
    sel.get_l3_search("how can I test a click command and capture its output?")
    hits = sel._last_l3_boosted
    assert "src/click/testing.py" in l3_files(sel)  # the floor counts tests as tests
    assert not any(h.get("_role_weight") for h in hits if h["id"].startswith("t"))


def test_project_code_only_is_untouched(tmp_path, monkeypatch):
    """An index of a library's source directory ranks exactly as before."""
    ranked = [
        hit("a_doc", "src/pkg/a.py", 0.9, "rationale"),
        hit("a", "src/pkg/a.py", 0.8),
        hit("b_doc", "src/pkg/b.py", 0.7, "rationale"),
        hit("c", "src/pkg/c.py", 0.6),
        hit("d", "src/pkg/d.py", 0.5),
        hit("e_doc", "src/pkg/e.py", 0.4, "rationale"),
    ]
    out = {}
    for flag in ("1", "0"):
        monkeypatch.setenv("NEURALMIND_L3_ROLES", flag)
        for intent in ("code", "docs", "auto"):
            sel = ContextSelector(StubEmbedder(tmp_path, ranked), str(tmp_path))
            text, _ = sel.get_l3_search("how does a parse b", query_type=intent)
            out[(flag, intent)] = (text, [(h["id"], h["score"]) for h in sel._last_l3_boosted])
    for intent in ("code", "docs", "auto"):
        assert out[("1", intent)] == out[("0", intent)]


def test_code_signal_scores_tests_as_docs():
    test = hit("test_parse_option", "tests/test_parser.py", 1.0)
    code = hit("parse_option", "src/pkg/parser.py", 1.0)
    out = apply_code_signal_boost(
        [dict(test), dict(code)],
        ["parse", "option"],
        lambda h: l3_slots.role(h) == l3_slots.SUPPORT,
    )
    scores = {h["id"]: h["score"] for h in out}
    assert scores["test_parse_option"] == pytest.approx(DOC_SIGNAL)
    assert scores["parse_option"] > 1.0
    # Without the predicate a test gets the code's identifier boost.
    plain = apply_code_signal_boost([dict(test)], ["parse", "option"])
    assert plain[0]["score"] > 1.0


# --------------------------------------------------------------------------- #
# L2
# --------------------------------------------------------------------------- #
MEMBERS = [
    member("inout", "examples/inout/inout.py"),
    member("inout_cli", "examples/inout/inout.py"),
    member("termui_test", "tests/test_termui.py"),
    member("progress", "src/click/_termui_impl.py"),
    member("pager", "src/click/_termui_impl.py"),
    member("guide", "docs/utils.md", file_type="document"),
]


def test_l2_lists_the_code_before_examples_and_tests(tmp_path):
    ranked = [hit("progress", "src/click/_termui_impl.py", 0.9, community=0)]
    emb = StubEmbedder(tmp_path, ranked, MEMBERS)
    text, comms = ContextSelector(emb, str(tmp_path)).get_l2_context("progress bar")
    assert comms == [0]
    listed = [line for line in text.splitlines() if line.startswith("- ")]
    assert listed[0].endswith("— _termui_impl.py")
    assert listed[-1].endswith("— utils.md")
    assert "Contains: 5 codes, 1 documents" in text  # types count the members shown


def test_l2_off_keeps_index_order(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_L3_ROLES", "0")
    ranked = [hit("progress", "src/click/_termui_impl.py", 0.9, community=0)]
    emb = StubEmbedder(tmp_path, ranked, MEMBERS)
    text, _ = ContextSelector(emb, str(tmp_path)).get_l2_context("progress bar")
    listed = [line for line in text.splitlines() if line.startswith("- ")]
    assert listed[0].endswith("— inout.py")
    assert emb.summary_calls == [10]


def test_l2_weighs_a_test_hit_a_third(tmp_path):
    ranked = [
        hit("t1", "tests/test_termui.py", 0.9, community=1),
        hit("impl", "src/click/termui.py", 0.5, community=2),
        hit("t2", "tests/test_options.py", 0.4, community=3),
    ]
    members = [member("t1", "tests/test_termui.py", 1), member("impl", "src/click/termui.py", 2)]
    members.append(member("t2", "tests/test_options.py", 3))
    sel = ContextSelector(StubEmbedder(tmp_path, ranked, members), str(tmp_path), l2_recall_k=2)
    _, comms = sel.get_l2_context("progress bar")
    assert comms == [2, 1]


def test_l2_project_code_only_is_untouched(tmp_path, monkeypatch):
    members = [member(f"n{i}", f"src/pkg/m{i % 3}.py", file_type="code") for i in range(14)]
    ranked = [hit("n0", "src/pkg/m0.py", 0.9)]
    texts = []
    for flag in ("1", "0"):
        monkeypatch.setenv("NEURALMIND_L3_ROLES", flag)
        emb = StubEmbedder(tmp_path, ranked, members)
        texts.append(ContextSelector(emb, str(tmp_path)).get_l2_context("m0")[0])
    assert texts[0] == texts[1]
