"""Regression tests: edges are attributed to the right definitions.

- A call is attributed to the definition that encloses it — not to the first
  function anywhere in the project that happens to share its name (``B.run``'s
  call used to land on ``A.run``; a nested ``wrapper`` inside ``outer()`` gave
  its calls to ``other.py``'s ``wrapper``).
- A Python relative import resolves against the importing module's package
  (``from .utils import x`` in ``pkg/a.py`` used to link the top-level
  ``utils.py``), and a src-layout absolute import (``from lib.core import f``
  under ``src/``) resolves at all.
- A ``.h`` header is parsed as C++ in a C++ project (or when it uses C++-only
  syntax): its classes/namespaces used to be lost and ``namespace ui {``
  became a bogus function ``ui()``.
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


# --------------------------------------------------------------------------- #
# Python imports → the right module
# --------------------------------------------------------------------------- #
_PKG = {
    "pkg/__init__.py": "from .utils import helper\n",
    "pkg/utils.py": "def helper(): pass\n",
    "pkg/sub/__init__.py": "",
    "utils.py": "def other(): pass\n",
}


def test_relative_import_resolves_against_the_importers_package(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            **_PKG,
            "pkg/a.py": "from .utils import helper\n",
            "pkg/sub/b.py": "from ..utils import helper\n",
        },
    )
    imports = _edges(graphgen.build_graph(tmp_path), "imports_from")
    assert ("pkg_a_py", "pkg_utils_py") in imports
    assert ("pkg_sub_b_py", "pkg_utils_py") in imports
    # A package's own __init__ resolves `.` to itself, not to its parent.
    assert ("pkg_init_py", "pkg_utils_py") in imports
    assert not any(target == "utils_py" for _, target in imports)


def test_from_dot_import_submodule_links_the_submodule(tmp_path: Path) -> None:
    _write(tmp_path, {**_PKG, "pkg/a.py": "from . import utils\n"})
    imports = _edges(graphgen.build_graph(tmp_path), "imports_from")
    assert ("pkg_a_py", "pkg_utils_py") in imports
    assert ("pkg_a_py", "utils_py") not in imports


def test_relative_import_above_the_project_root_links_nothing(tmp_path: Path) -> None:
    """``...utils`` from ``pkg/a.py`` names a module outside the indexed tree —
    it must not fall back to the project's own top-level ``utils.py``."""
    _write(tmp_path, {**_PKG, "pkg/a.py": "from ...utils import helper\n"})
    imports = _edges(graphgen.build_graph(tmp_path), "imports_from")
    assert not any(src == "pkg_a_py" for src, _ in imports)


def test_src_layout_absolute_import_resolves(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "src/lib/__init__.py": "",
            "src/lib/core.py": "def f(): pass\n",
            "src/lib/api.py": "from lib.core import f\n",
            "src/lib/cli.py": "import lib.core\n",
            "src/lib/rel.py": "from .core import f\n",
        },
    )
    imports = _edges(graphgen.build_graph(tmp_path), "imports_from")
    assert ("src_lib_api_py", "src_lib_core_py") in imports
    assert ("src_lib_cli_py", "src_lib_core_py") in imports
    assert ("src_lib_rel_py", "src_lib_core_py") in imports


def test_exact_module_wins_over_the_src_layout_fallback(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "lib/core.py": "def f(): pass\n",
            "src/lib/core.py": "def f(): pass\n",
            "app.py": "from lib.core import f\n",
        },
    )
    imports = _edges(graphgen.build_graph(tmp_path), "imports_from")
    assert ("app_py", "lib_core_py") in imports
    assert ("app_py", "src_lib_core_py") not in imports


# --------------------------------------------------------------------------- #
# .h headers → C or C++
# --------------------------------------------------------------------------- #
_needs_c_cpp = pytest.mark.skipif(
    not (graphgen.language_available("c") and graphgen.language_available("cpp")),
    reason="tree-sitter-c / tree-sitter-cpp not installed",
)
_WIDGET_H = (
    "#pragma once\n"
    "namespace ui {\n"
    "class Widget : public Base {\n"
    "public:\n"
    "  void draw();\n"
    "  int size() const;\n"
    "};\n"
    "}\n"
)


@_needs_c_cpp
def test_header_in_a_cpp_project_is_parsed_as_cpp(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "src/widget.h": _WIDGET_H,
            "src/widget.cpp": (
                '#include "widget.h"\n'
                "namespace ui {\n"
                "void Widget::draw() { size(); }\n"
                "int Widget::size() const { return 1; }\n"
                "}\n"
            ),
        },
    )
    graph = graphgen.build_graph(tmp_path)
    ids = {n["id"] for n in graph["nodes"]}
    assert "src_widget_h__ui_fn" not in ids  # the C grammar's bogus `ui()`
    assert {
        "src_widget_h__widget_cls",
        "src_widget_h__widget_cls__draw_fn",
        "src_widget_h__widget_cls__size_fn",
    } <= ids
    assert ("src_widget_h__widget_cls", "ext__base_cls") in _edges(graph, "inherits")
    assert ("src_widget_cpp", "src_widget_h") in _edges(graph, "imports_from")


