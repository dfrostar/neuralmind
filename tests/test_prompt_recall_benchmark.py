"""The prompt-recall benchmark reads every file a recall block names."""

from __future__ import annotations

import json
from pathlib import Path

from tests.benchmark.prompt_recall import _code_files, _is_doc, _named_files


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


def test_the_fallback_suffixes_cover_the_ingested_document_formats():
    for path in ("book/ch1.markdown", "notes.mkd", "a.text", "todo.org", "spec.pdf", "README.MD"):
        assert _is_doc(path), path
    assert not _is_doc("src/click/core.py")


def test_the_index_decides_which_named_files_are_code():
    nodes = [
        {"source_file": "config/settings.yaml", "file_type": "document"},
        {"source_file": "src/app.py", "file_type": "code"},
        {"source_file": "src/app.py", "file_type": "rationale"},
        {"source_file": "README.md", "file_type": "document"},
    ]
    assert _code_files(nodes) == {
        "config/settings.yaml": False,
        "src/app.py": True,
        "README.md": False,
    }


def test_the_release_notes_table_is_the_committed_results():
    # Each "Measured" row in the v4.11.0 notes must be what the committed runs say.
    root = Path(__file__).resolve().parents[1]
    data = json.loads((root / "tests/benchmark/prompt_recall_results.json").read_text("utf-8"))
    notes = (root / "docs/releases/RELEASE_NOTES_v4.11.0.md").read_text("utf-8")

    def cells(report):
        named, first = report["named"], report["first"]
        tokens = f"{round(report['mean_tokens_injected'])} ({report['max_tokens']})"
        if report["injected"] < report["n"]:
            tokens += f", {report['injected']} prompts got a block"
        return [str(named), str(first), tokens]

    sets = data["sets"]
    for label in sets["click"]["runs"]:
        row = cells(sets["click"]["runs"][label]) + cells(sets["neuralmind"]["runs"][label])
        name = label
        if label == "v4.11.0":
            name, row = f"**{name}**", [f"**{c}**" for c in row]
        assert "| " + " | ".join([name, *row]) + " |" in notes, label
