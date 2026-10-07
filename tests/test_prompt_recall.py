"""Tests for neuralmind.prompt_recall: the block the prompt-submit hook injects.

The regression these guard: on a freshly built index the hook listed the
spreading-activation neighbours of documentation headings, as node ids, with
activations of 0.00, and never named the code the prompt matched (2026-10-06,
Click: "which files in this repo handle parsing command-line options?" got
``docs_parameters_md__h3`` and friends, not ``parser.py`` or ``core.py``).
"""

from __future__ import annotations

import pytest

from neuralmind import prompt_recall
from neuralmind.prompt_recall import format_block, is_test_path, recall
from neuralmind.synapses import SHARED_NAMESPACE, SynapseStore

PARSER = "src_click_parser_py__optionparser_cls"
MAKE_PARSER = "src_click_core_py__command_cls__make_parser_fn"
ADD_TO_PARSER = "src_click_core_py__parameter_cls__add_to_parser_fn"
RESOLVE = "src_click_shell_completion_py__resolve_context_fn"
RUNNER = "src_click_testing_py__clirunner_cls"
OPTIONS_H = "docs_parameters_md__h10"
ESCAPES_H = "docs_arguments_md__h98"


def _node(node_id, path, label, line=1, file_type="code"):
    return {
        "id": node_id,
        "source_file": path,
        "label": label,
        "source_location": f"L{line}",
        "file_type": file_type,
    }


NODES = [
    _node("src_click_parser_py", "src/click/parser.py", "parser.py"),
    _node(PARSER, "src/click/parser.py", "_OptionParser", 224),
    _node(PARSER + "__rationale", "src/click/parser.py", "The option parser is…", 224, "rationale"),
    _node(MAKE_PARSER, "src/click/core.py", "make_parser()", 1256),
    _node(MAKE_PARSER + "__rationale", "src/click/core.py", "Creates the…", 1256, "rationale"),
    _node(ADD_TO_PARSER, "src/click/core.py", "add_to_parser()", 2400),
    _node(RESOLVE, "src/click/shell_completion.py", "_resolve_context()", 696),
    _node(RUNNER, "src/click/testing.py", "CliRunner", 317),
    _node("docs_parameters_md", "docs/parameters.md", "parameters.md", 1, "document"),
    _node(OPTIONS_H, "docs/parameters.md", "Options", 10, "document"),
    _node("docs_parameters_md__h20", "docs/parameters.md", "Arguments", 20, "document"),
    _node("docs_arguments_md", "docs/arguments.md", "arguments.md", 1, "document"),
    _node(ESCAPES_H, "docs/arguments.md", "Argument Escape Sequences", 98, "document"),
]

# The four nearest nodes for the Click prompt, in the order the index gave them.
HITS = [
    (OPTIONS_H, 0.569),
    (ESCAPES_H, 0.545),
    (MAKE_PARSER + "__rationale", 0.523),
    (PARSER + "__rationale", 0.490),
]


class _Embedder:
    def __init__(self, nodes, hits, extra=None, edges=()):
        self.nodes = nodes
        self.edges = list(edges)
        self._hits = [{"id": i, "score": s, "metadata": {}} for i, s in hits]
        self._extra = extra or {}

    def search(self, query, n):
        return self._hits[:n]

    def get_nodes_by_ids(self, node_ids):
        return [{"id": i, "metadata": self._extra[i]} for i in node_ids if i in self._extra]


class _Mind:
    def __init__(self, store, hits=HITS, nodes=NODES, extra=None, edges=()):
        self.embedder = _Embedder(nodes, hits, extra, edges)
        self.synapses = store


def _store(tmp_path) -> SynapseStore:
    """A fresh build's store: structural edges and doc containment, nothing learned."""
    store = SynapseStore(tmp_path / "synapses.db")
    for pair in (
        ("docs_parameters_md", OPTIONS_H),
        ("docs_parameters_md", "docs_parameters_md__h20"),
        ("docs_arguments_md", ESCAPES_H),
        (MAKE_PARSER, PARSER),
        (MAKE_PARSER, ADD_TO_PARSER),
        (PARSER, RESOLVE),
    ):
        store.reinforce(pair, namespace=SHARED_NAMESPACE)
    return store


