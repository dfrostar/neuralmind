"""Regression tests: edges are attributed to the right definitions.

- A call is attributed to the definition that encloses it — not to the first
  function anywhere in the project that happens to share its name (``B.run``'s
  call used to land on ``A.run``; a nested ``wrapper`` inside ``outer()`` gave
  its calls to ``other.py``'s ``wrapper``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from neuralmind import graphgen

pytestmark = pytest.mark.skipif(not graphgen.is_available(), reason="tree-sitter not installed")


def _write(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


def _edges(graph: dict, relation: str) -> set[tuple[str, str]]:
    return {(e["source"], e["target"]) for e in graph["links"] if e["relation"] == relation}


# --------------------------------------------------------------------------- #
# Calls → the enclosing definition
# --------------------------------------------------------------------------- #
def test_python_method_calls_attach_to_their_own_class(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "m.py": (
                "class A:\n"
                "    def run(self):\n"
                "        helper_a()\n"
                "class B:\n"
                "    def run(self):\n"
                "        helper_b()\n"
                "def helper_a(): pass\n"
                "def helper_b(): pass\n"
            )
        },
    )
    calls = _edges(graphgen.build_graph(tmp_path), "calls")
    assert ("m_py__a_cls__run_fn", "m_py__helper_a_fn") in calls
    assert ("m_py__b_cls__run_fn", "m_py__helper_b_fn") in calls
    assert ("m_py__a_cls__run_fn", "m_py__helper_b_fn") not in calls


def test_python_nested_function_calls_stay_in_their_file(tmp_path: Path) -> None:
    """A nested def has no node of its own; its calls belong to the enclosing
    function — never to a same-named function in another file."""
    _write(
        tmp_path,
        {
            "m.py": (
                "def helper(): pass\n"
                "def outer():\n"
                "    def wrapper():\n"
                "        helper()\n"
                "    return wrapper\n"
            ),
            "other.py": "def wrapper():\n    pass\n",
        },
    )
    calls = _edges(graphgen.build_graph(tmp_path), "calls")
    assert ("m_py__outer_fn", "m_py__helper_fn") in calls
    assert not any(src == "other_py__wrapper_fn" for src, _ in calls)


def test_python_nested_def_shadowing_a_top_level_name(tmp_path: Path) -> None:
    """A nested def named like a top-level function in the same file must not
    hand its calls to that top-level function."""
    _write(
        tmp_path,
        {
            "m.py": (
                "def target(): pass\n"
                "def helper():\n"
                "    pass\n"
                "def outer():\n"
                "    def helper():\n"
                "        target()\n"
                "    return helper\n"
            ),
        },
    )
    calls = _edges(graphgen.build_graph(tmp_path), "calls")
    assert ("m_py__outer_fn", "m_py__target_fn") in calls
    assert ("m_py__helper_fn", "m_py__target_fn") not in calls


# Two classes, each with a ``run`` method calling a different helper. Before the
# fix every language looked the enclosing ``run`` up by bare name, so both bodies
# were attributed to whichever ``run`` came first.
_TWO_RUNS: dict[str, tuple[str, str, dict[tuple[str, str], bool]]] = {
    "typescript": (
        "m.ts",
        (
            "function helperA(): void {}\n"
            "function helperB(): void {}\n"
            "class A {\n  run(): void { helperA(); }\n}\n"
            "class B {\n  run(): void { helperB(); }\n}\n"
        ),
        {
            ("m_ts__a_cls__run_fn", "m_ts__helpera_fn"): True,
            ("m_ts__b_cls__run_fn", "m_ts__helperb_fn"): True,
            ("m_ts__a_cls__run_fn", "m_ts__helperb_fn"): False,
        },
    ),
    "rust": (
        "m.rs",
        (
            "fn helper_a() {}\nfn helper_b() {}\nstruct A;\nstruct B;\n"
            "impl A { fn run(&self) { helper_a(); } }\n"
            "impl B { fn run(&self) { helper_b(); } }\n"
        ),
        {
            ("m_rs__a_cls__run_fn", "m_rs__helper_a_fn"): True,
            ("m_rs__b_cls__run_fn", "m_rs__helper_b_fn"): True,
            ("m_rs__a_cls__run_fn", "m_rs__helper_b_fn"): False,
        },
    ),
    "java": (
        "M.java",
        (
            "class M { static void helperA() {} static void helperB() {} }\n"
            "class A { void run() { M.helperA(); } }\n"
            "class B { void run() { M.helperB(); } }\n"
        ),
        {
            ("m_java__a_cls__run_fn", "m_java__m_cls__helpera_fn"): True,
            ("m_java__b_cls__run_fn", "m_java__m_cls__helperb_fn"): True,
            ("m_java__a_cls__run_fn", "m_java__m_cls__helperb_fn"): False,
        },
    ),
    "cpp": (
        "m.cpp",
        (
            "void helperA() {}\nvoid helperB() {}\n"
            "class A { public: void run() { helperA(); } };\n"
            "class B { public: void run() { helperB(); } };\n"
        ),
        {
            ("m_cpp__a_cls__run_fn", "m_cpp__helpera_fn"): True,
            ("m_cpp__b_cls__run_fn", "m_cpp__helperb_fn"): True,
            ("m_cpp__a_cls__run_fn", "m_cpp__helperb_fn"): False,
        },
    ),
    "csharp": (
        "M.cs",
        (
            "class H { public static void HelperA() {} public static void HelperB() {} }\n"
            "class A { void Run() { H.HelperA(); } }\n"
            "class B { void Run() { H.HelperB(); } }\n"
        ),
        {
            ("m_cs__a_cls__run_fn", "m_cs__h_cls__helpera_fn"): True,
            ("m_cs__b_cls__run_fn", "m_cs__h_cls__helperb_fn"): True,
            ("m_cs__a_cls__run_fn", "m_cs__h_cls__helperb_fn"): False,
        },
    ),
    "ruby": (
        "m.rb",
        (
            "def helper_a()\nend\ndef helper_b()\nend\n"
            "class A\n  def run\n    helper_a()\n  end\nend\n"
            "class B\n  def run\n    helper_b()\n  end\nend\n"
        ),
        {
            ("m_rb__a_cls__run_fn", "m_rb__helper_a_fn"): True,
            ("m_rb__b_cls__run_fn", "m_rb__helper_b_fn"): True,
            ("m_rb__a_cls__run_fn", "m_rb__helper_b_fn"): False,
        },
    ),
    "php": (
        "m.php",
        (
            "<?php\nfunction helperA() {}\nfunction helperB() {}\n"
            "class A { function run() { helperA(); } }\n"
            "class B { function run() { helperB(); } }\n"
        ),
        {
            ("m_php__a_cls__run_fn", "m_php__helpera_fn"): True,
            ("m_php__b_cls__run_fn", "m_php__helperb_fn"): True,
            ("m_php__a_cls__run_fn", "m_php__helperb_fn"): False,
        },
    ),
}


@pytest.mark.parametrize("language", sorted(_TWO_RUNS))
def test_same_named_methods_keep_their_own_calls(tmp_path: Path, language: str) -> None:
    if not graphgen.language_available(language):
        pytest.skip(f"tree-sitter grammar for {language} not installed")
    rel, text, expected = _TWO_RUNS[language]
    _write(tmp_path, {rel: text})
    calls = _edges(graphgen.build_graph(tmp_path), "calls")
    for edge, present in expected.items():
        assert (edge in calls) is present, (edge, sorted(calls))


def test_update_files_attributes_calls_like_a_full_build(tmp_path: Path) -> None:
    """The incremental per-file path resolves calls the same way."""
    _write(
        tmp_path,
        {
            "m.py": (
                "class A:\n    def run(self):\n        helper_a()\n"
                "class B:\n    def run(self):\n        helper_b()\n"
                "def helper_a(): pass\ndef helper_b(): pass\n"
            )
        },
    )
    graph = graphgen.build_graph(tmp_path)
    graph, _ = graphgen.update_files(tmp_path, graph, ["m.py"])
    calls = _edges(graph, "calls")
    assert ("m_py__b_cls__run_fn", "m_py__helper_b_fn") in calls
    assert ("m_py__a_cls__run_fn", "m_py__helper_b_fn") not in calls
