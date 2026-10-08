"""The prompt-recall benchmark reads every file a recall block names."""

from __future__ import annotations

from tests.benchmark.prompt_recall import _named_files


def test_the_docs_line_counts_as_named():
    block = "\n".join(
        [
            "## NeuralMind associative recall",
            "",
            "Code matching this prompt:",
            "- src/click/core.py: make_parser() L1256",
            "Connected to it in the synapse graph:",
            "- src/click/parser.py",
            "Docs: docs/parameters.md, docs/arguments.md",
        ]
    )
    assert _named_files(block, {}) == [
        "src/click/core.py",
        "src/click/parser.py",
        "docs/parameters.md",
        "docs/arguments.md",
    ]


def test_the_old_node_id_format_still_maps_to_files():
    block = "- pkg_mod_py__load_fn (activation 0.05)"
    assert _named_files(block, {"pkg_mod_py__load_fn": "pkg/mod.py"}) == ["pkg/mod.py"]