def test_a_fresh_index_names_the_matching_code_not_doc_headings(tmp_path):
    block = format_block(recall(_Mind(_store(tmp_path)), "which files parse options?"))
    assert block.splitlines()[:5] == [
        "## NeuralMind associative recall",
        "",
        "Code matching this prompt:",
        "- src/click/core.py: make_parser() L1256",
        "- src/click/parser.py: _OptionParser L224",
    ]
    assert "- src/click/shell_completion.py: _resolve_context() L696" in block
    assert block.endswith("Docs: docs/parameters.md, docs/arguments.md")
    # No node ids and no activation numbers: paths and symbols only.
    assert "docs_" not in block
    assert "src_click" not in block
    assert "activation" not in block


def test_a_docstring_match_names_its_function(tmp_path):
    result = recall(_Mind(None, hits=[(PARSER + "__rationale", 0.6)]), "q")
    assert [(f.path, f.symbols) for f in result.matches] == [
        ("src/click/parser.py", ["_OptionParser L224"])
    ]


def test_a_graphify_docstring_match_names_its_function_through_its_edge():
    # graphify names rationale nodes without the __rationale suffix.
    rationale = "src_click_parser_py_optionparser_rationale"
    nodes = NODES + [
        _node(rationale, "src/click/parser.py", "The option parser…", 224, "rationale")
    ]
    edges = [{"relation": "rationale_for", "source": rationale, "target": PARSER}]
    result = recall(_Mind(None, hits=[(rationale, 0.6)], nodes=nodes, edges=edges), "q")
    assert result.code
    assert [(f.path, f.symbols) for f in result.matches] == [
        ("src/click/parser.py", ["_OptionParser L224"])
    ]


def test_edges_learned_on_a_docstring_id_are_still_linked(tmp_path):
    # Query feedback stores raw hit ids: a docstring node can carry its own
    # learned edges, which must stay reachable once it counts as its function.
    store = SynapseStore(tmp_path / "synapses.db")
    store.reinforce([PARSER + "__rationale", RUNNER])
    result = recall(_Mind(store, hits=[(PARSER + "__rationale", 0.6)]), "q")
    assert "src/click/testing.py" in [entry.path for entry in result.linked]


def test_a_docstring_and_its_symbol_dont_double_a_shared_link(tmp_path):
    # _OptionParser is linked more strongly to _resolve_context() than to
    # CliRunner. Its docstring is linked to CliRunner too, which mustn't
    # add up to put CliRunner first.
    store = SynapseStore(tmp_path / "synapses.db")
    for _ in range(3):
        store.reinforce([PARSER, RESOLVE])
    for _ in range(2):
        store.reinforce([PARSER, RUNNER])
        store.reinforce([PARSER + "__rationale", RUNNER])
    result = recall(_Mind(store, hits=[(PARSER + "__rationale", 0.6)]), "q")
    assert result.linked_ids == [RESOLVE, RUNNER]


def test_linked_code_skips_files_that_already_matched(tmp_path):
    result = recall(_Mind(_store(tmp_path)), "q")
    # add_to_parser() is linked to make_parser(), but core.py is already named.
    assert [f.path for f in result.linked] == ["src/click/shell_completion.py"]
    assert result.linked_ids == [RESOLVE]


def test_a_match_past_the_listed_files_can_still_be_linked(tmp_path):
    # Five code files match, the block lists four, and the fifth is linked to
    # the best: it belongs under "connected", not in neither section.
    ids = [f"pkg_{c}_py__fn_{c}_fn" for c in "abcde"]
    nodes = [_node(i, f"pkg/{c}.py", f"fn_{c}()", 10) for i, c in zip(ids, "abcde", strict=True)]
    hits = [(i, 0.6 - n / 100) for n, i in enumerate(ids)]
    store = SynapseStore(tmp_path / "synapses.db")
    store.reinforce((ids[0], ids[4]), namespace=SHARED_NAMESPACE)
    result = recall(_Mind(store, hits=hits, nodes=nodes), "q")
    assert [f.path for f in result.matches] == ["pkg/a.py", "pkg/b.py", "pkg/c.py", "pkg/d.py"]
    assert [f.path for f in result.linked] == ["pkg/e.py"]