@_needs_c_cpp
def test_header_with_cpp_only_syntax_is_parsed_as_cpp(tmp_path: Path) -> None:
    """A header-only C++ library (no .cpp at all) still gets its classes."""
    _write(tmp_path, {"include/widget.h": _WIDGET_H})
    ids = {n["id"] for n in graphgen.build_graph(tmp_path)["nodes"]}
    assert "include_widget_h__widget_cls" in ids
    assert "include_widget_h__ui_fn" not in ids


@_needs_c_cpp
def test_header_in_a_c_project_stays_c(tmp_path: Path) -> None:
    _write(tmp_path, {"include/db.h": "int db_connect(void);\n", "src/db.c": "int x;\n"})
    assert graphgen._parse_language(tmp_path / "include" / "db.h", False) == "c"
    assert graphgen._parse_language(tmp_path / "include" / "db.h", True) == "cpp"


@_needs_c_cpp
def test_c_file_still_links_a_header_parsed_as_cpp(tmp_path: Path) -> None:
    """In a mixed C/C++ project the header joins the C++ group; the C file that
    includes it (and calls what it declares) must still resolve against it."""
    _write(
        tmp_path,
        {
            "include/api.h": "int compute(int x);\nint helper(int x);\n",
            "src/api.c": (
                '#include "api.h"\n'
                "int compute(int x) { return helper(x); }\n"
                "int helper(int x) { return x; }\n"
            ),
            "src/main.cpp": '#include "api.h"\nint main() { return compute(1); }\n',
        },
    )
    graph = graphgen.build_graph(tmp_path)
    imports = _edges(graph, "imports_from")
    assert ("src_api_c", "include_api_h") in imports
    assert ("src_main_cpp", "include_api_h") in imports


# An inline member function: C++ the header's own sniffing doesn't flag, which
# only the C++ grammar parses (the C grammar turns the body into an ERROR, so
# the call inside it is lost).
_INLINE_H = "int helper(void);\nstruct Widget {\n  int size() { return helper(); }\n};\n"
_INLINE_CALL = ("lib_widget_h__widget_cls__size_fn", "lib_widget_h__helper_fn")


@_needs_c_cpp
def test_headers_reparse_when_the_first_cpp_file_arrives(tmp_path: Path) -> None:
    """Whether a .h is C++ depends on the project; an incremental build must
    notice when that flips even though the header itself didn't change."""
    import json

    root = _write(tmp_path / "p", {"lib/widget.h": _INLINE_H, "lib/a.c": "int a;\n"})
    graph = json.loads(graphgen.write_graph(root).read_text(encoding="utf-8"))
    assert _INLINE_CALL not in _edges(graph, "calls")  # C project: parsed as C

    _write(root, {"lib/b.cpp": "int b;\n"})
    graph = json.loads(graphgen.write_graph(root).read_text(encoding="utf-8"))
    assert _INLINE_CALL in _edges(graph, "calls")

    (root / "lib" / "b.cpp").unlink()
    graph = json.loads(graphgen.write_graph(root).read_text(encoding="utf-8"))
    assert _INLINE_CALL not in _edges(graph, "calls")


@_needs_c_cpp
def test_update_files_reparses_headers_when_the_first_cpp_file_arrives(tmp_path: Path) -> None:
    _write(tmp_path, {"lib/widget.h": _INLINE_H, "lib/a.c": "int a;\n"})
    graph = graphgen.build_graph(tmp_path)
    assert _INLINE_CALL not in _edges(graph, "calls")
    _write(tmp_path, {"lib/b.cpp": "int b;\n"})
    graph, _ = graphgen.update_files(tmp_path, graph, ["lib/b.cpp"])
    assert _INLINE_CALL in _edges(graph, "calls")


@_needs_c_cpp
def test_update_files_parses_a_header_like_a_full_build(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {"src/widget.h": _WIDGET_H, "src/widget.cpp": '#include "widget.h"\n'},
    )
    graph = graphgen.build_graph(tmp_path)
    graph, _ = graphgen.update_files(tmp_path, graph, ["src/widget.h"])
    ids = {n["id"] for n in graph["nodes"]}
    assert "src_widget_h__widget_cls" in ids
    assert "src_widget_h__ui_fn" not in ids