def test_a_learned_association_is_linked(tmp_path):
    store = _store(tmp_path)
    for _ in range(4):
        store.reinforce([PARSER, RUNNER])
    result = recall(_Mind(store), "q")
    # Co-activation outweighs the structural edge, so it ranks first.
    assert [f.path for f in result.linked] == [
        "src/click/testing.py",
        "src/click/shell_completion.py",
    ]


def test_every_listed_file_seeds_the_links(tmp_path):
    nodes = [
        _node(f"src_click_core_py__f{i}_fn", "src/click/core.py", f"f{i}()", i) for i in range(4)
    ]
    nodes += [n for n in NODES if n["id"] in (PARSER, RUNNER)]
    store = SynapseStore(tmp_path / "synapses.db")
    for _ in range(3):
        store.reinforce([PARSER, RUNNER])
    # core.py holds the four best matches; parser.py's one match still seeds.
    hits = [(n["id"], 0.9 - i * 0.01) for i, n in enumerate(nodes[:4])] + [(PARSER, 0.5)]
    result = recall(_Mind(store, hits=hits, nodes=nodes), "q")
    assert [f.path for f in result.matches] == ["src/click/core.py", "src/click/parser.py"]
    assert [f.path for f in result.linked] == ["src/click/testing.py"]


def test_a_listed_files_own_links_dont_crowd_out_the_rest(tmp_path):
    # Co-editing links every node of a file to every other.
    own = [f"src_click_parser_py__f{i}_fn" for i in range(40)]
    nodes = [_node(nid, "src/click/parser.py", nid, 1) for nid in own]
    nodes += [n for n in NODES if n["id"] == RUNNER]
    store = SynapseStore(tmp_path / "synapses.db")
    for _ in range(4):
        store.reinforce(own)
    store.reinforce([own[0], RUNNER])
    result = recall(_Mind(store, hits=[(own[0], 0.5)], nodes=nodes), "q")
    assert [f.path for f in result.linked] == ["src/click/testing.py"]


def test_a_linked_docstring_names_its_function(tmp_path):
    store = SynapseStore(tmp_path / "synapses.db")
    store.reinforce([MAKE_PARSER, PARSER + "__rationale"])
    result = recall(_Mind(store, hits=[(MAKE_PARSER, 0.5)]), "q")
    assert [(f.path, f.symbols) for f in result.linked] == [
        ("src/click/parser.py", ["_OptionParser L224"])
    ]


def test_a_faint_link_is_dropped(tmp_path):
    store = SynapseStore(tmp_path / "synapses.db")
    store.reinforce([PARSER, RESOLVE], namespace=SHARED_NAMESPACE)
    # A third of an edge's weight (decayed, or a weak seed) is below the floor.
    store.reinforce([PARSER, RUNNER], strength=0.3, namespace=SHARED_NAMESPACE)
    result = recall(_Mind(store, hits=[(PARSER, 0.5)]), "q")
    assert result.linked_ids == [RESOLVE]


def test_links_are_one_hop(tmp_path):
    store = SynapseStore(tmp_path / "synapses.db")
    for _ in range(4):
        store.reinforce([PARSER, RESOLVE])
        store.reinforce([RESOLVE, RUNNER])
    result = recall(_Mind(store, hits=[(PARSER, 0.5)]), "q")
    assert result.linked_ids == [RESOLVE]


def test_a_hub_is_damped_out(tmp_path):
    store = SynapseStore(tmp_path / "synapses.db")
    store.reinforce([PARSER, RESOLVE], namespace=SHARED_NAMESPACE)
    store.reinforce([PARSER, RUNNER], namespace=SHARED_NAMESPACE)
    # CliRunner links to everything, so a link to it says nothing about the prompt.
    for i in range(200):
        store.reinforce([RUNNER, f"spoke_{i}"], namespace=SHARED_NAMESPACE)
    result = recall(_Mind(store, hits=[(PARSER, 0.5)]), "q")
    assert result.linked_ids == [RESOLVE]


def test_a_file_with_several_matches_outranks_a_stray_one():
    stray = "examples_repo_repo_py__cli_fn"
    nodes = [n for n in NODES if n["id"] in (MAKE_PARSER, ADD_TO_PARSER)]
    nodes.append(_node(stray, "examples/repo/repo.py", "cli()", 44))
    hits = [(stray, 0.55), (MAKE_PARSER, 0.52), (ADD_TO_PARSER, 0.48)]
    result = recall(_Mind(None, hits=hits, nodes=nodes), "q")
    assert [f.path for f in result.matches] == ["src/click/core.py", "examples/repo/repo.py"]


def test_tests_follow_the_code_unless_the_prompt_is_about_tests():
    nodes = [
        _node("tests_test_parser_py__test_parse_fn", "tests/test_parser.py", "test_parse()", 9),
        _node("tests_test_parser_py__test_split_fn", "tests/test_parser.py", "test_split()", 30),
        _node(PARSER, "src/click/parser.py", "_OptionParser", 224),
    ]
    hits = [
        ("tests_test_parser_py__test_parse_fn", 0.6),
        ("tests_test_parser_py__test_split_fn", 0.55),
        (PARSER, 0.5),
    ]
    mind = _Mind(None, hits=hits, nodes=nodes)
    paths = [f.path for f in recall(mind, "how are options parsed").matches]
    assert paths == ["src/click/parser.py", "tests/test_parser.py"]
    paths = [f.path for f in recall(mind, "why does the parser test fail").matches]
    assert paths == ["tests/test_parser.py", "src/click/parser.py"]


def test_a_project_without_code_lists_its_document_matches(tmp_path):
    mind = _Mind(_store(tmp_path), hits=[(OPTIONS_H, 0.6), (ESCAPES_H, 0.5)])
    block = format_block(recall(mind, "q"))
    assert "Files matching this prompt:\n- docs/parameters.md: Options L10" in block
    assert "Docs:" not in block


def test_the_block_is_capped():
    # 16 hits, the most one search returns: six symbols in one file, one in
    # each of six more files, and four docs.
    nodes = (
        [_node(f"pkg_m0_py__s{s}_fn", "pkg/m0.py", f"s{s}()", s) for s in range(6)]
        + [_node(f"pkg_m{f}_py__s_fn", f"pkg/m{f}.py", "s()", 1) for f in range(1, 7)]
        + [_node(f"docs_d{d}_md", f"docs/d{d}.md", f"d{d}.md", 1, "document") for d in range(4)]
    )
    assert len(nodes) == prompt_recall.SEARCH_N
    hits = [(n["id"], 0.9 - i * 0.001) for i, n in enumerate(nodes)]
    result = recall(_Mind(None, hits=hits, nodes=nodes), "q")
    assert len(result.matches) == prompt_recall.MATCH_FILES
    assert len(result.matches[0].symbols) == prompt_recall.SYMBOLS_PER_FILE
    assert len(result.docs) == prompt_recall.DOC_FILES


def test_a_node_the_graph_file_lacks_is_fetched_from_the_index(tmp_path):
    store = SynapseStore(tmp_path / "synapses.db")
    store.reinforce([PARSER, "content_runbook__h1"], namespace=SHARED_NAMESPACE)
    extra = {"content_runbook__h1": {"source_file": "ops/runbook.md", "label": "Rollback"}}
    result = recall(_Mind(store, hits=[(PARSER, 0.5)], extra=extra), "q")
    assert [(f.path, f.symbols) for f in result.linked] == [("ops/runbook.md", ["Rollback"])]


def test_no_match_names_nothing():
    result = recall(_Mind(None, hits=[]), "q")
    assert result.count == 0
    assert format_block(result) == ""


def test_a_long_label_is_shortened():
    label = "x" * 200
    nodes = [_node("pkg_m_py__x_fn", "pkg/m.py", label, 3)]
    result = recall(_Mind(None, hits=[("pkg_m_py__x_fn", 0.5)], nodes=nodes), "q")
    (symbol,) = result.matches[0].symbols
    assert symbol.endswith("… L3")
    assert len(symbol) < prompt_recall.LABEL_MAX + 5


@pytest.mark.parametrize(
    "path, expected",
    [
        ("tests/test_core.py", True),
        ("src/pkg/tests/helpers.py", True),
        ("pkg/core_test.go", True),
        ("web/src/app.test.ts", True),
        ("web/src/__tests__/app.tsx", True),
        ("spec/models/user_spec.rb", True),
        ("src/test/java/AppTest.java", True),
        ("src/click/testing.py", False),
        ("src/click/core.py", False),
        ("docs/testing.md", False),
        ("src/contest.py", False),
    ],
)
def test_is_test_path(path, expected):
    assert is_test_path(path) is expected
